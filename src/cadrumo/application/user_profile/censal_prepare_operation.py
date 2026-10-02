"""Prepare an exact-profile censal review without contacting AEAT."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
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
from .access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from .access_errors import ProfileAccessRefusedError
from .censal_operation import CensalOperationRequest, build_censal_operation_request
from .censo_sync import CENSAL_ADOPTABLE_PATHS
from .profile_record_repository import ProfileRecordRepository
from .projections import record_to_effective_facts

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

CENSAL_PREPARE_OPERATION_DEFINITION_ID = "user-profile.censo-prepare"
CENSAL_PREPARE_PHASE_READ = "user-profile.censo-prepare.read"
MAX_CENSAL_PREPARE_VALUE_LENGTH = 4_096
_CENSAL_PREPARE_RESULT_MAX_BYTES = min(16_384, PROJECTION_DOCUMENT_MAX_BYTES - 4_096)

_BoundedEffectiveValue = Annotated[str, Field(max_length=MAX_CENSAL_PREPARE_VALUE_LENGTH)]
_CensalPath = Annotated[str, Field(min_length=3, max_length=160)]


class CensalPrepareOperationRequest(CredentialFreeOperationRequest):
    """Select one profile for a credential-free local preparation read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request_version: Literal[1] = 1
    profile_id: UUID


class CensalPrepareFieldState(StrEnum):
    """Distinguish absent, present, and explicitly cleared effective facts."""

    UNSET = "unset"
    VALUE = "value"
    CLEARED = "cleared"


class CensalPrepareFieldProjection(BaseModel):
    """One adoptable field's minimal effective state, without provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    path: _CensalPath
    state: CensalPrepareFieldState
    effective_value: _BoundedEffectiveValue | None = None

    @model_validator(mode="after")
    def _validate_state_value(self) -> Self:
        if (self.state is CensalPrepareFieldState.VALUE) != (self.effective_value is not None):
            raise ValueError("censal field state and effective value disagree")
        if self.path not in CENSAL_ADOPTABLE_PATHS:
            raise ValueError("censal preparation may expose only canonical adoptable paths")
        return self


class CensalPrepareOperationProjection(BaseModel):
    """Bounded public preparation data for one exact profile revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    response_version: Literal[1] = 1
    profile_id: UUID
    operation_request: CensalOperationRequest
    effective_fields: tuple[CensalPrepareFieldProjection, ...]

    @model_validator(mode="after")
    def _validate_exact_profile_and_order(self) -> Self:
        if self.operation_request.baseline.profile_id != str(self.profile_id):
            raise ValueError("censal preparation request belongs to another profile")
        if tuple(item.path for item in self.effective_fields) != CENSAL_ADOPTABLE_PATHS:
            raise ValueError("censal preparation fields are not in canonical adoptable-path order")
        return self


def _prepare_exact_profile(
    profile_id: UUID,
    *,
    authority_operation: PinnedAuthorityOperation,
) -> CensalPrepareOperationProjection:
    """Load one authenticated record and project only censal preparation data."""
    profile_id_text = str(profile_id)
    profile_decode_context = authority_operation.profile_decode_context()
    record = ProfileRecordRepository.for_current_session(
        profile_id_text,
        profile_decode_context=profile_decode_context,
    ).load(profile_id_text)
    if record.profile_id != profile_id_text:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    effective = record_to_effective_facts(record)
    effective_fields: list[CensalPrepareFieldProjection] = []
    for path in CENSAL_ADOPTABLE_PATHS:
        current = effective.get(path)
        if current is None:
            field = CensalPrepareFieldProjection(path=path, state=CensalPrepareFieldState.UNSET)
        elif current.value is None:
            field = CensalPrepareFieldProjection(path=path, state=CensalPrepareFieldState.CLEARED)
        else:
            if len(current.value) > MAX_CENSAL_PREPARE_VALUE_LENGTH:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            field = CensalPrepareFieldProjection(
                path=path,
                state=CensalPrepareFieldState.VALUE,
                effective_value=current.value,
            )
        effective_fields.append(field)

    projection = CensalPrepareOperationProjection(
        profile_id=profile_id,
        operation_request=build_censal_operation_request(record),
        effective_fields=tuple(effective_fields),
    )
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _CENSAL_PREPARE_RESULT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return projection


class CensalPrepareOperationExecutor:
    """Read the current profile record and publish its bounded preparation."""

    async def execute(
        self,
        request: OperationRequest[CensalPrepareOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Prepare the canonical review request without provider access or writes."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        subject = profile_operation_subject(profile_id)
        if (
            request.definition_id != CENSAL_PREPARE_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != profile_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        await context.events.phase(CENSAL_PREPARE_PHASE_READ)
        projection = await asyncio.to_thread(
            _prepare_exact_profile,
            payload.profile_id,
            authority_operation=context.authority_operation,
        )

        async def capture() -> str:
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="censal-prepare-operation")


def resolve_censal_prepare_operation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve a period-independent, exact-profile read with no provider."""
    payload = request.payload
    if request.definition_id != CENSAL_PREPARE_OPERATION_DEFINITION_ID or not isinstance(
        payload, CensalPrepareOperationRequest
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

    disclosure = None
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
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
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def build_censal_prepare_operation_definition() -> OperationDefinition:
    """Declare the recorded, credential-free, nonmutating preparation read."""
    return OperationDefinition(
        definition_id=CENSAL_PREPARE_OPERATION_DEFINITION_ID,
        request_type=CensalPrepareOperationRequest,
        result_type=CensalPrepareOperationProjection,
        executor_factory=OperationExecutorFactory(
            request_type=CensalPrepareOperationRequest,
            executor_type=CensalPrepareOperationExecutor,
            build=CensalPrepareOperationExecutor,
        ),
        phase_codes=(CENSAL_PREPARE_PHASE_READ,),
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


def build_censal_prepare_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the credential-free request and exact-profile result schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=CensalPrepareOperationRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=CensalPrepareOperationProjection,
        ),
        access_resolver=resolve_censal_prepare_operation_access,
    )


__all__ = [
    "CENSAL_PREPARE_OPERATION_DEFINITION_ID",
    "MAX_CENSAL_PREPARE_VALUE_LENGTH",
    "CensalPrepareFieldProjection",
    "CensalPrepareFieldState",
    "CensalPrepareOperationExecutor",
    "CensalPrepareOperationProjection",
    "CensalPrepareOperationRequest",
    "build_censal_prepare_operation_definition",
    "build_censal_prepare_operation_registration",
    "resolve_censal_prepare_operation_access",
]
