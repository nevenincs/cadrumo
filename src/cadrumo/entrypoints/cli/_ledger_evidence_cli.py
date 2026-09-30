"""Behavior handlers for ledger purchase invoice evidence commands."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Never, Protocol, cast
from uuid import UUID

import typer

from ...adapters.outbound.llm.consent import (
    OffHostEvidenceReadOutcome,
    classify_off_host_evidence_read,
)
from ...application.ledger.attachment_review import get_attachment_review_item, list_attachment_review_queue
from ...application.ledger.confirmation_gate import FindingResolutionAction
from ...application.ledger.evidence import PurchaseInvoiceEvidencePatch
from ...application.ledger.invoice_draft_payloads import EvidenceExtractResult
from ...application.ledger.invoice_draft_records import FieldProvenance
from ...application.ledger.invoice_evidence_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
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
)
from ...application.operations.public_scalar import PublicDecimal
from ...core.aggregation import IntracomOperationType
from ...core.config import load_settings
from ...core.config_support import LLMProvider
from ...core.confirmation_gate import ConfirmationBlockReason
from ...core.field_grounding import FieldGroundingOutcome
from ...core.i18n.render import tr
from ...core.iva_category_resolution import IvaCategoryOutcome
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaCategory
from ...domain.iva.supply_nature import SupplyNature
from ._date_parsing import _parse_iso_date, _parse_optional_iso_date_str
from ._decimal_parsing import parse_decimal_amount, parse_optional_decimal_amount
from ._evidence_field_notices import field_degradation_notices
from ._ledger_evidence_review_cli import parse_finding_resolution
from .common import bad, current_workflow_state, emit_envelope, transaction_catalogue_repo
from .ledger_business_payloads import (
    AttachmentReviewQueueResult,
    AttachmentReviewViewResult,
    EvidenceAddResult,
    EvidenceConfirmResult,
    EvidenceRemoveResult,
    EvidenceUpdateResult,
)
from .runtime_ledger_evidence_add import run_ledger_evidence_add
from .runtime_ledger_evidence_mutation import run_ledger_evidence_remove, run_ledger_evidence_update
from .runtime_ledger_evidence_read import run_ledger_evidence_list, run_ledger_evidence_view
from .runtime_ledger_invoice_evidence import (
    submit_invoice_evidence_confirm,
    submit_invoice_evidence_extract,
)


def _attachment_store(bucket_id: str):
    """Build the active bucket's encrypted attachment repository."""
    from ...adapters.persistence.storage.attachment import AttachmentStore
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    return AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, load_settings()))


class _JsonModel(Protocol):
    def model_dump(self, *, mode: str) -> dict[str, object]: ...


def _attachment_review_payload(item: _JsonModel) -> dict[str, object]:
    return item.model_dump(mode="json")


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
    bucket_id = transaction_catalogue_repo(current_workflow_state()).bucket_id
    rows = list_attachment_review_queue(_attachment_store(bucket_id))
    payloads = [_attachment_review_payload(row) for row in rows]
    emit_envelope(
        ctx,
        command="ledger.evidence.attachment_queue",
        result=AttachmentReviewQueueResult.model_validate(
            {"bucket_id": bucket_id, "count": len(payloads), "rows": payloads}
        ),
        lines=[line for payload in payloads for line in _attachment_review_lines(payload)],
    )


def attachment_view(ctx: typer.Context, attachment_id: str) -> None:
    """Inspect non-secret metadata and provenance for one attachment."""
    bucket_id = transaction_catalogue_repo(current_workflow_state()).bucket_id
    item = get_attachment_review_item(_attachment_store(bucket_id), attachment_id)
    payload = {"bucket_id": bucket_id, **_attachment_review_payload(item)}
    emit_envelope(
        ctx,
        command="ledger.evidence.attachment_view",
        result=AttachmentReviewViewResult.model_validate(payload),
        lines=[f"bucket_id\t{bucket_id}", *_attachment_review_lines(payload)],
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
    payload = {str(key): value for key, value in draft.model_dump(mode="json").items()}
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
        decimal_fields=("quantity", "unit_price", "taxable_base", "iva_rate", "iva_amount", "recargo_rate", "recargo_amount"),
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


def _evidence_extract_notices(reference: str, draft: InvoiceDraftProjectionV1) -> list[Notice]:
    """Project review and field-degradation notices for one extracted draft."""
    notices: list[Notice] = [
        Notice(
            severity=NoticeSeverity.INFO,
            code="ledger.evidence.extract.review_hint",
            message=tr("cli.app.ledger.evidence.extract_review_hint_message"),
            context={"reference": reference},
        ),
    ]
    notices.extend(field_degradation_notices(_domain_provenance(draft)))
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
    transaction_repository = transaction_catalogue_repo(current_workflow_state())
    profile_id = UUID(transaction_repository.bucket_id)
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
            result=EvidenceExtractResult.model_validate(
                _evidence_extract_payload(bucket_id=transaction_repository.bucket_id, projection=projection),
            ),
            lines=_evidence_extract_lines(transaction_repository.bucket_id, projection),
            notices=_evidence_extract_notices(reference, projection.draft),
        )

    _present_registered_evidence_operation(completed, render)


def evidence_confirm(
    ctx: typer.Context,
    *,
    kind: InvoiceKind,
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    counterparty_nif: str | None = None,
    counterparty_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: str | None = None,
    taxable_base: str | None = None,
    iva_rate: str | None = None,
    country_code: str,
    currency: str | None = None,
    operation_type: IntracomOperationType | None = None,
    supply_nature: SupplyNature | None = None,
    invoice_class: str | None = None,
    rectifies: str | None = None,
    series: str | None = None,
    notes: str = "",
    resolve: tuple[str, ...] = (),
) -> None:
    """Non-interactively confirm a reviewed evidence extraction into an Invoice.

    Re-runs the on-host extraction (never a cloud call, never a temp
    file), layers any supplied override on top of each extracted field,
    and delegates the write to the sole sanctioned catalogue-invoice
    writer. A confirm whose resolved fields match an already-persisted
    invoice is a guarded no-op: the existing invoice is returned
    unchanged (``created: false``) rather than raising or duplicating.
    """
    _run_evidence_confirm(
        ctx=ctx,
        kind=kind,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        counterparty_nif=counterparty_nif,
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        country_code=country_code,
        currency=currency,
        operation_type=operation_type,
        supply_nature=supply_nature,
        invoice_class=invoice_class,
        rectifies=rectifies,
        series=series,
        notes=notes,
        resolve=list(resolve),
    )


def _evidence_confirm_payload(
    *,
    bucket_id: str,
    evidence_id: str | None,
    attachment_id: str | None,
    result: InvoiceConfirmationResult,
) -> dict[str, object]:
    """Project the confirmed invoice and both draft/provenance views."""
    invoice = result.invoice
    return {
        "bucket_id": bucket_id,
        "evidence_id": evidence_id,
        "attachment_id": attachment_id,
        "created": result.created,
        **catalogue_invoice_shared_fields(invoice),
        # Read off the draft the confirmation was based on, so the how-was-this-
        # obtained record reaches the operator on the confirm surface too and not
        # only on extract. `result.draft` is the pre-override extraction, which is
        # exactly the thing the provenance describes.
        "provenance": [envelope.model_dump(mode="json") for envelope in result.draft.provenance],
        "discrepancies": [finding.model_dump(mode="json") for finding in result.draft.discrepancies],
        # The confirmed view, beside the document's own. An operator-asserted
        # field reads OPERATOR here while `provenance` still shows what the
        # document said, which is the pairing the confirmation record persists.
        "confirmed_provenance": [envelope.model_dump(mode="json") for envelope in result.confirmed_provenance],
        "confirmation_id": result.confirmation_id,
        # Which IVA treatment this record got and which rung established it.
        # Result data rather than a diagnostic: a consumer enumerating the
        # weakly-placed records is asking about what was written, and before
        # this it could only find them by re-running the resolution.
        "iva_category": _resolved_category(result),
        "iva_category_outcome": _resolved_outcome(result),
    }


def _evidence_confirm_lines(
    bucket_id: str,
    result: InvoiceConfirmationResult,
    evidence_id: str | None,
    attachment_id: str | None,
) -> list[str]:
    """Render the stable tabular projection of one confirmed invoice."""
    invoice = result.invoice
    return [
        f"bucket_id\t{bucket_id}",
        f"evidence_id\t{evidence_id or '-'}",
        f"attachment_id\t{attachment_id or '-'}",
        f"created\t{result.created}",
        f"invoice_id\t{invoice.invoice_id}",
        f"kind\t{invoice.kind.value}",
        f"counterparty_name\t{invoice.counterparty_name}",
        f"counterparty_tax_id\t{invoice.counterparty_tax_id}",
        f"invoice_number\t{invoice.invoice_number}",
        f"issued_at\t{invoice.issued_at.isoformat()}",
        f"grand_total\t{format(invoice.grand_total, 'f')}",
        f"currency\t{invoice.currency}",
        *confirm_resolution_lines(result.establishment),
    ]


def _evidence_confirm_notices(result: InvoiceConfirmationResult) -> list[Notice]:
    """Project discrepancy, idempotency, and field-resolution notices."""
    notices: list[Notice] = []
    if result.total_discrepancy is not None:
        # The derived total stands; this only reports that the document disagrees
        # with it. A recargo de equivalencia, an unread rate that fell back to the
        # EXEMPT slot, or a misread base all surface here as a figure the record
        # could not represent -- silently dropping the printed total is what let
        # those through.
        discrepancy = result.total_discrepancy
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.evidence.confirm.printed_total_mismatch",
                message=tr(
                    "cli.app.ledger.evidence.confirm_printed_total_mismatch_message",
                ),
                context={
                    "printed_total": format(discrepancy.printed_total, "f"),
                    "recorded_total": format(discrepancy.recorded_total, "f"),
                    "difference": format(discrepancy.difference, "f"),
                    "currency": result.invoice.currency,
                },
            ),
        )
    if not result.created:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.evidence.confirm.already_exists",
                message=tr(
                    "cli.app.ledger.evidence.confirm_already_exists_message",
                ),
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
    # The confirm surface describes the SAME pre-override draft, so the operator
    # sees why a field they are about to accept was not corroborated.
    notices.extend(field_degradation_notices(result.draft.provenance))
    # What the confirm path resolved about the operation's IVA treatment and
    # what it left open. Every one of these was computed on this call and read
    # by nobody before this line.
    notices.extend(confirm_resolution_notices(result.establishment))
    return notices


def _run_evidence_confirm(
    *,
    ctx: typer.Context,
    kind: InvoiceKind,
    evidence_id: str | None,
    attachment_id: str | None,
    counterparty_nif: str | None,
    counterparty_name: str | None,
    invoice_number: str | None,
    invoice_date: str | None,
    taxable_base: str | None,
    iva_rate: str | None,
    country_code: str,
    currency: str | None,
    operation_type: IntracomOperationType | None,
    supply_nature: SupplyNature | None,
    invoice_class: str | None,
    rectifies: str | None,
    series: str | None,
    notes: str,
    resolve: list[str],
) -> None:
    _require_exact_evidence_reference(evidence_id, attachment_id)
    transaction_repository = transaction_catalogue_repo(current_workflow_state())
    bucket_id = transaction_repository.bucket_id
    evidence_ports = ledger_evidence_ports_factory(ctx)(bucket_id=bucket_id)
    catalogue_ports = catalogue_creation_ports_factory(ctx)(bucket_id=bucket_id)
    invoice_confirmation_ports = invoice_confirmation_ports_factory(ctx)(bucket_id=bucket_id)
    counterparty_establishment_repository = counterparty_establishment_repository_factory(ctx)(
        bucket_id=bucket_id,
    )
    resolutions: list[FindingResolution] = [parse_finding_resolution(raw) for raw in resolve]
    try:
        with bundled_indexed_authority().operation() as operation:
            period = default_invoice_extraction_period()
            legends = resolve_regime_legends(operation=operation, effective_date=period.end_date)
            result = confirm_invoice_draft_from_evidence(
                bucket_id=bucket_id,
                kind=kind,
                counterparty_country=country_code,
                evidence_id=evidence_id,
                attachment_id=attachment_id,
                counterparty_tax_id=counterparty_nif,
                counterparty_name=counterparty_name,
                invoice_number=invoice_number,
                invoice_date=_parse_iso_date(invoice_date, label="invoice-date") if invoice_date else None,
                taxable_base=parse_decimal_amount(taxable_base, label="taxable-base") if taxable_base else None,
                iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
                currency=currency,
                operation_type=operation_type,
                supply_nature=supply_nature,
                # Leave an omitted class omitted so document-derived defaults survive.
                **_invoice_class_kwarg(invoice_class, effective_date=period.end_date),
                rectifies_invoice_number=rectifies,
                series=series,
                notes=notes,
                resolutions=resolutions,
                catalogue_creation_ports=catalogue_ports,
                invoice_confirmation_ports=invoice_confirmation_ports,
                counterparty_establishment_repository=counterparty_establishment_repository,
                evidence_ports=evidence_ports,
                extraction_ports=invoice_draft_extraction_ports(evidence_ports=evidence_ports),
                operation=operation,
                legends=legends,
            )
    except (InvoiceValidationError, ValidationError) as exc:
        if (refusal := ledger_invoice_validation_no_recovery(exc)) is not None:
            raise refusal from None
        raise
    emit_envelope(
        ctx,
        command="ledger.evidence.confirm",
        result=EvidenceConfirmResult.model_validate(
            _evidence_confirm_payload(
                bucket_id=bucket_id,
                evidence_id=evidence_id,
                attachment_id=attachment_id,
                result=result,
            ),
        ),
        lines=_evidence_confirm_lines(bucket_id, result, evidence_id, attachment_id),
        notices=_evidence_confirm_notices(result),
    )


def _resolved_category(result: InvoiceConfirmationResult) -> str | None:
    """Return the IVA treatment this confirm recorded, or ``None`` where none was.

    ``None`` is a real answer here and not an absence of information: it is what
    a withheld relief claim, a self-contradicting document and an unplaceable
    operation all leave behind, and the accompanying outcome says which.
    """
    if result.establishment is None or result.establishment.category.category is None:
        return None
    return result.establishment.category.category.value


def _resolved_outcome(result: InvoiceConfirmationResult) -> str | None:
    """Return which rung established the treatment, or why none did.

    Emitted beside the category rather than folded into it, because the pair is
    the whole point: a category on the weakest rung and one the rule table placed
    outright are the same string, and only this field tells them apart.
    """
    if result.establishment is None:
        return None
    return result.establishment.category.outcome.value


def _invoice_class_kwarg(
    invoice_class: str | None,
    *,
    effective_date: date,
) -> _InvoiceClassKwarg:
    """Keep an omitted invoice class omitted so document-derived defaults survive."""
    if invoice_class is None:
        return {}
    from ...domain.calculations.registry.errors import RegistryValidationError
    from ...domain.calculations.registry.invoice_legal_classification import (
        resolve_invoice_legal_classification_catalogue,
    )

    catalogue = resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
    )
    try:
        return {"invoice_class": catalogue.require_invoice_class(invoice_class)}
    except RegistryValidationError:
        accepted = ", ".join(invoice_class.value for invoice_class in catalogue.invoice_class_choices)
        raise typer.BadParameter(
            f"Unknown invoice class {invoice_class!r}. Accepted ids: {accepted}",
            param_hint="--invoice-class",
        ) from None


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
