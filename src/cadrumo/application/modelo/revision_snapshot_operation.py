"""Registered exact-profile inspection of one persisted calculation revision."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.identity.hex_ids import CalculationRevisionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.access_port import OperationAccessResolver
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.profile_record_repository import ProfileRecordRepository
from .calculate_input import modelo_202_modality_for_record
from .calculation_advisory_projection import Modelo202ModalitySnapshot
from .calculation_projection import ModeloCalculationSnapshot
from .metadata_projection import ModeloWorkMetadataSnapshot
from .verification_repository_ports import VerificationRepositoryBundleFactory

MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID = "modelo.work.revision_snapshot"


class ModeloWorkRevisionSnapshotRequest(CredentialFreeOperationRequest):
    """An explicit profile and immutable revision selected through the read door."""

    profile_id: UUID
    calculation_revision_id: CalculationRevisionId


class ModeloWorkRevisionSnapshotProjection(BaseModel):
    """Canonical visible values and modality with their exact parent coordinates."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    unit: ModeloWorkMetadataSnapshot
    calculation: ModeloCalculationSnapshot
    modality: Modelo202ModalitySnapshot | None

    @model_validator(mode="after")
    def _require_exact_parent(self) -> ModeloWorkRevisionSnapshotProjection:
        if (
            self.unit.bucket_id != str(self.profile_id)
            or self.calculation.bucket_id != str(self.profile_id)
            or self.calculation.work_unit_id != self.unit.work_unit_id
            or self.calculation.modelo != self.unit.modelo
            or self.calculation.filing_year != self.unit.filing_year
            or self.calculation.period != self.unit.period
            or (self.modality is not None and self.unit.modelo != "202")
        ):
            raise ValueError("revision snapshot and parent coordinates disagree")
        return self


class ModeloWorkRevisionSnapshotExecutor:
    """Capture a full read in worker custody without activating another profile."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        """Retain the exact-profile repository composition capability."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkRevisionSnapshotRequest], context: OperationExecutorContext
    ) -> str:
        """Store only the encrypted canonical projection; public effect is NONE."""
        if (
            request.definition_id != MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID
            or request.subject_ref != context.identity.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        await context.events.phase(MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID)

        def read() -> ModeloWorkRevisionSnapshotProjection:
            payload = request.payload
            profile_id = str(payload.profile_id)
            operation = context.authority_operation
            bundle = self._factory(profile_id, operation=operation)
            if bundle.calculation.bucket_id != profile_id or bundle.work_unit.bucket_id != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            revision = bundle.calculation.load(operation=operation).get(payload.calculation_revision_id)
            if revision is None or revision.work_unit_id != request.subject_ref:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            unit = bundle.work_unit.load().get(revision.work_unit_id)
            if unit is None or unit.bucket_id != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            modality = None
            if str(unit.modelo) == "202":
                record = ProfileRecordRepository.for_current_session(
                    profile_id, profile_decode_context=operation.profile_decode_context()
                ).load(profile_id)
                summary = modelo_202_modality_for_record(unit, record, operation=operation)
                if summary is not None:
                    modality = Modelo202ModalitySnapshot.from_modality(summary)
            return ModeloWorkRevisionSnapshotProjection(
                profile_id=payload.profile_id,
                unit=ModeloWorkMetadataSnapshot.from_work_unit(unit),
                calculation=ModeloCalculationSnapshot.from_revision(revision, work_unit=unit, operation=operation),
                modality=modality,
            )

        return await capture_read_result(context, read, task_name="modelo-revision-snapshot")


def build_modelo_work_revision_snapshot_definition(factory: VerificationRepositoryBundleFactory) -> OperationDefinition:
    """Declare the full-value read separately from metadata-only selection."""
    return build_single_phase_definition(
        definition_id=MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkRevisionSnapshotRequest,
        result_type=ModeloWorkRevisionSnapshotProjection,
        executor_type=ModeloWorkRevisionSnapshotExecutor,
        build=lambda: ModeloWorkRevisionSnapshotExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_revision_snapshot_registration(
    definition: OperationDefinition, *, access_resolver: OperationAccessResolver
) -> OperationPublicDefinitionRegistrationV1:
    """Use persisted revision scope and explicit TAX_VALUES disclosure admission."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkRevisionSnapshotProjection,
        access_resolver=access_resolver,
    )
