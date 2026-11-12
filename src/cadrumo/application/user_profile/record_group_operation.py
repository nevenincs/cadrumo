"""Registered read of the active profile's record groups, with the ledger rows that name them."""

from __future__ import annotations

import asyncio

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationInteractionKind, profile_operation_subject
from ...core.time.clock import now
from ..operations.capabilities import EPHEMERAL_CREDENTIAL_FREE_READ_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from .profile_operation_access import resolve_profile_view_access
from .record_group_contracts import (
    PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID,
    PROFILE_RECORD_GROUPS_PHASES,
    ProfileRecordGroupsProjection,
    ProfileRecordGroupsRequest,
    ProfileRecordGroupsResult,
    project_record_groups_result,
)
from .record_groups import LedgerRowsLoader, read_profile_record_groups


class ProfileRecordGroupsExecutor:
    """Read the record groups through the canonical encrypted record owner and the profile's ledger."""

    def __init__(self, ledger_rows: LedgerRowsLoader) -> None:
        """Bind the read of the profile's ledger rows the groups join."""
        self._ledger_rows = ledger_rows

    async def execute(
        self,
        request: OperationRequest[ProfileRecordGroupsRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read the record and the ledger once and persist the page; the read has no effect."""
        profile_id = str(request.payload.profile_id)
        if request.subject_ref != profile_operation_subject(profile_id):
            raise ValueError("record group read subject does not match its exact profile")
        if require_active_bucket_id() != profile_id:
            raise ValueError("record group read requires its profile to be active")
        await context.events.phase(PROFILE_RECORD_GROUPS_PHASES[0])
        result = await await_cancellation_complete(
            asyncio.to_thread(
                read_profile_record_groups,
                request.payload,
                authority_operation=context.authority_operation,
                ledger_rows=self._ledger_rows,
            ),
            task_name="profile-record-groups-read",
        )
        await context.events.phase(PROFILE_RECORD_GROUPS_PHASES[1])
        result_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return result_ref


def build_record_groups_definition(ledger_rows: LedgerRowsLoader) -> OperationDefinition:
    """Declare the exact-profile read of the record groups over ``ledger_rows``."""
    return OperationDefinition(
        definition_id=PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID,
        request_type=ProfileRecordGroupsRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=ProfileRecordGroupsResult,
        executor_factory=OperationExecutorFactory(
            request_type=ProfileRecordGroupsRequest,
            executor_type=ProfileRecordGroupsExecutor,
            build=lambda: ProfileRecordGroupsExecutor(ledger_rows),
        ),
        phase_codes=PROFILE_RECORD_GROUPS_PHASES,
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=EPHEMERAL_CREDENTIAL_FREE_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        public_error_detail=True,
    )


def build_record_groups_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the read to its stable public schemas, exact-profile access and receipt projection."""
    if definition.definition_id != PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID:
        raise ValueError(f"{definition.definition_id}: not the record group read")
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{definition.definition_id}.request", schema_version=1, model_type=ProfileRecordGroupsRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{definition.definition_id}.result",
            schema_version=1,
            model_type=ProfileRecordGroupsProjection,
        ),
        result_projector=project_record_groups_result,
        access_resolver=resolve_profile_view_access,
    )


__all__ = [
    "ProfileRecordGroupsExecutor",
    "build_record_groups_definition",
    "build_record_groups_registration",
]
