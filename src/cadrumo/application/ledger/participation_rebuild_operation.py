"""Guarded regeneration of the profile's derived finalized participation index."""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel, NonNegativeInt

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ..modelo.participation_index_rebuild import rebuild_participation_index
from ..modelo.participation_index_rebuild_ports import ParticipationIndexRebuildPortsFactory
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .read_access import resolve_ledger_commit_access

LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID = "ledger.participation.rebuild"


class LedgerParticipationRebuildRequest(CredentialFreeOperationRequest):
    """An explicit profile whose derived index is to be replaced."""

    profile_id: UUID


class LedgerParticipationRebuildProjection(BaseModel):
    """The canonical committed replacement counts for the bound profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_count: NonNegativeInt
    participation_count: NonNegativeInt
    revision_count: NonNegativeInt
    stale_removed_count: NonNegativeInt


class LedgerParticipationRebuildExecutor:
    """Rebuild only within current whole-profile COMMIT authority."""

    def __init__(self, ports: ParticipationIndexRebuildPortsFactory) -> None:
        """Retain the explicit profile-bound repository composition."""
        self._ports = ports

    async def execute(
        self, request: OperationRequest[LedgerParticipationRebuildRequest], context: OperationExecutorContext
    ) -> str:
        """Hold the denial fence through canonical reads, replacement and receipt publication."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if (
            request.definition_id != LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(bucket_id)
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID)

        def rebuild() -> LedgerParticipationRebuildProjection:
            ports = self._ports(bucket_id=bucket_id, operation=context.authority_operation)
            if (
                ports.calculation_repository.bucket_id != bucket_id
                or ports.work_unit_repository.bucket_id != bucket_id
                or ports.filing_repository.bucket_id != bucket_id
                or ports.participation_index_repository.bucket_id != bucket_id
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            stats = rebuild_participation_index(ports=ports, operation=context.authority_operation)
            return LedgerParticipationRebuildProjection(
                profile_id=payload.profile_id,
                transaction_count=stats.transaction_count,
                participation_count=stats.participation_count,
                revision_count=stats.revision_count,
                stale_removed_count=stats.stale_removed_count,
            )

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                projection = await asyncio.to_thread(rebuild)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(projection, written_at=now())

        return await await_cancellation_complete(commit(), task_name="ledger-participation-rebuild")


def build_ledger_participation_rebuild_definition(ports: ParticipationIndexRebuildPortsFactory) -> OperationDefinition:
    """Declare one guarded index replacement with interrupted effects retained honestly."""
    return build_single_phase_definition(
        definition_id=LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
        request_type=LedgerParticipationRebuildRequest,
        result_type=LedgerParticipationRebuildProjection,
        executor_type=LedgerParticipationRebuildExecutor,
        build=lambda: LedgerParticipationRebuildExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def resolve_ledger_participation_rebuild_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require unrestricted periods and explicit COMMIT for the index replacement."""
    if request.definition_id != LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerParticipationRebuildRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_participation_rebuild_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the replacement receipt and its exact-profile mutation policy."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerParticipationRebuildRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerParticipationRebuildProjection,
        ),
        access_resolver=resolve_ledger_participation_rebuild_access,
    )
