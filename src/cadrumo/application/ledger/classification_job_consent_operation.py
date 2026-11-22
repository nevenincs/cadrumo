"""Registered exact-profile grant and withdrawal of a ledger classification job's off-host reads.

An authorise records the person's grant, for the lane they saw, in the consent
ledger, and binds the job to it at the next revision. The lane must be the one
the agent reads with now: a grant for another lane is refused, never moved. The
job takes that lane if the agent's lane changed since the job was enqueued.
The movements that failed for want of a usable consent, or because the lane
changed, are asked again under the new grant; a settled job is queued again.

A revoke withdraws the grant the job runs under, from the next read onwards. A
grant for the agent session or a remembered grant covers other jobs too, and
the revocation withdraws it for them as well. The job record is left as it is:
its next run meets the withdrawn grant and refuses with that cause.

Both name the revision the person saw, and neither runs a model or writes a
ledger fact.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Final

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.model_runs import ModelRunTaskKind

from ...core.async_cleanup import await_cancellation_complete
from ...core.model_roles import ModelRole
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.transactions.classification_job import (
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobConsent,
    ClassificationJobLane,
    ClassificationJobStatus,
)
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .classification_job_consent import CONSENT_FAILURE_CAUSES, granted_lane
from .classification_job_contracts import (
    LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID,
    LedgerClassifyJobAuthoriseRequest,
    LedgerClassifyJobChangeResult,
    LedgerClassifyJobProjection,
    LedgerClassifyJobRevokeConsentRequest,
)
from .classification_job_errors import (
    ClassificationJobConsentNotNeededError,
    ClassificationJobStaleRevisionError,
    ClassificationJobStateRefusedError,
    ClassificationJobUnknownError,
)
from .classification_job_ports import ClassificationJobConsentPorts
from .classification_job_repository import (
    ClassificationJobNotFoundError,
    ClassificationJobRepository,
    ClassificationJobRevisionConflictError,
)
from .evidence_errors import LedgerOffHostConsentRequiredError
from .read_access import resolve_ledger_commit_access

__all__ = [
    "ClassificationJobAuthoriseExecutor",
    "ClassificationJobRevokeConsentExecutor",
    "authorised_job",
    "build_ledger_classify_job_authorise_definition",
    "build_ledger_classify_job_consent_registration",
    "build_ledger_classify_job_revoke_consent_definition",
    "resolve_ledger_classify_job_consent_access",
]

_AUTHORISABLE: Final = frozenset(
    {ClassificationJobStatus.QUEUED, ClassificationJobStatus.INTERRUPTED, ClassificationJobStatus.SETTLED}
)
"""A job no run owns and the person has not cancelled or put away."""

type _ConsentRequest = LedgerClassifyJobAuthoriseRequest | LedgerClassifyJobRevokeConsentRequest

_REQUEST_TYPES: Final[dict[str, type[_ConsentRequest]]] = {
    LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID: LedgerClassifyJobAuthoriseRequest,
    LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID: LedgerClassifyJobRevokeConsentRequest,
}


def authorised_job(
    job: ClassificationJob, *, lane: ClassificationJobLane, consent: ClassificationJobConsent, at: datetime
) -> ClassificationJob:
    """Bind ``job`` to a new grant on ``lane`` and ask again for the movements a missing grant or lane failed.

    Raises:
        ClassificationJobStateRefusedError: A run owns the job, or it was
            cancelled or put away.
    """
    if job.status not in _AUTHORISABLE:
        raise ClassificationJobStateRefusedError(action="authorise", job_status=job.status.value)
    items = tuple(
        item.transitioned(ClassificationItemState.PENDING)
        if item.state is ClassificationItemState.FAILED and item.failure_cause in CONSENT_FAILURE_CAUSES
        else item
        for item in job.items
    )
    pending = any(item.state is ClassificationItemState.PENDING for item in items)
    status = ClassificationJobStatus.QUEUED if job.status is ClassificationJobStatus.SETTLED and pending else job.status
    return job.authorised(at=at, lane=lane, consent=consent, status=status, items=items)


def _stored_job(repository: ClassificationJobRepository, job_id: str) -> ClassificationJob:
    try:
        return repository.get(job_id)
    except ClassificationJobNotFoundError as exc:
        raise ClassificationJobUnknownError from exc


class _ConsentChange:
    """The shared admission of a consent change: the exact profile, the stored job and the revision seen."""

    def __init__(self, definition_id: str, ports: ClassificationJobConsentPorts) -> None:
        self._definition_id = definition_id
        self._ports = ports

    async def _admitted[RequestT: (LedgerClassifyJobAuthoriseRequest, LedgerClassifyJobRevokeConsentRequest)](
        self, request: OperationRequest[RequestT], context: OperationExecutorContext
    ) -> tuple[ClassificationJobRepository, ClassificationJob]:
        payload = request.payload
        if request.definition_id != self._definition_id or type(payload) is not _REQUEST_TYPES[self._definition_id]:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(self._definition_id)
        repository = await asyncio.to_thread(self._ports.jobs, bucket_id=str(payload.profile_id))
        job = await asyncio.to_thread(_stored_job, repository, payload.job_id)
        if job.revision != payload.expected_revision:
            raise ClassificationJobStaleRevisionError(
                expected_revision=payload.expected_revision, stored_revision=job.revision
            )
        return repository, job

    @staticmethod
    async def _publish(
        context: OperationExecutorContext, write: Callable[[], Awaitable[tuple[BaseModel, bool]]], *, task_name: str
    ) -> str:
        async def store() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result, wrote = await write()
                await context.events.effect(OperationEffect.UPDATED if wrote else OperationEffect.NONE)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(store(), task_name=task_name)


class ClassificationJobAuthoriseExecutor(_ConsentChange):
    """Record a person's grant for the lane the agent reads with, and bind the job to it."""

    def __init__(self, ports: ClassificationJobConsentPorts) -> None:
        """Bind the job repository, the lane lookup and the consent ledger."""
        super().__init__(LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID, ports)

    async def execute(
        self, request: OperationRequest[LedgerClassifyJobAuthoriseRequest], context: OperationExecutorContext
    ) -> str:
        """Check the job and the lane, record the grant, then store the job under it."""
        payload = request.payload
        repository, job = await self._admitted(request, context)
        if job.status not in _AUTHORISABLE:
            raise ClassificationJobStateRefusedError(action="authorise", job_status=job.status.value)
        lane = await self._ports.resolve_lane(ModelRole.TEXT_EXTRACTION, task_kind=ModelRunTaskKind.CLASSIFICATION)
        job_lane = granted_lane(payload.consent, lane)
        bucket_id = str(payload.profile_id)

        def record() -> LedgerClassifyJobChangeResult:
            consent = self._ports.consent.grant(
                bucket_id=bucket_id,
                lane=job_lane,
                scope=payload.consent.scope,
                job_id=job.job_id,
                surface=LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID,
            )
            changed = authorised_job(job, lane=job_lane, consent=consent, at=max(now(), job.updated_at))
            try:
                repository.update(changed)
            except ClassificationJobRevisionConflictError as exc:
                # The grant is recorded; the job moved before it could be bound, so the person reads it again.
                raise ClassificationJobStaleRevisionError(
                    expected_revision=payload.expected_revision, stored_revision=None
                ) from exc
            except ClassificationJobNotFoundError as exc:
                raise ClassificationJobUnknownError from exc
            return LedgerClassifyJobChangeResult(
                profile_id=payload.profile_id, outcome="authorised", job=LedgerClassifyJobProjection.from_job(changed)
            )

        async def write() -> tuple[BaseModel, bool]:
            try:
                return await asyncio.to_thread(record), True
            except LedgerOffHostConsentRequiredError:
                # A standing bar refused the grant before anything was recorded.
                await context.events.effect(OperationEffect.NONE)
                raise

        return await self._publish(context, write, task_name="ledger-classify-job-authorise")


class ClassificationJobRevokeConsentExecutor(_ConsentChange):
    """Withdraw the grant a job runs under, from the next read onwards."""

    def __init__(self, ports: ClassificationJobConsentPorts) -> None:
        """Bind the job repository and the consent ledger."""
        super().__init__(LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID, ports)

    async def execute(
        self, request: OperationRequest[LedgerClassifyJobRevokeConsentRequest], context: OperationExecutorContext
    ) -> str:
        """Record the revocation of the job's grant; the job record is left as it is."""
        payload = request.payload
        _repository, job = await self._admitted(request, context)
        consent = job.consent
        if consent is None:
            raise ClassificationJobConsentNotNeededError
        bucket_id = str(payload.profile_id)

        def record() -> tuple[BaseModel, bool]:
            # A grant already withdrawn stays withdrawn; nothing more is recorded.
            wrote = self._ports.consent.revoke(
                bucket_id=bucket_id, consent=consent, surface=LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID
            )
            result = LedgerClassifyJobChangeResult(
                profile_id=payload.profile_id, outcome="consent_revoked", job=LedgerClassifyJobProjection.from_job(job)
            )
            return result, wrote

        async def write() -> tuple[BaseModel, bool]:
            return await asyncio.to_thread(record)

        return await self._publish(context, write, task_name="ledger-classify-job-revoke-consent")


def build_ledger_classify_job_authorise_definition(ports: ClassificationJobConsentPorts) -> OperationDefinition:
    """Declare one recorded, revision-guarded grant whose refusals carry their typed detail."""
    return build_single_phase_definition(
        definition_id=LEDGER_CLASSIFY_JOB_AUTHORISE_DEFINITION_ID,
        request_type=LedgerClassifyJobAuthoriseRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerClassifyJobChangeResult,
        executor_type=ClassificationJobAuthoriseExecutor,
        build=lambda: ClassificationJobAuthoriseExecutor(ports),
        # A grant names the revision it follows, so a replay meets a newer revision and is refused.
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
        # A refused lane names the lane the agent reads with; a refused grant names its standing; never a movement.
        public_error_detail=True,
    )


def build_ledger_classify_job_revoke_consent_definition(ports: ClassificationJobConsentPorts) -> OperationDefinition:
    """Declare one recorded, revision-guarded withdrawal whose refusals carry their typed detail."""
    return build_single_phase_definition(
        definition_id=LEDGER_CLASSIFY_JOB_REVOKE_CONSENT_DEFINITION_ID,
        request_type=LedgerClassifyJobRevokeConsentRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerClassifyJobChangeResult,
        executor_type=ClassificationJobRevokeConsentExecutor,
        build=lambda: ClassificationJobRevokeConsentExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
        public_error_detail=True,
    )


def resolve_ledger_classify_job_consent_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger commit rights for the exact profile and the definition's own request."""
    request_type = _REQUEST_TYPES.get(request.definition_id)
    payload = request.payload
    if request_type is None or type(payload) is not request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(payload, LedgerClassifyJobAuthoriseRequest | LedgerClassifyJobRevokeConsentRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def build_ledger_classify_job_consent_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and result schemas at the canonical registry."""
    if _REQUEST_TYPES.get(definition.definition_id) is not definition.request_type:
        raise ValueError("invalid ledger classification job consent definition binding")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerClassifyJobChangeResult,
        access_resolver=resolve_ledger_classify_job_consent_access,
    )
