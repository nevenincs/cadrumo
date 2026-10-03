"""Registered exact-profile reads of encrypted local verification observations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from pydantic import BaseModel

from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .live_operation_execution import publish_live_read_report, require_exact_profile_worker
from .live_operation_registration import build_live_operation_definition, require_live_read_receipt
from .verify import VerifyObservation, VerifyObservationNotFoundError, VerifyService
from .verify_ports import VerifyObservationPersistencePort
from .verify_read_contracts import (
    VerifyLatestOperationReport,
    VerifyLatestPublicResultV1,
    VerifyLatestRequest,
    VerifyListOperationReport,
    VerifyListPublicResultV1,
    VerifyListRequest,
    VerifyObservationPublicV1,
    VerifyObservationSummaryPublicV1,
    VerifyViewOperationReport,
    VerifyViewRequest,
)

VERIFY_LIST_DEFINITION_ID = "live.verify.list"
VERIFY_VIEW_DEFINITION_ID = "live.verify.view"
VERIFY_LATEST_DEFINITION_ID = "live.verify.latest"
_LIST_PHASES = ("verify-list.read", "verify-list.result")
_VIEW_PHASES = ("verify-view.read", "verify-view.result")
_LATEST_PHASES = ("verify-latest.read", "verify-latest.result")
_MAX_VERIFY_LIST_ROWS = 10_000
_RESULT_DOCUMENT_MAX_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096
VerifyObservationPersistenceFactory = Callable[[str], VerifyObservationPersistencePort]


def _require_bucket(observation: VerifyObservation, bucket_id: str) -> None:
    if str(observation.bucket_id) != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _summary(observation: VerifyObservation) -> VerifyObservationSummaryPublicV1:
    """Copy exactly the existing verify list fields, excluding stored evidence locator."""
    return VerifyObservationSummaryPublicV1(
        observation_id=observation.observation_id,
        surface=observation.surface,
        nif=observation.nif,
        verdict=observation.verdict,
        expected=observation.expected,
        matched_expectation=observation.matched_expectation,
        checked_at=observation.checked_at,
    )


def _require_bounded_result(result: BaseModel) -> None:
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > _RESULT_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


class VerifyListExecutor:
    """Read local verify summaries without contacting an AEAT provider."""

    def __init__(self, persistence_factory: VerifyObservationPersistenceFactory) -> None:
        self._persistence_factory = persistence_factory

    async def execute(self, request: OperationRequest[VerifyListRequest], context: OperationExecutorContext) -> str:
        bucket_id = require_exact_profile_worker(
            request.payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        if request.definition_id != VERIFY_LIST_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, request.payload.profile_id)
        await context.events.phase(_LIST_PHASES[0])

        def read() -> VerifyListOperationReport:
            observations = VerifyService(persistence=self._persistence_factory(bucket_id)).list_observations(
                bucket_id=bucket_id,
                surface=request.payload.surface,
                nif=request.payload.nif,
            )
            if any(str(observation.bucket_id) != bucket_id for observation in observations):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            if any(
                (request.payload.surface is not None and observation.surface is not request.payload.surface)
                or (request.payload.nif is not None and observation.nif != request.payload.nif)
                for observation in observations
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            if len(observations) > _MAX_VERIFY_LIST_ROWS:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            rows = tuple(_summary(observation) for observation in observations)
            projection = VerifyListPublicResultV1(bucket_id=bucket_id, count=len(rows), rows=rows)
            _require_bounded_result(projection)
            return VerifyListOperationReport(bucket_id=bucket_id, rows=rows)

        report = await asyncio.to_thread(read)
        return await publish_live_read_report(
            context, report, result_phase=_LIST_PHASES[1], effect=OperationEffect.NONE, task_name="verify-list-result"
        )


class VerifyViewExecutor:
    """Read one exact-profile local observation while keeping its evidence locator private."""

    def __init__(self, persistence_factory: VerifyObservationPersistenceFactory) -> None:
        self._persistence_factory = persistence_factory

    async def execute(self, request: OperationRequest[VerifyViewRequest], context: OperationExecutorContext) -> str:
        bucket_id = require_exact_profile_worker(
            request.payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        if request.definition_id != VERIFY_VIEW_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, request.payload.profile_id)
        await context.events.phase(_VIEW_PHASES[0])

        def read() -> VerifyViewOperationReport:
            try:
                observation = VerifyService(persistence=self._persistence_factory(bucket_id)).show(
                    bucket_id=bucket_id,
                    observation_id=request.payload.observation_id,
                )
            except VerifyObservationNotFoundError as exc:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from exc
            _require_bucket(observation, bucket_id)
            if not str(observation.observation_id).startswith(request.payload.observation_id):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            projection = VerifyObservationPublicV1(**_summary(observation).model_dump(), bucket_id=bucket_id)
            _require_bounded_result(projection)
            return VerifyViewOperationReport(observation=observation)

        report = await asyncio.to_thread(read)
        return await publish_live_read_report(
            context, report, result_phase=_VIEW_PHASES[1], effect=OperationEffect.NONE, task_name="verify-view-result"
        )


class VerifyLatestExecutor:
    """Read a latest local observation, including the stable empty result."""

    def __init__(self, persistence_factory: VerifyObservationPersistenceFactory) -> None:
        self._persistence_factory = persistence_factory

    async def execute(self, request: OperationRequest[VerifyLatestRequest], context: OperationExecutorContext) -> str:
        bucket_id = require_exact_profile_worker(
            request.payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        if request.definition_id != VERIFY_LATEST_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, request.payload.profile_id)
        await context.events.phase(_LATEST_PHASES[0])

        def read() -> VerifyLatestOperationReport:
            observation = VerifyService(persistence=self._persistence_factory(bucket_id)).latest_for_nif(
                bucket_id=bucket_id,
                surface=request.payload.surface,
                nif=request.payload.nif,
            )
            if observation is not None:
                _require_bucket(observation, bucket_id)
                if observation.surface is not request.payload.surface or observation.nif != request.payload.nif:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            report = VerifyLatestOperationReport(
                bucket_id=bucket_id,
                surface=request.payload.surface,
                nif=request.payload.nif,
                observation=observation,
            )
            _require_bounded_result(_project_latest_report(report))
            return report

        report = await asyncio.to_thread(read)
        return await publish_live_read_report(
            context,
            report,
            result_phase=_LATEST_PHASES[1],
            effect=OperationEffect.NONE,
            task_name="verify-latest-result",
        )


def build_verify_list_definition(persistence_factory: VerifyObservationPersistenceFactory) -> OperationDefinition:
    """Declare encrypted exact-profile verify history with bounded output."""
    return build_live_operation_definition(
        definition_id=VERIFY_LIST_DEFINITION_ID,
        request_type=VerifyListRequest,
        result_type=VerifyListOperationReport,
        executor_type=VerifyListExecutor,
        build=lambda: VerifyListExecutor(persistence_factory),
        phase_codes=_LIST_PHASES,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def build_verify_view_definition(persistence_factory: VerifyObservationPersistenceFactory) -> OperationDefinition:
    """Declare exact-profile detail lookup without releasing raw evidence locator."""
    return build_live_operation_definition(
        definition_id=VERIFY_VIEW_DEFINITION_ID,
        request_type=VerifyViewRequest,
        result_type=VerifyViewOperationReport,
        executor_type=VerifyViewExecutor,
        build=lambda: VerifyViewExecutor(persistence_factory),
        phase_codes=_VIEW_PHASES,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def build_verify_latest_definition(persistence_factory: VerifyObservationPersistenceFactory) -> OperationDefinition:
    """Declare exact-profile latest verify observation with a stable empty state."""
    return build_live_operation_definition(
        definition_id=VERIFY_LATEST_DEFINITION_ID,
        request_type=VerifyLatestRequest,
        result_type=VerifyLatestOperationReport,
        executor_type=VerifyLatestExecutor,
        build=lambda: VerifyLatestExecutor(persistence_factory),
        phase_codes=_LATEST_PHASES,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


_RECEIPT_CONTRADICTION = "verify read result contradicts its terminal receipt"


def _project_list(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not VerifyListOperationReport:
        raise ValueError("invalid verify list report")
    report = VerifyListOperationReport.model_validate(result, strict=True)
    require_live_read_receipt(
        receipt,
        definition_id=VERIFY_LIST_DEFINITION_ID,
        bucket_id=str(report.bucket_id),
        message=_RECEIPT_CONTRADICTION,
    )
    projection = VerifyListPublicResultV1(bucket_id=report.bucket_id, count=len(report.rows), rows=report.rows)
    if len(report.rows) > _MAX_VERIFY_LIST_ROWS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    _require_bounded_result(projection)
    return projection


def _project_view(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not VerifyViewOperationReport:
        raise ValueError("invalid verify view report")
    report = VerifyViewOperationReport.model_validate(result, strict=True)
    observation = report.observation
    require_live_read_receipt(
        receipt,
        definition_id=VERIFY_VIEW_DEFINITION_ID,
        bucket_id=str(observation.bucket_id),
        message=_RECEIPT_CONTRADICTION,
    )
    projection = VerifyObservationPublicV1(**_summary(observation).model_dump(), bucket_id=observation.bucket_id)
    _require_bounded_result(projection)
    return projection


def _project_latest_report(report: VerifyLatestOperationReport) -> VerifyLatestPublicResultV1:
    observation = report.observation
    if observation is None:
        return VerifyLatestPublicResultV1(
            bucket_id=report.bucket_id,
            observation_id=None,
            surface=report.surface,
            nif=report.nif,
        )
    if str(observation.bucket_id) != str(report.bucket_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    summary = _summary(observation)
    return VerifyLatestPublicResultV1(
        bucket_id=report.bucket_id,
        observation_id=summary.observation_id,
        surface=report.surface,
        nif=report.nif,
        verdict=summary.verdict,
        expected=summary.expected,
        matched_expectation=summary.matched_expectation,
        checked_at=summary.checked_at,
    )


def _project_latest(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not VerifyLatestOperationReport:
        raise ValueError("invalid verify latest report")
    report = VerifyLatestOperationReport.model_validate(result, strict=True)
    require_live_read_receipt(
        receipt,
        definition_id=VERIFY_LATEST_DEFINITION_ID,
        bucket_id=str(report.bucket_id),
        message=_RECEIPT_CONTRADICTION,
    )
    projection = _project_latest_report(report)
    _require_bounded_result(projection)
    return projection


def _resolve_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, definition_id: str
) -> ResolvedOperationAccess:
    if definition_id == VERIFY_LIST_DEFINITION_ID:
        request_type = VerifyListRequest
    elif definition_id == VERIFY_VIEW_DEFINITION_ID:
        request_type = VerifyViewRequest
    elif definition_id == VERIFY_LATEST_DEFINITION_ID:
        request_type = VerifyLatestRequest
    else:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.definition_id != definition_id or type(request.payload) is not request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if not isinstance(payload, (VerifyListRequest, VerifyViewRequest, VerifyLatestRequest)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def resolve_verify_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile TAX_VALUES authority for filtered verify history."""
    return _resolve_read_access(request, context, VERIFY_LIST_DEFINITION_ID)


def resolve_verify_view_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile TAX_VALUES authority for one local verify row."""
    return _resolve_read_access(request, context, VERIFY_VIEW_DEFINITION_ID)


def resolve_verify_latest_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile TAX_VALUES authority for the latest verify row."""
    return _resolve_read_access(request, context, VERIFY_LATEST_DEFINITION_ID)


def build_verify_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the verify list request to its whole-profile TAX_VALUES projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=VerifyListPublicResultV1,
        result_projector=_project_list,
        access_resolver=resolve_verify_list_access,
    )


def build_verify_view_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind verify detail to its whole-profile TAX_VALUES projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=VerifyObservationPublicV1,
        result_projector=_project_view,
        access_resolver=resolve_verify_view_access,
    )


def build_verify_latest_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the verify latest request to its whole-profile TAX_VALUES projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=VerifyLatestPublicResultV1,
        result_projector=_project_latest,
        access_resolver=resolve_verify_latest_access,
    )


__all__ = [
    "VERIFY_LATEST_DEFINITION_ID",
    "VERIFY_LIST_DEFINITION_ID",
    "VERIFY_VIEW_DEFINITION_ID",
    "VerifyObservationPersistenceFactory",
    "build_verify_latest_definition",
    "build_verify_latest_registration",
    "build_verify_list_definition",
    "build_verify_list_registration",
    "build_verify_view_definition",
    "build_verify_view_registration",
    "resolve_verify_latest_access",
    "resolve_verify_list_access",
    "resolve_verify_view_access",
]
