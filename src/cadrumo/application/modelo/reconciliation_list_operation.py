"""Registered whole-profile reads of persisted modelo reconciliation history."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hashing import canonical_json_bytes
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import profile_operation_subject
from ...core.time.utc import validate_utc_aware
from ...domain.buckets.event import BucketEventId
from ...domain.modelos.filing_text import ModeloActorLabel
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_period_independent_admission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .reconciliation_records import (
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationHistoryEntry,
    ModeloReconciliationVerdict,
    list_modelo_reconciliations,
)

MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID = "modelo.reconcile.list"
MAX_MODELO_RECONCILIATION_SOURCE_PATH_LENGTH = 4_096
_RESULT_DOCUMENT_MAX_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096

_BoundedSourcePath = Annotated[str, Field(max_length=MAX_MODELO_RECONCILIATION_SOURCE_PATH_LENGTH)]


class ModeloReconciliationListRequest(CredentialFreeOperationRequest):
    """Select one profile's complete reconciliation history or one work unit."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    work_unit_id: WorkUnitId | None = None


class ModeloReconciliationListEntryProjection(BaseModel):
    """The established CLI history fields without persisted reconciliation detail."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    event_id: BucketEventId
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationEvidenceKind
    source_path: _BoundedSourcePath
    verdict: ModeloReconciliationVerdict
    diff_count: NonNegativeInt
    actor: ModeloActorLabel
    reconciled_at: datetime

    @field_validator("reconciled_at")
    @classmethod
    @pydantic_validation_boundary
    def _reconciled_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @classmethod
    def from_history_entry(cls, entry: ModeloReconciliationHistoryEntry) -> ModeloReconciliationListEntryProjection:
        """Copy only fields admitted by the CLI history result contract."""
        return cls(
            event_id=entry.event_id,
            bucket_id=entry.bucket_id,
            work_unit_id=entry.work_unit_id,
            source_kind=entry.source_kind,
            source_path=entry.source_path,
            verdict=entry.verdict,
            diff_count=entry.diff_count,
            actor=entry.actor,
            reconciled_at=entry.reconciled_at,
        )


class ModeloReconciliationListProjection(BaseModel):
    """Bounded, encrypted result for one exact-profile reconciliation listing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    work_unit_id: WorkUnitId | None = None
    reconciliation_count: NonNegativeInt
    reconciliations: tuple[ModeloReconciliationListEntryProjection, ...]

    @model_validator(mode="after")
    def _bound_history(self) -> Self:
        """Reject cross-profile, out-of-scope, duplicate, or reordered rows."""
        if self.reconciliation_count != len(self.reconciliations):
            raise ValueError("reconciliation history count does not match its rows")
        if any(row.bucket_id != str(self.profile_id) for row in self.reconciliations):
            raise ValueError("reconciliation history contains another profile")
        if self.work_unit_id is not None and any(row.work_unit_id != self.work_unit_id for row in self.reconciliations):
            raise ValueError("reconciliation history exceeds its requested work unit")
        if len({row.event_id for row in self.reconciliations}) != len(self.reconciliations):
            raise ValueError("reconciliation history repeats an event")
        expected = tuple(sorted(self.reconciliations, key=lambda row: (row.reconciled_at, row.event_id)))
        if self.reconciliations != expected:
            raise ValueError("reconciliation history is not in canonical order")
        return self


class ModeloReconciliationListExecutor:
    """Read canonical reconciliation records and retain their bounded projection."""

    async def execute(
        self,
        request: OperationRequest[ModeloReconciliationListRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Capture the active profile's history without mutating it."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID)

        def read() -> ModeloReconciliationListProjection:
            entries = list_modelo_reconciliations(
                bucket_id=profile_id,
                operation=context.authority_operation,
                work_unit_id=payload.work_unit_id,
            )
            if any(len(entry.source_path) > MAX_MODELO_RECONCILIATION_SOURCE_PATH_LENGTH for entry in entries):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            projection = ModeloReconciliationListProjection(
                profile_id=payload.profile_id,
                work_unit_id=payload.work_unit_id,
                reconciliation_count=len(entries),
                reconciliations=tuple(
                    ModeloReconciliationListEntryProjection.from_history_entry(entry) for entry in entries
                ),
            )
            if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _RESULT_DOCUMENT_MAX_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return projection

        return await capture_read_result(context, read, task_name="modelo-reconciliation-list")


def build_modelo_reconciliation_list_definition() -> OperationDefinition:
    """Declare a credential-free, recorded, nonmutating history read."""
    return OperationDefinition(
        definition_id=MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
        request_type=ModeloReconciliationListRequest,
        result_type=ModeloReconciliationListProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloReconciliationListRequest,
            executor_type=ModeloReconciliationListExecutor,
            build=ModeloReconciliationListExecutor,
        ),
        phase_codes=(MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_modelo_reconciliation_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Require unrestricted all-period consent for reconciliation history."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(
            payload, ModeloReconciliationListRequest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            require_period_independent_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        return bind_operation_access_profile(
            context,
            LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=frozenset(),
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloReconciliationListProjection,
        access_resolver=resolve,
    )


__all__ = [
    "MAX_MODELO_RECONCILIATION_SOURCE_PATH_LENGTH",
    "MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID",
    "ModeloReconciliationListEntryProjection",
    "ModeloReconciliationListExecutor",
    "ModeloReconciliationListProjection",
    "ModeloReconciliationListRequest",
    "build_modelo_reconciliation_list_definition",
    "build_modelo_reconciliation_list_registration",
]
