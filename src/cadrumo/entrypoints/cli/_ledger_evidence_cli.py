"""Behavior handlers for ledger purchase invoice evidence commands."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import cast
from uuid import UUID

import typer
from pydantic import BaseModel, ValidationError

from ...adapters.outbound.llm.consent import (
    OffHostEvidenceReadOutcome,
    classify_off_host_evidence_read,
)
from ...application.ledger.evidence import PurchaseInvoiceEvidencePatch
from ...application.ledger.invoice_draft_payloads import EvidenceExtractResult
from ...application.ledger.invoice_draft_records import FieldProvenance, LabelReadingFallback
from ...application.ledger.invoice_evidence_operation import (
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    FindingResolutionInputV1,
    LedgerEvidenceConfirmProjection,
    LedgerEvidenceConfirmRequest,
    LedgerEvidenceExtractProjection,
    LedgerEvidenceExtractRequest,
)
from ...application.ledger.invoice_evidence_operation_dtos import (
    ConfirmedEstablishmentProjectionV1,
    InvoiceConfirmationProjectionV1,
    InvoiceDraftProjectionV1,
    LabelReadingFallbackProjectionV1,
)
from ...application.operations.public_scalar import PublicDecimal
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.aggregation import IntracomOperationType
from ...core.config_support import LLMProvider
from ...core.confirmation_gate import ConfirmationBlockReason
from ...core.i18n.render import tr
from ...core.iva_category_resolution import IvaCategoryOutcome
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaCategory
from ...domain.iva.supply_nature import SupplyNature
from ._date_parsing import _parse_iso_date, _parse_optional_iso_date_str
from ._decimal_parsing import parse_optional_decimal_amount
from ._evidence_field_notices import field_degradation_notices, label_reading_fallback_notices
from ._ledger_evidence_review_cli import parse_finding_resolution
from .common import active_bucket_id_or_refuse, bad, emit_envelope
from .errors import CliRefusedBoundaryError
from .ledger_business_payloads import (
    EvidenceAddResult,
    EvidenceConfirmResult,
    EvidenceRemoveResult,
    EvidenceUpdateResult,
)
from .runtime_ledger_evidence_add import run_ledger_evidence_add
from .runtime_ledger_evidence_followup import (
    run_ledger_evidence_attachment_queue,
    run_ledger_evidence_attachment_view,
)
from .runtime_ledger_evidence_mutation import run_ledger_evidence_remove, run_ledger_evidence_update
from .runtime_ledger_evidence_read import run_ledger_evidence_list, run_ledger_evidence_view
from .runtime_ledger_invoice_evidence import (
    submit_invoice_evidence_confirm,
    submit_invoice_evidence_extract,
)
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    submitted_operation_error,
)


def _attachment_review_lines(payload: dict[str, object]) -> list[str]:
    return [
        f"attachment_id\t{payload['attachment_id']}",
        f"sha256\t{payload['sha256']}",
        f"mime_type\t{payload['mime_type']}",
        f"bytes_size\t{payload['bytes_size']}",
        f"source\t{payload['source']}",
        f"provider_locator\t{payload['provider_locator']}",
        f"captured_at\t{payload['captured_at']}",
        f"pending_review\t{payload['pending_review']}",
        f"linked_invoice_ids\t{','.join(cast(Iterable[str], payload['linked_invoice_ids']))}",
    ]


def attachment_queue(ctx: typer.Context) -> None:
    """List Drive attachments that still require invoice review."""
    result = run_ledger_evidence_attachment_queue(ctx)
    payloads = [row.model_dump(mode="json") for row in result.rows]
    emit_envelope(
        ctx,
        command="ledger.evidence.attachment_queue",
        result=result,
        lines=[line for payload in payloads for line in _attachment_review_lines(payload)],
    )


def attachment_view(ctx: typer.Context, attachment_id: str) -> None:
    """Inspect non-secret metadata and provenance for one attachment."""
    result = run_ledger_evidence_attachment_view(ctx, attachment_id=attachment_id)
    payload = result.model_dump(mode="json")
    emit_envelope(
        ctx,
        command="ledger.evidence.attachment_view",
        result=result,
        lines=[f"bucket_id\t{result.bucket_id}", *_attachment_review_lines(payload)],
    )


def evidence_add(
    ctx: typer.Context,
    source_path: str,
    supplier: str | None = None,
    invoice_number: str | None = None,
    invoice_date: str | None = None,
    taxable_base: str | None = None,
    iva_rate: str | None = None,
    iva_amount: str | None = None,
    notes: str = "",
    idempotency_key: str | None = None,
) -> None:
    """Register a purchase invoice evidence record and return its id.

    Without ``--idempotency-key`` the verb is additive: the same file attached
    twice is two pieces of evidence, which is a real case. With one, a repeat of
    the same key resolves to the record it already made -- no second record, no
    second bucket event -- and a repeat carrying different content refuses.
    """
    # The same boundary refusal the import verbs raise for a missing --file; the
    # argument stays a string so the record echoes the path exactly as typed.
    if not Path(source_path).expanduser().is_file():
        raise bad(tr("cli.help.path_not_found", path=source_path))
    result = run_ledger_evidence_add(
        ctx,
        source_path=source_path,
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=_parse_optional_iso_date_str(invoice_date, label="invoice-date"),
        taxable_base=parse_optional_decimal_amount(taxable_base, label="taxable-base", signed=False),
        iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate", signed=False),
        iva_amount=parse_optional_decimal_amount(iva_amount, label="iva-amount", signed=False),
        notes=notes,
        idempotency_key=idempotency_key,
    )
    record_payload = dict(result.record.model_dump(mode="json"))
    payload = {**record_payload, "bucket_event_ids": list(result.bucket_event_ids)}
    lines = _evidence_text_lines_payload(record_payload)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    emit_envelope(ctx, command="ledger.evidence.add", result=EvidenceAddResult.model_validate(payload), lines=lines)


def evidence_view(ctx: typer.Context, evidence_id: str) -> None:
    """Show one purchase invoice evidence record by id."""
    result = run_ledger_evidence_view(ctx, evidence_id=evidence_id)
    payload = result.model_dump(mode="json")
    lines = [
        f"evidence_id\t{payload['evidence_id']}",
        f"bucket_id\t{payload['bucket_id']}",
        f"source_path\t{payload['source_path']}",
        f"source_sha256\t{payload['source_sha256']}",
        f"media_kind\t{payload['media_kind']}",
        f"supplier\t{payload.get('supplier') or '-'}",
        f"invoice_number\t{payload.get('invoice_number') or '-'}",
        f"invoice_date\t{payload.get('invoice_date') or '-'}",
        f"taxable_base\t{payload.get('taxable_base') or '-'}",
        f"iva_rate\t{payload.get('iva_rate') or '-'}",
        f"iva_amount\t{payload.get('iva_amount') or '-'}",
        f"notes\t{payload.get('notes') or '-'}",
        f"created_at\t{payload['created_at']}",
        f"updated_at\t{payload['updated_at']}",
    ]
    emit_envelope(
        ctx,
        command="ledger.evidence.view",
        result=result,
        lines=lines,
    )


def evidence_list(ctx: typer.Context) -> None:
    """List every purchase invoice evidence record in the active bucket."""
    result = run_ledger_evidence_list(ctx)
    lines = ["evidence_id\tmedia_kind\tsupplier\tinvoice_number\tinvoice_date\ttaxable_base\tnotes"]
    for record in result.rows:
        data = record.model_dump(mode="json")
        lines.append(
            f"{data['evidence_id']}\t{data['media_kind']}\t"
            f"{data.get('supplier') or '-'}\t{data.get('invoice_number') or '-'}\t"
            f"{data.get('invoice_date') or '-'}\t{data.get('taxable_base') or '-'}\t"
            f"{data.get('notes') or '-'}"
        )
    emit_envelope(ctx, command="ledger.evidence.list", result=result, lines=lines)


def evidence_update(
    ctx: typer.Context,
    evidence_id: str,
    supplier: str | None = None,
    invoice_number: str | None = None,
    invoice_date: str | None = None,
    taxable_base: str | None = None,
    iva_rate: str | None = None,
    iva_amount: str | None = None,
    notes: str | None = None,
) -> None:
    """Update mutable fields on one purchase invoice evidence record."""
    patch = PurchaseInvoiceEvidencePatch(
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=_parse_optional_iso_date_str(invoice_date, label="invoice-date"),
        taxable_base=parse_optional_decimal_amount(taxable_base, label="taxable-base"),
        iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
        iva_amount=parse_optional_decimal_amount(iva_amount, label="iva-amount"),
        notes=notes,
    )
    result = run_ledger_evidence_update(ctx, evidence_id=evidence_id, patch=patch)
    payload = dict(result.record.model_dump(mode="json"))
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _evidence_text_lines_payload(payload)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    emit_envelope(
        ctx, command="ledger.evidence.update", result=EvidenceUpdateResult.model_validate(payload), lines=lines
    )


def evidence_remove(ctx: typer.Context, evidence_id: str, yes: bool = False) -> None:
    """Delete one purchase invoice evidence record."""
    if not yes:
        raise bad(tr("cli.app.ledger.evidence.yes_required"))
    result = run_ledger_evidence_remove(ctx, evidence_id=evidence_id)
    payload = dict(result.record.model_dump(mode="json"))
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _evidence_text_lines_payload(payload)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    emit_envelope(
        ctx, command="ledger.evidence.remove", result=EvidenceRemoveResult.model_validate(payload), lines=lines
    )


#: The operator-facing wording for each refusal the shared classifier returns.
#: The rules are decided in :mod:`~llm.consent`; only the phrasing is CLI-owned.
_OFF_HOST_REFUSAL_LOCALE_KEYS: dict[OffHostEvidenceReadOutcome, str] = {
    OffHostEvidenceReadOutcome.ACKNOWLEDGEMENT_WITHOUT_PROVIDER: (
        "cli.app.ledger.evidence.extract_acknowledge_without_provider"
    ),
    OffHostEvidenceReadOutcome.PROVIDER_READS_ON_HOST: ("cli.app.ledger.evidence.extract_off_host_provider_is_local"),
    OffHostEvidenceReadOutcome.PROVIDER_WITHOUT_ACKNOWLEDGEMENT: (
        "cli.app.ledger.evidence.extract_provider_without_acknowledge"
    ),
}


def _validate_extract_consent_options(
    *,
    evidence_id: str | None,
    off_host_provider: LLMProvider | None,
    acknowledged: bool,
) -> None:
    """Translate malformed per-invocation consent flags before submission.

    Whether the two flags constitute a well-formed off-host request is decided
    by :func:`~llm.consent.classify_off_host_evidence_read`; the registered
    worker owns profile eligibility, content binding and token minting.

    Raises:
        typer.BadParameter: When the flags are supplied incompletely, when the
            provider names the on-host default, or when an off-host read has no
            persisted evidence reference to bind to.
    """
    outcome = classify_off_host_evidence_read(provider=off_host_provider, acknowledged=acknowledged)
    if outcome is OffHostEvidenceReadOutcome.ON_HOST_DEFAULT:
        return
    refusal_key = _OFF_HOST_REFUSAL_LOCALE_KEYS.get(outcome)
    if refusal_key is not None:
        raise bad(tr(refusal_key))
    # Only the one consented outcome may reach the request constructor below. The
    # wording table above covers the refusals that exist today, so reaching
    # here with anything else means an outcome was added to the classifier and
    # not given a sentence. A consent request without a classified outcome must
    # fail closed.
    if outcome is not OffHostEvidenceReadOutcome.OFF_HOST_CONSENTED:
        raise bad(tr("cli.app.ledger.evidence.extract_off_host_unclassified", outcome=outcome.value))

    if evidence_id is None:
        raise bad(tr("cli.app.ledger.evidence.extract_off_host_needs_evidence_id"))


def _require_exact_evidence_reference(evidence_id: str | None, attachment_id: str | None) -> None:
    """Require exactly one secure evidence reference for a read or confirm."""
    if (evidence_id is None) == (attachment_id is None):
        raise bad(tr("cli.app.ledger.evidence.extract_reference_required"))


def _display_optional(value: object) -> object:
    """Render an absent scalar with the extract surface's established marker."""
    return value if value is not None else "-"


def _display_text(value: str | None) -> str:
    """Render an absent text field with the extract surface's established marker."""
    return value or "-"


def _display_suggested_kind(draft: InvoiceDraftProjectionV1) -> str:
    """Render the optional application-derived invoice kind."""
    return "-" if draft.suggested_kind is None else draft.suggested_kind.value


def _decimal_text(value: PublicDecimal | None) -> str | None:
    """Render a tagged decimal as its exact public scalar spelling."""
    return None if value is None else value.decimal


def _decimal_rows(
    rows: tuple[BaseModel, ...],
    *,
    decimal_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    """Flatten tagged decimal values in one already-typed DTO sequence."""
    payloads: list[dict[str, object]] = []
    for row in rows:
        payload = row.model_dump(mode="json")
        for field in decimal_fields:
            payload[field] = _decimal_text(getattr(row, field))
        payloads.append(payload)
    return payloads


def _draft_payload(draft: InvoiceDraftProjectionV1) -> dict[str, object]:
    """Render every application draft fact into the established CLI scalar shape."""
    payload = cast(dict[str, object], draft.model_dump(mode="json"))
    for field in (
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "grand_total",
        "recargo_amount",
        "retencion_rate",
        "retencion_amount",
        "suplidos_amount",
    ):
        payload[field] = _decimal_text(getattr(draft, field))
    payload["lines"] = _decimal_rows(
        draft.lines,
        decimal_fields=(
            "quantity",
            "unit_price",
            "taxable_base",
            "iva_rate",
            "iva_amount",
            "recargo_rate",
            "recargo_amount",
        ),
    )
    payload["iva_breakdown"] = _decimal_rows(
        draft.iva_breakdown,
        decimal_fields=("iva_rate", "taxable_base", "iva_amount", "recargo_rate", "recargo_amount"),
    )
    discrepancies: list[dict[str, object]] = []
    for finding in draft.discrepancies:
        payload_row = finding.model_dump(mode="json")
        payload_row["expected"] = _decimal_text(finding.expected)
        payload_row["observed"] = _decimal_text(finding.observed)
        discrepancies.append(payload_row)
    payload["discrepancies"] = discrepancies
    return payload


def _evidence_extract_payload(
    *,
    bucket_id: str,
    projection: LedgerEvidenceExtractProjection,
) -> dict[str, object]:
    """Project the full operation DTO, its exact digests and consent effect."""
    return {
        "bucket_id": bucket_id,
        "evidence_id": projection.evidence_id,
        "attachment_id": projection.attachment_id,
        "source_sha256": projection.source_sha256,
        "draft_review_sha256": projection.draft_review_sha256,
        "consent_audit_effect": projection.consent_audit_effect,
        **_draft_payload(projection.draft),
        "off_host_provider": projection.off_host_provider,
        "off_host_acknowledged_surface": (
            f"runtime:{LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID}"
            if projection.off_host_provider is not None
            else None
        ),
    }


def _evidence_extract_lines(
    bucket_id: str,
    projection: LedgerEvidenceExtractProjection,
) -> list[str]:
    """Render the stable tabular projection of one extracted draft."""
    draft = projection.draft
    return [
        f"bucket_id\t{bucket_id}",
        f"evidence_id\t{_display_text(projection.evidence_id)}",
        f"attachment_id\t{_display_text(projection.attachment_id)}",
        f"source_sha256\t{projection.source_sha256}",
        f"draft_review_sha256\t{projection.draft_review_sha256}",
        f"consent_audit_effect\t{projection.consent_audit_effect.value}",
        f"supplier_tax_id\t{_display_text(draft.supplier_tax_id)}",
        f"supplier_name\t{_display_text(draft.supplier_name)}",
        f"customer_tax_id\t{_display_text(draft.customer_tax_id)}",
        f"customer_name\t{_display_text(draft.customer_name)}",
        f"invoice_number\t{_display_text(draft.invoice_number)}",
        f"invoice_series\t{_display_text(draft.invoice_series)}",
        f"invoice_date\t{_display_text(draft.invoice_date)}",
        f"taxable_base\t{_display_optional(_decimal_text(draft.taxable_base))}",
        f"iva_rate\t{_display_optional(_decimal_text(draft.iva_rate))}",
        f"iva_amount\t{_display_optional(_decimal_text(draft.iva_amount))}",
        f"grand_total\t{_display_optional(_decimal_text(draft.grand_total))}",
        f"currency\t{_display_optional(draft.currency)}",
        f"retencion_rate\t{_display_optional(_decimal_text(draft.retencion_rate))}",
        f"retencion_amount\t{_display_optional(_decimal_text(draft.retencion_amount))}",
        f"suplidos_amount\t{_display_optional(_decimal_text(draft.suplidos_amount))}",
        f"suggested_kind\t{_display_suggested_kind(draft)}",
        f"transcription_sha256\t{_display_text(draft.transcription_sha256)}",
        f"provenance_fields\t{len(draft.provenance)}",
        f"discrepancies\t{len(draft.discrepancies)}",
        f"raw_text_length\t{draft.raw_text_length}",
    ]


def _domain_provenance(draft: InvoiceDraftProjectionV1) -> tuple[FieldProvenance, ...]:
    """Restore the validated provenance records for the existing notice projector."""
    return tuple(FieldProvenance.model_validate(row.model_dump(mode="python")) for row in draft.provenance)


def _domain_fallback(fallback: LabelReadingFallbackProjectionV1 | None) -> LabelReadingFallback | None:
    """Restore the canonical label-reading fallback for its notice projector."""
    return None if fallback is None else fallback.to_fallback()


def _evidence_extract_notices(reference: str, projection: LedgerEvidenceExtractProjection) -> list[Notice]:
    """Project review, field-degradation and label-reading notices for one extracted draft."""
    notices: list[Notice] = [
        Notice(
            severity=NoticeSeverity.INFO,
            code="ledger.evidence.extract.review_hint",
            message=tr("cli.app.ledger.evidence.extract_review_hint_message"),
            context={"reference": reference},
        ),
    ]
    notices.extend(field_degradation_notices(_domain_provenance(projection.draft)))
    notices.extend(label_reading_fallback_notices(_domain_fallback(projection.label_reading_fallback)))
    return notices


def evidence_extract(
    ctx: typer.Context,
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    off_host_provider: LLMProvider | None = None,
    acknowledge_off_host: bool = False,
) -> None:
    """Submit one evidence extraction and print its source-bound review digests."""
    _require_exact_evidence_reference(evidence_id, attachment_id)
    _validate_extract_consent_options(
        evidence_id=evidence_id,
        off_host_provider=off_host_provider,
        acknowledged=acknowledge_off_host,
    )
    bucket_id = active_bucket_id_or_refuse()
    profile_id = UUID(bucket_id)
    request = LedgerEvidenceExtractRequest(
        profile_id=profile_id,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        off_host_provider=off_host_provider,
        acknowledge_off_host=acknowledge_off_host,
    )
    completed = submit_invoice_evidence_extract(ctx, request)
    projection = completed.projection

    def render() -> None:
        reference = projection.evidence_id or projection.attachment_id or ""
        emit_envelope(
            ctx,
            command="ledger.evidence.extract",
            result=EvidenceExtractResult.model_validate_json(
                json.dumps(_evidence_extract_payload(bucket_id=bucket_id, projection=projection)),
            ),
            lines=_evidence_extract_lines(bucket_id, projection),
            notices=_evidence_extract_notices(reference, projection),
        )

    _present_registered_evidence_operation(completed, render)


def _present_registered_evidence_operation[ProjectionT: BaseModel](
    completed: RegisteredOperationCompletion[ProjectionT],
    render: Callable[[], None],
) -> None:
    """Keep the submitted operation receipt if local result presentation fails."""
    try:
        render()
    except typer.Exit:
        raise
    except Exception as exc:
        code = (
            RuntimeRefusalCode.INVALID_FRAME.value
            if isinstance(exc, (CliRefusedBoundaryError, ValidationError))
            else RuntimeRefusalCode.UNAVAILABLE.value
        )
        raise submitted_operation_error(
            completed.operation_id,
            code,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def _decimal_request_text(value: str | None, *, label: str) -> str | None:
    """Parse one optional CLI amount and preserve its canonical decimal spelling."""
    parsed = parse_optional_decimal_amount(value, label=label)
    return None if parsed is None else str(parsed)


def evidence_confirm(
    ctx: typer.Context,
    *,
    kind: InvoiceKind,
    expected_source_sha256: str,
    expected_draft_review_sha256: str,
    country_code: str,
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    counterparty_nif: str | None = None,
    counterparty_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: str | None = None,
    taxable_base: str | None = None,
    iva_rate: str | None = None,
    iva_amount: str | None = None,
    iva_category: IvaCategory | None = None,
    currency: str | None = None,
    operation_type: IntracomOperationType | None = None,
    operation_date: str | None = None,
    retention_rate: str | None = None,
    retention_amount: str | None = None,
    recargo_amount: str | None = None,
    supply_nature: SupplyNature | None = None,
    invoice_class: str | None = None,
    rectifies: str | None = None,
    series: str | None = None,
    notes: str = "",
    resolve: tuple[str, ...] = (),
) -> None:
    """Confirm the exact source and draft the operator reviewed during extract."""
    _require_exact_evidence_reference(evidence_id, attachment_id)
    bucket_id = active_bucket_id_or_refuse()
    profile_id = UUID(bucket_id)
    parsed_resolutions = tuple(parse_finding_resolution(raw) for raw in resolve)
    resolutions = tuple(
        FindingResolutionInputV1(
            blocker_id=resolution.blocker_id,
            action=resolution.action,
            value=resolution.value,
            note=resolution.note,
        )
        for resolution in parsed_resolutions
    )
    request = LedgerEvidenceConfirmRequest(
        profile_id=profile_id,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        expected_source_sha256=expected_source_sha256,
        expected_draft_review_sha256=expected_draft_review_sha256,
        kind=kind,
        counterparty_country=country_code,
        counterparty_tax_id=counterparty_nif,
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        invoice_date=_parse_iso_date(invoice_date, label="invoice-date") if invoice_date else None,
        taxable_base=_decimal_request_text(taxable_base, label="taxable-base"),
        iva_rate=_decimal_request_text(iva_rate, label="iva-rate"),
        iva_amount=_decimal_request_text(iva_amount, label="iva-amount"),
        currency=currency,
        iva_category=iva_category.value if iva_category is not None else None,
        operation_type=operation_type,
        operation_date=_parse_iso_date(operation_date, label="operation-date") if operation_date else None,
        retention_rate=_decimal_request_text(retention_rate, label="retention-rate"),
        retention_amount=_decimal_request_text(retention_amount, label="retention-amount"),
        recargo_amount=_decimal_request_text(recargo_amount, label="recargo-amount"),
        invoice_class=invoice_class,
        supply_nature=supply_nature,
        series=series,
        rectifies_invoice_number=rectifies,
        notes=notes,
        resolutions=resolutions,
    )
    completed = submit_invoice_evidence_confirm(ctx, request)
    projection = completed.projection

    def render() -> None:
        confirmation = projection.confirmation
        emit_envelope(
            ctx,
            command="ledger.evidence.confirm",
            result=EvidenceConfirmResult.model_validate(
                _evidence_confirm_payload(
                    bucket_id=bucket_id,
                    projection=projection,
                ),
            ),
            lines=_evidence_confirm_lines(bucket_id, projection),
            notices=_evidence_confirm_notices(confirmation),
        )

    _present_registered_evidence_operation(completed, render)


def _evidence_confirm_payload(
    *,
    bucket_id: str,
    projection: LedgerEvidenceConfirmProjection,
) -> dict[str, object]:
    """Project the canonical invoice snapshot and the exact reviewed digests."""
    confirmation = projection.confirmation
    invoice = confirmation.invoice
    establishment = confirmation.establishment
    category = None if establishment is None else establishment.category
    return {
        "bucket_id": bucket_id,
        "evidence_id": projection.evidence_id,
        "attachment_id": projection.attachment_id,
        "source_sha256": projection.source_sha256,
        "reviewed_draft_sha256": projection.reviewed_draft_sha256,
        "created": confirmation.created,
        "invoice_id": invoice.invoice_id,
        "kind": invoice.kind.value,
        "invoice_number": invoice.invoice_number,
        "issued_at": invoice.issued_at.isoformat(),
        "counterparty_name": invoice.counterparty_name,
        "counterparty_tax_id": invoice.counterparty_tax_id,
        "counterparty_country": invoice.counterparty_country,
        "base_total": invoice.base_total.decimal,
        "iva_total": invoice.iva_total.decimal,
        "grand_total": invoice.grand_total.decimal,
        "currency": invoice.currency,
        "payment_status": invoice.payment_status.value,
        "linked_transaction_ids": list(invoice.linked_transaction_ids),
        "notes": invoice.notes,
        "retention_rate": _decimal_text(invoice.retention_rate),
        "retention_amount": _decimal_text(invoice.retention_amount),
        "recargo_amount": _decimal_text(invoice.recargo_amount),
        "fx_rate": _decimal_text(invoice.fx_rate),
        "fx_rate_date": invoice.fx_rate_date.isoformat() if invoice.fx_rate_date is not None else None,
        "fx_rate_source": invoice.fx_rate_source,
        "base_total_eur": _decimal_text(invoice.base_total_eur),
        "iva_total_eur": _decimal_text(invoice.iva_total_eur),
        "grand_total_eur": _decimal_text(invoice.grand_total_eur),
        "provenance": [row.model_dump(mode="json") for row in confirmation.draft.provenance],
        "discrepancies": _decimal_rows(
            confirmation.draft.discrepancies,
            decimal_fields=("expected", "observed"),
        ),
        "confirmed_provenance": [row.model_dump(mode="json") for row in confirmation.confirmed_provenance],
        "confirmation_id": confirmation.confirmation_id,
        "iva_category": None if category is None else category.category,
        "iva_category_outcome": None if category is None else category.outcome.value,
    }


def _confirm_resolution_lines(establishment: ConfirmedEstablishmentProjectionV1 | None) -> list[str]:
    """Render the category result and every retained review item."""
    if establishment is None:
        return []
    category = establishment.category
    lines = [
        f"iva_category\t{category.category or '-'}\t{category.outcome.value}",
    ]
    lines.extend(
        f"review_item\t{item.reason.value}\t{item.field or '-'}\t{item.detail}" for item in establishment.review_items
    )
    return lines


def _evidence_confirm_lines(
    bucket_id: str,
    projection: LedgerEvidenceConfirmProjection,
) -> list[str]:
    """Render the stable tabular projection of one confirmed invoice."""
    confirmation = projection.confirmation
    invoice = confirmation.invoice
    return [
        f"bucket_id\t{bucket_id}",
        f"evidence_id\t{projection.evidence_id or '-'}",
        f"attachment_id\t{projection.attachment_id or '-'}",
        f"source_sha256\t{projection.source_sha256}",
        f"reviewed_draft_sha256\t{projection.reviewed_draft_sha256}",
        f"created\t{confirmation.created}",
        f"invoice_id\t{invoice.invoice_id}",
        f"kind\t{invoice.kind.value}",
        f"counterparty_name\t{invoice.counterparty_name}",
        f"counterparty_tax_id\t{invoice.counterparty_tax_id or '-'}",
        f"invoice_number\t{invoice.invoice_number}",
        f"issued_at\t{invoice.issued_at.isoformat()}",
        f"grand_total\t{invoice.grand_total.decimal}",
        f"currency\t{invoice.currency}",
        *_confirm_resolution_lines(confirmation.establishment),
    ]


def _resolution_notices(
    establishment: ConfirmedEstablishmentProjectionV1 | None,
) -> list[Notice]:
    """Keep the existing IVA category and establishment review notices."""
    if establishment is None:
        return []
    result = establishment.category
    severity = NoticeSeverity.INFO if result.category is not None else NoticeSeverity.WARNING
    outcome = result.outcome
    if outcome is IvaCategoryOutcome.RATE_INFERRED:
        code = "ledger.evidence.confirm.category_rate_inferred"
        message = tr("cli.app.ledger.evidence.confirm_category_rate_inferred_message")
    elif outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF:
        code = "ledger.evidence.confirm.category_unsupported_relief"
        message = tr("cli.app.ledger.evidence.confirm_category_unsupported_relief_message")
    elif outcome is IvaCategoryOutcome.CONTRADICTED:
        code = "ledger.evidence.confirm.category_contradicted"
        message = tr("cli.app.ledger.evidence.confirm_category_contradicted_message")
    elif outcome is IvaCategoryOutcome.UNRESOLVED:
        code = "ledger.evidence.confirm.category_unresolved"
        message = tr("cli.app.ledger.evidence.confirm_category_unresolved_message")
    else:
        code = None
        message = None
    notices: list[Notice] = []
    if code is not None and message is not None:
        context = {"outcome": outcome.value}
        if result.category is not None:
            context["iva_category"] = result.category
        if result.declared is not None:
            context["declared_category"] = result.declared.value
        if result.note:
            context["note"] = result.note
        notices.append(Notice(severity=severity, code=code, message=message, context=context))
    for item in establishment.review_items:
        if item.reason is ConfirmationBlockReason.CONTRADICTED_REGIME:
            code = "ledger.evidence.confirm.review_contradicted_regime"
            message = tr("cli.app.ledger.evidence.confirm_review_contradicted_regime_message")
        elif item.reason is ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT:
            code = "ledger.evidence.confirm.review_undetermined_establishment"
            message = tr("cli.app.ledger.evidence.confirm_review_undetermined_establishment_message")
        else:
            raise KeyError(item.reason)
        notices.append(
            Notice(
                severity=severity,
                code=code,
                message=message,
                context={
                    "finding_id": item.blocker_id,
                    "reason": item.reason.value,
                    "field": item.field or "",
                    "detail": item.detail,
                },
            ),
        )
    return notices


def _evidence_confirm_notices(result: InvoiceConfirmationProjectionV1) -> list[Notice]:
    """Project discrepancy, idempotency, draft and IVA-resolution notices."""
    notices: list[Notice] = []
    if result.total_discrepancy is not None:
        discrepancy = result.total_discrepancy
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.evidence.confirm.printed_total_mismatch",
                message=tr("cli.app.ledger.evidence.confirm_printed_total_mismatch_message"),
                context={
                    "printed_total": discrepancy.printed_total.decimal,
                    "recorded_total": discrepancy.recorded_total.decimal,
                    "difference": discrepancy.difference.decimal,
                    "currency": result.invoice.currency,
                },
            ),
        )
    if not result.created:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.evidence.confirm.already_exists",
                message=tr("cli.app.ledger.evidence.confirm_already_exists_message"),
                context={"invoice_id": result.invoice.invoice_id},
            ),
        )
    else:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.evidence.confirm.linked_transaction_hint",
                message=tr("cli.app.ledger.evidence.confirm_link_hint_message"),
                context={"invoice_id": result.invoice.invoice_id},
            ),
        )
    # The confirm surface describes the same re-read draft, so the operator
    # sees why a field they are about to accept was not corroborated.
    notices.extend(field_degradation_notices(_domain_provenance(result.draft)))
    notices.extend(label_reading_fallback_notices(_domain_fallback(result.label_reading_fallback)))
    notices.extend(_resolution_notices(result.establishment))
    return notices


def _evidence_text_lines_payload(payload: dict[str, object]) -> list[str]:
    """Render the established tab-separated evidence record presentation."""
    return [
        f"evidence_id\t{payload['evidence_id']}",
        f"bucket_id\t{payload['bucket_id']}",
        f"source_path\t{payload['source_path']}",
        f"source_sha256\t{payload['source_sha256']}",
        f"media_kind\t{payload['media_kind']}",
        f"supplier\t{payload.get('supplier') or '-'}",
        f"invoice_number\t{payload.get('invoice_number') or '-'}",
        f"invoice_date\t{payload.get('invoice_date') or '-'}",
        f"taxable_base\t{payload.get('taxable_base') or '-'}",
        f"iva_rate\t{payload.get('iva_rate') or '-'}",
        f"iva_amount\t{payload.get('iva_amount') or '-'}",
        f"notes\t{payload.get('notes') or '-'}",
        f"created_at\t{payload['created_at']}",
        f"updated_at\t{payload['updated_at']}",
    ]


__all__ = [
    "attachment_queue",
    "attachment_view",
    "evidence_add",
    "evidence_confirm",
    "evidence_extract",
    "evidence_list",
    "evidence_remove",
    "evidence_update",
    "evidence_view",
]
