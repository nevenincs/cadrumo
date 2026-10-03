"""Registered exact-profile reads of encrypted local verification observations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hashing import canonical_json_bytes
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.identity_check_verdict import IdentityCheckVerdictValue
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES, OperationCapabilities
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_terminal_receipt_match
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .verify import VerifyObservation, VerifyObservationNotFoundError, VerifyService, VerifySurface
from .verify_ports import VerifyObservationPersistencePort

VERIFY_LIST_DEFINITION_ID = "live.verify.list"
VERIFY_VIEW_DEFINITION_ID = "live.verify.view"
VERIFY_LATEST_DEFINITION_ID = "live.verify.latest"
_LIST_PHASES = ("verify-list.read", "verify-list.result")
_VIEW_PHASES = ("verify-view.read", "verify-view.result")
_LATEST_PHASES = ("verify-latest.read", "verify-latest.result")
_MAX_VERIFY_LIST_ROWS = 10_000
_RESULT_DOCUMENT_MAX_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096
_OBSERVATION_ID_PREFIX = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$"),
]
_NIF = Annotated[str, Field(min_length=1, max_length=32)]


class VerifyListRequest(BaseModel):
    """Filter one exact profile's local verify history."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    surface: VerifySurface | None = None
    nif: _NIF | None = None


class VerifyViewRequest(BaseModel):
    """Resolve one local verify observation by full digest or unambiguous prefix."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    observation_id: _OBSERVATION_ID_PREFIX


class VerifyLatestRequest(BaseModel):
    """Read the latest stored observation for an exact surface and NIF."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    surface: VerifySurface
    nif: _NIF


class VerifyObservationSummaryPublicV1(BaseModel):
    """Allowlisted fields already present in the existing verify list row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    observation_id: ContentDigest
    surface: VerifySurface
    nif: _NIF
    verdict: IdentityCheckVerdictValue
    expected: IdentityCheckVerdictValue | None
    matched_expectation: bool | None
    checked_at: datetime

    @field_validator("checked_at")
    @classmethod
    @pydantic_validation_boundary
    def _checked_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _expectation_matches_verdict(self) -> Self:
        if self.expected is None and self.matched_expectation is not None:
            raise ValueError("verify observation without an expectation carries a match result")
        if self.expected is not None and self.matched_expectation is not (self.expected == self.verdict):
            raise ValueError("verify observation expectation result disagrees with its verdict")
        return self


class VerifyListOperationReport(BaseModel):
    """Private, profile-scoped list operand with only existing list summary fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    rows: tuple[VerifyObservationSummaryPublicV1, ...]


class VerifyViewOperationReport(BaseModel):
    """Selected encrypted observation retained inside operation custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    observation: VerifyObservation


class VerifyLatestOperationReport(BaseModel):
    """Private latest row and its lookup coordinates, including an empty state."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    surface: VerifySurface
    nif: _NIF
    observation: VerifyObservation | None

    @model_validator(mode="after")
    def _observation_matches_query(self) -> Self:
        if self.observation is not None and (
            self.observation.bucket_id != self.bucket_id
            or self.observation.surface is not self.surface
            or self.observation.nif != self.nif
        ):
            raise ValueError("latest verify observation differs from its bucket or lookup coordinates")
        return self


class VerifyObservationPublicV1(VerifyObservationSummaryPublicV1):
    """Detail row with the existing verify view's exact bucket field."""

    bucket_id: BucketId


class VerifyListPublicResultV1(BaseModel):
    """Closed local verify inventory for an authorized whole-profile read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    count: NonNegativeInt
    rows: tuple[VerifyObservationSummaryPublicV1, ...]

    @model_validator(mode="after")
    def _count_matches_rows(self) -> Self:
        if self.count != len(self.rows):
            raise ValueError("verify observation count disagrees with its rows")
        return self


class VerifyLatestPublicResultV1(BaseModel):
    """Latest observation fields or the existing all-empty observation state."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    observation_id: ContentDigest | None
    surface: VerifySurface
    nif: _NIF
    verdict: IdentityCheckVerdictValue | None = None
    expected: IdentityCheckVerdictValue | None = None
    matched_expectation: bool | None = None
    checked_at: datetime | None = None

    @field_validator("checked_at")
    @classmethod
    @pydantic_validation_boundary
    def _checked_at_is_utc(cls, value: datetime | None) -> datetime | None:
        return validate_utc_aware(value) if value is not None else None

    @model_validator(mode="after")
    def _optional_fields_agree(self) -> Self:
        row_fields = (self.verdict, self.expected, self.matched_expectation, self.checked_at)
        if self.observation_id is None and any(value is not None for value in row_fields):
            raise ValueError("empty latest verify result carries observation fields")
        if self.observation_id is not None and (self.verdict is None or self.checked_at is None):
            raise ValueError("latest verify result lacks observation fields")
        if self.expected is None and self.matched_expectation is not None:
            raise ValueError("latest verify result without an expectation carries a match result")
        if self.expected is not None and self.matched_expectation is not (self.expected == self.verdict):
            raise ValueError("latest verify expectation result disagrees with its verdict")
        return self


VerifyObservationPersistenceFactory = Callable[[str], VerifyObservationPersistencePort]


def _exact_bucket(profile_id: UUID, subject_ref: str) -> str:
    """Refuse a request outside the exact profile worker currently active."""
    bucket_id = canonical_profile_bucket_id(profile_id)
    if require_active_bucket_id() != bucket_id or subject_ref != profile_operation_subject(bucket_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


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
        bucket_id = _exact_bucket(request.payload.profile_id, request.subject_ref)
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
        await context.events.phase(_LIST_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="verify-list-result"
        )


class VerifyViewExecutor:
    """Read one exact-profile local observation while keeping its evidence locator private."""

    def __init__(self, persistence_factory: VerifyObservationPersistenceFactory) -> None:
        self._persistence_factory = persistence_factory

    async def execute(self, request: OperationRequest[VerifyViewRequest], context: OperationExecutorContext) -> str:
        bucket_id = _exact_bucket(request.payload.profile_id, request.subject_ref)
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
        await context.events.phase(_VIEW_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="verify-view-result"
        )


class VerifyLatestExecutor:
    """Read a latest local observation, including the stable empty result."""

    def __init__(self, persistence_factory: VerifyObservationPersistenceFactory) -> None:
        self._persistence_factory = persistence_factory

    async def execute(self, request: OperationRequest[VerifyLatestRequest], context: OperationExecutorContext) -> str:
        bucket_id = _exact_bucket(request.payload.profile_id, request.subject_ref)
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
        await context.events.phase(_LATEST_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="verify-latest-result"
        )


def _capabilities() -> OperationCapabilities:
    return RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES


def build_verify_list_definition(persistence_factory: VerifyObservationPersistenceFactory) -> OperationDefinition:
    """Declare encrypted exact-profile verify history with bounded output."""
    return OperationDefinition(
        definition_id=VERIFY_LIST_DEFINITION_ID,
        request_type=VerifyListRequest,
        result_type=VerifyListOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=VerifyListRequest,
            executor_type=VerifyListExecutor,
            build=lambda: VerifyListExecutor(persistence_factory),
        ),
        phase_codes=_LIST_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_verify_view_definition(persistence_factory: VerifyObservationPersistenceFactory) -> OperationDefinition:
    """Declare exact-profile detail lookup without releasing raw evidence locator."""
    return OperationDefinition(
        definition_id=VERIFY_VIEW_DEFINITION_ID,
        request_type=VerifyViewRequest,
        result_type=VerifyViewOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=VerifyViewRequest,
            executor_type=VerifyViewExecutor,
            build=lambda: VerifyViewExecutor(persistence_factory),
        ),
        phase_codes=_VIEW_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_verify_latest_definition(persistence_factory: VerifyObservationPersistenceFactory) -> OperationDefinition:
    """Declare exact-profile latest verify observation with a stable empty state."""
    return OperationDefinition(
        definition_id=VERIFY_LATEST_DEFINITION_ID,
        request_type=VerifyLatestRequest,
        result_type=VerifyLatestOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=VerifyLatestRequest,
            executor_type=VerifyLatestExecutor,
            build=lambda: VerifyLatestExecutor(persistence_factory),
        ),
        phase_codes=_LATEST_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


_RECEIPT_CONTRADICTION = "verify read result contradicts its terminal receipt"


def _project_list(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not VerifyListOperationReport:
        raise ValueError("invalid verify list report")
    report = VerifyListOperationReport.model_validate(result, strict=True)
    require_terminal_receipt_match(
        receipt,
        definition_id=VERIFY_LIST_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(report.bucket_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
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
    require_terminal_receipt_match(
        receipt,
        definition_id=VERIFY_VIEW_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(observation.bucket_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
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
    require_terminal_receipt_match(
        receipt,
        definition_id=VERIFY_LATEST_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(report.bucket_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
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
    "VerifyLatestPublicResultV1",
    "VerifyLatestRequest",
    "VerifyListPublicResultV1",
    "VerifyListRequest",
    "VerifyObservationPersistenceFactory",
    "VerifyObservationPublicV1",
    "VerifyObservationSummaryPublicV1",
    "VerifyViewRequest",
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
