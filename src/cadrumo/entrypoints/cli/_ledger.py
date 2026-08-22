"""User-facing ledger and transaction management CLI commands.

Provides the ``aeat app ledger`` command group for importing, reviewing, and
exporting financial transaction data. Transaction records are accessed through
:class:`TransactionCatalogueRepository` and invoice
records through :class:`InvoiceCatalogueRepository`.
Lifecycle events are appended to the profile audit trail via
:class:`BucketEventHistoryRepository`. Mutation and read
verbs validate registered
:class:`OutputSchema` payloads and emit
:class:`SchemaEnvelope` documents through
:func:`_emit_envelope` so CLI JSON stays aligned
with the registered ledger payload contracts.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

import typer
from pydantic import ValidationError

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...application.ledger import (
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    create_manual_transaction,
    resolve_lineage_transaction_id,
    update_manual_transaction_fields,
)
from ...core import (
    Art104TresExclusion,
    IvaDeductionFactKind,
    ProrrataRegisterRegime,
    resolve_active_bucket_id,
)
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.logging import get_logger
from ...domain.iva import (
    EUMemberState,
    InputClassification,
    IvaCategory,
)
from ...domain.transactions import (
    BusinessClassification,
    TransactionDirection,
    TransactionIdPrefixError,
    TransactionValidationError,
    is_classified,
)
from ._bienes_inversion_cli import register_bienes_inversion_commands
from ._command_policy import command_execution_policy
from ._common import (
    _bad,
    _emit_envelope,
    _parse_iso_date,
    _profile_to_taxpayer,
    _state,
    _tx_repo,
)
from ._ledger_business_invoice_cli import (
    invoice_app,
    register_business_invoice_commands,
)
from ._ledger_classify_cli import ledger_classify_bulk_csv, require_single_ledger_classification_request
from ._ledger_counterparty_cli import register_counterparty_commands
from ._ledger_evidence_cli import register_evidence_commands
from ._ledger_execution_policies import (
    LEDGER_COMPUTE_WRITE,
    LEDGER_NETWORK_COMPUTE_WRITE,
    LEDGER_NETWORK_WRITE,
    LEDGER_WRITE,
    declare_metadata_group,
)
from ._ledger_import_cli import register_import_commands
from ._ledger_inventory_cli import inventory_app, register_inventory_commands
from ._ledger_lifecycle_cli import (
    ledger_archive,
    ledger_attach,
    ledger_doclink,
    ledger_merge,
    ledger_pull_folder,
    ledger_remove,
    ledger_reset,
    ledger_split,
    ledger_stash,
    register_lifecycle_commands,
)
from ._ledger_llm_cli import (
    dispatch_autosplit,
    ledger_classify_llm,
    ledger_operator_iva_derive,
    ledger_saturate_llm,
)
from ._ledger_m210_classify_cli import (
    M210ApplicableRateOpt,
    M210AssetOrRightIdOpt,
    M210GrossIncomeAmountOpt,
    M210LedgerClassifyOptions,
    M210PayerIdOpt,
    M210PayerModeOpt,
    M210TipoRentaCodeOpt,
)
from ._ledger_ratios_cli import ratios_app, register_ratios_commands
from ._ledger_read_cli import register_read_commands
from ._ledger_rules_cli import register_rule_commands, rule_app
from ._ledger_support import (
    _emit_update_result,
    _invoice_link_error_bad_parameter,
    _ledger_cli_no_recovery,
    _ledger_transaction_validation_no_recovery,
    _ledger_validation_bad,
    _parse_amount_magnitude,
    _parse_decimal,
    _parse_required_decimal,
    _resolve_business_pct_with_censo,
    _resolve_id,
    _resolve_source_jurisdiction,
    _TransactionRepo,
    _validate_business_pct_range,
    _validate_category_id,
)
from ._prorrata_register_cli import register_prorrata_register_commands

_log = get_logger(__name__)

__all__ = [
    "app",
    "inventory_app",
    "invoice_app",
    "ledger_archive",
    "ledger_attach",
    "ledger_doclink",
    "ledger_merge",
    "ledger_pull_folder",
    "ledger_remove",
    "ledger_reset",
    "ledger_split",
    "ledger_stash",
    "ratios_app",
    "rule_app",
]

app = typer.Typer(
    name="ledger",
    help=tr("cli.ledger.app_help"),
    no_args_is_help=True,
)
declare_metadata_group(app)


def _resolve_read_id(transaction_repository: _TransactionRepo, prefix: str) -> str:
    """Resolve a CLI-supplied id for the *read* verbs, following edit lineage.

    This is the D3 stable-lineage-handle resolution path for
    ``ledger history`` / ``view`` / ``track``. It first resolves ``prefix``
    against live catalogue ids exactly as :func:`_resolve_id` does; when no
    live row matches, it walks the edit-lineage chain so a superseded
    (pre-``update``) id written down by the operator still resolves to the
    current row — see
    :func:`resolve_lineage_transaction_id`. The
    content-addressed id stays authoritative; this is a read-side lookup
    convenience, never a change to how ids are minted.
    """
    if not isinstance(transaction_repository, TransactionCatalogueRepository):
        # Read verbs always receive a real catalogue repository through
        # _tx_repo; the structural Protocol is only used by mutation
        # helpers. Fall back to the live-id resolver if a non-catalogue
        # repository is ever supplied so the read path never crashes.
        return _resolve_id(transaction_repository, prefix)
    catalogue = transaction_repository.load()
    try:
        return resolve_lineage_transaction_id(prefix, catalogue)
    except TransactionIdPrefixError as exc:
        from ...application.cli_exception_preconditions import CliExceptionPrecondition

        raise _ledger_cli_no_recovery(
            exc,
            condition=CliExceptionPrecondition.LEDGER_TRANSACTION_ID_RESOLVES,
            facts={"transaction_id_resolves": False},
        ) from None


def _patch_from_options(**values: object) -> ManualLedgerTransactionPatch:
    return ManualLedgerTransactionPatch.model_validate(
        {key: value for key, value in values.items() if value is not None},
    )


def _prorrata_especial_inert_notice(
    *,
    bucket_id: str,
    ejercicio: int,
    input_classification: InputClassification | None,
    sector_id: str | None,
) -> Notice | None:
    """Warn when --input-classification is set but no especial election applies.

    LIVA art. 106 per-input routing fires only when the ``(ejercicio, sector)``
    prorrata register entry regime is especial. Absent that election the
    classification is inert: the input deducts under the general / whole-entity
    percentage. Surface a non-blocking advisory so the operator is not falsely
    signalled that art. 106 routing applies, rather than silently ignoring the
    flag (no-silent-under-declaration).
    """
    if input_classification is None:
        return None
    from ...adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ...application.prorrata_register import ProrrataRegisterService

    service = ProrrataRegisterService(repository=ProrrataRegisterRepository(bucket_id=bucket_id))
    entry = service.get(ejercicio, sector_id=sector_id)
    if entry is not None and entry.regime is ProrrataRegisterRegime.ESPECIAL:
        return None
    message = tr(
        "cli.ledger.add.input_classification_inert",
        ejercicio=ejercicio,
    )
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="ledger.add.input_classification_inert",
        message=message,
        context={
            "ejercicio": str(ejercicio),
            "input_classification": input_classification.value,
            "sector_id": sector_id or "",
        },
    )


def _prorrata_sector_unmatched_notice(
    *,
    bucket_id: str,
    sector_id: str | None,
) -> Notice | None:
    """Warn when --sector names a sector absent from the declared partition.

    Sectores diferenciados (LIVA arts. 9.1.c / 101) are operator-declared: the
    per-sector apportionment routing keys on ``sector_id`` and applies the
    sector's own percentage only when the tag matches a declared
    :class:`SectorDefinition`. An unmatched tag — a typo, or a sector not yet
    declared — is not rejected (declare-order is intentionally free, so a
    not-yet-declared sector is legitimate), but it falls through to the
    common-use / whole-entity apportionment at aggregation. Surface a
    non-blocking advisory naming the sector and the ``declare-sector`` route,
    so the operator is not silently deducting at the common percentage under a
    mistyped tag (no-silent-under-declaration), rather than accepting the tag
    without any signal.
    """
    if sector_id is None:
        return None
    from ...adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
    from ...application.prorrata_register import ProrrataRegisterService

    service = ProrrataRegisterService(repository=ProrrataRegisterRepository(bucket_id=bucket_id))
    if service.list_all().sector_definition_for(sector_id) is not None:
        return None
    message = tr(
        "cli.ledger.add.sector_unmatched",
        sector_id=sector_id,
    )
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="ledger.add.sector_unmatched",
        message=message,
        context={"sector_id": sector_id},
    )


@app.command("add", help=tr("cli.ledger.add.help"))
@command_execution_policy(LEDGER_NETWORK_WRITE)
def ledger_add(
    ctx: typer.Context,
    booked_date: str = typer.Option(..., "--date", help=tr("cli.ledger.add.date_help")),
    amount: str = typer.Option(..., "--amount", help=tr("cli.ledger.add.amount_help")),
    direction: TransactionDirection = typer.Option(..., "--direction", help=tr("cli.ledger.add.direction_help")),
    description: str = typer.Option(..., "--description", help=tr("cli.ledger.add.description_help")),
    value_date: str | None = typer.Option(None, "--value-date", help=tr("cli.ledger.add.value_date_help")),
    currency: str = typer.Option(DEFAULT_CURRENCY, "--currency", help=tr("cli.ledger.add.currency_help")),
    counterparty: str | None = typer.Option(None, "--counterparty", help=tr("cli.ledger.add.counterparty_help")),
    business_classification: BusinessClassification = typer.Option(
        BusinessClassification.NOT_YET_PROCESSED,
        "--classification",
        help=tr("cli.ledger.add.classification_help"),
    ),
    business_pct: str | None = typer.Option(None, "--business-pct", help=tr("cli.ledger.add.business_pct_help")),
    category_id: str | None = typer.Option(None, "--category-id", help=tr("cli.ledger.add.category_help")),
    taxable_base: str | None = typer.Option(None, "--taxable-base", help=tr("cli.ledger.add.taxable_base_help")),
    iva_rate: str | None = typer.Option(None, "--iva-rate", help=tr("cli.ledger.add.iva_rate_help")),
    iva_amount: str | None = typer.Option(None, "--iva-amount", help=tr("cli.ledger.add.iva_amount_help")),
    iva_category: _IvaCategoryOpt = None,
    deduction_fact_kind: _DeductionFactKindOpt = None,
    counterparty_country: _CounterpartyCountryOpt = None,
    counterparty_identification_state: _CounterpartyIdentificationStateOpt = None,
    recargo_amount: str | None = typer.Option(None, "--recargo-amount", help=tr("cli.ledger.add.recargo_amount_help")),
    irpf_category: str | None = typer.Option(None, "--irpf-category", help=tr("cli.ledger.add.irpf_category_help")),
    usage_ratio_id: str | None = typer.Option(None, "--usage-ratio-id", help=tr("cli.ledger.add.usage_ratio_help")),
    prorrata_reference: str | None = typer.Option(
        None,
        "--prorrata-reference",
        help=tr("cli.ledger.add.prorrata_reference_help"),
    ),
    art_104_tres_exclusion: Art104TresExclusion | None = typer.Option(
        None,
        "--art-104-tres-exclusion",
        help=tr("cli.ledger.add.art_104_tres_exclusion_help"),
    ),
    input_classification: InputClassification | None = typer.Option(
        None,
        "--input-classification",
        help=tr("cli.ledger.add.input_classification_help"),
    ),
    prorrata_sector: str | None = typer.Option(
        None,
        "--sector",
        help=tr("cli.ledger.add.prorrata_sector_help"),
    ),
    purchase_invoice_evidence_id: str | None = typer.Option(
        None,
        "--purchase-invoice-evidence-id",
        help=tr("cli.ledger.add.purchase_invoice_evidence_help"),
    ),
    attachment_ids: list[str] = typer.Option(
        [],
        "--attachment-id",
        help=tr("cli.ledger.add.attachment_help"),
    ),
    notes: str = typer.Option("", "--notes", help=tr("cli.ledger.add.notes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.add.actor_help")),
    idempotency_key: str | None = typer.Option(
        None,
        "--idempotency-key",
        help=tr("cli.ledger.add.idempotency_key_help"),
    ),
    source_jurisdiction: str | None = typer.Option(
        None,
        "--source-jurisdiction",
        help=tr("cli.ledger.add.source_jurisdiction_help"),
    ),
) -> None:
    """Create one manual ledger transaction through the bucket-scoped backend."""
    operator_assignable_on_add = (
        is_classified(business_classification) or business_classification is BusinessClassification.NOT_YET_PROCESSED
    )
    if not operator_assignable_on_add:
        # PROCESSED_UNCLASSIFIED / SKIPPED_BY_RULE / FAILED_VALIDATION are
        # produced by the classification pipeline, never assigned by hand. A new
        # row is BUSINESS, PERSONAL, MIXED, or left at the NOT_YET_PROCESSED
        # default; refuse the internal states instructively.
        raise _bad(
            tr("cli.ledger.add.system_state_not_assignable", value=business_classification.value),
        )
    current_state = _state()
    transaction_repository = _tx_repo(current_state)
    validated_category_id = _validate_category_id(category_id)
    resolved_business_pct = _resolve_business_pct_with_censo(
        bucket_id=transaction_repository.bucket_id,
        active_profile=resolve_active_bucket_id(),
        category_id=validated_category_id,
        operator_supplied=_validate_business_pct_range(_parse_decimal(business_pct, label="business-pct")),
    )
    active_taxpayer = _profile_to_taxpayer(current_state)
    resolved_source_jurisdiction = _resolve_source_jurisdiction(
        source_jurisdiction,
        fiscal_residency=active_taxpayer.fiscal_residency,
        irpf_special_regime=active_taxpayer.irpf_special_regime,
    )
    try:
        command = ManualLedgerTransactionCommand(
            bucket_id=transaction_repository.bucket_id,
            booked_date=_parse_iso_date(booked_date, label="date"),
            value_date=_parse_iso_date(value_date, label="value-date") if value_date is not None else None,
            amount=_parse_amount_magnitude(amount),
            currency=currency,
            direction=direction,
            counterparty=counterparty,
            description=description,
            business_classification=business_classification,
            business_pct=resolved_business_pct,
            category_id=validated_category_id,
            taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
            iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
            iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
            iva_category=iva_category,
            deduction_fact_kind=deduction_fact_kind,
            counterparty_country=counterparty_country,
            counterparty_identification_state=counterparty_identification_state,
            recargo_amount=_parse_decimal(recargo_amount, label="recargo-amount"),
            irpf_category=irpf_category,
            usage_ratio_id=usage_ratio_id,
            prorrata_reference=prorrata_reference,
            art_104_tres_exclusion=art_104_tres_exclusion,
            input_classification=input_classification,
            prorrata_sector_id=prorrata_sector,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            attachment_ids=tuple(attachment_ids),
            notes=notes,
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger add",
            idempotency_key=idempotency_key,
            source_jurisdiction=resolved_source_jurisdiction,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    except TransactionValidationError as exc:
        raise _ledger_transaction_validation_no_recovery(exc) from None
    # The gross-invariant (`taxable_base + iva_amount == amount`) and other
    # `Transaction.model_validate` rules fire inside `create_manual_transaction`,
    # raising a pydantic `ValidationError` whose default rendering dumps the full
    # `RawTransaction(...)` repr (~30 lines) to the operator. Catch it at the CLI
    # boundary and surface only the human-readable validator message, matching
    # the `ManualLedgerTransactionCommand` treatment above — CLI errors are
    # typed refusals, never raw dumps.
    # Same ECB-backed normalizer the file-import path wires in: a manually
    # entered foreign-currency row must convert at entry, or it persists with no
    # value_in_eur and every aggregation gate withholds it from the modelo.
    from ...adapters.outbound.fx import default_ecb_rate_provider
    from ...domain.currency import CurrencyNormalizationService

    try:
        result = create_manual_transaction(
            command,
            transaction_repository=transaction_repository,
            currency_normalizer=CurrencyNormalizationService(rate_provider=default_ecb_rate_provider()),
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerAddResult

    # An empty bucket_event_ids tuple is the guarded-idempotent no-op signal
    # from create_manual_transaction: the keyed add matched an already-stored
    # row and wrote nothing. Surface it as an info Notice on the typed channel
    # (never a bespoke result field) and fold the same text into the lines so
    # JSON and text output cannot drift.
    notices: list[Notice] = []
    noop_lines: list[str] = []
    if not result.bucket_event_ids:
        noop_message = tr(
            "cli.ledger.add.idempotent_noop",
            transaction_id=result.ref.transaction_id,
        )
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.add.idempotent_noop",
                message=noop_message,
                context={
                    "transaction_id": result.ref.transaction_id,
                    "idempotency_key": command.idempotency_key or "",
                },
            )
        )
        noop_lines.append(noop_message)
    especial_notice = _prorrata_especial_inert_notice(
        bucket_id=result.ref.bucket_id,
        ejercicio=command.booked_date.year,
        input_classification=command.input_classification,
        sector_id=command.prorrata_sector_id,
    )
    if especial_notice is not None:
        notices.append(especial_notice)
        noop_lines.append(especial_notice.message)
    sector_notice = _prorrata_sector_unmatched_notice(
        bucket_id=result.ref.bucket_id,
        sector_id=command.prorrata_sector_id,
    )
    if sector_notice is not None:
        notices.append(sector_notice)
        noop_lines.append(sector_notice.message)
    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        tuple(result.bucket_event_ids),
        command="ledger.add",
        result_cls=LedgerAddResult,
        notices=notices or None,
        extra_lines=noop_lines,
    )


@app.command("update", help=tr("cli.ledger.update.help"))
@command_execution_policy(LEDGER_WRITE)
def ledger_update(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.update.id_help")),
    booked_date: str | None = typer.Option(None, "--date", help=tr("cli.ledger.update.date_help")),
    value_date: str | None = typer.Option(None, "--value-date", help=tr("cli.ledger.update.value_date_help")),
    amount: str | None = typer.Option(None, "--amount", help=tr("cli.ledger.update.amount_help")),
    direction: TransactionDirection | None = typer.Option(
        None,
        "--direction",
        help=tr("cli.ledger.update.direction_help"),
    ),
    currency: str | None = typer.Option(None, "--currency", help=tr("cli.ledger.update.currency_help")),
    counterparty: str | None = typer.Option(None, "--counterparty", help=tr("cli.ledger.update.counterparty_help")),
    description: str | None = typer.Option(None, "--description", help=tr("cli.ledger.update.description_help")),
    taxable_base: str | None = typer.Option(None, "--taxable-base", help=tr("cli.ledger.update.taxable_base_help")),
    iva_rate: str | None = typer.Option(None, "--iva-rate", help=tr("cli.ledger.update.iva_rate_help")),
    iva_amount: str | None = typer.Option(None, "--iva-amount", help=tr("cli.ledger.update.iva_amount_help")),
    irpf_category: str | None = typer.Option(None, "--irpf-category", help=tr("cli.ledger.update.irpf_category_help")),
    notes: str | None = typer.Option(None, "--notes", help=tr("cli.ledger.update.notes_help")),
    group: str | None = typer.Option(None, "--group", help=tr("cli.ledger.update.group_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.update.actor_help")),
) -> None:
    """Correct editable transaction facts through the bucket-scoped backend."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    # A leaked `pydantic.ValidationError` (negative amount, illegal field
    # combination) would be swallowed by the generic CLI boundary into an
    # opaque "config repair" hint. Catch it here and surface the real
    # validator cause, mirroring the `ledger classify` treatment.
    try:
        result = update_manual_transaction_fields(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=resolved_id,
            patch=_patch_from_options(
                booked_date=_parse_iso_date(booked_date, label="date") if booked_date is not None else None,
                value_date=_parse_iso_date(value_date, label="value-date") if value_date is not None else None,
                amount=_parse_amount_magnitude(amount) if amount is not None else None,
                direction=direction,
                currency=currency,
                counterparty=counterparty,
                description=description,
                taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
                iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
                iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
                irpf_category=irpf_category,
                notes=notes,
                group_label=group,
            ),
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger update",
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerUpdateResult

    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.update",
        result_cls=LedgerUpdateResult,
    )


_IvaCategoryOpt = Annotated[
    IvaCategory | None,
    typer.Option("--iva-category", help=tr("cli.ledger.classify.iva_category_help")),
]
_DeductionFactKindOpt = Annotated[
    IvaDeductionFactKind | None,
    typer.Option("--deduction-kind", help=tr("cli.ledger.classify.deduction_fact_kind_help")),
]
_CounterpartyCountryOpt = Annotated[
    str | None,
    typer.Option("--counterparty-country", help=tr("cli.ledger.classify.counterparty_country_help")),
]
_CounterpartyIdentificationStateOpt = Annotated[
    EUMemberState | None,
    typer.Option(
        "--counterparty-identification-state",
        help=tr("cli.ledger.classify.counterparty_identification_state_help"),
    ),
]
_FileOpt = Annotated[
    str | None,
    typer.Option(
        "--file",
        help=tr("cli.ledger.classify.file_help"),
    ),
]


@app.command("classify", help=tr("cli.ledger.classify.help"))
@command_execution_policy(LEDGER_NETWORK_COMPUTE_WRITE)
def ledger_classify(
    ctx: typer.Context,
    transaction_id: str | None = typer.Argument(None, help=tr("cli.ledger.classify.id_help")),
    classification: BusinessClassification | None = typer.Option(
        None,
        "--classification",
        help=tr("cli.ledger.classify.classification_help"),
    ),
    file: _FileOpt = None,
    business_pct: str | None = typer.Option(
        None,
        "--business-pct",
        help=tr("cli.ledger.classify.business_pct_help"),
    ),
    category_id: str | None = typer.Option(None, "--category-id", help=tr("cli.ledger.classify.category_help")),
    taxable_base: str | None = typer.Option(None, "--taxable-base", help=tr("cli.ledger.classify.taxable_base_help")),
    iva_rate: str | None = typer.Option(None, "--iva-rate", help=tr("cli.ledger.classify.iva_rate_help")),
    iva_amount: str | None = typer.Option(None, "--iva-amount", help=tr("cli.ledger.classify.iva_amount_help")),
    irpf_category: str | None = typer.Option(
        None,
        "--irpf-category",
        help=tr("cli.ledger.classify.irpf_category_help"),
    ),
    m210_tipo_renta_code: M210TipoRentaCodeOpt = None,
    m210_gross_income_amount: M210GrossIncomeAmountOpt = None,
    m210_applicable_rate: M210ApplicableRateOpt = None,
    m210_payer_mode: M210PayerModeOpt = None,
    m210_payer_id: M210PayerIdOpt = None,
    m210_asset_or_right_id: M210AssetOrRightIdOpt = None,
    iva_category: _IvaCategoryOpt = None,
    deduction_fact_kind: _DeductionFactKindOpt = None,
    counterparty_country: _CounterpartyCountryOpt = None,
    counterparty_identification_state: _CounterpartyIdentificationStateOpt = None,
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.classify.actor_help")),
    reaffirm: bool = typer.Option(False, "--reaffirm", help=tr("cli.ledger.classify.reaffirm_help")),
    llm: bool = typer.Option(False, "--llm", help=tr("cli.ledger.classify.llm_help")),
    apply: bool = typer.Option(False, "--apply", help=tr("cli.ledger.classify.apply_help")),
    saturate: bool = typer.Option(False, "--saturate", help=tr("cli.ledger.classify.saturate_help")),
    read_evidence: bool = typer.Option(False, "--read-evidence", help=tr("cli.ledger.classify.read_evidence_help")),
    vision_model: str | None = typer.Option(
        None,
        "--vision-model",
        help=tr("cli.ledger.classify.vision_model_help"),
    ),
    auto_split: bool = typer.Option(
        False,
        "--auto-split",
        help=tr("cli.ledger.classify.auto_split_help"),
    ),
    reject: bool = typer.Option(False, "--reject", help=tr("cli.ledger.classify.reject_help")),
    reason: str | None = typer.Option(None, "--reason", help=tr("cli.ledger.classify.reason_help")),
) -> None:
    """Classify one ledger transaction (positional id), via LLM (--llm), or in bulk (--file)."""
    m210_options = M210LedgerClassifyOptions(
        tipo_renta_code=m210_tipo_renta_code,
        gross_income_amount=m210_gross_income_amount,
        applicable_rate=m210_applicable_rate,
        payer_mode=m210_payer_mode,
        payer_id=m210_payer_id,
        asset_or_right_id=m210_asset_or_right_id,
    )
    m210_options.refuse_non_direct_routes(
        llm_requested=llm is not None,
        read_evidence=read_evidence,
        saturate=saturate,
        file=file,
        auto_split=auto_split,
    )
    if auto_split:
        dispatch_autosplit(
            ctx,
            transaction_id=transaction_id,
            classification=classification,
            file=file,
            apply=apply,
            actor=actor,
            read_evidence=read_evidence,
            vision_model=vision_model,
            reject=reject,
            reason=reason or "",
        )
        return
    if llm or read_evidence:
        saturate_kwargs = {
            "ctx": ctx,
            "transaction_id": transaction_id,
            "classification": classification,
            "file": file,
            "business_pct": business_pct,
            "apply": apply,
            "actor": actor,
            "read_evidence": read_evidence,
            "vision_model": vision_model,
            "reject": reject,
            "reason": reason or "",
        }
        if saturate:
            ledger_saturate_llm(**saturate_kwargs)
            return
        ledger_classify_llm(**saturate_kwargs)
        return
    if saturate:
        ledger_operator_iva_derive(
            ctx,
            transaction_id=transaction_id,
            classification=classification,
            file=file,
            iva_category=iva_category,
            actor=actor,
        )
        return
    state = _state()
    transaction_repository = _tx_repo(state)

    if file is not None:
        ledger_classify_bulk_csv(
            ctx,
            transaction_repository=transaction_repository,
            transaction_id=transaction_id,
            classification=classification,
            file=file,
            actor=actor,
        )
        return

    transaction_id, classification = require_single_ledger_classification_request(
        transaction_id=transaction_id,
        classification=classification,
        reason=reason,
    )
    validated_category_id = _validate_category_id(category_id)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    m210_income_classification = m210_options.to_income_classification(
        transaction_repository=transaction_repository,
        transaction_id=resolved_id,
    )
    if classification is BusinessClassification.MIXED and business_pct is None:
        # MIXED demands a proportion; surface the `--business-pct` flag
        # directly rather than letting the patch validator's generic
        # message route through the opaque boundary.
        raise _bad(tr("cli.ledger.classify.mixed_requires_business_pct"))
    if classification is not BusinessClassification.MIXED and business_pct is not None:
        # `--business-pct` only carries meaning for a MIXED row; a
        # BUSINESS or PERSONAL classification is wholly business or
        # wholly private. Refuse rather than silently dropping it.
        raise _bad(tr("cli.ledger.classify.business_pct_requires_mixed"))
    # A leaked `pydantic.ValidationError` (negative `--taxable-base`,
    # an illegal field combination) is otherwise wrapped by the generic
    # CLI boundary into "command input failed validation. Run config
    # repair" — a misleading hint, since `config repair` cannot fix a
    # bad CLI argument. Catch it here and surface the real validator
    # cause, matching the `ledger add` / `ledger review` treatment.
    try:
        patch = _patch_from_options(
            business_classification=classification,
            business_pct=_validate_business_pct_range(_parse_decimal(business_pct, label="business-pct")),
            category_id=validated_category_id,
            taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
            iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
            iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
            irpf_category=irpf_category,
            m210_income_classification=m210_income_classification,
            iva_category=iva_category,
            deduction_fact_kind=deduction_fact_kind,
            counterparty_country=counterparty_country,
            counterparty_identification_state=counterparty_identification_state,
            notes=reason,
        )
        result = update_manual_transaction_fields(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=resolved_id,
            patch=patch,
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger classify",
            reaffirm=reaffirm,
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    except TransactionValidationError as exc:
        raise _ledger_transaction_validation_no_recovery(exc) from None
    from ._ledger_payloads import LedgerClassifySingleResult

    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        tuple(result.bucket_event_ids),
        command="ledger.classify",
        result_cls=LedgerClassifySingleResult,
        prepend_lines=(tr("cli.ledger.classify.reaffirmed"),) if reaffirm else (),
    )


@app.command("allocate", help=tr("cli.ledger.allocate.help"))
@command_execution_policy(LEDGER_COMPUTE_WRITE)
def ledger_allocate(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.allocate.id_help")),
    business_pct: str = typer.Option(..., "--business-pct", help=tr("cli.ledger.allocate.business_pct_help")),
    category_id: str | None = typer.Option(None, "--category-id", help=tr("cli.ledger.allocate.category_help")),
    usage_ratio_id: str | None = typer.Option(
        None,
        "--usage-ratio-id",
        help=tr("cli.ledger.allocate.usage_ratio_help"),
    ),
    prorrata_reference: str | None = typer.Option(
        None,
        "--prorrata-reference",
        help=tr("cli.ledger.allocate.prorrata_reference_help"),
    ),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.allocate.actor_help")),
) -> None:
    """Record business/private proportionality through the ledger backend."""
    state = _state()
    transaction_repository = _tx_repo(state)
    validated_category_id = _validate_category_id(category_id)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    parsed_business_pct = _validate_business_pct_range(_parse_required_decimal(business_pct, label="business-pct"))
    assert parsed_business_pct is not None
    # The classification follows the proportion: a 100% allocation is
    # BUSINESS, a 0% allocation is PERSONAL, and anything strictly
    # between is genuinely MIXED. Hard-coding MIXED silently mislabels
    # a fully-business expense as mixed-use (CLI testimonial, Nuria).
    if parsed_business_pct == Decimal(1):
        allocation_classification = BusinessClassification.BUSINESS
    elif parsed_business_pct == Decimal(0):
        allocation_classification = BusinessClassification.PERSONAL
    else:
        allocation_classification = BusinessClassification.MIXED
    # A leaked `pydantic.ValidationError` (business_pct out of range, illegal
    # field combination) is caught here and surfaced as the real validator
    # cause, mirroring the `ledger classify` treatment.
    try:
        result = update_manual_transaction_fields(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=resolved_id,
            patch=_patch_from_options(
                business_classification=allocation_classification,
                business_pct=parsed_business_pct,
                category_id=validated_category_id,
                usage_ratio_id=usage_ratio_id,
                prorrata_reference=prorrata_reference,
            ),
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger allocate",
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerAllocateResult

    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.allocate",
        result_cls=LedgerAllocateResult,
    )


register_lifecycle_commands(app)


@app.command(
    "link",
    help=tr("cli.ledger.link.help"),
)
@command_execution_policy(LEDGER_COMPUTE_WRITE)
def ledger_link(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(
        ...,
        help=tr("cli.ledger.link.id_help"),
    ),
    invoice_id: str = typer.Option(
        ...,
        "--invoice-id",
        help=tr("cli.ledger.link.invoice_id_help"),
    ),
    actor: str | None = typer.Option(
        None,
        "--by",
        help=tr("cli.ledger.link.actor_help"),
    ),
) -> None:
    """Bind a transaction to one reconciliation-catalogue invoice, atomically."""
    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ...application.ledger import link_manual_transaction_invoice
    from ...domain.invoices import InvoiceLinkError

    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    bucket_id = transaction_repository.bucket_id
    actor_label = (actor or "operator").strip() or "operator"

    # Pre-write instructive gate: the reconciliation InvoiceCatalogue is the only
    # store `link` targets. A missing/cross-bucket id is refused with the typed
    # localized message (the operator's first instructive surface) before the
    # atomic writer runs.
    invoice_repo = InvoiceCatalogueRepository()
    invoice_record = invoice_repo.load().invoices.get(invoice_id)
    if invoice_record is None:
        raise _bad(
            tr("cli.ledger.link.errors.invoice_not_found"),
        )
    if invoice_record.bucket_id not in (None, bucket_id):
        raise _bad(
            tr("cli.ledger.link.errors.cross_bucket_invoice"),
        )
    try:
        link_manual_transaction_invoice(
            bucket_id=bucket_id,
            transaction_id=resolved_id,
            invoice_id=invoice_id,
            actor=actor_label,
            source_command="aeat app ledger link",
            transaction_repository=transaction_repository,
            invoice_repository=invoice_repo,
        )
    except InvoiceLinkError as exc:
        raise _invoice_link_error_bad_parameter() from exc

    payload: dict[str, object] = {
        "operation": "ledger.link",
        "bucket_id": bucket_id,
        "transaction_id": resolved_id,
        "invoice_id": invoice_id,
        "actor": actor_label,
    }
    lines = [
        "operation\tledger.link",
        f"bucket\t{bucket_id}",
        f"transaction_id\t{resolved_id}",
        f"actor\t{actor_label}",
        f"invoice_id\t{invoice_id}",
    ]
    from ._ledger_payloads import LedgerLinkResult

    _emit_envelope(
        ctx,
        command="ledger.link",
        result=LedgerLinkResult.model_validate(payload),
        lines=lines,
    )


register_read_commands(app, resolve_transaction_id=_resolve_read_id)


register_ratios_commands(app)


register_business_invoice_commands(app)


register_inventory_commands(app)


register_bienes_inversion_commands(app)


register_prorrata_register_commands(app)


register_evidence_commands(app)


register_rule_commands(app)
register_counterparty_commands(app)


register_import_commands(app)
