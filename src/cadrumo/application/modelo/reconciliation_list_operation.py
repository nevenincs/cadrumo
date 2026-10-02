"""Registered whole-profile reads of persisted modelo reconciliation history."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import canonical_json_bytes
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from ...domain.buckets.event import BucketEventId
from ...domain.modelos.filing_text import ModeloActorLabel
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
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
    def _reconciled_at_is_utc(cls, value: datetime) -> datetime:
        """Retain the canonical UTC instant contract at the public boundary."""
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
        from ...core.bucket_pointer import require_active_bucket_id

        payload = request.payload
        profile_id = str(payload.profile_id)
        subject = profile_operation_subject(profile_id)
        if (
            request.definition_id != MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != profile_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
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

        async def capture() -> str:
            projection = await asyncio.to_thread(read)
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-reconciliation-list")


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
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
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
        if (
            admitted is not None
            and context.action
            in {
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
            and (
                admitted.profile_id != context.profile_id
                or admitted.definition_id != request.definition_id
                or admitted.action is not AccessAction.SUBMIT
                or not admitted.period_independent
                or admitted.periods
            )
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset[DisclosurePermission]()
        if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
            disclosures = frozenset(
                (
                    DisclosurePermission(
                        destination_id=context.destination_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                )
            )
        elif context.action is AccessAction.RESULT:
            schema = context.contract.result_schema
            if schema is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            disclosures = frozenset(
                (
                    DisclosurePermission(
                        destination_id=context.destination_id,
                        projection_id=schema.schema_id,
                        category=DisclosureCategory.TAX_VALUES,
                    ),
                )
            )
        return ResolvedOperationAccess(
            request=OperationAccessRequest(
                profile_id=context.profile_id,
                definition_id=request.definition_id,
                action=context.action,
                frontend=context.frontend,
                periods=frozenset(),
                period_independent=True,
                destination_id=context.destination_id,
            ),
            policy=OperationAccessPolicy(
                definition_id=request.definition_id,
                definition_contract_digest=context.contract.definition_contract_digest,
                actions=frozenset(
                    {
                        AccessAction.SUBMIT,
                        AccessAction.START,
                        AccessAction.RESUME,
                        AccessAction.OBSERVE,
                        AccessAction.RESULT,
                        AccessAction.CANCEL,
                        AccessAction.DETACH,
                    }
                ),
                disclosures=disclosures,
                periods=frozenset(),
                allow_period_independent=True,
                requires_all_periods=True,
                backend=Availability.AVAILABLE,
                published_authority=context.published_authority,
                provider=Availability.NOT_REQUIRED,
                transaction_authority_required=False,
            ),
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloReconciliationListRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloReconciliationListProjection,
        ),
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
