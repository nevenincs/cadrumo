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
:func:`emit_envelope` so CLI JSON stays aligned
with the registered ledger payload contracts.
"""

from __future__ import annotations

from decimal import Decimal

import typer
from pydantic import ValidationError

from ...application.ledger.actions_manual import create_manual_transaction, update_manual_transaction_fields
from ...application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n.render import tr
from ...core.irnr import M210PayerMode
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.json_contract import Notice, NoticeSeverity
from ...core.prorrata_exclusions import Art104TresExclusion
from ...core.prorrata_register import ProrrataRegisterRegime
from ...domain.iva.prorrata import InputClassification
from ...domain.iva.schema import EUMemberState, IvaCategory
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, is_classified
from ...domain.transactions.errors import TransactionValidationError
from ._common import bad, current_workflow_state, emit_envelope, profile_to_taxpayer, transaction_catalogue_repo
from ._date_parsing import _parse_iso_date
from ._ledger_classify_cli import ledger_classify_bulk_csv, require_single_ledger_classification_request
from ._ledger_llm_cli import (
    LedgerLlmRouteArguments,
    dispatch_autosplit,
    ledger_classify_llm,
    ledger_operator_iva_derive,
    ledger_saturate_llm,
)
from ._ledger_m210_classify_cli import M210LedgerClassifyOptions
from ._ledger_support import (
    emit_update_result,
    invoice_link_error_bad_parameter,
    ledger_transaction_validation_no_recovery,
    ledger_validation_bad,
    parse_amount_magnitude,
    parse_decimal_option,
    parse_required_decimal,
    resolve_business_pct_with_censo,
    resolve_id,
    resolve_source_jurisdiction,
    validate_business_pct_range,
    validate_category_id,
)
from .ledger_lifecycle_cli import (
    ledger_archive,
    ledger_attach,
    ledger_evidence_pull,
    ledger_evidence_pull_all,
    ledger_merge,
    ledger_remove,
    ledger_reset,
    ledger_split,
    ledger_stash,
)

__all__ = [
    "ledger_archive",
    "ledger_attach",
    "ledger_evidence_pull",
    "ledger_evidence_pull_all",
    "ledger_merge",
    "ledger_remove",
    "ledger_reset",
    "ledger_split",
    "ledger_stash",
]


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
    from ...application.prorrata_register.service import ProrrataRegisterService

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
    from ...application.prorrata_register.service import ProrrataRegisterService

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


def ledger_add(
    ctx: typer.Context,
    booked_date: str,
    amount: str,
    direction: TransactionDirection,
    description: str,
    value_date: str | None = None,
    currency: str = DEFAULT_CURRENCY,
    counterparty: str | None = None,
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    business_pct: str | None = None,
    category_id: str | None = None,
    taxable_base: str | None = None,
    iva_rate: str | None = None,
    iva_amount: str | None = None,
    iva_category: IvaCategory | None = None,
    deduction_fact_kind: IvaDeductionFactKind | None = None,
    counterparty_country: str | None = None,
    counterparty_identification_state: EUMemberState | None = None,
    recargo_amount: str | None = None,
    irpf_category: str | None = None,
    usage_ratio_id: str | None = None,
    prorrata_reference: str | None = None,
    art_104_tres_exclusion: Art104TresExclusion | None = None,
    input_classification: InputClassification | None = None,
    prorrata_sector: str | None = None,
    purchase_invoice_evidence_id: str | None = None,
    attachment_ids: tuple[str, ...] = (),
    notes: str = "",
    actor: str | None = None,
    idempotency_key: str | None = None,
    source_jurisdiction: str | None = None,
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
        raise bad(
            tr("cli.ledger.add.system_state_not_assignable", value=business_classification.value),
        )
    current_state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(current_state)
    validated_category_id = validate_category_id(category_id)
    resolved_business_pct = resolve_business_pct_with_censo(
        bucket_id=transaction_repository.bucket_id,
        active_profile=resolve_active_bucket_id(),
        category_id=validated_category_id,
        operator_supplied=validate_business_pct_range(parse_decimal_option(business_pct, label="business-pct")),
        year=_parse_iso_date(booked_date, label="date").year,
    )
    active_taxpayer = profile_to_taxpayer(current_state)
    resolved_source_jurisdiction = resolve_source_jurisdiction(
        source_jurisdiction,
        fiscal_residency=active_taxpayer.fiscal_residency,
        irpf_special_regime=active_taxpayer.irpf_special_regime,
    )
    try:
        command = ManualLedgerTransactionCommand(
            bucket_id=transaction_repository.bucket_id,
            booked_date=_parse_iso_date(booked_date, label="date"),
            value_date=_parse_iso_date(value_date, label="value-date") if value_date is not None else None,
            amount=parse_amount_magnitude(amount),
            currency=currency,
            direction=direction,
            counterparty=counterparty,
            description=description,
            business_classification=business_classification,
            business_pct=resolved_business_pct,
            category_id=validated_category_id,
            taxable_base=parse_decimal_option(taxable_base, label="taxable-base"),
            iva_rate=parse_decimal_option(iva_rate, label="iva-rate"),
            iva_amount=parse_decimal_option(iva_amount, label="iva-amount"),
            iva_category=iva_category,
            deduction_fact_kind=deduction_fact_kind,
            counterparty_country=counterparty_country,
            counterparty_identification_state=counterparty_identification_state,
            recargo_amount=parse_decimal_option(recargo_amount, label="recargo-amount"),
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
        raise ledger_validation_bad(exc) from exc
    except TransactionValidationError as exc:
        raise ledger_transaction_validation_no_recovery(exc) from None
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
    from ...adapters.outbound.fx.ecb_provider import default_ecb_rate_provider
    from ...domain.currency.service import CurrencyNormalizationService

    try:
        result = create_manual_transaction(
            command,
            transaction_repository=transaction_repository,
            currency_normalizer=CurrencyNormalizationService(rate_provider=default_ecb_rate_provider()),
        )
    except ValidationError as exc:
        raise ledger_validation_bad(exc) from exc
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
    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        tuple(result.bucket_event_ids),
        command="ledger.add",
        result_cls=LedgerAddResult,
        notices=notices or None,
        extra_lines=noop_lines,
    )


def ledger_update(
    ctx: typer.Context,
    transaction_id: str,
    booked_date: str | None = None,
    value_date: str | None = None,
    amount: str | None = None,
    direction: TransactionDirection | None = None,
    currency: str | None = None,
    counterparty: str | None = None,
    description: str | None = None,
    taxable_base: str | None = None,
    iva_rate: str | None = None,
    iva_amount: str | None = None,
    irpf_category: str | None = None,
    notes: str | None = None,
    group: str | None = None,
    actor: str | None = None,
) -> None:
    """Correct editable transaction facts through the bucket-scoped backend."""
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)
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
                amount=parse_amount_magnitude(amount) if amount is not None else None,
                direction=direction,
                currency=currency,
                counterparty=counterparty,
                description=description,
                taxable_base=parse_decimal_option(taxable_base, label="taxable-base"),
                iva_rate=parse_decimal_option(iva_rate, label="iva-rate"),
                iva_amount=parse_decimal_option(iva_amount, label="iva-amount"),
                irpf_category=irpf_category,
                notes=notes,
                group_label=group,
            ),
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger update",
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerUpdateResult

    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.update",
        result_cls=LedgerUpdateResult,
    )


def ledger_classify(
    ctx: typer.Context,
    transaction_id: str | None = None,
    classification: BusinessClassification | None = None,
    file: str | None = None,
    business_pct: str | None = None,
    category_id: str | None = None,
    taxable_base: str | None = None,
    iva_rate: str | None = None,
    iva_amount: str | None = None,
    irpf_category: str | None = None,
    m210_tipo_renta_code: str | None = None,
    m210_gross_income_amount: str | None = None,
    m210_applicable_rate: str | None = None,
    m210_payer_mode: M210PayerMode | None = None,
    m210_payer_id: str | None = None,
    m210_asset_or_right_id: str | None = None,
    iva_category: IvaCategory | None = None,
    deduction_fact_kind: IvaDeductionFactKind | None = None,
    counterparty_country: str | None = None,
    counterparty_identification_state: EUMemberState | None = None,
    actor: str | None = None,
    reaffirm: bool = False,
    llm: bool = False,
    apply: bool = False,
    saturate: bool = False,
    read_evidence: bool = False,
    vision_model: str | None = None,
    auto_split: bool = False,
    reject: bool = False,
    reason: str | None = None,
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
        llm_requested=llm,
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
        saturate_kwargs: LedgerLlmRouteArguments = {
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
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)

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
    validated_category_id = validate_category_id(category_id)
    resolved_id = resolve_id(transaction_repository, transaction_id)
    m210_income_classification = m210_options.to_income_classification(
        transaction_repository=transaction_repository,
        transaction_id=resolved_id,
    )
    if classification is BusinessClassification.MIXED and business_pct is None:
        # MIXED demands a proportion; surface the `--business-pct` flag
        # directly rather than letting the patch validator's generic
        # message route through the opaque boundary.
        raise bad(tr("cli.ledger.classify.mixed_requires_business_pct"))
    if classification is not BusinessClassification.MIXED and business_pct is not None:
        # `--business-pct` only carries meaning for a MIXED row; a
        # BUSINESS or PERSONAL classification is wholly business or
        # wholly private. Refuse rather than silently dropping it.
        raise bad(tr("cli.ledger.classify.business_pct_requires_mixed"))
    # A leaked `pydantic.ValidationError` (negative `--taxable-base`,
    # an illegal field combination) is otherwise wrapped by the generic
    # CLI boundary into "command input failed validation. Run config
    # repair" — a misleading hint, since `config repair` cannot fix a
    # bad CLI argument. Catch it here and surface the real validator
    # cause, matching the `ledger add` / `ledger review` treatment.
    try:
        patch = _patch_from_options(
            business_classification=classification,
            business_pct=validate_business_pct_range(parse_decimal_option(business_pct, label="business-pct")),
            category_id=validated_category_id,
            taxable_base=parse_decimal_option(taxable_base, label="taxable-base"),
            iva_rate=parse_decimal_option(iva_rate, label="iva-rate"),
            iva_amount=parse_decimal_option(iva_amount, label="iva-amount"),
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
        raise ledger_validation_bad(exc) from exc
    except TransactionValidationError as exc:
        raise ledger_transaction_validation_no_recovery(exc) from None
    from ._ledger_payloads import LedgerClassifySingleResult

    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        tuple(result.bucket_event_ids),
        command="ledger.classify",
        result_cls=LedgerClassifySingleResult,
        prepend_lines=(tr("cli.ledger.classify.reaffirmed"),) if reaffirm else (),
    )


def ledger_allocate(
    ctx: typer.Context,
    transaction_id: str,
    business_pct: str,
    category_id: str | None = None,
    usage_ratio_id: str | None = None,
    prorrata_reference: str | None = None,
    actor: str | None = None,
) -> None:
    """Record business/private proportionality through the ledger backend."""
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    validated_category_id = validate_category_id(category_id)
    resolved_id = resolve_id(transaction_repository, transaction_id)
    parsed_business_pct = parse_required_decimal(business_pct, label="business-pct")
    validate_business_pct_range(parsed_business_pct)
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
        raise ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerAllocateResult

    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.allocate",
        result_cls=LedgerAllocateResult,
    )


def _link_refusal(exc: Exception) -> typer.BadParameter:
    """Map one link refusal to the instructive message for its actual cause.

    Only the two operator-caused refusals get a specific message. They are
    identified by context keys the writer sets for those cases alone:
    ``invoice_bucket_id`` names the bucket a resolved invoice really belongs
    to, and ``bucket_id`` accompanies an invoice id that resolved to nothing.
    Every other link failure -- an invoice missing after its own update, a
    malformed digest, a catalogue validation error -- is an internal
    inconsistency the operator cannot act on differently, and keeps the generic
    message. Matching on ``invoice_id`` alone would be wrong: three unrelated
    raise sites carry it.
    """
    context = getattr(exc, "context", None) or {}
    if "invoice_bucket_id" in context:
        return bad(tr("cli.ledger.link.errors.cross_bucket_invoice"))
    if "bucket_id" in context:
        return bad(tr("cli.ledger.link.errors.invoice_not_found"))
    return invoice_link_error_bad_parameter()


def ledger_link(
    ctx: typer.Context,
    transaction_id: str,
    invoice_id: str,
    actor: str | None = None,
) -> None:
    """Bind a transaction to one reconciliation-catalogue invoice, atomically."""
    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ...application.ledger.actions_manual import link_manual_transaction_invoice
    from ...domain.invoices.errors import InvoiceLinkError

    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)
    bucket_id = transaction_repository.bucket_id
    actor_label = (actor or "operator").strip() or "operator"

    invoice_repo = InvoiceCatalogueRepository()
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
        # The writer owns the missing/cross-bucket policy and refuses before it
        # writes anything, so this adapter reads neither the catalogue nor the
        # record: it maps the refusal it was given back to the instructive
        # message the operator needs. The two cases are told apart by the
        # context the writer already supplies -- an invoice that resolved but
        # belongs elsewhere carries its owning bucket, one that never resolved
        # cannot.
        raise _link_refusal(exc) from exc

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

    emit_envelope(
        ctx,
        command="ledger.link",
        result=LedgerLinkResult.model_validate(payload),
        lines=lines,
    )
