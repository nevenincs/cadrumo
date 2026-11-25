"""Exact-profile read comparing the imported Modelo 100 borrador with the saved calculation.

The read writes nothing and contacts nothing: it reads the profile's encrypted
borrador store and its Modelo calculation catalogue under the worker's pinned
authority, and serves the comparison in the requested language.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.access_resolution import (
    HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_declared_action,
    require_period_independent_replay_or_authority,
)
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .borrador_100 import Borrador100SnapshotRepository, Borrador100SnapshotService
from .borrador_100_comparison import (
    Borrador100ComparisonProjection,
    Borrador100ComparisonSources,
    compare_borrador_100_with_calculation,
)

BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID = "live.borrador.100.compare"


class Borrador100CompareRequest(CredentialFreeOperationRequest):
    """Exact profile, one Renta year and the language the comparison is served in."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    filing_year: FilingYear
    output_language: OutputLanguage


class Borrador100CompareExecutionResult(BaseModel):
    """Encrypted retention of the served comparison."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: Borrador100ComparisonProjection


@dataclass(frozen=True, slots=True)
class Borrador100ComparisonPorts:
    """The exact profile's borrador store and calculation repositories under one pinned authority."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    borrador_snapshots: Borrador100SnapshotRepository
    sources: Borrador100ComparisonSources


class Borrador100ComparisonPortsFactory(Protocol):
    """Compose the read's repositories only after exact-profile worker admission."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> Borrador100ComparisonPorts:
        """Return the profile's repositories without reading them."""
        ...


def _compose(
    factory: Borrador100ComparisonPortsFactory,
    request: OperationRequest[Borrador100CompareRequest],
    context: OperationExecutorContext,
) -> Borrador100ComparisonPorts:
    profile_id = request.payload.profile_id
    require_operation_profile(request, context, profile_id)
    operation = context.authority_operation
    ports = factory(profile_id=profile_id, operation=operation)
    bucket_id = str(profile_id)
    if (
        ports.profile_id != profile_id
        or ports.operation is not operation
        or ports.borrador_snapshots.bucket_id != bucket_id
        or ports.sources.bucket_id != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


class Borrador100CompareExecutor:
    """Read both sides and serve the comparison without writes or provider calls."""

    def __init__(self, factory: Borrador100ComparisonPortsFactory) -> None:
        """Bind the trusted composition."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[Borrador100CompareRequest], context: OperationExecutorContext
    ) -> str:
        """Compare the year's newest readable draft with the saved calculation."""
        if request.definition_id != BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID)

        def read() -> Borrador100CompareExecutionResult:
            ports = _compose(self._factory, request, context)
            bucket_id = str(payload.profile_id)
            reading = Borrador100SnapshotService(
                bucket_id=bucket_id, repository=ports.borrador_snapshots
            ).read_latest_for_year(filing_year=payload.filing_year, operation=ports.operation)
            stored = (*reading.readable, *(item.snapshot for item in reading.refused))
            if any(snapshot.bucket_id != bucket_id for snapshot in stored):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return Borrador100CompareExecutionResult(
                projection=compare_borrador_100_with_calculation(
                    profile_id=payload.profile_id,
                    filing_year=payload.filing_year,
                    reading=reading,
                    sources=ports.sources,
                    operation=ports.operation,
                    language=payload.output_language,
                )
            )

        result = await await_cancellation_complete(
            asyncio.to_thread(read), task_name=BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID
        )
        await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(result, written_at=now())


def resolve_borrador_100_compare_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Admit the exact profile's human read of its whole-profile tax values."""
    if request.definition_id != BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if type(payload) is not Borrador100CompareRequest:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    access_profile = HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
    require_declared_action(context, actions=access_profile.actions)
    require_period_independent_replay_or_authority(
        context, profile_id=payload.profile_id, definition_id=BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID
    )
    return bind_operation_access_profile(
        context,
        access_profile,
        profile_id=payload.profile_id,
        definition_id=BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID,
        periods=frozenset(),
    )


def project_borrador_100_compare_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the exact successful no-effect comparison."""
    if type(result) is not Borrador100CompareExecutionResult:
        raise ValueError("invalid borrador comparison result")
    projection = result.projection
    if (
        receipt.identity.definition_id != BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("borrador comparison differs from its exact-purpose terminal receipt")
    return Borrador100ComparisonProjection.model_validate_json(projection.model_dump_json(), strict=True)


def build_borrador_100_compare_definition(factory: Borrador100ComparisonPortsFactory) -> OperationDefinition:
    """Declare the exact-profile, no-effect comparison read."""
    return build_single_phase_definition(
        definition_id=BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID,
        request_type=Borrador100CompareRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=Borrador100CompareExecutionResult,
        executor_type=Borrador100CompareExecutor,
        build=lambda: Borrador100CompareExecutor(factory),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
    )


def build_borrador_100_compare_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the public comparison schema, its projector and its access resolver."""
    if definition.definition_id != BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID:
        raise ValueError("borrador comparison registration needs its own definition")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=Borrador100ComparisonProjection,
        result_projector=project_borrador_100_compare_result,
        access_resolver=resolve_borrador_100_compare_access,
    )
