"""Registered exact-profile reads of ledger classification jobs.

The read of one job and the list of the profile's newest jobs release only the
job projections and the queue's revision, with an exact-profile, no-effect
receipt. A storage failure is a failure, never an empty queue: a window that
cannot read the queue is told so.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.transactions.classification_job import ClassificationJobStatus
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .classification_job_contracts import (
    LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID,
    LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID,
    LedgerClassifyJobListRequest,
    LedgerClassifyJobListResult,
    LedgerClassifyJobProjection,
    LedgerClassifyJobReadRequest,
    LedgerClassifyJobReadResult,
    classification_queue_revision,
)
from .classification_job_errors import ClassificationJobUnknownError
from .classification_job_ports import ClassificationJobRepositoryFactory
from .classification_job_repository import ClassificationJobNotFoundError, ClassificationJobRepository
from .read_access import resolve_ledger_read_access

__all__ = [
    "ClassificationJobListExecutor",
    "ClassificationJobReadExecutor",
    "build_ledger_classify_job_list_definition",
    "build_ledger_classify_job_list_registration",
    "build_ledger_classify_job_read_definition",
    "build_ledger_classify_job_read_registration",
    "resolve_ledger_classify_job_list_access",
    "resolve_ledger_classify_job_read_access",
]


def _read_job(
    repository: ClassificationJobRepository, payload: LedgerClassifyJobReadRequest
) -> LedgerClassifyJobReadResult:
    try:
        job = repository.get(payload.job_id)
    except ClassificationJobNotFoundError as exc:
        raise ClassificationJobUnknownError from exc
    return LedgerClassifyJobReadResult(profile_id=payload.profile_id, job=LedgerClassifyJobProjection.from_job(job))


def _list_jobs(
    repository: ClassificationJobRepository, payload: LedgerClassifyJobListRequest
) -> LedgerClassifyJobListResult:
    stored = repository.list_jobs()
    listed = [
        job
        for job in reversed(stored)
        if payload.include_dismissed or job.status is not ClassificationJobStatus.DISMISSED
    ]
    return LedgerClassifyJobListResult(
        profile_id=payload.profile_id,
        queue_revision=classification_queue_revision(stored),
        jobs=tuple(LedgerClassifyJobProjection.from_job(job) for job in listed[: payload.limit]),
        more=len(listed) > payload.limit,
    )


class ClassificationJobReadExecutor:
    """Read one job from the profile's encrypted repository."""

    def __init__(self, repository_factory: ClassificationJobRepositoryFactory) -> None:
        """Bind the profile's job repository factory."""
        self._repository_factory = repository_factory

    async def execute(
        self, request: OperationRequest[LedgerClassifyJobReadRequest], context: OperationExecutorContext
    ) -> str:
        """Read the job and publish it, or refuse an identity this profile does not hold."""
        payload = request.payload
        if request.definition_id != LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID)
        repository = await asyncio.to_thread(self._repository_factory, bucket_id=str(payload.profile_id))
        result = await asyncio.to_thread(_read_job, repository, payload)
        await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(result, written_at=now())


class ClassificationJobListExecutor:
    """List the profile's newest jobs from its encrypted repository."""

    def __init__(self, repository_factory: ClassificationJobRepositoryFactory) -> None:
        """Bind the profile's job repository factory."""
        self._repository_factory = repository_factory

    async def execute(
        self, request: OperationRequest[LedgerClassifyJobListRequest], context: OperationExecutorContext
    ) -> str:
        """Read every job, newest first within the asked bound, and publish them with the queue's revision."""
        payload = request.payload
        if request.definition_id != LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID)
        repository = await asyncio.to_thread(self._repository_factory, bucket_id=str(payload.profile_id))
        result = await asyncio.to_thread(_list_jobs, repository, payload)
        await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(result, written_at=now())


def build_ledger_classify_job_read_definition(
    repository_factory: ClassificationJobRepositoryFactory,
) -> OperationDefinition:
    """Declare one recorded read of one job; an unknown job is refused with its typed detail."""
    return build_single_phase_definition(
        definition_id=LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID,
        request_type=LedgerClassifyJobReadRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerClassifyJobReadResult,
        executor_type=ClassificationJobReadExecutor,
        build=lambda: ClassificationJobReadExecutor(repository_factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        public_error_detail=True,
    )


def build_ledger_classify_job_list_definition(
    repository_factory: ClassificationJobRepositoryFactory,
) -> OperationDefinition:
    """Declare one recorded, bounded list of the profile's jobs."""
    return build_single_phase_definition(
        definition_id=LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID,
        request_type=LedgerClassifyJobListRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerClassifyJobListResult,
        executor_type=ClassificationJobListExecutor,
        build=lambda: ClassificationJobListExecutor(repository_factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        public_error_detail=True,
    )


def _resolve_read_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    request_type: type[LedgerClassifyJobReadRequest] | type[LedgerClassifyJobListRequest],
) -> ResolvedOperationAccess:
    payload = request.payload
    if request.definition_id != definition_id or type(payload) is not request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(payload, LedgerClassifyJobReadRequest | LedgerClassifyJobListRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def resolve_ledger_classify_job_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger read rights for the exact profile."""
    return _resolve_read_access(
        request,
        context,
        definition_id=LEDGER_CLASSIFY_JOB_READ_DEFINITION_ID,
        request_type=LedgerClassifyJobReadRequest,
    )


def resolve_ledger_classify_job_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger read rights for the exact profile."""
    return _resolve_read_access(
        request,
        context,
        definition_id=LEDGER_CLASSIFY_JOB_LIST_DEFINITION_ID,
        request_type=LedgerClassifyJobListRequest,
    )


def build_ledger_classify_job_read_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and result schemas and the read-only admission policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerClassifyJobReadResult,
        access_resolver=resolve_ledger_classify_job_read_access,
    )


def build_ledger_classify_job_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and result schemas and the read-only admission policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerClassifyJobListResult,
        access_resolver=resolve_ledger_classify_job_list_access,
    )
