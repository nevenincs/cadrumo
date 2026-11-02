"""Registered operations that read and state the RIRPF art. 7 election for one ejercicio."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..operations.capabilities import (
    EPHEMERAL_CREDENTIAL_FREE_READ_CAPABILITIES,
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..wizard.errors import WizardMissingFlagError, WizardValidationError
from .capsule_record import ProfileRecordConflictError
from .imputation_election_contracts import (
    PROFILE_IMPUTATION_ELECTION_READ_OPERATION_DEFINITION_ID,
    PROFILE_IMPUTATION_ELECTION_READ_PHASES,
    PROFILE_IMPUTATION_ELECTION_SET_OPERATION_DEFINITION_ID,
    PROFILE_IMPUTATION_ELECTION_SET_PHASES,
    ProfileImputationElectionReadProjection,
    ProfileImputationElectionReadRequest,
    ProfileImputationElectionReadResult,
    ProfileImputationElectionSetProjection,
    ProfileImputationElectionSetRequest,
    ProfileImputationElectionSetResult,
    project_imputation_election_read_result,
    project_imputation_election_set_result,
)
from .imputation_election_service import apply_imputation_election, read_imputation_election
from .profile_operation_access import resolve_profile_mutation_access, resolve_profile_view_access


def _require_active_profile_subject(
    request: OperationRequest[ProfileImputationElectionReadRequest]
    | OperationRequest[ProfileImputationElectionSetRequest],
) -> None:
    profile_id = str(request.payload.profile_id)
    if request.subject_ref != profile_operation_subject(profile_id):
        raise ValueError("imputation election operation subject does not match its exact profile")
    if require_active_bucket_id() != profile_id:
        raise ValueError("imputation election operation requires its profile to be active")


class ProfileImputationElectionReadExecutor:
    """Read one ejercicio's election through the canonical encrypted record owner."""

    async def execute(
        self,
        request: OperationRequest[ProfileImputationElectionReadRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read the record once and persist the worded result; the read has no effect."""
        _require_active_profile_subject(request)
        await context.events.phase(PROFILE_IMPUTATION_ELECTION_READ_PHASES[0])
        result = await await_cancellation_complete(
            asyncio.to_thread(
                read_imputation_election, request.payload, authority_operation=context.authority_operation
            ),
            task_name="profile-imputation-election-read",
        )
        await context.events.phase(PROFILE_IMPUTATION_ELECTION_READ_PHASES[1])
        result_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return result_ref


class ProfileImputationElectionSetExecutor:
    """Publish one ejercicio's election through the wizard's validator and the shared fact writer."""

    async def execute(
        self,
        request: OperationRequest[ProfileImputationElectionSetRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Persist the change witness inside the commit guard; a refusal before publication has no effect."""
        payload = request.payload
        _require_active_profile_subject(request)
        await context.events.phase(PROFILE_IMPUTATION_ELECTION_SET_PHASES[0])
        await context.events.phase(PROFILE_IMPUTATION_ELECTION_SET_PHASES[1])

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    record = await asyncio.to_thread(
                        apply_imputation_election, payload, authority_operation=context.authority_operation
                    )
                except (ProfileRecordConflictError, WizardValidationError, WizardMissingFlagError):
                    await context.events.effect(OperationEffect.NONE)
                    raise
                result = ProfileImputationElectionSetResult(
                    profile_id=payload.profile_id,
                    record_revision=record.record_revision,
                    content_digest=record.content_digest,
                    tax_year=payload.tax_year,
                    changed=record.record_revision != payload.expected_revision,
                )
                result_ref = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED if result.changed else OperationEffect.NONE)
                return result_ref

        result_ref = await await_cancellation_complete(publish(), task_name="profile-imputation-election-publication")
        await context.events.phase(PROFILE_IMPUTATION_ELECTION_SET_PHASES[2])
        return result_ref


def _definition(
    *,
    definition_id: str,
    request_type: type[ProfileImputationElectionReadRequest] | type[ProfileImputationElectionSetRequest],
    result_type: type[ProfileImputationElectionReadResult] | type[ProfileImputationElectionSetResult],
    executor_type: type[ProfileImputationElectionReadExecutor] | type[ProfileImputationElectionSetExecutor],
    phase_codes: tuple[str, ...],
    capabilities: OperationCapabilities,
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type, executor_type=executor_type, build=executor_type
        ),
        phase_codes=phase_codes,
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=capabilities,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        public_error_detail=True,
    )


def build_imputation_election_definitions() -> tuple[OperationDefinition, ...]:
    """Return the election read and the election change, in definition order."""
    return (
        _definition(
            definition_id=PROFILE_IMPUTATION_ELECTION_READ_OPERATION_DEFINITION_ID,
            request_type=ProfileImputationElectionReadRequest,
            result_type=ProfileImputationElectionReadResult,
            executor_type=ProfileImputationElectionReadExecutor,
            phase_codes=PROFILE_IMPUTATION_ELECTION_READ_PHASES,
            capabilities=EPHEMERAL_CREDENTIAL_FREE_READ_CAPABILITIES,
        ),
        _definition(
            definition_id=PROFILE_IMPUTATION_ELECTION_SET_OPERATION_DEFINITION_ID,
            request_type=ProfileImputationElectionSetRequest,
            result_type=ProfileImputationElectionSetResult,
            executor_type=ProfileImputationElectionSetExecutor,
            phase_codes=PROFILE_IMPUTATION_ELECTION_SET_PHASES,
            capabilities=OperationCapabilities(
                durability=OperationDurability.RECORDED,
                cancellation=OperationCancellation.UNSUPPORTED,
                deadline=OperationDeadline.ABSENT,
                replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
                baseline=OperationBaselinePolicy.NONE,
                request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
                sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
                conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
                owned_resources=frozenset(),
                permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
                close_policy=OperationClosePolicy.DETACH_ALLOWED,
            ),
        ),
    )


def _schema(definition: OperationDefinition, schema_kind: str, model_type: type[BaseModel]) -> OperationSchemaBindingV1:
    return OperationSchemaBindingV1.bind(
        schema_id=f"{definition.definition_id}.{schema_kind}", schema_version=1, model_type=model_type
    )


def build_imputation_election_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind the election definitions to their stable public schemas and exact-profile access."""
    registrations: list[OperationPublicDefinitionRegistrationV1] = []
    for definition in definitions:
        if definition.definition_id == PROFILE_IMPUTATION_ELECTION_READ_OPERATION_DEFINITION_ID:
            registrations.append(
                OperationPublicDefinitionRegistrationV1.compose(
                    definition=definition,
                    request_schema=_schema(definition, "request", definition.request_type),
                    result_schema=_schema(definition, "result", ProfileImputationElectionReadProjection),
                    result_projector=project_imputation_election_read_result,
                    access_resolver=resolve_profile_view_access,
                )
            )
        elif definition.definition_id == PROFILE_IMPUTATION_ELECTION_SET_OPERATION_DEFINITION_ID:
            registrations.append(
                OperationPublicDefinitionRegistrationV1.compose(
                    definition=definition,
                    request_schema=_schema(definition, "request", definition.request_type),
                    result_schema=_schema(definition, "result", ProfileImputationElectionSetProjection),
                    result_projector=project_imputation_election_set_result,
                    access_resolver=resolve_profile_mutation_access,
                )
            )
        else:
            raise ValueError(f"{definition.definition_id}: not an imputation election definition")
    return tuple(sorted(registrations, key=lambda item: item.contract.definition_id))


__all__ = [
    "ProfileImputationElectionReadExecutor",
    "ProfileImputationElectionSetExecutor",
    "build_imputation_election_definitions",
    "build_imputation_election_registrations",
]
