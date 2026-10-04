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

import typer
from pydantic import ValidationError

from ...application.ledger.classify_result_contracts import (
    LedgerClassifyOperationResult,
)
from ...application.ledger.ledger_add_contracts import LedgerAddOperationResult
from ...application.ledger.models import (
    ManualLedgerTransactionPatch,
)
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n.render import tr
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.json_contract import Notice, NoticeSeverity
from ...core.prorrata_exclusions import Art104TresExclusion
from ...domain.iva.schema import EUMemberState, IvaCategory
from ...domain.transactions.enums import (
    BusinessClassification,
    TransactionDirection,
    is_classified,
    takes_business_share,
)
from ...domain.transactions.errors import TransactionValidationError
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
    invoice_link_error_bad_parameter,
    ledger_transaction_validation_no_recovery,
    ledger_validation_bad,
    parse_amount_magnitude,
    parse_decimal_option,
    parse_required_decimal,
    validate_business_pct_range,
    validate_category_id,
)
from .common import bad, emit_envelope
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


def _require_add_assignable_classification(business_classification: BusinessClassification) -> None:
    """Refuse pipeline-owned states before constructing a manual add command."""
    if is_classified(business_classification) or business_classification is BusinessClassification.NOT_YET_PROCESSED:
        return
    raise bad(
        tr("cli.ledger.add.system_state_not_assignable", value=business_classification.value),
    )


def _manual_add_notices(
    *, result: LedgerAddOperationResult, idempotency_key: str | None
) -> tuple[list[Notice], list[str]]:
    """Project add advisories into the shared notice and text channels."""
    transaction = result.transaction
    if transaction is None:
        raise RuntimeError("ledger add notices require a successful transaction projection")
    normalized_idempotency_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
    notices: list[Notice] = []
    extra_lines: list[str] = []
    if not result.bucket_event_ids:
        noop_message = tr(
            "cli.ledger.add.idempotent_noop",
            transaction_id=transaction.transaction_id,
        )
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.add.idempotent_noop",
                message=noop_message,
                context={
                    "transaction_id": transaction.transaction_id,
                    "idempotency_key": normalized_idempotency_key or "",
                },
            )
        )
        extra_lines.append(noop_message)
    if result.advisory_input_classification_inert:
        input_classification = result.advisory_input_classification
        if input_classification is None:
            raise RuntimeError("ledger add inert-classification advisory omitted its source token")
        ejercicio = int(transaction.booked_date[:4])
        inert_message = tr(
            "cli.ledger.add.input_classification_inert",
            ejercicio=ejercicio,
        )
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.add.input_classification_inert",
                message=inert_message,
                context={
                    "ejercicio": str(ejercicio),
                    "input_classification": input_classification,
                    "sector_id": result.advisory_sector_id or "",
                },
            )
        )
        extra_lines.append(inert_message)
    _append_unmatched_sector_notice(result, notices, extra_lines)
    return notices, extra_lines


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
    investment_asset_id: str | None = None,
    counterparty_country: str | None = None,
    counterparty_identification_state: EUMemberState | None = None,
    recargo_amount: str | None = None,
    irpf_category: str | None = None,
    usage_ratio_id: str | None = None,
    prorrata_reference: str | None = None,
    art_104_tres_exclusion: Art104TresExclusion | None = None,
    input_classification: str | None = None,
    prorrata_sector: str | None = None,
    purchase_invoice_evidence_id: str | None = None,
    attachment_ids: tuple[str, ...] = (),
    notes: str = "",
    actor: str | None = None,
    idempotency_key: str | None = None,
    source_jurisdiction: str | None = None,
    account: str | None = None,
) -> None:
    """Create one manual ledger transaction through exact-profile operation custody."""
    _require_add_assignable_classification(business_classification)
    from .runtime_ledger_add import run_ledger_add

    result = run_ledger_add(
        ctx,
        booked_date=booked_date,
        amount=amount,
        direction=direction,
        description=description,
        value_date=value_date,
        currency=currency,
        counterparty=counterparty,
        business_classification=business_classification,
        business_pct=business_pct,
        category_id=category_id,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        iva_category=iva_category,
        deduction_fact_kind=deduction_fact_kind,
        investment_asset_id=investment_asset_id,
        counterparty_country=counterparty_country,
        counterparty_identification_state=counterparty_identification_state,
        recargo_amount=recargo_amount,
        irpf_category=irpf_category,
        usage_ratio_id=usage_ratio_id,
        prorrata_reference=prorrata_reference,
        art_104_tres_exclusion=art_104_tres_exclusion,
        input_classification=input_classification,
        prorrata_sector=prorrata_sector,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
        attachment_ids=attachment_ids,
        notes=notes,
        actor=actor,
        idempotency_key=idempotency_key,
        source_jurisdiction=source_jurisdiction,
        own_account_id=account,
    )
    if result.transaction is None or result.review_status is None:
        raise RuntimeError("ledger add runtime returned no successful transaction projection")
    notices, extra_lines = _manual_add_notices(
        result=result,
        idempotency_key=idempotency_key,
    )

    from ._ledger_payloads import LedgerAddResult, TransactionPayload

    transaction = result.transaction
    transaction_payload = TransactionPayload.model_validate(transaction.model_dump(mode="json"))
    output = LedgerAddResult.model_validate(
        {
            "bucket_id": str(result.profile_id),
            "transaction_id": transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": result.review_status.value,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    emit_envelope(
        ctx,
        command="ledger.add",
        result=output,
        lines=[
            f"{tr('cli.ledger.labels.id')}\t{transaction.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{result.review_status.value}",
            *extra_lines,
        ],
        notices=notices or None,
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
    account: str | None = None,
    actor: str | None = None,
) -> None:
    """Correct editable transaction facts through the exact-profile worker."""
    try:
        patch = _patch_from_options(
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
            own_account_id=account,
        )
    except ValidationError as exc:
        raise ledger_validation_bad(exc) from exc
    from .runtime_ledger_update import run_ledger_update

    try:
        result = run_ledger_update(ctx, transaction_id=transaction_id, patch=patch, actor=actor)
    except ValidationError as exc:
        raise ledger_validation_bad(exc) from exc
    if result.outcome == "validation_error":
        details = "; ".join(result.validation_messages)
        raise bad(
            tr(
                "cli.ledger.errors.command_input_invalid",
                details=details or tr("cli.ledger.errors.command_input_invalid_fallback"),
            ),
        )
    transaction = result.transaction
    review_status = result.review_status
    if transaction is None or review_status is None:
        from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    from ._ledger_payloads import LedgerUpdateResult

    output_result = LedgerUpdateResult.model_validate(
        {
            "bucket_id": str(result.profile_id),
            "transaction_id": transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction.model_dump(mode="json"),
        },
    )
    emit_envelope(
        ctx,
        command="ledger.update",
        result=output_result,
        lines=[
            f"{tr('cli.ledger.labels.id')}\t{transaction.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
        ],
    )


def _build_m210_classify_options(
    *,
    tipo_renta_code: str | None,
    gross_income_amount: str | None,
    applicable_rate: str | None,
    payer_mode: str | None,
    payer_id: str | None,
    asset_or_right_id: str | None,
) -> M210LedgerClassifyOptions:
    """Build the existing M210 option contract from the command arguments."""
    return M210LedgerClassifyOptions(
        tipo_renta_code=tipo_renta_code,
        gross_income_amount=gross_income_amount,
        applicable_rate=applicable_rate,
        payer_mode=payer_mode,
        payer_id=payer_id,
        asset_or_right_id=asset_or_right_id,
    )


def _dispatch_non_direct_classification_route(
    ctx: typer.Context,
    *,
    m210_options: M210LedgerClassifyOptions,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    file: str | None,
    business_pct: str | None,
    apply: bool,
    actor: str | None,
    llm: bool,
    read_evidence: bool,
    saturate: bool,
    iva_category: IvaCategory | None,
    vision_model: str | None,
    auto_split: bool,
    reject: bool,
    reason: str,
) -> bool:
    """Route LLM, evidence, autosplit, and M210-incompatible modes as one gate."""
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
            reason=reason,
        )
        return True
    if llm or read_evidence:
        route_arguments: LedgerLlmRouteArguments = {
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
            "reason": reason,
        }
        if saturate:
            ledger_saturate_llm(**route_arguments)
            return True
        ledger_classify_llm(**route_arguments)
        return True
    if saturate:
        ledger_operator_iva_derive(
            ctx,
            transaction_id=transaction_id,
            classification=classification,
            file=file,
            iva_category=iva_category,
            actor=actor,
        )
        return True
    return False


def _dispatch_bulk_classification_route(
    ctx: typer.Context,
    *,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    file: str | None,
    actor: str | None,
) -> bool:
    """Run the existing CSV classifier when ``--file`` owns the request."""
    if file is None:
        return False
    ledger_classify_bulk_csv(
        ctx,
        transaction_id=transaction_id,
        classification=classification,
        file=file,
        actor=actor,
    )
    return True


def _require_classification_business_pct(
    classification: BusinessClassification,
    business_pct: str | None,
) -> None:
    """Enforce the domain classification/share coupling before patch validation."""
    if takes_business_share(classification) and business_pct is None:
        raise bad(tr("cli.ledger.classify.mixed_requires_business_pct"))
    if not takes_business_share(classification) and business_pct is not None:
        raise bad(tr("cli.ledger.classify.business_pct_requires_mixed"))


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
    m210_payer_mode: str | None = None,
    m210_payer_id: str | None = None,
    m210_asset_or_right_id: str | None = None,
    iva_category: IvaCategory | None = None,
    deduction_fact_kind: IvaDeductionFactKind | None = None,
    investment_asset_id: str | None = None,
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
    m210_options = _build_m210_classify_options(
        tipo_renta_code=m210_tipo_renta_code,
        gross_income_amount=m210_gross_income_amount,
        applicable_rate=m210_applicable_rate,
        payer_mode=m210_payer_mode,
        payer_id=m210_payer_id,
        asset_or_right_id=m210_asset_or_right_id,
    )
    if _dispatch_non_direct_classification_route(
        ctx,
        m210_options=m210_options,
        transaction_id=transaction_id,
        classification=classification,
        file=file,
        business_pct=business_pct,
        apply=apply,
        actor=actor,
        llm=llm,
        read_evidence=read_evidence,
        saturate=saturate,
        iva_category=iva_category,
        vision_model=vision_model,
        auto_split=auto_split,
        reject=reject,
        reason=reason or "",
    ):
        return
    if file is not None and _dispatch_bulk_classification_route(
        ctx,
        transaction_id=transaction_id,
        classification=classification,
        file=file,
        actor=actor,
    ):
        return

    transaction_id, classification = require_single_ledger_classification_request(
        transaction_id=transaction_id,
        classification=classification,
        reason=reason,
    )
    # Category membership is resolved under the worker's pinned authority;
    # keep only the CLI's historical blank-as-omitted behavior here.
    normalized_category_id = category_id.strip() if category_id is not None else None
    validated_category_id = normalized_category_id or None
    _require_classification_business_pct(classification, business_pct)
    # A leaked `pydantic.ValidationError` (negative `--taxable-base`,
    # an illegal field combination) is otherwise wrapped by the generic
    # CLI boundary into "command input failed validation. Run config
    # repair" — a misleading hint, since `config repair` cannot fix a
    # bad CLI argument. Catch it here and surface the real validator
    # cause, matching the `ledger add` / `ledger review` treatment.
    try:
        parsed_business_pct = validate_business_pct_range(parse_decimal_option(business_pct, label="business-pct"))
        patch = _patch_from_options(
            business_classification=classification,
            business_pct=parsed_business_pct,
            category_id=validated_category_id,
            taxable_base=parse_decimal_option(taxable_base, label="taxable-base"),
            iva_rate=parse_decimal_option(iva_rate, label="iva-rate"),
            iva_amount=parse_decimal_option(iva_amount, label="iva-amount"),
            irpf_category=irpf_category,
            iva_category=iva_category,
            deduction_fact_kind=deduction_fact_kind,
            investment_asset_id=investment_asset_id,
            counterparty_country=counterparty_country,
            counterparty_identification_state=counterparty_identification_state,
            notes=reason,
        )
        parsed_m210_gross_income_amount = parse_decimal_option(
            m210_options.gross_income_amount,
            label="m210-gross-income-amount",
        )
        parsed_m210_applicable_rate = parse_decimal_option(
            m210_options.applicable_rate,
            label="m210-applicable-rate",
        )
    except ValidationError as exc:
        raise ledger_validation_bad(exc) from exc
    except TransactionValidationError as exc:
        raise ledger_transaction_validation_no_recovery(exc) from None
    from .runtime_ledger_classify import run_ledger_classify

    try:
        result = run_ledger_classify(
            ctx,
            transaction_id=transaction_id,
            classification=classification,
            patch=patch,
            business_pct=parsed_business_pct,
            m210_tipo_renta_code=m210_options.tipo_renta_code,
            m210_gross_income_amount=parsed_m210_gross_income_amount,
            m210_applicable_rate=parsed_m210_applicable_rate,
            m210_payer_mode=m210_options.payer_mode,
            m210_payer_id=m210_options.payer_id,
            m210_asset_or_right_id=m210_options.asset_or_right_id,
            actor=actor,
            reaffirm=reaffirm,
        )
    except ValidationError as exc:
        raise ledger_validation_bad(exc) from exc
    _emit_single_classification(ctx, result, reaffirm)


def ledger_allocate(
    ctx: typer.Context,
    transaction_id: str,
    business_pct: str,
    category_id: str | None = None,
    usage_ratio_id: str | None = None,
    prorrata_reference: str | None = None,
    actor: str | None = None,
) -> None:
    """Record business/private proportionality through the exact-profile worker."""
    parsed_business_pct = parse_required_decimal(business_pct, label="business-pct")
    validate_business_pct_range(parsed_business_pct)
    validated_category_id = validate_category_id(category_id)
    from .runtime_ledger_allocate import run_ledger_allocate

    projection = run_ledger_allocate(
        ctx,
        transaction_id=transaction_id,
        business_pct=parsed_business_pct,
        category_id=validated_category_id,
        usage_ratio_id=usage_ratio_id,
        prorrata_reference=prorrata_reference,
        actor=actor,
    )
    transaction = projection.transaction
    from ._ledger_payloads import LedgerAllocateResult

    result = LedgerAllocateResult.model_validate(
        {
            "bucket_id": str(projection.profile_id),
            "transaction_id": transaction.transaction_id,
            "bucket_event_ids": list(projection.bucket_event_ids),
            "review_status": projection.review_status.value,
            "transaction": transaction.model_dump(mode="json"),
        },
    )
    emit_envelope(
        ctx,
        command="ledger.allocate",
        result=result,
        lines=[
            f"{tr('cli.ledger.labels.id')}\t{transaction.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{projection.review_status.value}",
        ],
    )


def _link_refusal(reason: str | None) -> typer.BadParameter:
    """Map the closed worker refusal reason to its existing operator message."""
    if reason == "cross_bucket_invoice":
        return bad(tr("cli.ledger.link.errors.cross_bucket_invoice"))
    if reason == "missing_invoice":
        return bad(tr("cli.ledger.link.errors.invoice_not_found"))
    return invoice_link_error_bad_parameter()


def ledger_link(
    ctx: typer.Context,
    transaction_id: str,
    invoice_id: str,
    actor: str | None = None,
) -> None:
    """Bind a transaction to one reconciliation-catalogue invoice, atomically."""
    from .runtime_ledger_export_link import link_ledger_invoice_for_cli

    outcome = link_ledger_invoice_for_cli(
        ctx,
        transaction_id=transaction_id,
        invoice_id=invoice_id,
        actor=actor,
    )
    if outcome.outcome == "refused":
        raise _link_refusal(outcome.reason)
    projection = outcome.projection
    if projection is None:
        raise invoice_link_error_bad_parameter()

    payload: dict[str, object] = {
        "operation": "ledger.link",
        "bucket_id": projection.bucket_id,
        "transaction_id": projection.transaction_id,
        "invoice_id": projection.invoice_id,
        "actor": projection.actor,
    }
    lines = [
        "operation\tledger.link",
        f"bucket\t{projection.bucket_id}",
        f"transaction_id\t{projection.transaction_id}",
        f"actor\t{projection.actor}",
        f"invoice_id\t{projection.invoice_id}",
    ]
    from ._ledger_payloads import LedgerLinkResult

    emit_envelope(
        ctx,
        command="ledger.link",
        result=LedgerLinkResult.model_validate(payload),
        lines=lines,
    )


def _emit_single_classification(ctx: typer.Context, result: LedgerClassifyOperationResult, reaffirm: bool) -> None:
    """Refuse an incomplete result before emitting its settled classification."""
    if result.outcome == "validation_error":
        if result.validation_kind == "m210_incoming_only":
            raise bad(tr("cli.ledger.classify.m210_incoming_only"))
        if result.validation_kind == "m210_required_options":
            raise bad(tr("cli.ledger.classify.m210_required_options"))
        details = "; ".join(result.validation_messages)
        raise bad(
            tr(
                "cli.ledger.errors.command_input_invalid",
                details=details or tr("cli.ledger.errors.command_input_invalid_fallback"),
            ),
        )
    transaction = result.transaction
    review_status = result.review_status
    if transaction is None or review_status is None:
        from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    from ._ledger_payloads import LedgerClassifySingleResult, TransactionPayload

    transaction_payload = TransactionPayload.model_validate(transaction.model_dump(mode="json"))
    output_result = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": str(result.profile_id),
            "transaction_id": transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    emit_envelope(
        ctx,
        command="ledger.classify",
        result=output_result,
        lines=[
            *([tr("cli.ledger.classify.reaffirmed")] if reaffirm else []),
            f"{tr('cli.ledger.labels.id')}\t{transaction.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
        ],
    )


def _append_unmatched_sector_notice(
    result: LedgerAddOperationResult, notices: list[Notice], extra_lines: list[str]
) -> None:
    """Append the unmatched-sector advisory after the add and inert-input notices."""
    if result.advisory_sector_unmatched:
        sector_id = result.advisory_sector_id
        if sector_id is None:
            raise RuntimeError("ledger add unmatched-sector advisory omitted its sector")
        unmatched_message = tr("cli.ledger.add.sector_unmatched", sector_id=sector_id)
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.add.sector_unmatched",
                message=unmatched_message,
                context={"sector_id": sector_id},
            )
        )
        extra_lines.append(unmatched_message)
