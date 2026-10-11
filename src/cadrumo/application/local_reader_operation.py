"""Supervised operation for provisioning the local document reader from any frontend.

One definition, ``local-reader.provision``, carries every action a status area
or the command line offers -- install, start, pull, load, verify, remove, and
the one-shot setup that runs the first five in order -- so a TUI button and
``aeat config provision <verb>`` run the same implementation. Installing runs
a package manager and therefore requires ``consent`` on the request; every
frontend gathers that consent explicitly before submitting.

Process control is injected. The application layer never spawns a process
itself; the entrypoint composition binds the outbound adapters.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from ..core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from .local_reader import (
    TextExtractionFitnessProbe,
)
from .local_reader_contracts import (
    LOCAL_READER_EXECUTE_PHASE,
    LOCAL_READER_OPERATION_DEFINITION_ID,
    LOCAL_READER_OPERATION_SUBJECT,
    LOCAL_READER_PREFLIGHT_PHASE,
    LOCAL_READER_SETTLEMENT_PHASE,
    LocalReaderProvisionAction,
    LocalReaderProvisionOutcome,
    LocalReaderProvisionPublicResultV2,
    LocalReaderProvisionRequest,
    LocalReaderSetupStep,
    local_reader_setup_phase,
    project_local_reader_result,
)
from .local_reader_provisioning import LocalReaderProvisionExecutor, RuntimeServerOwnerStart
from .operations.access_resolution import (
    LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_replayed_period_independent_access,
    with_commit_action,
)
from .operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .operations.models import OperationRequest
from .operations.operation_definition import OperationDefinition, OperationExecutorFactory
from .operations.profile_guard import require_access_request_payload
from .operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from .operations.subject_reference import OperationSubjectReferenceV1
from .provisioning_host import (
    InstallerRunner,
    RuntimeSpawner,
)
from .user_profile.access_contracts import AccessDenialCode
from .user_profile.access_errors import ProfileAccessRefusedError

__all__ = [
    "LOCAL_READER_REQUEST_SCHEMA_VERSION",
    "LOCAL_READER_RESULT_SCHEMA_VERSION",
    "bind_machine_provisioning_access",
    "build_local_reader_operation_definition",
    "build_local_reader_operation_registration",
    "resolve_local_reader_provision_access",
]

LOCAL_READER_REQUEST_SCHEMA_VERSION = 2
LOCAL_READER_RESULT_SCHEMA_VERSION = 2

_PHASES = (
    LOCAL_READER_PREFLIGHT_PHASE,
    LOCAL_READER_EXECUTE_PHASE,
    *(local_reader_setup_phase(step) for step in LocalReaderSetupStep),
    LOCAL_READER_SETTLEMENT_PHASE,
)


def build_local_reader_operation_definition(
    *,
    spawn: RuntimeSpawner | RuntimeServerOwnerStart,
    run_installer: InstallerRunner,
    text_probe: TextExtractionFitnessProbe,
) -> OperationDefinition:
    """Bind the injected process and fitness ports to the canonical provisioning operation.

    ``spawn`` starts the runtime's server from the executing process, or
    through the process that owns it when the executing one is contained.
    """

    def build() -> LocalReaderProvisionExecutor:
        return LocalReaderProvisionExecutor(spawn=spawn, run_installer=run_installer, text_probe=text_probe)

    return OperationDefinition(
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        request_type=LocalReaderProvisionRequest,
        subject_reference=OperationSubjectReferenceV1.fixed(LOCAL_READER_OPERATION_SUBJECT),
        result_type=LocalReaderProvisionOutcome,
        executor_factory=OperationExecutorFactory(
            request_type=LocalReaderProvisionRequest,
            executor_type=LocalReaderProvisionExecutor,
            build=build,
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset[OperationInteractionKind](),
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
            # Pulling several models, or a setup that installs and then stops
            # at a later step, commits only part of what was asked.
            permitted_effects=frozenset(OperationEffect),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
    )


def build_local_reader_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the provisioning definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{LOCAL_READER_OPERATION_DEFINITION_ID}.request",
            schema_version=LOCAL_READER_REQUEST_SCHEMA_VERSION,
            model_type=LocalReaderProvisionRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{LOCAL_READER_OPERATION_DEFINITION_ID}.result",
            schema_version=LOCAL_READER_RESULT_SCHEMA_VERSION,
            model_type=LocalReaderProvisionPublicResultV2,
        ),
        result_projector=project_local_reader_result,
        access_resolver=resolve_local_reader_provision_access,
    )


def bind_machine_provisioning_access[PayloadT: BaseModel](
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    payload_type: type[PayloadT],
    subject_ref: str,
    commits: Callable[[PayloadT], bool],
) -> ResolvedOperationAccess:
    """Bind period-independent access to one thing the machine holds, with COMMIT where ``commits`` says so.

    What is provisioned belongs to the machine, so the request names no profile
    and its subject is the fixed one the operation declares. A request that
    can install, start, load or remove something carries COMMIT, so a session
    whose scope holds none is refused it at submission; one that only measures
    does not.
    """
    payload = require_access_request_payload(request, definition_id=definition_id, payload_type=payload_type)
    if context.contract.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.subject_ref != subject_ref:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    resolved = bind_replayed_period_independent_access(
        context,
        LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
        definition_id=definition_id,
    )
    return with_commit_action(resolved) if commits(payload) else resolved


def resolve_local_reader_provision_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind access to the machine's reader, with COMMIT for every action but verify.

    Verify measures and changes nothing; every other action can install,
    start, load or remove something.
    """
    return bind_machine_provisioning_access(
        request,
        context,
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        payload_type=LocalReaderProvisionRequest,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        commits=lambda payload: payload.action is not LocalReaderProvisionAction.VERIFY,
    )
