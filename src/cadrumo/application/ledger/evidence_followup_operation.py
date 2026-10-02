"""Profile-bound, worker-owned reads for invoice evidence follow-up surfaces."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, ValidationError, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import Settings
from ...core.confirmation_gate import ConfirmationBlockReason, ReviewAdvisoryKind
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from ...domain.attachments.errors import AttachmentNotFoundError, AttachmentValidationError
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva.establishment import StatedCountryCodeStatus
from ...domain.iva.regime_legend import resolve_regime_legends
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .attachment_review import AttachmentReviewItem, get_attachment_review_item, list_attachment_review_queue
from .confirmation_gate import ConfirmationBlocker, confirmation_blockers
from .consent_withdrawal import (
    CloudDerivedArtefact,
    ConsentedDispatch,
    ConsentWithdrawalSurvey,
    survey_cloud_consent,
)
from .country_vocabulary_advisory import country_vocabulary_advisory
from .extraction_draft_store import (
    ExtractionDraftDocument,
    ExtractionDraftRepositoryFactory,
    StoredExtractionDraft,
    bind_extraction_draft_repository_factory,
    load_extraction_drafts,
)
from .invoice_evidence_operation_dtos import ConfirmationBlockerProjectionV1, InvoiceDraftProjectionV1
from .invoice_extraction_authority import default_invoice_extraction_period
from .party_attribution import party_attribution_advisory
from .read_access import resolve_ledger_read_access
from .review_advisories import review_advisory_kinds

LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID = "ledger.evidence.attachment_queue"
LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID = "ledger.evidence.attachment_view"
LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID = "ledger.evidence.consent.list"
LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID = "ledger.evidence.review.list"
LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID = "ledger.evidence.review.view"

_MAX_READ_ROWS = 4_096
_MAX_RESULT_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096
_Reference = Annotated[str, Field(min_length=1, max_length=64)]
_AttachmentId = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
_ShortText = Annotated[str, Field(min_length=1, max_length=2_048)]
_ReviewRows = Annotated[tuple["EvidenceReviewQueueRowProjection", ...], Field(max_length=_MAX_READ_ROWS)]
_AttachmentRows = Annotated[tuple[AttachmentReviewItem, ...], Field(max_length=_MAX_READ_ROWS)]
_BlockerRows = Annotated[tuple[ConfirmationBlockerProjectionV1, ...], Field(max_length=128)]


class AttachmentStoreFactory(Protocol):
    """Compose the encrypted attachment capability for one active profile."""

    def __call__(self, bucket_id: str, /) -> AttachmentStoreProtocol:
        """Return the attachment store bound to ``bucket_id``."""
        ...


class EvidenceConsentEntriesFactory(Protocol):
    """Project adapter-side consent entries for the consent survey."""

    def __call__(self, *, bucket_id: str) -> tuple[ConsentedDispatch, ...]:
        """Load consent entries; the application survey scopes them to the profile."""
        ...


@dataclass(frozen=True, slots=True)
class LedgerEvidenceFollowupOperationPorts:
    """Explicit capabilities needed by the five evidence follow-up reads."""

    settings: Settings
    attachment_store_factory: AttachmentStoreFactory
    extraction_draft_repository_factory: ExtractionDraftRepositoryFactory
    consent_entries_factory: EvidenceConsentEntriesFactory


class LedgerEvidenceAttachmentQueueRequest(BaseModel):
    """Private request for all pending attachments in one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class LedgerEvidenceAttachmentViewRequest(BaseModel):
    """Private request for one exact attachment manifest."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    attachment_id: _AttachmentId


class LedgerEvidenceConsentListRequest(BaseModel):
    """Private request for one profile's consent and derived-artifact survey."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class LedgerEvidenceReviewListRequest(BaseModel):
    """Private request for a typed, optionally narrowed pending-review queue."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    reason: ConfirmationBlockReason | None = None
    finding: DraftDiscrepancyKind | None = None
    advisory: ReviewAdvisoryKind | None = None
    blocking_only: bool = False


class LedgerEvidenceReviewViewRequest(BaseModel):
    """Private request for one pending extraction draft."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_reference: _Reference


class LedgerEvidenceAttachmentQueueProjection(BaseModel):
    """Complete bounded pending-attachment projection for one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    count: NonNegativeInt
    rows: _AttachmentRows = ()

    @model_validator(mode="after")
    def _correlate_count_and_pending_rows(self) -> LedgerEvidenceAttachmentQueueProjection:
        if self.count != len(self.rows) or any(not row.pending_review for row in self.rows):
            raise ValueError("attachment queue count or pending status is inconsistent")
        attachment_ids = tuple(row.attachment_id for row in self.rows)
        if len(set(attachment_ids)) != len(self.rows) or attachment_ids != tuple(sorted(attachment_ids)):
            raise ValueError("attachment queue identities or order are inconsistent")
        return self


class LedgerEvidenceAttachmentViewProjection(BaseModel):
    """One review-safe attachment manifest for the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    item: AttachmentReviewItem


class ConsentedDispatchProjection(BaseModel):
    """Closed consent-ledger row with a plain public UTC datetime schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_bucket_id: str
    evidence_content_address: str
    provider: str
    model: str
    surface: str
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def _recorded_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @classmethod
    def from_dispatch(cls, value: ConsentedDispatch) -> ConsentedDispatchProjection:
        """Copy every canonical consent fact into the schema-safe DTO."""
        return cls(**value.model_dump())


class CloudDerivedArtefactProjection(BaseModel):
    """Closed draft-history row with a plain public UTC datetime schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    evidence_reference: str
    provenance_stamp: str
    transport: str | None = None
    drafted_at: datetime

    @field_validator("drafted_at")
    @classmethod
    def _drafted_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @classmethod
    def from_artefact(cls, value: CloudDerivedArtefact) -> CloudDerivedArtefactProjection:
        """Copy every canonical derived-artifact fact into the schema-safe DTO."""
        return cls(**value.model_dump())


class ConsentWithdrawalSurveyProjection(BaseModel):
    """Complete consent survey copied into schema-safe public snapshots."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    consented_dispatches: Annotated[tuple[ConsentedDispatchProjection, ...], Field(max_length=_MAX_READ_ROWS)] = ()
    cloud_derived_artefacts: Annotated[
        tuple[CloudDerivedArtefactProjection, ...], Field(max_length=_MAX_READ_ROWS)
    ] = ()
    transmitted_bytes_are_unrecallable: Literal[True] = True


def _project_consent_survey(value: ConsentWithdrawalSurvey) -> ConsentWithdrawalSurveyProjection:
    if value.transmitted_bytes_are_unrecallable is not True:
        raise ValueError("consent survey must retain the canonical unrecallable-bytes statement")
    return ConsentWithdrawalSurveyProjection(
        consented_dispatches=tuple(
            ConsentedDispatchProjection.from_dispatch(row) for row in value.consented_dispatches
        ),
        cloud_derived_artefacts=tuple(
            CloudDerivedArtefactProjection.from_artefact(row) for row in value.cloud_derived_artefacts
        ),
        transmitted_bytes_are_unrecallable=True,
    )


class LedgerEvidenceConsentListProjection(BaseModel):
    """Consent history and cloud-derived artifacts for one exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    survey: ConsentWithdrawalSurveyProjection

    @model_validator(mode="after")
    def _correlate_consent_dispatches(self) -> LedgerEvidenceConsentListProjection:
        if any(row.profile_bucket_id != str(self.profile_id) for row in self.survey.consented_dispatches):
            raise ValueError("consent survey contains a dispatch from another profile")
        return self


class EvidenceReviewQueueRowProjection(BaseModel):
    """One pending draft with its complete blocker/advisory summary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    evidence_reference: _Reference
    extractor: _ShortText
    drafted_at: datetime
    blocking_count: NonNegativeInt
    reasons: Annotated[tuple[ConfirmationBlockReason, ...], Field(max_length=64)] = ()
    advisory_count: NonNegativeInt
    advisories: Annotated[tuple[ReviewAdvisoryKind, ...], Field(max_length=16)] = ()

    @field_validator("drafted_at")
    @classmethod
    def _drafted_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _correlate_counts_and_unique_summaries(self) -> EvidenceReviewQueueRowProjection:
        if self.advisory_count != len(self.advisories):
            raise ValueError("review queue advisory count does not match its kinds")
        if len(set(self.reasons)) != len(self.reasons) or len(set(self.advisories)) != len(self.advisories):
            raise ValueError("review queue row repeats a kind")
        if self.blocking_count < len(self.reasons):
            raise ValueError("review queue blocker summary exceeds its blocker count")
        return self


class PartyAttributionWarningProjection(BaseModel):
    """Public party warning with the canonical territory token as a string."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    role: _ShortText
    fields: Annotated[tuple[_ShortText, ...], Field(max_length=16)] = ()
    scope_if_attributed: _ShortText | None = None


class PartyAttributionAdvisoryProjection(BaseModel):
    """Closed public projection of all party attribution warnings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    parties: Annotated[tuple[PartyAttributionWarningProjection, ...], Field(min_length=1, max_length=2)]

    @property
    def fields(self) -> tuple[str, ...]:
        """Return all unverified address fields in party order."""
        return tuple(field for party in self.parties for field in party.fields)


class CountryVocabularyWarningProjection(BaseModel):
    """Public country warning retaining its closed status and exact finding text."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    role: _ShortText
    field: _ShortText
    stated_code: _ShortText
    status: StatedCountryCodeStatus
    detail: _ShortText


class CountryVocabularyAdvisoryProjection(BaseModel):
    """Closed public projection of every country-vocabulary warning."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    parties: Annotated[tuple[CountryVocabularyWarningProjection, ...], Field(min_length=1, max_length=2)]

    def by_status(self, status: StatedCountryCodeStatus) -> tuple[CountryVocabularyWarningProjection, ...]:
        """Return the warnings for one exact canonical country-code status."""
        return tuple(party for party in self.parties if party.status is status)


class LedgerEvidenceReviewListProjection(BaseModel):
    """Complete bounded queue result and the request's displayed filters."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    filters: Annotated[tuple[str, ...], Field(max_length=4)] = ()
    rows: _ReviewRows = ()

    @model_validator(mode="after")
    def _ordered_unique_rows(self) -> LedgerEvidenceReviewListProjection:
        references = tuple(row.evidence_reference for row in self.rows)
        if references != tuple(sorted(set(references))):
            raise ValueError("review queue rows must have unique stable reference order")
        return self


class LedgerEvidenceReviewViewProjection(BaseModel):
    """Full canonical draft plus every finding and advisory needed for review."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_reference: _Reference
    extractor: _ShortText
    drafted_at: datetime
    draft: InvoiceDraftProjectionV1
    blockers: _BlockerRows = ()
    party_attribution_advisory: PartyAttributionAdvisoryProjection | None = None
    country_vocabulary_advisory: CountryVocabularyAdvisoryProjection | None = None

    @field_validator("drafted_at")
    @classmethod
    def _drafted_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _blocker_ids_are_unique(self) -> LedgerEvidenceReviewViewProjection:
        blocker_ids = tuple(blocker.blocker_id for blocker in self.blockers)
        if len(set(blocker_ids)) != len(blocker_ids):
            raise ValueError("review view repeats a blocker identity")
        return self


class LedgerEvidenceAttachmentQueueExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceAttachmentQueueProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceAttachmentQueueExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("attachment queue result belongs to another profile")
        return self


class LedgerEvidenceAttachmentViewExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceAttachmentViewProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceAttachmentViewExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("attachment view result belongs to another profile")
        return self


class LedgerEvidenceConsentListExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceConsentListProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceConsentListExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("consent list result belongs to another profile")
        return self


class LedgerEvidenceReviewListExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceReviewListProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceReviewListExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("review queue result belongs to another profile")
        return self


class LedgerEvidenceReviewViewExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceReviewViewProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceReviewViewExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("review view result belongs to another profile")
        return self


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
            if len(rows) > _MAX_READ_ROWS:
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
            if len(entries) > _MAX_READ_ROWS:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            with bind_extraction_draft_repository_factory(self._ports.extraction_draft_repository_factory):
                survey = survey_cloud_consent(
                    bucket_id=bucket_id,
                    settings=self._ports.settings,
                    consent_entries=entries,
                )
            projected_survey = _project_consent_survey(survey)
            if (
                len(projected_survey.consented_dispatches) > _MAX_READ_ROWS
                or len(projected_survey.cloud_derived_artefacts) > _MAX_READ_ROWS
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
            if len(document.drafts) > _MAX_READ_ROWS:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            _require_bounded_draft_metadata(document)
            with validating_governed_facts(context.authority_operation):
                rows = tuple(
                    row
                    for stored in sorted(document.drafts, key=lambda item: item.evidence_reference)
                    if (row := _review_row(stored, request=payload, operation=context)) is not None
                )
            if len(rows) > _MAX_READ_ROWS:
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
            document = _draft_document(self._ports, bucket_id)
            stored = next(
                (row for row in document.drafts if row.evidence_reference == payload.evidence_reference),
                None,
            )
            if stored is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            if len(stored.evidence_reference) > 64 or len(stored.extractor) > 2_048:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            draft = stored.draft.with_label_reading_fallback(stored.label_reading_fallback)
            with validating_governed_facts(context.authority_operation):
                period = default_invoice_extraction_period()
                legends = resolve_regime_legends(
                    operation=context.authority_operation,
                    effective_date=period.end_date,
                )
                party_advisory = party_attribution_advisory(
                    draft,
                    legends=legends,
                    operation=context.authority_operation,
                )
                country_advisory = country_vocabulary_advisory(
                    draft,
                    operation=context.authority_operation,
                )
            try:
                projected_draft = InvoiceDraftProjectionV1.from_draft(draft)
            except ValidationError:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
            projected_party_advisory = (
                None
                if party_advisory is None
                else PartyAttributionAdvisoryProjection(
                    parties=tuple(
                        PartyAttributionWarningProjection(
                            role=row.role,
                            fields=row.fields,
                            scope_if_attributed=(
                                row.scope_if_attributed.value if row.scope_if_attributed is not None else None
                            ),
                        )
                        for row in party_advisory.parties
                    ),
                )
            )
            projected_country_advisory = (
                None
                if country_advisory is None
                else CountryVocabularyAdvisoryProjection(
                    parties=tuple(
                        CountryVocabularyWarningProjection(
                            role=row.role,
                            field=row.field,
                            stated_code=row.stated_code,
                            status=row.status,
                            detail=row.detail,
                        )
                        for row in country_advisory.parties
                    ),
                )
            )
            result = LedgerEvidenceReviewViewProjection(
                profile_id=payload.profile_id,
                evidence_reference=stored.evidence_reference,
                extractor=stored.extractor,
                drafted_at=stored.drafted_at,
                draft=projected_draft,
                blockers=tuple(
                    ConfirmationBlockerProjectionV1.from_blocker(row) for row in confirmation_blockers(draft)
                ),
                party_attribution_advisory=projected_party_advisory,
                country_vocabulary_advisory=projected_country_advisory,
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


def _build_definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    build: Callable[[], object],
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=build,
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_ledger_evidence_followup_definitions(
    ports: LedgerEvidenceFollowupOperationPorts,
) -> tuple[OperationDefinition, ...]:
    """Build the five exact-profile follow-up read definitions."""
    return (
        _build_definition(
            definition_id=LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceAttachmentQueueRequest,
            result_type=LedgerEvidenceAttachmentQueueExecutionResult,
            executor_type=LedgerEvidenceAttachmentQueueExecutor,
            build=lambda: LedgerEvidenceAttachmentQueueExecutor(ports),
        ),
        _build_definition(
            definition_id=LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceAttachmentViewRequest,
            result_type=LedgerEvidenceAttachmentViewExecutionResult,
            executor_type=LedgerEvidenceAttachmentViewExecutor,
            build=lambda: LedgerEvidenceAttachmentViewExecutor(ports),
        ),
        _build_definition(
            definition_id=LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceConsentListRequest,
            result_type=LedgerEvidenceConsentListExecutionResult,
            executor_type=LedgerEvidenceConsentListExecutor,
            build=lambda: LedgerEvidenceConsentListExecutor(ports),
        ),
        _build_definition(
            definition_id=LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceReviewListRequest,
            result_type=LedgerEvidenceReviewListExecutionResult,
            executor_type=LedgerEvidenceReviewListExecutor,
            build=lambda: LedgerEvidenceReviewListExecutor(ports),
        ),
        _build_definition(
            definition_id=LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceReviewViewRequest,
            result_type=LedgerEvidenceReviewViewExecutionResult,
            executor_type=LedgerEvidenceReviewViewExecutor,
            build=lambda: LedgerEvidenceReviewViewExecutor(ports),
        ),
    )


def _require_terminal_success(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
) -> None:
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or getattr(result, "profile_id", None) != profile_id
    ):
        raise ValueError("evidence follow-up read is not bound to its successful receipt")


def _project_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    expected_type: type[BaseModel],
    definition_id: str,
) -> BaseModel:
    if type(result) is not expected_type:
        raise ValueError("invalid evidence follow-up result")
    profile_id = getattr(result, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise ValueError("invalid evidence follow-up profile")
    _require_terminal_success(result, receipt, definition_id=definition_id, profile_id=profile_id)
    projection = getattr(result, "result", None)
    if not isinstance(projection, BaseModel):
        raise ValueError("invalid evidence follow-up projection")
    return projection


def _project_attachment_queue(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceAttachmentQueueExecutionResult,
        definition_id=LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    )


def _project_attachment_view(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceAttachmentViewExecutionResult,
        definition_id=LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    )


def _project_consent_list(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceConsentListExecutionResult,
        definition_id=LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    )


def _project_review_list(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceReviewListExecutionResult,
        definition_id=LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    )


def _project_review_view(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceReviewViewExecutionResult,
        definition_id=LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    )


def _resolve_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
    *,
    definition_id: str,
    request_type: type[BaseModel],
) -> ResolvedOperationAccess:
    if request.definition_id != definition_id or type(request.payload) is not request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = getattr(request.payload, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(
        request,
        context,
        profile_id=profile_id,
        periods=frozenset(),
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    projector: Callable[[BaseModel, OperationTerminalReceipt], BaseModel],
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=result_type,
        ),
        result_projector=projector,
        access_resolver=lambda request, context: _resolve_access(
            request,
            context,
            definition_id=definition.definition_id,
            request_type=request_type,
        ),
    )


def build_ledger_evidence_followup_registrations(
    definitions: Sequence[OperationDefinition],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind exact typed contracts and all-period tax disclosure for each read."""
    by_id = {definition.definition_id: definition for definition in definitions}
    expected = (
        LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    )
    if len(by_id) != len(definitions) or set(by_id) != set(expected):
        raise ValueError("follow-up registration requires the exact five read definitions")
    return (
        _registration(
            by_id[expected[0]],
            request_type=LedgerEvidenceAttachmentQueueRequest,
            result_type=LedgerEvidenceAttachmentQueueProjection,
            projector=_project_attachment_queue,
        ),
        _registration(
            by_id[expected[1]],
            request_type=LedgerEvidenceAttachmentViewRequest,
            result_type=LedgerEvidenceAttachmentViewProjection,
            projector=_project_attachment_view,
        ),
        _registration(
            by_id[expected[2]],
            request_type=LedgerEvidenceConsentListRequest,
            result_type=LedgerEvidenceConsentListProjection,
            projector=_project_consent_list,
        ),
        _registration(
            by_id[expected[3]],
            request_type=LedgerEvidenceReviewListRequest,
            result_type=LedgerEvidenceReviewListProjection,
            projector=_project_review_list,
        ),
        _registration(
            by_id[expected[4]],
            request_type=LedgerEvidenceReviewViewRequest,
            result_type=LedgerEvidenceReviewViewProjection,
            projector=_project_review_view,
        ),
    )


__all__ = [
    "LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID",
    "AttachmentStoreFactory",
    "CloudDerivedArtefactProjection",
    "ConsentWithdrawalSurveyProjection",
    "ConsentedDispatchProjection",
    "CountryVocabularyAdvisoryProjection",
    "CountryVocabularyWarningProjection",
    "EvidenceConsentEntriesFactory",
    "EvidenceReviewQueueRowProjection",
    "LedgerEvidenceAttachmentQueueExecutor",
    "LedgerEvidenceAttachmentQueueProjection",
    "LedgerEvidenceAttachmentQueueRequest",
    "LedgerEvidenceAttachmentViewExecutor",
    "LedgerEvidenceAttachmentViewProjection",
    "LedgerEvidenceAttachmentViewRequest",
    "LedgerEvidenceConsentListExecutor",
    "LedgerEvidenceConsentListProjection",
    "LedgerEvidenceConsentListRequest",
    "LedgerEvidenceFollowupOperationPorts",
    "LedgerEvidenceReviewListExecutor",
    "LedgerEvidenceReviewListProjection",
    "LedgerEvidenceReviewListRequest",
    "LedgerEvidenceReviewViewExecutor",
    "LedgerEvidenceReviewViewProjection",
    "LedgerEvidenceReviewViewRequest",
    "PartyAttributionAdvisoryProjection",
    "PartyAttributionWarningProjection",
    "build_ledger_evidence_followup_definitions",
    "build_ledger_evidence_followup_registrations",
]
