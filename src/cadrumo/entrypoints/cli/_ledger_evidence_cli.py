"""Behavior handlers for ledger purchase invoice evidence commands."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final, Protocol, TypedDict, cast

import typer
from pydantic import ValidationError

from ...adapters.outbound.llm.consent import (
    EvidenceConsentToken,
    OffHostEvidenceReadOutcome,
    classify_off_host_evidence_read,
    mint_evidence_consent_token,
)
from ...application.ledger.attachment_review import get_attachment_review_item, list_attachment_review_queue
from ...application.ledger.confirmation_gate import FindingResolution
from ...application.ledger.evidence import (
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceService,
)
from ...application.ledger.invoice_confirmation import InvoiceConfirmationResult, confirm_invoice_draft_from_evidence
from ...application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence
from ...application.ledger.invoice_draft_payloads import EvidenceExtractResult
from ...application.ledger.invoice_draft_records import InvoiceDraft
from ...application.user_profile.capabilities import cloud_evidence_upload_eligible_for_active_profile
from ...core.aggregation import IntracomOperationType
from ...core.config import load_settings
from ...core.config_support import LLMProvider
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.invoices.enums import InvoiceClass
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.supply_nature import SupplyNature
from ._date_parsing import _parse_iso_date, _parse_optional_iso_date_str
from ._decimal_parsing import parse_decimal_amount, parse_optional_decimal_amount
from ._evidence_field_notices import field_degradation_notices
from ._ledger_business_invoice_cli import catalogue_invoice_shared_fields
from ._ledger_evidence_confirm_notices import confirm_resolution_lines, confirm_resolution_notices
from ._ledger_evidence_extraction_wiring import invoice_draft_extraction_ports
from ._ledger_evidence_review_cli import parse_finding_resolution
from ._ledger_support import ledger_invoice_validation_no_recovery
from .common import bad, current_workflow_state, emit_envelope, transaction_catalogue_repo
from .ledger_business_payloads import (
    AttachmentReviewQueueResult,
    AttachmentReviewViewResult,
    EvidenceAddResult,
    EvidenceConfirmResult,
    EvidenceListResult,
    EvidenceRemoveResult,
    EvidenceUpdateResult,
    EvidenceViewResult,
)


class _InvoiceClassKwarg(TypedDict, total=False):
    """Optional keyword passed only when the operator supplied an invoice class."""

    invoice_class: InvoiceClass


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
) -> None:
    """Register a purchase invoice evidence record and return its id."""
    transaction_repository = transaction_catalogue_repo(current_workflow_state())
    result = _evidence_service().add(
        bucket_id=transaction_repository.bucket_id,
        source_path=source_path,
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=_parse_optional_iso_date_str(invoice_date, label="invoice-date"),
        taxable_base=parse_optional_decimal_amount(taxable_base, label="taxable-base"),
        iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
        iva_amount=parse_optional_decimal_amount(iva_amount, label="iva-amount"),
        notes=notes,
    )
    payload = _evidence_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _evidence_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    emit_envelope(ctx, command="ledger.evidence.add", result=EvidenceAddResult.model_validate(payload), lines=lines)


def evidence_view(ctx: typer.Context, evidence_id: str) -> None:
    """Show one purchase invoice evidence record by id."""
    transaction_repository = transaction_catalogue_repo(current_workflow_state())
    record = _evidence_service().view(bucket_id=transaction_repository.bucket_id, evidence_id=evidence_id)
    emit_envelope(
        ctx,
        command="ledger.evidence.view",
        result=EvidenceViewResult.model_validate(_evidence_payload(record)),
        lines=_evidence_text_lines(record),
    )


def evidence_list(ctx: typer.Context) -> None:
    """List every purchase invoice evidence record in the active bucket."""
    transaction_repository = transaction_catalogue_repo(current_workflow_state())
    records = _evidence_service().list_all(bucket_id=transaction_repository.bucket_id)
    payload = {
        "bucket_id": transaction_repository.bucket_id,
        "count": len(records),
        "rows": [_evidence_payload(record) for record in records],
    }
    lines = ["evidence_id\tmedia_kind\tsupplier\tinvoice_number\tinvoice_date\ttaxable_base\tnotes"]
    for record in records:
        data = _evidence_payload(record)
        lines.append(
            f"{data['evidence_id']}\t{data['media_kind']}\t"
            f"{data.get('supplier') or '-'}\t{data.get('invoice_number') or '-'}\t"
            f"{data.get('invoice_date') or '-'}\t{data.get('taxable_base') or '-'}\t"
            f"{data.get('notes') or '-'}"
        )
    emit_envelope(ctx, command="ledger.evidence.list", result=EvidenceListResult.model_validate(payload), lines=lines)


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
    transaction_repository = transaction_catalogue_repo(current_workflow_state())
    patch = PurchaseInvoiceEvidencePatch(
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=_parse_optional_iso_date_str(invoice_date, label="invoice-date"),
        taxable_base=parse_optional_decimal_amount(taxable_base, label="taxable-base"),
        iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
        iva_amount=parse_optional_decimal_amount(iva_amount, label="iva-amount"),
        notes=notes,
    )
    result = _evidence_service().update(
        bucket_id=transaction_repository.bucket_id, evidence_id=evidence_id, patch=patch
    )
    payload = _evidence_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _evidence_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    emit_envelope(
        ctx, command="ledger.evidence.update", result=EvidenceUpdateResult.model_validate(payload), lines=lines
    )


def evidence_remove(ctx: typer.Context, evidence_id: str, yes: bool = False) -> None:
    """Delete one purchase invoice evidence record."""
    if not yes:
        raise bad(tr("cli.app.ledger.evidence.yes_required"))
    transaction_repository = transaction_catalogue_repo(current_workflow_state())
    result = _evidence_service().remove(bucket_id=transaction_repository.bucket_id, evidence_id=evidence_id)
    payload = _evidence_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _evidence_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    emit_envelope(
        ctx, command="ledger.evidence.remove", result=EvidenceRemoveResult.model_validate(payload), lines=lines
    )


#: Operator surface recorded on a token this command mints. Names the exact verb
#: rather than "cli", because a withdrawal survey answers "where was this
#: acknowledged" and a whole-entrypoint label cannot.
_EXTRACT_CONSENT_SURFACE = "cli:ledger.evidence.extract"

#: The operator-facing wording for each refusal the shared classifier returns.
#: The rules are decided in :mod:`~llm.consent`; only the phrasing is CLI-owned.
_OFF_HOST_REFUSAL_LOCALE_KEYS: Final[dict[OffHostEvidenceReadOutcome, str]] = {
    OffHostEvidenceReadOutcome.ACKNOWLEDGEMENT_WITHOUT_PROVIDER: (
        "cli.app.ledger.evidence.extract_acknowledge_without_provider"
    ),
    OffHostEvidenceReadOutcome.PROVIDER_READS_ON_HOST: ("cli.app.ledger.evidence.extract_off_host_provider_is_local"),
    OffHostEvidenceReadOutcome.PROVIDER_WITHOUT_ACKNOWLEDGEMENT: (
        "cli.app.ledger.evidence.extract_provider_without_acknowledge"
    ),
}


def _mint_extract_consent(
    *,
    bucket_id: str,
    evidence_id: str | None,
    off_host_provider: LLMProvider | None,
    acknowledged: bool,
) -> EvidenceConsentToken | None:
    """Return the token authorising ONE off-host read, or ``None`` for the on-host default.

    Whether the two flags constitute a well-formed off-host request is decided
    by :func:`~llm.consent.classify_off_host_evidence_read`, beside the minting
    path it guards; this function supplies the operator-facing wording and the
    binding to the document's content address. Both flags absent is the
    overwhelmingly common call and returns ``None`` immediately: no token, no
    provider override, behaviour identical to before this option existed.

    Nothing here is stored. There is no config key and no profile field behind
    either flag -- a stored acknowledgement would be exactly the standing
    enablement the default-off posture exists to prevent, and it would decay
    into consent nobody remembers granting.

    Returns:
        The minted token, or ``None`` when no off-host read was requested.

    Raises:
        typer.BadParameter: When the flags are supplied incompletely, when the
            provider names the on-host default, when the read has no
            content-addressable evidence record behind it, or when the consent
            gate refuses this invocation.
    """
    outcome = classify_off_host_evidence_read(provider=off_host_provider, acknowledged=acknowledged)
    if outcome is OffHostEvidenceReadOutcome.ON_HOST_DEFAULT:
        return None
    refusal_key = _OFF_HOST_REFUSAL_LOCALE_KEYS.get(outcome)
    if refusal_key is not None:
        raise bad(tr(refusal_key))
    # Only the one consented outcome may reach the minting path below. The
    # wording table above covers the refusals that exist today, so reaching
    # here with anything else means an outcome was added to the classifier and
    # not given a sentence -- and the default for an unclassified answer on a
    # consent gate has to be refusal. Falling through on the strength of "no
    # refusal wording was found" would mint a token authorising financial
    # evidence to leave this host, which is the one thing the default-off
    # posture exists to prevent.
    if outcome is not OffHostEvidenceReadOutcome.OFF_HOST_CONSENTED:
        raise bad(tr("cli.app.ledger.evidence.extract_off_host_unclassified", outcome=outcome.value))

    # The token binds to the BYTES, so a read with no content-addressable record
    # behind it cannot mint one. An attachment-only extract is exactly that case:
    # an id names the bytes but does not fingerprint them, and recording one as
    # the other would let a later withdrawal believe it had proved a match it
    # never checked.
    if evidence_id is None:
        raise bad(
            tr("cli.app.ledger.evidence.extract_off_host_needs_evidence_id"),
        )
    record = PurchaseInvoiceEvidenceService().view(bucket_id=bucket_id, evidence_id=evidence_id)
    content_address = record.source_sha256
    if not content_address:
        raise bad(
            tr("cli.app.ledger.evidence.extract_off_host_needs_content_address"),
        )

    return mint_evidence_consent_token(
        settings=load_settings(),
        # The SINGLE production reading of the standing per-profile bar. Passed
        # through rather than re-decided here: the minting path refuses when it
        # is false, so a surface cannot widen the posture by forgetting it.
        profile_eligible=cloud_evidence_upload_eligible_for_active_profile(),
        acknowledged=acknowledged,
        surface=_EXTRACT_CONSENT_SURFACE,
        evidence_content_address=content_address,
    )


def _require_exact_evidence_reference(evidence_id: str | None, attachment_id: str | None) -> None:
    """Require exactly one secure evidence reference for a read or confirm."""
    if (evidence_id is None) == (attachment_id is None):
        raise bad(tr("cli.app.ledger.evidence.extract_reference_required"))


def _extract_evidence_draft(
    *,
    bucket_id: str,
    evidence_id: str | None,
    attachment_id: str | None,
    off_host_provider: LLMProvider | None,
    consent_token: EvidenceConsentToken | None,
) -> InvoiceDraft:
    """Run the application-owned evidence reader for one secure reference."""
    return extract_invoice_draft_from_evidence(
        bucket_id=bucket_id,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        off_host_provider=off_host_provider,
        consent_token=consent_token,
        ports=invoice_draft_extraction_ports(),
    )


def _display_optional(value: object) -> object:
    """Render an absent scalar with the extract surface's established marker."""
    return value if value is not None else "-"


def _display_text(value: str | None) -> str:
    """Render an absent text field with the extract surface's established marker."""
    return value or "-"


def _display_suggested_kind(draft: InvoiceDraft) -> str:
    """Render the optional application-derived invoice kind."""
    return "-" if draft.suggested_kind is None else draft.suggested_kind.value


def _evidence_extract_payload(
    *,
    bucket_id: str,
    evidence_id: str | None,
    attachment_id: str | None,
    off_host_provider: LLMProvider | None,
    consent_token: EvidenceConsentToken | None,
    draft: InvoiceDraft,
) -> dict[str, object]:
    """Project the application draft and one-read consent provenance."""
    return {
        "bucket_id": bucket_id,
        "evidence_id": evidence_id,
        "attachment_id": attachment_id,
        **draft.model_dump(mode="json"),
        "off_host_provider": None if consent_token is None else off_host_provider,
        "off_host_acknowledged_surface": None if consent_token is None else consent_token.surface,
    }


def _evidence_extract_lines(
    bucket_id: str,
    evidence_id: str | None,
    attachment_id: str | None,
    draft: InvoiceDraft,
) -> list[str]:
    """Render the stable tabular projection of one extracted draft."""
    return [
        f"bucket_id\t{bucket_id}",
        f"evidence_id\t{_display_text(evidence_id)}",
        f"attachment_id\t{_display_text(attachment_id)}",
        f"supplier_tax_id\t{_display_text(draft.supplier_tax_id)}",
        f"supplier_name\t{_display_text(draft.supplier_name)}",
        f"customer_tax_id\t{_display_text(draft.customer_tax_id)}",
        f"customer_name\t{_display_text(draft.customer_name)}",
        f"invoice_number\t{_display_text(draft.invoice_number)}",
        f"invoice_series\t{_display_text(draft.invoice_series)}",
        f"invoice_date\t{_display_text(draft.invoice_date)}",
        f"taxable_base\t{_display_optional(draft.taxable_base)}",
        f"iva_rate\t{_display_optional(draft.iva_rate)}",
        f"iva_amount\t{_display_optional(draft.iva_amount)}",
        f"grand_total\t{_display_optional(draft.grand_total)}",
        f"currency\t{_display_optional(draft.currency)}",
        f"retencion_rate\t{_display_optional(draft.retencion_rate)}",
        f"retencion_amount\t{_display_optional(draft.retencion_amount)}",
        f"suplidos_amount\t{_display_optional(draft.suplidos_amount)}",
        f"suggested_kind\t{_display_suggested_kind(draft)}",
        f"transcription_sha256\t{_display_text(draft.transcription_sha256)}",
        f"provenance_fields\t{len(draft.provenance)}",
        f"discrepancies\t{len(draft.discrepancies)}",
        f"raw_text_length\t{draft.raw_text_length}",
    ]


def _evidence_extract_notices(reference: str, draft: InvoiceDraft) -> list[Notice]:
    """Project review and field-degradation notices for one extracted draft."""
    notices: list[Notice] = [
        Notice(
            severity=NoticeSeverity.INFO,
            code="ledger.evidence.extract.review_hint",
            message=tr("cli.app.ledger.evidence.extract_review_hint_message"),
            context={"reference": reference},
        ),
    ]
    notices.extend(field_degradation_notices(draft.provenance))
    return notices


def evidence_extract(
    ctx: typer.Context,
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    off_host_provider: LLMProvider | None = None,
    acknowledge_off_host: bool = False,
) -> None:
    """Run the on-host PDF text-layer extractor over stored evidence bytes.

    Reads the evidence or attachment bytes from secure storage into memory,
    runs the grounded on-host heuristics (never a cloud call, never a
    temp file: ``sensitive-financial-data-secure-storage-only``), and
    prints the best-effort :class:`InvoiceDraft` for operator review.
    Every field the heuristics could not ground in the extracted text is
    ``null`` rather than guessed. Extracting never mints or persists an
    invoice; confirmation is a separate operator action.
    """
    _require_exact_evidence_reference(evidence_id, attachment_id)
    transaction_repository = transaction_catalogue_repo(current_workflow_state())
    consent_token = _mint_extract_consent(
        bucket_id=transaction_repository.bucket_id,
        evidence_id=evidence_id,
        off_host_provider=off_host_provider,
        acknowledged=acknowledge_off_host,
    )
    draft = _extract_evidence_draft(
        bucket_id=transaction_repository.bucket_id,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        off_host_provider=off_host_provider,
        consent_token=consent_token,
    )
    reviewed_reference = evidence_id or attachment_id or ""
    emit_envelope(
        ctx,
        command="ledger.evidence.extract",
        result=EvidenceExtractResult.model_validate(
            _evidence_extract_payload(
                bucket_id=transaction_repository.bucket_id,
                evidence_id=evidence_id,
                attachment_id=attachment_id,
                off_host_provider=off_host_provider,
                consent_token=consent_token,
                draft=draft,
            ),
        ),
        lines=_evidence_extract_lines(transaction_repository.bucket_id, evidence_id, attachment_id, draft),
        notices=_evidence_extract_notices(reviewed_reference, draft),
    )


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
    invoice_class: InvoiceClass | None = None,
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
    invoice_class: InvoiceClass | None,
    rectifies: str | None,
    series: str | None,
    notes: str,
    resolve: list[str],
) -> None:
    _require_exact_evidence_reference(evidence_id, attachment_id)
    transaction_repository = transaction_catalogue_repo(current_workflow_state())
    bucket_id = transaction_repository.bucket_id
    resolutions: list[FindingResolution] = [parse_finding_resolution(raw) for raw in resolve]
    try:
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
            **_invoice_class_kwarg(invoice_class),
            rectifies_invoice_number=rectifies,
            series=series,
            notes=notes,
            resolutions=resolutions,
            extraction_ports=invoice_draft_extraction_ports(),
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


def _invoice_class_kwarg(invoice_class: InvoiceClass | None) -> _InvoiceClassKwarg:
    """Keep an omitted invoice class omitted so document-derived defaults survive."""
    if invoice_class is None:
        return {}
    return {"invoice_class": invoice_class}


def _evidence_service() -> PurchaseInvoiceEvidenceService:
    return PurchaseInvoiceEvidenceService()


def _evidence_payload(record: PurchaseInvoiceEvidence) -> dict[str, object]:
    # `model_dump` on a plain (non-root) BaseModel is annotated and guaranteed
    # to return a str-keyed dict, so neither a mapping check nor a key check
    # could fire here. (A `RootModel` would differ -- see _root_payloads.py,
    # where the parameter is `type[BaseModel]` and the guard IS live.)
    payload: dict[str, object] = dict(record.model_dump(mode="json"))
    return payload


def _evidence_text_lines(record: PurchaseInvoiceEvidence) -> list[str]:
    payload = _evidence_payload(record)
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
