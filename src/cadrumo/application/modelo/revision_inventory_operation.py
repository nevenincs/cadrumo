"""Read-only revision discovery within an explicitly authorized profile scope."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_period_independent_admission,
    require_single_period_admission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .verification_repository_ports import VerificationRepositoryBundleFactory

MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID = "modelo.work.revisions"


class ModeloWorkRevisionsRequest(CredentialFreeOperationRequest):
    """An exact unit filter, or explicit profile-wide discovery."""

    profile_id: UUID
    work_unit_id: WorkUnitId | None = None


class ModeloRevisionInventoryRow(BaseModel):
    """Stored revision identity and lifecycle metadata without calculation values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: CalculationRevisionState
    created_at: datetime


class ModeloWorkRevisionsProjection(BaseModel):
    """One complete ordered inventory captured inside profile custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    work_unit_id_filter: WorkUnitId | None
    revisions: tuple[ModeloRevisionInventoryRow, ...]

    @model_validator(mode="after")
    def _coherent_rows(self) -> ModeloWorkRevisionsProjection:
        if len({row.calculation_revision_id for row in self.revisions}) != len(self.revisions):
            raise ValueError("revision inventory repeats an identity")
        if self.work_unit_id_filter is not None and any(
            row.work_unit_id != self.work_unit_id_filter for row in self.revisions
        ):
            raise ValueError("revision inventory contains another work unit")
        if tuple(sorted(self.revisions, key=lambda row: (row.work_unit_id, row.created_at))) != self.revisions:
            raise ValueError("revision inventory is not chronologically ordered")
        return self


def _require_revision_inventory_filter(
    payload: ModeloWorkRevisionsRequest, units: WorkUnitCatalogue, profile_id: str
) -> None:
    if payload.work_unit_id is not None:
        unit = units.get(payload.work_unit_id)
        if unit is None or unit.bucket_id != profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _capture_revision_inventory(
    payload: ModeloWorkRevisionsRequest,
    factory: VerificationRepositoryBundleFactory,
    operation: PinnedAuthorityOperation,
) -> ModeloWorkRevisionsProjection:
    profile_id = str(payload.profile_id)
    bundle = factory(profile_id, operation=operation)
    if bundle.calculation.bucket_id != profile_id or bundle.work_unit.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    units = bundle.work_unit.load()
    _require_revision_inventory_filter(payload, units, profile_id)
    rows: list[ModeloRevisionInventoryRow] = []
    for revision in bundle.calculation.load(operation=operation):
        if payload.work_unit_id is not None and revision.work_unit_id != payload.work_unit_id:
            continue
        unit = units.get(revision.work_unit_id)
        if unit is None or unit.bucket_id != profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_calculation_revision_coordinates_current(revision, operation=operation)
        rows.append(
            ModeloRevisionInventoryRow(
                calculation_revision_id=revision.calculation_revision_id,
                work_unit_id=revision.work_unit_id,
                state=revision.state,
                created_at=revision.created_at,
            )
        )
    return ModeloWorkRevisionsProjection(
        profile_id=payload.profile_id,
        work_unit_id_filter=payload.work_unit_id,
        revisions=tuple(sorted(rows, key=lambda row: (row.work_unit_id, row.created_at))),
    )


class ModeloWorkRevisionsExecutor:
    """Capture discovery without the old read-side catalogue migration write."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        """Retain the exact-profile repository composition capability."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkRevisionsRequest], context: OperationExecutorContext
    ) -> str:
        """Store the canonical inventory in encrypted operands with no mutation."""
        payload = request.payload
        if (
            request.definition_id != MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID)

        def read() -> ModeloWorkRevisionsProjection:
            return _capture_revision_inventory(payload, self._factory, context.authority_operation)

        return await capture_read_result(context, read, task_name="modelo-revision-inventory")


def build_modelo_work_revisions_definition(factory: VerificationRepositoryBundleFactory) -> OperationDefinition:
    """Declare recorded encrypted discovery with no domain mutation capability."""
    return build_single_phase_definition(
        definition_id=MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkRevisionsRequest,
        result_type=ModeloWorkRevisionsProjection,
        executor_type=ModeloWorkRevisionsExecutor,
        build=lambda: ModeloWorkRevisionsExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def _selected_revision_inventory_period(
    payload: ModeloWorkRevisionsRequest,
    context: OperationAccessContext,
    factory: VerificationRepositoryBundleFactory,
) -> Period:
    if context.authority_operation is None or payload.work_unit_id is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    bundle = factory(str(context.profile_id), operation=context.authority_operation)
    if bundle.work_unit.bucket_id != str(context.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    unit = bundle.work_unit.load().get(payload.work_unit_id)
    if unit is None or unit.bucket_id != str(context.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return unit.period


def _resolve_revision_inventory_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
    *,
    definition: OperationDefinition,
    factory: VerificationRepositoryBundleFactory,
) -> ResolvedOperationAccess:
    payload = require_access_request_profile_payload(
        request,
        definition_id=definition.definition_id,
        payload_type=ModeloWorkRevisionsRequest,
        access_profile_id=context.profile_id,
    )
    independent = payload.work_unit_id is None
    periods: frozenset[Period]
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        if independent:
            require_period_independent_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
            periods = frozenset[Period]()
        else:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
    elif independent:
        periods = frozenset[Period]()
    else:
        periods = frozenset({_selected_revision_inventory_period(payload, context, factory)})
    return bind_operation_access_profile(
        context,
        LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS
        if independent
        else LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        periods=periods,
    )


def build_modelo_work_revisions_registration(
    definition: OperationDefinition, factory: VerificationRepositoryBundleFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Require independent-profile permission for unfiltered discovery.

    A period-restricted grant cannot list other periods by omitting the filter,
    even when it permits unrelated period-independent profile operations.
    Filtered discovery derives its one period from the immutable unit identity;
    historical release uses sealed admission rather than rereading the catalogue.
    """

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        return _resolve_revision_inventory_access(request, context, definition=definition, factory=factory)

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkRevisionsProjection,
        access_resolver=resolve,
    )
