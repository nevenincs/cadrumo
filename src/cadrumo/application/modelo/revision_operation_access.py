"""Resolve revision mutations against the execution profile's persisted scope."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.filing_record import ModeloRecord
from ...domain.modelos.work_unit import WorkUnit
from ..operations.access_port import OperationAccessResolver
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    COMMITTING_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_single_period_admission,
)
from ..operations.models import OperationRequest
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .operation_definitions import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    ModeloExportRequest,
    ModeloWorkAmendRequest,
    ModeloWorkFileRequest,
    ModeloWorkVerifyRequest,
)
from .review_package_operation import (
    MODELO_REVIEW_PACKAGE_BUILD_OPERATION_DEFINITION_ID,
    ModeloReviewPackageBuildRequest,
)
from .revision_snapshot_operation import (
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionSnapshotRequest,
)
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory


def compose_modelo_revision_access(factory: VerificationRepositoryBundleFactory) -> OperationAccessResolver:
    """Bind exact revision and work-unit reads without inferring scope from IDs."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        filing_id, revision_id = _revision_target(request, context)
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            periods = _persisted_revision_periods(factory, request, context, filing_id, revision_id)
        return bind_operation_access_profile(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS
            if request.definition_id == MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID
            else COMMITTING_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=periods,
        )

    return resolve


def _revision_target(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> tuple[str | None, str | None]:
    target = _verify_revision_target(request)
    if target is not None:
        return target
    target = _file_revision_target(request)
    if target is not None:
        return target
    target = _amend_revision_target(request)
    if target is not None:
        return target
    target = _export_revision_target(request)
    if target is not None:
        return target
    target = _review_package_revision_target(request, context)
    if target is not None:
        return target
    target = _revision_snapshot_target(request, context)
    if target is not None:
        return target
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _verify_revision_target(request: OperationRequest[BaseModel]) -> tuple[str | None, str | None] | None:
    payload = request.payload
    if request.definition_id == MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID and isinstance(
        payload, ModeloWorkVerifyRequest
    ):
        return None, payload.calculation_revision_id
    return None


def _file_revision_target(request: OperationRequest[BaseModel]) -> tuple[str | None, str | None] | None:
    payload = request.payload
    if request.definition_id == MODELO_WORK_FILE_OPERATION_DEFINITION_ID and isinstance(payload, ModeloWorkFileRequest):
        return None, payload.approval.calculation_revision_id
    return None


def _amend_revision_target(request: OperationRequest[BaseModel]) -> tuple[str | None, str | None] | None:
    payload = request.payload
    if request.definition_id == MODELO_WORK_AMEND_OPERATION_DEFINITION_ID and isinstance(
        payload, ModeloWorkAmendRequest
    ):
        return payload.baseline.from_filing_record_id, None
    return None


def _export_revision_target(request: OperationRequest[BaseModel]) -> tuple[str | None, str | None] | None:
    payload = request.payload
    if request.definition_id == MODELO_EXPORT_OPERATION_DEFINITION_ID and isinstance(payload, ModeloExportRequest):
        return None, payload.calculation_revision_id
    return None


def _review_package_revision_target(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> tuple[str | None, str | None] | None:
    payload = request.payload
    if request.definition_id == MODELO_REVIEW_PACKAGE_BUILD_OPERATION_DEFINITION_ID and isinstance(
        payload, ModeloReviewPackageBuildRequest
    ):
        if payload.profile_id != context.profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return None, payload.calculation_revision_id
    return None


def _revision_snapshot_target(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> tuple[str | None, str | None] | None:
    payload = request.payload
    if request.definition_id == MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID and isinstance(
        payload, ModeloWorkRevisionSnapshotRequest
    ):
        if payload.profile_id != context.profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return None, payload.calculation_revision_id
    return None


def _persisted_revision_periods(
    factory: VerificationRepositoryBundleFactory,
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    filing_id: str | None,
    revision_id: str | None,
) -> frozenset[Period]:
    repositories, operation = _scoped_repositories(factory, context)
    filing = _scoped_filing(repositories, str(context.profile_id), filing_id) if filing_id is not None else None
    selected_revision_id = filing.calculation_revision_id if filing is not None else revision_id
    unit = _revision_work_unit(repositories, operation, request, context, selected_revision_id)
    if filing is not None:
        _require_filing_coordinates(filing, unit)
    return frozenset({unit.period})


def _scoped_repositories(
    factory: VerificationRepositoryBundleFactory, context: OperationAccessContext
) -> tuple[VerificationRepositoryBundle, PinnedAuthorityOperation]:
    operation = context.authority_operation
    if operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    bucket_id = str(context.profile_id)
    repositories = factory(bucket_id, operation=operation)
    if repositories.calculation.bucket_id != bucket_id or repositories.work_unit.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return repositories, operation


def _scoped_filing(repositories: VerificationRepositoryBundle, bucket_id: str, filing_id: str) -> ModeloRecord:
    if repositories.filing.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    filing = repositories.filing.load().get(filing_id)
    if filing is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if filing.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return filing


def _revision_work_unit(
    repositories: VerificationRepositoryBundle,
    operation: PinnedAuthorityOperation,
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    revision_id: str | None,
) -> WorkUnit:
    if revision_id is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    revision = repositories.calculation.load(operation=operation).get(revision_id)
    if revision is None or request.subject_ref != revision.work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    unit = repositories.work_unit.load().get(revision.work_unit_id)
    if unit is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if unit.bucket_id != str(context.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return unit


def _require_filing_coordinates(filing: ModeloRecord, unit: WorkUnit) -> None:
    if (
        filing.work_unit_id != unit.work_unit_id
        or filing.modelo != unit.modelo
        or filing.filing_year != unit.filing_year
        or filing.period != unit.period
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
