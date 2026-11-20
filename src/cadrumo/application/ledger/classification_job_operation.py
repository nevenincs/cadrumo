"""Registered exact-profile enqueue, cancel, retry and dismiss of ledger classification jobs.

An enqueue resolves the movements its scope names in the profile's own
catalogue, resolves the lane the agent service would read with, and stores a
queued job with every movement pending. It runs no model and writes no ledger
fact. A lane that reads off this computer needs a person-granted consent the
job carries; without one the enqueue is refused with the ledger's typed
off-host consent refusal and its two remedies, before anything is stored.

A cancel, retry or dismiss names the revision the person saw. A job that moved
since is refused rather than changed, and each change follows the job's own
transition tables: a cancel cancels the movements not yet asked and leaves an
in-flight movement to settle first, a retry asks again for the failed and
interrupted movements, and a dismiss puts away a finished job without applying
anything it proposed.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.model_runs import ModelRunRefusalCode, ModelRunTaskKind

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from ...core.time.clock import now
from ...domain.transactions.classification_job import (
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobItem,
    ClassificationJobLane,
    ClassificationJobScope,
    ClassificationJobScopeKind,
    ClassificationJobStatus,
)
from ...domain.transactions.dates import transaction_filing_date
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import TransactionCatalogue
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .classification_job_contracts import (
    LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID,
    LedgerClassifyJobCancelRequest,
    LedgerClassifyJobChangeResult,
    LedgerClassifyJobDismissRequest,
    LedgerClassifyJobEnqueueRequest,
    LedgerClassifyJobProjection,
    LedgerClassifyJobRetryRequest,
)
from .classification_job_errors import (
    CLASSIFICATION_JOB_NOTHING_TO_RETRY_LOCALE_KEY,
    ClassificationJobEmptyScopeError,
    ClassificationJobMovementUnknownError,
    ClassificationJobStaleRevisionError,
    ClassificationJobStateRefusedError,
    ClassificationJobUnknownError,
)
from .classification_job_ports import (
    CLASSIFICATION_READING_ROLE,
    ClassificationJobEnqueuePorts,
    ClassificationJobRepositoryFactory,
)
from .classification_job_repository import (
    ClassificationJobNotFoundError,
    ClassificationJobRepository,
    ClassificationJobRevisionConflictError,
)
from .evidence_errors import LedgerOffHostConsentRequiredError
from .off_host_consent_refusal import off_host_consent_required
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from .read_access import resolve_ledger_commit_access

__all__ = [
    "ClassificationJobChangeExecutor",
    "ClassificationJobEnqueueExecutor",
    "build_ledger_classify_job_change_definition",
    "build_ledger_classify_job_change_registration",
    "build_ledger_classify_job_enqueue_definition",
    "build_ledger_classify_job_enqueue_registration",
    "cancelled_job",
    "dismissed_job",
    "resolve_ledger_classify_job_change_access",
    "resolve_ledger_classify_job_enqueue_access",
    "retried_job",
]

type _ChangeRequest = LedgerClassifyJobCancelRequest | LedgerClassifyJobRetryRequest | LedgerClassifyJobDismissRequest
type _ChangeOutcome = Literal["cancelled", "cancelling", "retried", "dismissed"]

_ENQUEUE_CAPABILITIES: Final = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    # Each enqueue stores a new job, so a replayed submission would store a second one.
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

_CANCELLABLE_AT_ONCE: Final = frozenset({ClassificationItemState.PENDING, ClassificationItemState.UNKNOWN})
_ASKED_AGAIN: Final = frozenset({ClassificationItemState.FAILED, ClassificationItemState.UNKNOWN})
_RETRYABLE_STATUSES: Final = frozenset(
    {
        ClassificationJobStatus.QUEUED,
        ClassificationJobStatus.INTERRUPTED,
        ClassificationJobStatus.SETTLED,
        ClassificationJobStatus.CANCELLED,
    }
)
_DISMISSABLE_STATUSES: Final = frozenset({ClassificationJobStatus.SETTLED, ClassificationJobStatus.CANCELLED})


def _require_definition(requested: str, definition_id: str) -> None:
    if requested != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


# -- enqueue ---------------------------------------------------------------------------------------------------------


def _scope_movements(payload: LedgerClassifyJobEnqueueRequest, catalogue: TransactionCatalogue) -> tuple[str, ...]:
    """Return the movements the scope names, refusing an empty scope and a movement this profile does not hold."""
    if payload.scope is ClassificationJobScopeKind.PERIOD:
        start, end = payload.period_start, payload.period_end
        if start is None or end is None:
            raise ClassificationJobEmptyScopeError(scope=payload.scope.value)
        movements = tuple(
            sorted(
                transaction_id
                for transaction_id, transaction in catalogue.transactions.items()
                if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
                and start <= transaction_filing_date(transaction) <= end
            )
        )
    else:
        unknown = sum(movement_id not in catalogue.transactions for movement_id in payload.movement_ids)
        if unknown:
            raise ClassificationJobMovementUnknownError(unknown_count=unknown)
        movements = payload.movement_ids
    if not movements:
        raise ClassificationJobEmptyScopeError(scope=payload.scope.value)
    return movements


def _off_host_consent_missing() -> LedgerOffHostConsentRequiredError:
    """The ledger's off-host consent refusal, stating the agent's own refusal code as its fact."""
    return off_host_consent_required(
        ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE,
            facts={
                "model_run_refusal": ModelRunRefusalCode.CONSENT_MISSING.value,
                "model_role": CLASSIFICATION_READING_ROLE.value,
                "consent_token_present": False,
            },
        )
    )


class ClassificationJobEnqueueExecutor:
    """Store one queued job for the movements a scope names, on the lane the agent would read with."""

    def __init__(self, ports: ClassificationJobEnqueuePorts) -> None:
        """Bind the job repository, the movement catalogue and the lane lookup."""
        self._ports = ports

    async def execute(
        self, request: OperationRequest[LedgerClassifyJobEnqueueRequest], context: OperationExecutorContext
    ) -> str:
        """Resolve the scope and the lane, then store the job and publish it."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_definition(request.definition_id, LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID)
        catalogue = await asyncio.to_thread(
            self._ports.movements, bucket_id=bucket_id, operation=context.authority_operation
        )
        movement_ids = _scope_movements(payload, catalogue)
        lane = await self._ports.resolve_lane(CLASSIFICATION_READING_ROLE, task_kind=ModelRunTaskKind.CLASSIFICATION)
        if lane.reads_off_host:
            # No consent is bound to an enqueue yet, so an off-host lane is refused before anything is stored.
            raise _off_host_consent_missing()
        job = ClassificationJob.enqueue(
            bucket_id=bucket_id,
            scope=ClassificationJobScope(
                kind=payload.scope, period_start=payload.period_start, period_end=payload.period_end
            ),
            movement_ids=movement_ids,
            lane=ClassificationJobLane(
                provider_id=lane.provider_id,
                transport=lane.transport,
                model=lane.model,
                reads_off_host=lane.reads_off_host,
            ),
            consent=None,
            at=now(),
        )
        repository = await asyncio.to_thread(self._ports.jobs, bucket_id=bucket_id)
        result = LedgerClassifyJobChangeResult(
            profile_id=payload.profile_id, outcome="enqueued", job=LedgerClassifyJobProjection.from_job(job)
        )

        async def store() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                await asyncio.to_thread(repository.create, job)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(store(), task_name="ledger-classify-job-enqueue")


def build_ledger_classify_job_enqueue_definition(ports: ClassificationJobEnqueuePorts) -> OperationDefinition:
    """Declare one recorded, exact-profile enqueue whose refusals carry their typed detail."""
    return build_single_phase_definition(
        definition_id=LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID,
        request_type=LedgerClassifyJobEnqueueRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerClassifyJobChangeResult,
        executor_type=ClassificationJobEnqueueExecutor,
        build=lambda: ClassificationJobEnqueueExecutor(ports),
        capabilities=_ENQUEUE_CAPABILITIES,
        # A refused lane lookup carries the agent's verdict and the step that puts
        # it right; its context names refusal codes and counts, never a movement.
        public_error_detail=True,
    )


def resolve_ledger_classify_job_enqueue_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger commit rights for the exact profile."""
    if request.definition_id != LEDGER_CLASSIFY_JOB_ENQUEUE_DEFINITION_ID or not isinstance(
        request.payload, LedgerClassifyJobEnqueueRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_classify_job_enqueue_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and result schemas at the canonical registry."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerClassifyJobChangeResult,
        access_resolver=resolve_ledger_classify_job_enqueue_access,
    )


# -- cancel, retry, dismiss --------------------------------------------------------------------------------------------


def cancelled_job(job: ClassificationJob, *, at: datetime) -> tuple[ClassificationJob, _ChangeOutcome]:
    """Cancel every movement not yet asked; a job with a movement in flight waits for it to settle.

    Raises:
        ClassificationJobStateRefusedError: The job is cancelling, finished or dismissed.
    """
    if job.status in {ClassificationJobStatus.QUEUED, ClassificationJobStatus.INTERRUPTED}:
        status, outcome = ClassificationJobStatus.CANCELLED, "cancelled"
    elif job.status is ClassificationJobStatus.RUNNING:
        status, outcome = ClassificationJobStatus.CANCELLING, "cancelling"
    else:
        raise ClassificationJobStateRefusedError(action="cancel", job_status=job.status.value)
    items = tuple(
        item.transitioned(ClassificationItemState.CANCELLED) if item.state in _CANCELLABLE_AT_ONCE else item
        for item in job.items
    )
    return job.successor(at=at, status=status, items=items), outcome


def retried_job(job: ClassificationJob, *, at: datetime) -> tuple[ClassificationJob, _ChangeOutcome]:
    """Return every failed and interrupted movement to pending and queue the job again.

    Raises:
        ClassificationJobStateRefusedError: A run owns the job, the job is
            dismissed, or it holds no failed or interrupted movement.
    """
    if job.status not in _RETRYABLE_STATUSES:
        raise ClassificationJobStateRefusedError(action="retry", job_status=job.status.value)
    if not any(item.state in _ASKED_AGAIN for item in job.items):
        raise ClassificationJobStateRefusedError(
            action="retry",
            job_status=job.status.value,
            translated_message=CLASSIFICATION_JOB_NOTHING_TO_RETRY_LOCALE_KEY,
        )
    items: tuple[ClassificationJobItem, ...] = tuple(
        item.transitioned(ClassificationItemState.PENDING) if item.state in _ASKED_AGAIN else item for item in job.items
    )
    return job.successor(at=at, status=ClassificationJobStatus.QUEUED, items=items), "retried"


def dismissed_job(job: ClassificationJob, *, at: datetime) -> tuple[ClassificationJob, _ChangeOutcome]:
    """Put away a settled or cancelled job; nothing it proposed is applied or removed from the ledger.

    Raises:
        ClassificationJobStateRefusedError: The job has not finished, or is already dismissed.
    """
    if job.status not in _DISMISSABLE_STATUSES:
        raise ClassificationJobStateRefusedError(action="dismiss", job_status=job.status.value)
    return job.successor(at=at, status=ClassificationJobStatus.DISMISSED), "dismissed"


@dataclass(frozen=True, slots=True)
class _ChangeDeclaration:
    request_type: type[_ChangeRequest]
    change: Callable[[ClassificationJob], tuple[ClassificationJob, _ChangeOutcome]]
    task_name: str


def _changes(clock: Callable[[], datetime]) -> dict[str, _ChangeDeclaration]:
    def at(job: ClassificationJob) -> datetime:
        # A job's update time never goes back; a wall clock stepped back must not turn a change into a failure.
        return max(clock(), job.updated_at)

    return {
        LEDGER_CLASSIFY_JOB_CANCEL_DEFINITION_ID: _ChangeDeclaration(
            LedgerClassifyJobCancelRequest, lambda job: cancelled_job(job, at=at(job)), "ledger-classify-job-cancel"
        ),
        LEDGER_CLASSIFY_JOB_RETRY_DEFINITION_ID: _ChangeDeclaration(
            LedgerClassifyJobRetryRequest, lambda job: retried_job(job, at=at(job)), "ledger-classify-job-retry"
        ),
        LEDGER_CLASSIFY_JOB_DISMISS_DEFINITION_ID: _ChangeDeclaration(
            LedgerClassifyJobDismissRequest, lambda job: dismissed_job(job, at=at(job)), "ledger-classify-job-dismiss"
        ),
    }


_CHANGES: Final = _changes(now)


def _stored_job(repository: ClassificationJobRepository, job_id: str) -> ClassificationJob:
    try:
        return repository.get(job_id)
    except ClassificationJobNotFoundError as exc:
        raise ClassificationJobUnknownError from exc


class ClassificationJobChangeExecutor:
    """Change one job at the revision the person saw, as its definition declares."""

    def __init__(self, definition_id: str, repository_factory: ClassificationJobRepositoryFactory) -> None:
        """Bind the change this definition makes and the profile's job repository factory."""
        self._definition_id = definition_id
        self._declaration = _CHANGES[definition_id]
        self._repository_factory = repository_factory

    async def execute(self, request: OperationRequest[_ChangeRequest], context: OperationExecutorContext) -> str:
        """Check the stored job against the revision asked about, then store its change and publish it."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_definition(request.definition_id, self._definition_id)
        if type(payload) is not self._declaration.request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(self._definition_id)
        repository = await asyncio.to_thread(self._repository_factory, bucket_id=bucket_id)
        job = await asyncio.to_thread(_stored_job, repository, payload.job_id)
        if job.revision != payload.expected_revision:
            raise ClassificationJobStaleRevisionError(
                expected_revision=payload.expected_revision, stored_revision=job.revision
            )
        changed, outcome = self._declaration.change(job)
        result = LedgerClassifyJobChangeResult(
            profile_id=payload.profile_id, outcome=outcome, job=LedgerClassifyJobProjection.from_job(changed)
        )

        async def store() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    await asyncio.to_thread(repository.update, changed)
                except ClassificationJobRevisionConflictError as exc:
                    # The guarded write refused before writing: the job moved between the read and the write.
                    await context.events.effect(OperationEffect.NONE)
                    raise ClassificationJobStaleRevisionError(
                        expected_revision=payload.expected_revision, stored_revision=None
                    ) from exc
                except ClassificationJobNotFoundError as exc:
                    await context.events.effect(OperationEffect.NONE)
                    raise ClassificationJobUnknownError from exc
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(store(), task_name=self._declaration.task_name)


def build_ledger_classify_job_change_definition(
    definition_id: str, repository_factory: ClassificationJobRepositoryFactory
) -> OperationDefinition:
    """Declare one recorded, revision-guarded job change whose refusals carry their typed detail."""
    declaration = _CHANGES.get(definition_id)
    if declaration is None:
        raise ValueError("unknown ledger classification job change definition")
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=declaration.request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerClassifyJobChangeResult,
        executor_type=ClassificationJobChangeExecutor,
        build=lambda: ClassificationJobChangeExecutor(definition_id, repository_factory),
        # A change names the revision it follows, so a replay meets a newer revision and is refused.
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
        public_error_detail=True,
    )


def resolve_ledger_classify_job_change_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger commit rights for the exact profile and the definition's own request."""
    declaration = _CHANGES.get(request.definition_id)
    if declaration is None or type(request.payload) is not declaration.request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if not isinstance(
        payload, LedgerClassifyJobCancelRequest | LedgerClassifyJobRetryRequest | LedgerClassifyJobDismissRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def build_ledger_classify_job_change_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and result schemas at the canonical registry."""
    if definition.definition_id not in _CHANGES or definition.request_type is not (
        _CHANGES[definition.definition_id].request_type
    ):
        raise ValueError("invalid ledger classification job change definition binding")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerClassifyJobChangeResult,
        access_resolver=resolve_ledger_classify_job_change_access,
    )
