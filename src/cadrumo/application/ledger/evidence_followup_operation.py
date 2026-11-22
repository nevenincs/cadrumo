"""Worker-bound readers for ledger evidence follow-up operations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.projection_pages import PROJECTION_RESULT_MAX_BYTES

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.confirmation_gate import ConfirmationBlockReason, ReviewAdvisoryKind
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.attachments.errors import AttachmentNotFoundError, AttachmentValidationError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva.identification import nif_iva_issuing_country
from ...domain.iva.regime_legend import resolve_regime_legends
from ..operations.error_detail import served_words_language
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.result_size import refuse_oversized_result
from ..user_profile.access_errors import ProfileAccessRefusedError
from .attachment_review import get_attachment_review_item, list_attachment_review_queue
from .confirmation_block_words import served_block_reason_words
from .confirmation_gate import ConfirmationBlocker, confirmation_blockers
from .confirmation_record import load_confirmation_records
from .confirmation_record_repository import bind_confirmation_record_repository_factory
from .consent_withdrawal import survey_cloud_consent
from .country_vocabulary_advisory import CountryVocabularyAdvisory, country_vocabulary_advisory
from .evidence_followup_contracts import (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    MAX_EVIDENCE_FOLLOWUP_READ_ROWS,
    EvidenceConfirmPreconditionProjection,
    EvidenceReviewDirectionProjection,
    EvidenceReviewNifIvaPrefixCountryProjection,
    EvidenceReviewQueueRowProjection,
    LedgerEvidenceAttachmentQueueExecutionResult,
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewExecutionResult,
    LedgerEvidenceAttachmentViewProjection,
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceConsentListExecutionResult,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceFollowupOperationPorts,
    LedgerEvidenceReviewListExecutionResult,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
    LedgerEvidenceReviewSummaryExecutionResult,
    LedgerEvidenceReviewViewExecutionResult,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
    project_consent_withdrawal_survey,
)
from .evidence_review_advisories import (
    CountryVocabularyAdvisoryProjection,
    CountryVocabularyWarningProjection,
    PartyAttributionAdvisoryProjection,
    PartyAttributionWarningProjection,
)
from .evidence_review_summaries import LedgerEvidenceReviewSummaryProjection
from .extraction_draft_repository import bind_extraction_draft_repository_factory
from .extraction_draft_store import ExtractionDraftDocument, StoredExtractionDraft, load_extraction_drafts
from .filer_establishment import FILER_POSTCODE_MISSING_LOCALE_KEY, filer_postcode_declared, filer_postcode_step
from .invoice_draft_records import InvoiceDraft
from .invoice_evidence_operation_dtos import (
    ConfirmationBlockerProjectionV1,
    InvoiceDraftProjectionV1,
    LabelReadingFallbackProjectionV1,
)
from .invoice_extraction_authority import default_invoice_extraction_period
from .party_attribution import PartyAttributionAdvisory, party_attribution_advisory
from .preconditions import LedgerPreconditionCondition
from .review_advisories import review_advisory_kinds


def _require_worker_identity[PayloadT: BaseModel](
    request: OperationRequest[PayloadT],
    context: OperationExecutorContext,
    *,
    definition_id: str,
    profile_id: UUID,
) -> str:
    """Refuse a foreign request or stale active bucket before opening a port."""
    bucket_id = str(profile_id)
    subject = profile_operation_subject(bucket_id)
    if (
        request.definition_id != definition_id
        or context.identity.definition_id != definition_id
        or request.subject_ref != subject
        or context.identity.subject_ref != subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


def _check_result_size(result: BaseModel) -> None:
    """Refuse an oversized complete result instead of silently omitting rows."""
    refuse_oversized_result(result, PROJECTION_RESULT_MAX_BYTES)


async def _capture_result[ProjectionT: BaseModel](
    context: OperationExecutorContext,
    *,
    read: Callable[[], ProjectionT],
    wrap: Callable[[ProjectionT], BaseModel],
    task_name: str,
) -> str:
    """Read in a worker thread and retain only the bounded result in secure operands."""

    async def capture() -> str:
        result = await asyncio.to_thread(read)
        _check_result_size(result)
        return await context.operands.put(wrap(result), written_at=now())

    return await await_cancellation_complete(capture(), task_name=task_name)


class LedgerEvidenceAttachmentQueueExecutor:
    """Enumerate review-safe attachment manifests for the active profile."""

    def __init__(self, ports: LedgerEvidenceFollowupOperationPorts) -> None:
        """Bind the attachment-store read capability."""
        self._ports = ports

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceAttachmentQueueRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read all pending attachment manifests and seal the bounded result."""
        payload = request.payload
        bucket_id = _require_worker_identity(
            request,
            context,
            definition_id=LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def read() -> LedgerEvidenceAttachmentQueueProjection:
            if require_active_bucket_id() != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            store = self._ports.attachment_store_factory(bucket_id)
            rows = list_attachment_review_queue(store)
            if len(rows) > MAX_EVIDENCE_FOLLOWUP_READ_ROWS:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return LedgerEvidenceAttachmentQueueProjection(profile_id=payload.profile_id, count=len(rows), rows=rows)

        return await _capture_result(
            context,
            read=read,
            wrap=lambda result: LedgerEvidenceAttachmentQueueExecutionResult(
                profile_id=payload.profile_id,
                result=result,
            ),
            task_name="ledger-evidence-attachment-queue",
        )


class LedgerEvidenceAttachmentViewExecutor:
    """Inspect one exact attachment manifest without disclosing its bytes."""

    def __init__(self, ports: LedgerEvidenceFollowupOperationPorts) -> None:
        """Bind the attachment-store read capability."""
        self._ports = ports

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceAttachmentViewRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Verify and project the requested attachment manifest."""
        payload = request.payload
        bucket_id = _require_worker_identity(
            request,
            context,
            definition_id=LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def read() -> LedgerEvidenceAttachmentViewProjection:
            if require_active_bucket_id() != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            store = self._ports.attachment_store_factory(bucket_id)
            try:
                item = get_attachment_review_item(store, payload.attachment_id)
            except (AttachmentNotFoundError, AttachmentValidationError):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
            if item.attachment_id != payload.attachment_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return LedgerEvidenceAttachmentViewProjection(profile_id=payload.profile_id, item=item)

        return await _capture_result(
            context,
            read=read,
            wrap=lambda result: LedgerEvidenceAttachmentViewExecutionResult(
                profile_id=payload.profile_id,
                result=result,
            ),
            task_name="ledger-evidence-attachment-view",
        )


def _draft_document(ports: LedgerEvidenceFollowupOperationPorts, bucket_id: str) -> ExtractionDraftDocument:
    """Read the active profile's encrypted draft document through its injected port."""
    if require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    with bind_extraction_draft_repository_factory(ports.extraction_draft_repository_factory):
        document = load_extraction_drafts(bucket_id, ports.settings)
    if document.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return document


def _confirmed_references(ports: LedgerEvidenceFollowupOperationPorts, bucket_id: str) -> frozenset[str]:
    """The evidence references this profile has already confirmed into an invoice.

    A draft stays stored after its confirmation (the consent survey still lists
    what an off-host read derived), so the queue of drafts awaiting review
    leaves out the ones a confirmation record names. The record is written by
    the confirm after the invoice, so a confirm that stopped between the two
    leaves its draft in the queue, which is the safe side to err on.
    """
    if require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    with bind_confirmation_record_repository_factory(ports.confirmation_record_repository_factory):
        document = load_confirmation_records(bucket_id, ports.settings)
    if document.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return frozenset(record.evidence_reference for record in document.records)


def _require_bounded_draft_metadata(document: ExtractionDraftDocument) -> None:
    """Refuse old drafts whose reference/extractor metadata exceeds this projection."""
    if any(len(stored.evidence_reference) > 64 or len(stored.extractor) > 2_048 for stored in document.drafts):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _filters(payload: LedgerEvidenceReviewListRequest) -> tuple[str, ...]:
    filters: list[str] = []
    if payload.reason is not None:
        filters.append(f"reason={payload.reason.value}")
    if payload.finding is not None:
        filters.append(f"finding={payload.finding.value}")
    if payload.advisory is not None:
        filters.append(f"advisory={payload.advisory.value}")
    if payload.blocking_only:
        filters.append("blocking=true")
    return tuple(filters)


def _row_matches(
    stored: StoredExtractionDraft,
    *,
    reason: ConfirmationBlockReason | None,
    finding: DraftDiscrepancyKind | None,
    advisory: ReviewAdvisoryKind | None,
    blocking_only: bool,
    reasons: tuple[ConfirmationBlockReason, ...],
    advisories: tuple[ReviewAdvisoryKind, ...],
    blockers: tuple[ConfirmationBlocker, ...],
) -> bool:
    if reason is not None and reason not in reasons:
        return False
    if finding is not None and all(item.kind is not finding for item in stored.draft.discrepancies):
        return False
    if advisory is not None and advisory not in advisories:
        return False
    return not blocking_only or bool(blockers)


def _review_row(
    stored: StoredExtractionDraft,
    *,
    request: LedgerEvidenceReviewListRequest,
    operation: OperationExecutorContext,
) -> EvidenceReviewQueueRowProjection | None:
    blockers = confirmation_blockers(stored.draft)
    reasons = tuple(sorted({blocker.reason for blocker in blockers}, key=lambda item: item.value))
    advisories = review_advisory_kinds(stored.draft, operation=operation.authority_operation)
    if not _row_matches(
        stored,
        reason=request.reason,
        finding=request.finding,
        advisory=request.advisory,
        blocking_only=request.blocking_only,
        reasons=reasons,
        advisories=advisories,
        blockers=blockers,
    ):
        return None
    served = tuple(served_block_reason_words(reason) for reason in reasons)
    return EvidenceReviewQueueRowProjection(
        evidence_reference=stored.evidence_reference,
        extractor=stored.extractor,
        drafted_at=stored.drafted_at,
        blocking_count=len(blockers),
        reasons=reasons,
        reason_words=tuple(words for words, _language in served),
        reason_words_language=served[0][1] if served else None,
        advisory_count=len(advisories),
        advisories=advisories,
    )


def _stored_review_view_draft(
    ports: LedgerEvidenceFollowupOperationPorts,
    bucket_id: str,
    evidence_reference: str,
) -> StoredExtractionDraft:
    document = _draft_document(ports, bucket_id)
    stored = next((row for row in document.drafts if row.evidence_reference == evidence_reference), None)
    if stored is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if len(stored.evidence_reference) > 64 or len(stored.extractor) > 2_048:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return stored


def _review_view_advisories(
    draft: InvoiceDraft,
    operation: PinnedAuthorityOperation,
) -> tuple[PartyAttributionAdvisory | None, CountryVocabularyAdvisory | None]:
    with validating_governed_facts(operation):
        period = default_invoice_extraction_period()
        legends = resolve_regime_legends(operation=operation, effective_date=period.end_date)
        party_advisory = party_attribution_advisory(
            draft, legends=legends, effective_date=period.end_date, operation=operation
        )
        country_advisory = country_vocabulary_advisory(draft, effective_date=period.end_date, operation=operation)
    return party_advisory, country_advisory


def _review_view_nif_iva_prefix_country(
    draft: InvoiceDraft,
    operation: PinnedAuthorityOperation,
) -> EvidenceReviewNifIvaPrefixCountryProjection | None:
    """Name the country each party's NIF-IVA prefix carries, for the person to accept or ignore.

    Served beside the draft and never written into it: the reader refuses to
    take a tax-id prefix as the party's establishment, and a prefix still says
    only which Member State issued the number (Directive 2006/112/EC art. 215).
    """
    with validating_governed_facts(operation):
        supplier = nif_iva_issuing_country(draft.supplier_tax_id, operation=operation)
        customer = nif_iva_issuing_country(draft.customer_tax_id, operation=operation)
    if supplier is None and customer is None:
        return None
    return EvidenceReviewNifIvaPrefixCountryProjection(supplier=supplier, customer=customer)


def _review_view_invoice_draft_projection(draft: InvoiceDraft) -> InvoiceDraftProjectionV1:
    try:
        return InvoiceDraftProjectionV1.from_draft(draft)
    except ValidationError:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None


def _party_attribution_projection(
    advisory: PartyAttributionAdvisory | None,
) -> PartyAttributionAdvisoryProjection | None:
    if advisory is None:
        return None
    return PartyAttributionAdvisoryProjection(
        parties=tuple(
            PartyAttributionWarningProjection(
                role=row.role,
                fields=row.fields,
                scope_if_attributed=row.scope_if_attributed.value if row.scope_if_attributed is not None else None,
            )
            for row in advisory.parties
        ),
    )


def _country_vocabulary_projection(
    advisory: CountryVocabularyAdvisory | None,
) -> CountryVocabularyAdvisoryProjection | None:
    if advisory is None:
        return None
    return CountryVocabularyAdvisoryProjection(
        parties=tuple(
            CountryVocabularyWarningProjection(
                role=row.role,
                field=row.field,
                stated_code=row.stated_code,
                status=row.status,
                detail=row.detail,
            )
            for row in advisory.parties
        ),
    )


def _review_view_projection(
    profile_id: UUID,
    stored: StoredExtractionDraft,
    draft: InvoiceDraft,
    projected_draft: InvoiceDraftProjectionV1,
    party_advisory: PartyAttributionAdvisoryProjection | None,
    country_advisory: CountryVocabularyAdvisoryProjection | None,
    *,
    nif_iva_prefix_country: EvidenceReviewNifIvaPrefixCountryProjection | None,
    off_host_read_offered: bool,
) -> LedgerEvidenceReviewViewProjection:
    return LedgerEvidenceReviewViewProjection(
        profile_id=profile_id,
        evidence_reference=stored.evidence_reference,
        extractor=stored.extractor,
        drafted_at=stored.drafted_at,
        draft=projected_draft,
        label_reading_fallback=(
            None
            if (fallback := stored.label_reading_fallback) is None
            else LabelReadingFallbackProjectionV1.from_fallback(fallback)
        ),
        blockers=tuple(ConfirmationBlockerProjectionV1.from_blocker(row) for row in confirmation_blockers(draft)),
        party_attribution_advisory=party_advisory,
        country_vocabulary_advisory=country_advisory,
        direction=EvidenceReviewDirectionProjection.of(
            declared_kind=stored.declared_kind, suggested_kind=draft.suggested_kind
        ),
        counterparty_nif_iva_prefix_country=nif_iva_prefix_country,
        off_host_read_offered=off_host_read_offered,
    )


def _read_review_view(
    ports: LedgerEvidenceFollowupOperationPorts,
    bucket_id: str,
    payload: LedgerEvidenceReviewViewRequest,
    operation: PinnedAuthorityOperation,
) -> LedgerEvidenceReviewViewProjection:
    """Read one pending draft and derive its complete review under the retained authority."""
    stored = _stored_review_view_draft(ports, bucket_id, payload.evidence_reference)
    draft = stored.draft.with_label_reading_fallback(stored.label_reading_fallback)
    party_advisory, country_advisory = _review_view_advisories(draft, operation)
    projected_draft = _review_view_invoice_draft_projection(draft)
    result = _review_view_projection(
        payload.profile_id,
        stored,
        draft,
        projected_draft,
        _party_attribution_projection(party_advisory),
        _country_vocabulary_projection(country_advisory),
        nif_iva_prefix_country=_review_view_nif_iva_prefix_country(draft, operation),
        off_host_read_offered=ports.off_host_read_askable(bucket_id=bucket_id),
    )
    if result.evidence_reference != payload.evidence_reference:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return result


class LedgerEvidenceConsentListExecutor:
    """Enumerate consent entries and derived drafts within one profile."""

    def __init__(self, ports: LedgerEvidenceFollowupOperationPorts) -> None:
        """Bind encrypted draft and consent-history read capabilities."""
        self._ports = ports

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceConsentListRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read the complete consent survey for the active profile."""
        payload = request.payload
        bucket_id = _require_worker_identity(
            request,
            context,
            definition_id=LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def read() -> LedgerEvidenceConsentListProjection:
            if require_active_bucket_id() != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            entries = self._ports.consent_entries_factory(bucket_id=bucket_id)
            if len(entries) > MAX_EVIDENCE_FOLLOWUP_READ_ROWS:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            with bind_extraction_draft_repository_factory(self._ports.extraction_draft_repository_factory):
                survey = survey_cloud_consent(
                    bucket_id=bucket_id,
                    settings=self._ports.settings,
                    consent_entries=entries,
                )
            projected_survey = project_consent_withdrawal_survey(survey)
            if (
                len(projected_survey.consented_dispatches) > MAX_EVIDENCE_FOLLOWUP_READ_ROWS
                or len(projected_survey.cloud_derived_artefacts) > MAX_EVIDENCE_FOLLOWUP_READ_ROWS
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return LedgerEvidenceConsentListProjection(profile_id=payload.profile_id, survey=projected_survey)

        return await _capture_result(
            context,
            read=read,
            wrap=lambda result: LedgerEvidenceConsentListExecutionResult(profile_id=payload.profile_id, result=result),
            task_name="ledger-evidence-consent-list",
        )


def _confirm_precondition() -> EvidenceConfirmPreconditionProjection | None:
    """The profile fact every confirm reads and the active profile does not state, or ``None``.

    Read from the same profile record and through the same predicate the
    confirm's own refusal uses, worded with the same sentence and step, so the
    queue cannot call a draft ready that the confirm will refuse for this.
    """
    # Call-time import: the workflow persistence reaches back into this package.
    from ..workflow.persistence import workflow_state_repository

    if filer_postcode_declared(workflow_state_repository().load().active_profile_record()):
        return None
    language = served_words_language()
    return EvidenceConfirmPreconditionProjection(
        condition=LedgerPreconditionCondition.FILER_POSTCODE_VALID,
        words=tr(FILER_POSTCODE_MISSING_LOCALE_KEY, locale=language.value),
        words_language=language,
        next_step=filer_postcode_step()(language),
    )


class LedgerEvidenceReviewListExecutor:
    """Build the complete typed blocker/advisory queue for one profile."""

    def __init__(self, ports: LedgerEvidenceFollowupOperationPorts) -> None:
        """Bind the encrypted extraction-draft read capability."""
        self._ports = ports

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceReviewListRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read and filter every pending draft with retained authority."""
        payload = request.payload
        bucket_id = _require_worker_identity(
            request,
            context,
            definition_id=LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def read() -> LedgerEvidenceReviewListProjection:
            document = _draft_document(self._ports, bucket_id)
            if len(document.drafts) > MAX_EVIDENCE_FOLLOWUP_READ_ROWS:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            _require_bounded_draft_metadata(document)
            confirmed = _confirmed_references(self._ports, bucket_id)
            with validating_governed_facts(context.authority_operation):
                rows = tuple(
                    row
                    for stored in sorted(document.drafts, key=lambda item: item.evidence_reference)
                    if stored.evidence_reference not in confirmed
                    and (row := _review_row(stored, request=payload, operation=context)) is not None
                )
            if len(rows) > MAX_EVIDENCE_FOLLOWUP_READ_ROWS:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return LedgerEvidenceReviewListProjection(
                profile_id=payload.profile_id,
                filters=_filters(payload),
                rows=rows,
                confirm_precondition=_confirm_precondition() if rows else None,
            )

        return await _capture_result(
            context,
            read=read,
            wrap=lambda result: LedgerEvidenceReviewListExecutionResult(profile_id=payload.profile_id, result=result),
            task_name="ledger-evidence-review-list",
        )


class LedgerEvidenceReviewViewExecutor:
    """Read one full draft and derive its findings from the retained authority."""

    def __init__(self, ports: LedgerEvidenceFollowupOperationPorts) -> None:
        """Bind the encrypted extraction-draft read capability."""
        self._ports = ports

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceReviewViewRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read one full pending draft and its complete review findings."""
        payload = request.payload
        bucket_id = _require_worker_identity(
            request,
            context,
            definition_id=LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def read() -> LedgerEvidenceReviewViewProjection:
            return _read_review_view(self._ports, bucket_id, payload, context.authority_operation)

        return await _capture_result(
            context,
            read=read,
            wrap=lambda result: LedgerEvidenceReviewViewExecutionResult(profile_id=payload.profile_id, result=result),
            task_name="ledger-evidence-review-view",
        )


class LedgerEvidenceReviewSummaryExecutor:
    """Read one full draft review and retain only what an automation may hold of it."""

    def __init__(self, ports: LedgerEvidenceFollowupOperationPorts) -> None:
        """Bind the encrypted extraction-draft read capability."""
        self._ports = ports

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceReviewViewRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read one pending draft's review and seal its summary without document text."""
        payload = request.payload
        bucket_id = _require_worker_identity(
            request,
            context,
            definition_id=LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def read() -> LedgerEvidenceReviewSummaryProjection:
            # The person's complete review is built once and stays in worker
            # memory; the document's text never enters the result operand.
            view = _read_review_view(self._ports, bucket_id, payload, context.authority_operation)
            return LedgerEvidenceReviewSummaryProjection.from_review_view(view)

        return await _capture_result(
            context,
            read=read,
            wrap=lambda result: LedgerEvidenceReviewSummaryExecutionResult(
                profile_id=payload.profile_id, result=result
            ),
            task_name="ledger-evidence-review-summary",
        )


__all__ = [
    "LedgerEvidenceAttachmentQueueExecutor",
    "LedgerEvidenceAttachmentViewExecutor",
    "LedgerEvidenceConsentListExecutor",
    "LedgerEvidenceReviewListExecutor",
    "LedgerEvidenceReviewSummaryExecutor",
    "LedgerEvidenceReviewViewExecutor",
]
