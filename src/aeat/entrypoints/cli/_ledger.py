"""User-facing ledger and transaction management CLI commands.

Provides the ``aeat ledger`` command group for importing, reviewing, and
exporting financial transaction data. Transaction records are accessed
through :class:`TransactionCatalogueRepository` and invoice records through
:class:`InvoiceCatalogueRepository`. Lifecycle events are appended to the
profile audit trail via :class:`BucketEventHistoryRepository`. Mutation and
read verbs emit typed :class:`OutputSchema` envelopes so CLI JSON stays aligned
with the registered ledger payload contracts.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

import typer
from pydantic import ValidationError

from ...application.ledger import (
    LedgerTransactionResultPayload,
    LLMProvider,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    create_manual_transaction,
    ledger_transaction_payload,
    ledger_transaction_result_payload,
    ledger_transaction_review_status,
    resolve_lineage_transaction_id,
    update_manual_transaction_fields,
)
from ...core import resolve_active_bucket_id
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
from ...core.logging import get_logger
from ...domain.iva._schema import EUMemberState, IvaCategory
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionIdPrefixError,
    is_classified,
)
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
from ._ledger_classify_cli import ledger_classify_bulk_csv
from ._ledger_evidence_cli import register_evidence_commands
from ._ledger_import_cli import register_import_commands
from ._ledger_inventory_cli import inventory_app, register_inventory_commands
from ._ledger_lifecycle_cli import (
    ledger_archive,
    ledger_attach,
    ledger_doclink,
    ledger_merge,
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
from ._ledger_ratios_cli import ratios_app, register_ratios_commands
from ._ledger_read_cli import register_read_commands
from ._ledger_rules_cli import register_rule_commands, rule_app
from ._ledger_support import (
    _invoice_link_error_bad_parameter,
    _ledger_validation_bad,
    _parse_amount_magnitude,
    _parse_decimal,
    _parse_required_decimal,
    _prefix_error_bad,
    _resolve_business_pct_with_censo,
    _resolve_id,
    _resolve_source_jurisdiction,
    _TransactionRepo,
    _validate_business_pct_range,
    _validate_category_id,
)
from ._schemas import OutputSchema

_log = get_logger(__name__)

__all__ = [
    "app",
    "inventory_app",
    "invoice_app",
    "ledger_archive",
    "ledger_attach",
    "ledger_doclink",
    "ledger_merge",
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


def _resolve_read_id(transaction_repository: _TransactionRepo, prefix: str) -> str:
    """Resolve a CLI-supplied id for the *read* verbs, following edit lineage.

    This is the D3 stable-lineage-handle resolution path for
    ``ledger history`` / ``view`` / ``track``. It first resolves ``prefix``
    against live catalogue ids exactly as :func:`_resolve_id` does; when no
    live row matches, it walks the edit-lineage chain so a superseded
    (pre-``update``) id written down by the operator still resolves to the
    current row — see
    :func:`aeat.application.ledger.resolve_lineage_transaction_id`. The
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
        raise _prefix_error_bad(exc, prefix) from exc


def _patch_from_options(**values: object) -> ManualLedgerTransactionPatch:
    return ManualLedgerTransactionPatch.model_validate(
        {key: value for key, value in values.items() if value is not None},
    )


def _emit_update_result(
    ctx: typer.Context,
    result_transaction: Transaction,
    bucket_id: str,
    events: tuple[str, ...],
    *,
    command: str,
    result_cls: type[OutputSchema],
) -> None:
    transaction_payload = ledger_transaction_payload(result_transaction)
    review_status = ledger_transaction_review_status(result_transaction)
    result = result_cls.model_validate(
        {
            "bucket_id": bucket_id,
            "transaction_id": result_transaction.transaction_id,
            "bucket_event_ids": list(events),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    _emit_envelope(
        ctx,
        command=command,
        result=result,
        lines=[
            f"{tr('cli.ledger.labels.id')}\t{result_transaction.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
        ],
    )


@app.command("add", help=tr("cli.ledger.add.help"))
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
    iva_category: IvaCategory | None = typer.Option(
        None,
        "--iva-category",
        help=tr("cli.ledger.classify.iva_category_help"),
    ),
    recargo_amount: str | None = typer.Option(None, "--recargo-amount", help=tr("cli.ledger.add.recargo_amount_help")),
    irpf_category: str | None = typer.Option(None, "--irpf-category", help=tr("cli.ledger.add.irpf_category_help")),
    usage_ratio_id: str | None = typer.Option(None, "--usage-ratio-id", help=tr("cli.ledger.add.usage_ratio_help")),
    prorrata_reference: str | None = typer.Option(
        None,
        "--prorrata-reference",
        help=tr("cli.ledger.add.prorrata_reference_help"),
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
        is_classified(business_classification)
        or business_classification is BusinessClassification.NOT_YET_PROCESSED
    )
    if not operator_assignable_on_add:
        # PROCESSED_UNCLASSIFIED / SKIPPED_BY_RULE / FAILED_VALIDATION are
        # produced by the classification pipeline, never assigned by hand. A new
        # row is BUSINESS, PERSONAL, MIXED, or left at the NOT_YET_PROCESSED
        # default; refuse the internal states instructively.
        raise _bad(
            tr(
                "cli.ledger.add.system_state_not_assignable",
                value=business_classification.value,
                default=(
                    f"Classification '{business_classification.value}' is set automatically by aeat "
                    "and cannot be assigned by hand. Choose one of: BUSINESS, PERSONAL, MIXED, or "
                    "omit --classification to leave the row unclassified."
                ),
            ),
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
            recargo_amount=_parse_decimal(recargo_amount, label="recargo-amount"),
            irpf_category=irpf_category,
            usage_ratio_id=usage_ratio_id,
            prorrata_reference=prorrata_reference,
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
    # The gross-invariant (`taxable_base + iva_amount == amount`) and other
    # `Transaction.model_validate` rules fire inside `create_manual_transaction`,
    # raising a pydantic `ValidationError` whose default rendering dumps the full
    # `RawTransaction(...)` repr (~30 lines) to the operator. Catch it at the CLI
    # boundary and surface only the human-readable validator message, matching
    # the `ManualLedgerTransactionCommand` treatment above — CLI errors are
    # typed refusals, never raw dumps.
    try:
        result = create_manual_transaction(
            command,
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerAddResult

    transaction_payload = ledger_transaction_payload(result.transaction)
    review_status = ledger_transaction_review_status(result.transaction)
    add_result = LedgerAddResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.ref.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    _emit_envelope(
        ctx,
        command="ledger.add",
        result=add_result,
        lines=[
            f"{tr('cli.ledger.labels.id')}\t{result.ref.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
        ],
    )


@app.command("update", help=tr("cli.ledger.update.help"))
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


_FromCsvOpt = Annotated[
    str | None,
    typer.Option(
        "--from-csv",
        help=tr(
            "cli.ledger.classify.from_csv_help",
            default=(
                "Path to a CSV file with columns transaction_id, classification"
                "[, category_id, business_pct, taxable_base, iva_rate, iva_amount, iva_category, "
                "irpf_category]."
            ),
        ),
    ),
]


@app.command("classify", help=tr("cli.ledger.classify.help"))
def ledger_classify(
    ctx: typer.Context,
    transaction_id: str | None = typer.Argument(None, help=tr("cli.ledger.classify.id_help")),
    classification: BusinessClassification | None = typer.Option(
        None,
        "--classification",
        help=tr("cli.ledger.classify.classification_help"),
    ),
    from_csv: _FromCsvOpt = None,
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
    iva_category: IvaCategory | None = typer.Option(
        None,
        "--iva-category",
        help=tr("cli.ledger.classify.iva_category_help"),
    ),
    counterparty_eu_member_state: EUMemberState | None = typer.Option(
        None,
        "--counterparty-eu-member-state",
        help=tr("cli.ledger.classify.counterparty_eu_member_state_help"),
    ),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.classify.actor_help")),
    reaffirm: bool = typer.Option(False, "--reaffirm", help=tr("cli.ledger.classify.reaffirm_help")),
    llm: LLMProvider | None = typer.Option(None, "--llm", help=tr("cli.ledger.classify.llm_help")),
    apply: bool = typer.Option(False, "--apply", help=tr("cli.ledger.classify.apply_help")),
    saturate: bool = typer.Option(False, "--saturate", help=tr("cli.ledger.classify.saturate_help")),
    read_evidence: bool = typer.Option(False, "--read-evidence", help=tr("cli.ledger.classify.read_evidence_help")),
    evidence_acknowledged: bool = typer.Option(
        False,
        "--evidence-acknowledged",
        help=tr("cli.ledger.classify.evidence_acknowledged_help"),
    ),
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
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.classify.reason_help")),
) -> None:
    """Classify one ledger transaction (positional id), via LLM (--llm), or in bulk (--from-csv)."""
    if auto_split:
        dispatch_autosplit(
            ctx,
            transaction_id=transaction_id,
            classification=classification,
            from_csv=from_csv,
            provider=llm,
            apply=apply,
            actor=actor,
            read_evidence=read_evidence,
            evidence_acknowledged=evidence_acknowledged,
            vision_model=vision_model,
            reject=reject,
            reason=reason,
        )
        return
    if llm is not None or read_evidence:
        saturate_kwargs = {
            "ctx": ctx,
            "transaction_id": transaction_id,
            "classification": classification,
            "from_csv": from_csv,
            "business_pct": business_pct,
            "provider": llm,
            "apply": apply,
            "actor": actor,
            "read_evidence": read_evidence,
            "evidence_acknowledged": evidence_acknowledged,
            "vision_model": vision_model,
            "reject": reject,
            "reason": reason,
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
            from_csv=from_csv,
            iva_category=iva_category,
            actor=actor,
        )
        return
    state = _state()
    transaction_repository = _tx_repo(state)

    if from_csv is not None:
        ledger_classify_bulk_csv(
            ctx,
            transaction_repository=transaction_repository,
            transaction_id=transaction_id,
            classification=classification,
            from_csv=from_csv,
            actor=actor,
        )
        return

    # Single-transaction mode: the positional id and --classification are required
    if transaction_id is None:
        raise _bad(
            tr(
                "cli.ledger.classify.id_required",
                default="A transaction id is required when --from-csv is not provided.",
            ),
        )
    if classification is None:
        raise _bad(
            tr(
                "cli.ledger.classify.classification_required",
                default="--classification is required when --from-csv is not provided.",
            ),
        )
    if not is_classified(classification):
        # NOT_YET_PROCESSED / PROCESSED_UNCLASSIFIED / SKIPPED_BY_RULE /
        # FAILED_VALIDATION are pipeline-managed states; an operator classifies a
        # row only as BUSINESS, PERSONAL, or MIXED. Refuse the system states
        # instructively rather than letting the enum Choice apply one by hand.
        raise _bad(
            tr(
                "cli.ledger.classify.system_state_not_assignable",
                value=classification.value,
                default=(
                    f"Classification '{classification.value}' is set automatically by aeat and "
                    "cannot be assigned by hand. Choose one of: BUSINESS, PERSONAL, MIXED."
                ),
            ),
        )
    validated_category_id = _validate_category_id(category_id)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
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
            iva_category=iva_category,
            counterparty_eu_member_state=counterparty_eu_member_state,
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
    from ._ledger_payloads import LedgerClassifySingleResult

    transaction_payload = ledger_transaction_payload(result.transaction)
    review_status = ledger_transaction_review_status(result.transaction)
    classify_result = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
        f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
        f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    if reaffirm:
        lines.insert(0, tr("cli.ledger.classify.reaffirmed"))
    _emit_envelope(
        ctx,
        command="ledger.classify",
        result=classify_result,
        lines=lines,
    )


@app.command("allocate", help=tr("cli.ledger.allocate.help"))
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
    help=tr(
        "cli.ledger.link.help",
        default=(
            "Bind a ledger transaction to an invoice and/or a purchase-invoice "
            "evidence record in a single canonical call. Refuses cross-bucket "
            "links. Local-only; never contacts AEAT."
        ),
    ),
)
def ledger_link(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(
        ...,
        help=tr("cli.ledger.link.id_help", default="Ledger transaction id (SHA-256 or unambiguous prefix)."),
    ),
    invoice_id: str | None = typer.Option(
        None,
        "--invoice-id",
        help=tr(
            "cli.ledger.link.invoice_id_help",
            default="Invoice id to bind bidirectionally to the transaction.",
        ),
    ),
    evidence_id: str | None = typer.Option(
        None,
        "--evidence-id",
        help=tr(
            "cli.ledger.link.evidence_id_help",
            default="Purchase-invoice evidence record id to attach to the transaction.",
        ),
    ),
    actor: str | None = typer.Option(
        None,
        "--by",
        help=tr("cli.ledger.link.actor_help", default="Operator label recorded on bucket events."),
    ),
) -> None:
    """Bind a transaction to invoice / evidence references in one call."""
    from ...application.invoices import link_invoice_transaction_repositories
    from ...domain.invoices import InvoiceCatalogueRepository
    from ...domain.invoices._errors import InvoiceLinkError

    if invoice_id is None and evidence_id is None:
        raise _bad(
            tr(
                "cli.ledger.link.errors.missing_target",
                default="Supply at least one of --invoice-id or --evidence-id.",
            ),
        )

    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    bucket_id = transaction_repository.bucket_id
    actor_label = (actor or "operator").strip() or "operator"

    if invoice_id is not None:
        # Pre-write bucket guard: load the invoice and verify it is
        # scoped to the active bucket BEFORE invoking the linker.
        # link_invoice_transaction_repositories mutates both invoice and
        # transaction catalogues; a post-write check would leave a
        # cross-bucket link persisted.
        invoice_repo = InvoiceCatalogueRepository()
        invoices_snapshot = invoice_repo.load()
        invoice_record = invoices_snapshot.invoices.get(invoice_id)
        if invoice_record is None:
            raise _bad(
                tr(
                    "cli.ledger.link.errors.invoice_not_found",
                    default="Invoice id not found in the active profile invoice catalogue.",
                ),
            )
        if invoice_record.bucket_id not in (None, bucket_id):
            raise _bad(
                tr(
                    "cli.ledger.link.errors.cross_bucket_invoice",
                    default="Invoice belongs to a different bucket than the active profile.",
                ),
            )
        try:
            link_invoice_transaction_repositories(
                bucket_id=bucket_id,
                invoice_id=invoice_id,
                transaction_id=resolved_id,
                invoice_repository=invoice_repo,
                transaction_repository=transaction_repository,
            )
        except InvoiceLinkError as exc:
            raise _invoice_link_error_bad_parameter() from exc

    evidence_result_payload: LedgerTransactionResultPayload | None = None
    if evidence_id is not None:
        evidence_patch = ManualLedgerTransactionPatch(purchase_invoice_evidence_id=evidence_id)
        evidence_result = update_manual_transaction_fields(
            bucket_id=bucket_id,
            transaction_id=resolved_id,
            patch=evidence_patch,
            actor=actor_label,
            source_command="aeat app ledger link",
        )
        evidence_result_payload = ledger_transaction_result_payload(evidence_result)

    payload: dict[str, object] = {
        "operation": "ledger.link",
        "bucket_id": bucket_id,
        "transaction_id": resolved_id,
        "invoice_id": invoice_id,
        "evidence_id": evidence_id,
        "actor": actor_label,
    }
    if evidence_result_payload is not None:
        # D1/D2: project the mutated transaction onto the result's `transaction`
        # slot and carry the evidence update as a typed payload (mode="json" so
        # the nested TransactionPayload's str fields validate cleanly).
        payload["evidence_update"] = evidence_result_payload.model_dump(mode="json")
        payload["transaction"] = evidence_result_payload.transaction.model_dump(mode="json")
    lines = [
        "operation\tledger.link",
        f"bucket\t{bucket_id}",
        f"transaction_id\t{resolved_id}",
        f"actor\t{actor_label}",
    ]
    if invoice_id is not None:
        lines.append(f"invoice_id\t{invoice_id}")
    if evidence_id is not None:
        lines.append(f"evidence_id\t{evidence_id}")
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


register_evidence_commands(app)


register_rule_commands(app)


register_import_commands(app)
