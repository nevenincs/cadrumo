"""Registered exact-profile apply of the classification proposals a person accepted from a job.

A job never applies a proposal. The person names each proposal they accept,
with the movement revision it was made against and, for a mixed
classification, their own business share. Each accepted proposal is written
through the reviewed classification terminal the ledger review writes through,
against the movement exactly as the proposal read it: the guarded writer
refuses a movement that changed since. Each movement is decided on its own:
one refused proposal does not hold back the others, and a proposal the person
did not name stays a proposal.

An applied proposal is marked applied on the job, and a proposal whose
movement changed is marked stale, in one revision-guarded job write after the
ledger writes. The ledger write of each movement commits on its own; a job
write that cannot follow leaves the movement applied in the ledger and its
item proposed, and a later apply of it is refused as stale, never applied
twice.

The log names the job, counts and closed refusal tokens only; never a
movement's text.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.logging import get_logger
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.transactions.classification_job import (
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobItem,
    ClassificationJobStatus,
)
from ...domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ...domain.transactions.errors import (
    TransactionCatalogueError,
    TransactionNotFoundError,
    TransactionPersistenceError,
    TransactionValidationError,
)
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, require_exact_ledger_action_ports
from .classification_job_contracts import (
    LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID,
    LedgerClassifyJobAcceptedProposal,
    LedgerClassifyJobApplyItemResult,
    LedgerClassifyJobApplyRefusal,
    LedgerClassifyJobApplyRequest,
    LedgerClassifyJobApplyResult,
    LedgerClassifyJobProjection,
)
from .classification_job_errors import (
    ClassificationJobStaleRevisionError,
    ClassificationJobStateRefusedError,
    ClassificationJobUnknownError,
)
from .classification_job_ports import ClassificationJobApplyPorts
from .classification_job_repository import (
    ClassificationJobNotFoundError,
    ClassificationJobRepository,
    ClassificationJobRevisionConflictError,
)
from .classification_job_run import movement_revision_id
from .llm_classification_ports import LLMClassificationSuggestion
from .llm_review_execution import apply_reviewed_classification
from .persistence_ports import LedgerPersistenceConflictError
from .read_access import resolve_ledger_commit_access

__all__ = [
    "ClassificationJobApplyExecutor",
    "build_ledger_classify_job_apply_definition",
    "build_ledger_classify_job_apply_registration",
    "resolve_ledger_classify_job_apply_access",
]

_log = get_logger(__name__)

_APPLY_CAPABILITIES: Final = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    # Each accepted proposal names the movement revision it was made against, so a replay
    # meets an applied movement whose revision moved and is refused as stale, never applied twice.
    replay=OperationReplayPolicy.NONE,
    baseline=OperationBaselinePolicy.NONE,
    # The request names the profile's movements, so it is kept by secure reference.
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.NONE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)

_WRITE_ATTEMPTS: Final = 3
"""How often the job write re-reads the job after a run's write moved it first."""

_APPLY_REASON_PREFIX: Final = "ledger.classify.job.apply:"
"""The applied classification's reason names the job it was accepted from; the model's own reason is not kept."""


@dataclass(frozen=True, slots=True)
class _Decided:
    """One accepted proposal's outcome: applied, or refused with its cause."""

    movement_id: str
    refusal: LedgerClassifyJobApplyRefusal | None = None

    def result(self) -> LedgerClassifyJobApplyItemResult:
        return LedgerClassifyJobApplyItemResult(
            movement_id=self.movement_id,
            outcome="applied" if self.refusal is None else "refused",
            refusal=self.refusal,
        )


def _accepted_item(
    job: ClassificationJob, accepted: LedgerClassifyJobAcceptedProposal
) -> ClassificationJobItem | LedgerClassifyJobApplyRefusal:
    """Return the job item an accepted proposal names, or why it holds no proposal to apply."""
    item = next((item for item in job.items if item.movement_id == accepted.movement_id), None)
    if item is None:
        return LedgerClassifyJobApplyRefusal.NOT_IN_JOB
    if item.state is ClassificationItemState.STALE:
        return LedgerClassifyJobApplyRefusal.STALE
    proposal = item.proposal
    if (
        item.state is not ClassificationItemState.PROPOSED
        or proposal is None
        or proposal.movement_revision_id != accepted.movement_revision_id
    ):
        return LedgerClassifyJobApplyRefusal.NOT_PROPOSED
    return item


def _share_refusal(
    classification: BusinessClassification, business_pct: Decimal | None
) -> LedgerClassifyJobApplyRefusal | None:
    if classification is BusinessClassification.MIXED and business_pct is None:
        return LedgerClassifyJobApplyRefusal.BUSINESS_PCT_REQUIRED
    if classification is not BusinessClassification.MIXED and business_pct is not None:
        return LedgerClassifyJobApplyRefusal.BUSINESS_PCT_NOT_APPLICABLE
    return None


def _apply_one(
    job: ClassificationJob,
    accepted: LedgerClassifyJobAcceptedProposal,
    *,
    ledger: LedgerActionPorts,
    operation: PinnedAuthorityOperation,
    bucket_id: str,
    actor: str,
) -> _Decided:
    """Apply one accepted proposal against the movement exactly as its proposal read it."""
    movement_id = accepted.movement_id
    item = _accepted_item(job, accepted)
    if isinstance(item, LedgerClassifyJobApplyRefusal):
        return _Decided(movement_id, item)
    proposal = item.proposal
    if proposal is None:
        return _Decided(movement_id, LedgerClassifyJobApplyRefusal.NOT_PROPOSED)
    business_pct = None if accepted.business_pct is None else Decimal(accepted.business_pct)
    share_refusal = _share_refusal(proposal.classification, business_pct)
    if share_refusal is not None:
        return _Decided(movement_id, share_refusal)
    with validating_governed_facts(operation):
        current = ledger.transaction_repository.load().transactions.get(movement_id)
        if current is None or current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            return _Decided(movement_id, LedgerClassifyJobApplyRefusal.MOVEMENT_NOT_FOUND)
        if movement_revision_id(current) != proposal.movement_revision_id:
            return _Decided(movement_id, LedgerClassifyJobApplyRefusal.STALE)
        try:
            suggestion = LLMClassificationSuggestion.model_validate(
                {
                    "transaction_id": movement_id,
                    "provenance": proposal.provenance,
                    "classification": proposal.classification,
                    "category": proposal.category,
                    "confidence": proposal.confidence,
                    "reason": _APPLY_REASON_PREFIX + job.job_id,
                    "multiple_components": proposal.multiple_components,
                }
            )
        except ValidationError:
            # The registry the ledger reads now no longer holds the proposed category token.
            return _Decided(movement_id, LedgerClassifyJobApplyRefusal.CATEGORY_UNAVAILABLE)
    try:
        apply_reviewed_classification(
            suggestion,
            bucket_id=bucket_id,
            baseline=current,
            business_pct=business_pct,
            actor=actor,
            ports=ledger,
            operation=operation,
        )
    except LedgerPersistenceConflictError:
        # The movement changed between this read and the guarded write.
        return _Decided(movement_id, LedgerClassifyJobApplyRefusal.STALE)
    except TransactionNotFoundError:
        return _Decided(movement_id, LedgerClassifyJobApplyRefusal.MOVEMENT_NOT_FOUND)
    except TransactionPersistenceError:
        # Storage failed: what was applied before stays applied, and the operation reports the failure.
        raise
    except (TransactionCatalogueError, TransactionValidationError):
        return _Decided(movement_id, LedgerClassifyJobApplyRefusal.REJECTED)
    return _Decided(movement_id)


def _marked_job(job: ClassificationJob, decided: Sequence[_Decided]) -> ClassificationJob | None:
    """Mark applied and stale items on ``job``; ``None`` when nothing on the job changes.

    Only an item still holding the proposal that was applied or went stale is
    marked; one a concurrent write moved on is left as that write left it.
    """
    applied = {outcome.movement_id for outcome in decided if outcome.refusal is None}
    stale = {outcome.movement_id for outcome in decided if outcome.refusal is LedgerClassifyJobApplyRefusal.STALE}
    items = tuple(
        item.transitioned(ClassificationItemState.APPLIED)
        if item.state is ClassificationItemState.PROPOSED and item.movement_id in applied
        else item.transitioned(ClassificationItemState.STALE)
        if item.state is ClassificationItemState.PROPOSED and item.movement_id in stale
        else item
        for item in job.items
    )
    if items == job.items:
        return None
    return job.successor(at=max(now(), job.updated_at), items=items)


def _stored_job(repository: ClassificationJobRepository, job_id: str) -> ClassificationJob:
    try:
        return repository.get(job_id)
    except ClassificationJobNotFoundError as exc:
        raise ClassificationJobUnknownError from exc


def _marked(repository: ClassificationJobRepository, job_id: str, decided: Sequence[_Decided]) -> ClassificationJob:
    """Store the job with its applied and stale items marked, re-reading it after a concurrent write."""
    attempts_left = _WRITE_ATTEMPTS
    while True:
        stored = _stored_job(repository, job_id)
        changed = _marked_job(stored, decided)
        if changed is None:
            return stored
        try:
            repository.update(changed)
        except ClassificationJobRevisionConflictError as exc:
            attempts_left -= 1
            if attempts_left == 0:
                raise ClassificationJobStaleRevisionError(
                    expected_revision=stored.revision, stored_revision=None
                ) from exc
            continue
        except ClassificationJobNotFoundError as exc:
            raise ClassificationJobUnknownError from exc
        return changed


def _refusals(decided: Sequence[_Decided]) -> str:
    counted = Counter(outcome.refusal.value for outcome in decided if outcome.refusal is not None)
    return ",".join(f"{refusal}:{count}" for refusal, count in sorted(counted.items())) or "none"


class ClassificationJobApplyExecutor:
    """Apply the proposals a person accepted from one job, each on its own, and mark them on the job."""

    def __init__(
        self, ports: ClassificationJobApplyPorts, *, execution_caller_reader: OperationExecutionCallerReader | None
    ) -> None:
        """Bind the job repository, the ledger and the reader of who submitted the apply."""
        self._ports = ports
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self, request: OperationRequest[LedgerClassifyJobApplyRequest], context: OperationExecutorContext
    ) -> str:
        """Check the job at the revision seen, apply each accepted proposal, then mark the job and publish it."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID)
        repository = await asyncio.to_thread(self._ports.jobs, bucket_id=bucket_id)
        job = await asyncio.to_thread(_stored_job, repository, payload.job_id)
        if job.revision != payload.expected_revision:
            raise ClassificationJobStaleRevisionError(
                expected_revision=payload.expected_revision, stored_revision=job.revision
            )
        if job.status is ClassificationJobStatus.DISMISSED:
            raise ClassificationJobStateRefusedError(action="apply", job_status=job.status.value)
        operation = context.authority_operation
        ledger = await asyncio.to_thread(self._ports.ledger, bucket_id=bucket_id, operation=operation)
        require_exact_ledger_action_ports(ledger, bucket_id=bucket_id, operation=operation)
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=bucket_id)

        def apply_all() -> tuple[tuple[_Decided, ...], ClassificationJob]:
            decided = tuple(
                _apply_one(job, accepted, ledger=ledger, operation=operation, bucket_id=bucket_id, actor=actor)
                for accepted in payload.accepted
            )
            return decided, _marked(repository, job.job_id, decided)

        async def store() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                decided, marked = await asyncio.to_thread(apply_all)
                wrote = any(outcome.refusal is None for outcome in decided) or marked.revision != job.revision
                await context.events.effect(OperationEffect.UPDATED if wrote else OperationEffect.NONE)
                _log.info(
                    "ledger classification apply job=%s revision=%d applied=%d refused=%d refusals=%s",
                    marked.job_id,
                    marked.revision,
                    sum(outcome.refusal is None for outcome in decided),
                    sum(outcome.refusal is not None for outcome in decided),
                    _refusals(decided),
                )
                result = LedgerClassifyJobApplyResult(
                    profile_id=payload.profile_id,
                    job=LedgerClassifyJobProjection.from_job(marked),
                    items=tuple(outcome.result() for outcome in decided),
                )
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(store(), task_name="ledger-classify-job-apply")


def build_ledger_classify_job_apply_definition(
    ports: ClassificationJobApplyPorts, *, execution_caller_reader: OperationExecutionCallerReader | None = None
) -> OperationDefinition:
    """Declare one recorded, revision-guarded apply whose refusals carry their typed detail."""
    return build_single_phase_definition(
        definition_id=LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID,
        request_type=LedgerClassifyJobApplyRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerClassifyJobApplyResult,
        executor_type=ClassificationJobApplyExecutor,
        build=lambda: ClassificationJobApplyExecutor(ports, execution_caller_reader=execution_caller_reader),
        capabilities=_APPLY_CAPABILITIES,
        # A refusal names the job's status or revisions; never a movement.
        public_error_detail=True,
    )


def resolve_ledger_classify_job_apply_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger commit rights for the exact profile."""
    if request.definition_id != LEDGER_CLASSIFY_JOB_APPLY_DEFINITION_ID or not isinstance(
        request.payload, LedgerClassifyJobApplyRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_classify_job_apply_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and result schemas at the canonical registry."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerClassifyJobApplyResult,
        access_resolver=resolve_ledger_classify_job_apply_access,
    )
