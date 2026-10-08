"""Worker-bound readers for ledger evidence follow-up operations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.confirmation_gate import ConfirmationBlockReason, ReviewAdvisoryKind
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.attachments.errors import AttachmentNotFoundError, AttachmentValidationError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva.regime_legend import resolve_regime_legends
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .attachment_review import get_attachment_review_item, list_attachment_review_queue
from .confirmation_gate import ConfirmationBlocker, confirmation_blockers
from .consent_withdrawal import survey_cloud_consent
from .country_vocabulary_advisory import CountryVocabularyAdvisory, country_vocabulary_advisory
from .evidence_followup_contracts import (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    MAX_EVIDENCE_FOLLOWUP_READ_ROWS,
    CountryVocabularyAdvisoryProjection,
    CountryVocabularyWarningProjection,
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
    LedgerEvidenceReviewViewExecutionResult,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
    PartyAttributionAdvisoryProjection,
    PartyAttributionWarningProjection,
    project_consent_withdrawal_survey,
)
from .extraction_draft_repository import bind_extraction_draft_repository_factory
from .extraction_draft_store import ExtractionDraftDocument, StoredExtractionDraft, load_extraction_drafts
from .invoice_draft_records import InvoiceDraft
from .invoice_evidence_operation_dtos import (
    ConfirmationBlockerProjectionV1,
    InvoiceDraftProjectionV1,
    LabelReadingFallbackProjectionV1,
)
from .invoice_extraction_authority import default_invoice_extraction_period
from .party_attribution import PartyAttributionAdvisory, party_attribution_advisory
from .review_advisories import review_advisory_kinds

_MAX_RESULT_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096


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
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


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
    if str(document.bucket_id) != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return document


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
    return EvidenceReviewQueueRowProjection(
        evidence_reference=stored.evidence_reference,
        extractor=stored.extractor,
        drafted_at=stored.drafted_at,
        blocking_count=len(blockers),
        reasons=reasons,
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
        party_advisory = party_attribution_advisory(draft, legends=legends, operation=operation)
        country_advisory = country_vocabulary_advisory(draft, operation=operation)
    return party_advisory, country_advisory


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
    )


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
            with validating_governed_facts(context.authority_operation):
                rows = tuple(
                    row
                    for stored in sorted(document.drafts, key=lambda item: item.evidence_reference)
                    if (row := _review_row(stored, request=payload, operation=context)) is not None
                )
            if len(rows) > MAX_EVIDENCE_FOLLOWUP_READ_ROWS:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return LedgerEvidenceReviewListProjection(
                profile_id=payload.profile_id,
                filters=_filters(payload),
                rows=rows,
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
            stored = _stored_review_view_draft(self._ports, bucket_id, payload.evidence_reference)
            draft = stored.draft.with_label_reading_fallback(stored.label_reading_fallback)
            party_advisory, country_advisory = _review_view_advisories(draft, context.authority_operation)
            projected_draft = _review_view_invoice_draft_projection(draft)
            result = _review_view_projection(
                payload.profile_id,
                stored,
                draft,
                projected_draft,
                _party_attribution_projection(party_advisory),
                _country_vocabulary_projection(country_advisory),
            )
            if result.evidence_reference != payload.evidence_reference:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return result

        return await _capture_result(
            context,
            read=read,
            wrap=lambda result: LedgerEvidenceReviewViewExecutionResult(profile_id=payload.profile_id, result=result),
            task_name="ledger-evidence-review-view",
        )


__all__ = [
    "LedgerEvidenceAttachmentQueueExecutor",
    "LedgerEvidenceAttachmentViewExecutor",
    "LedgerEvidenceConsentListExecutor",
    "LedgerEvidenceReviewListExecutor",
    "LedgerEvidenceReviewViewExecutor",
]
