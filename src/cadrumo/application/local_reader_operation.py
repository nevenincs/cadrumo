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
    LOCAL_READER_PREFLIGHT_PHASE,
    LOCAL_READER_SETTLEMENT_PHASE,
    LocalReaderProvisionOutcome,
    LocalReaderProvisionPublicResultV1,
    LocalReaderProvisionRequest,
    LocalReaderSetupStep,
    local_reader_setup_phase,
    project_local_reader_result,
)
from .local_reader_provisioning import LocalReaderProvisionExecutor
from .operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .operations.operation_definition import OperationDefinition, OperationExecutorFactory
from .operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from .provisioning_host import (
    InstallerRunner,
    RuntimeSpawner,
)

__all__ = [
    "build_local_reader_operation_definition",
    "build_local_reader_operation_registration",
]

_PHASES = (
    LOCAL_READER_PREFLIGHT_PHASE,
    LOCAL_READER_EXECUTE_PHASE,
    *(local_reader_setup_phase(step) for step in LocalReaderSetupStep),
    LOCAL_READER_SETTLEMENT_PHASE,
)


def build_local_reader_operation_definition(
    *,
    spawn: RuntimeSpawner,
    run_installer: InstallerRunner,
    text_probe: TextExtractionFitnessProbe,
) -> OperationDefinition:
    """Bind the injected process and fitness ports to the canonical provisioning operation."""

    def build() -> LocalReaderProvisionExecutor:
        return LocalReaderProvisionExecutor(spawn=spawn, run_installer=run_installer, text_probe=text_probe)

    return OperationDefinition(
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        request_type=LocalReaderProvisionRequest,
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
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_local_reader_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the provisioning definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{LOCAL_READER_OPERATION_DEFINITION_ID}.request",
            schema_version=1,
            model_type=LocalReaderProvisionRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{LOCAL_READER_OPERATION_DEFINITION_ID}.result",
            schema_version=1,
            model_type=LocalReaderProvisionPublicResultV1,
        ),
        result_projector=project_local_reader_result,
    )
