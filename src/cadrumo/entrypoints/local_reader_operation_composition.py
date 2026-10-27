"""Compose the operations that judge and report on what the machine holds for local reading.

The two operations share one subject, the local AI the native component
engine installed and the runtime manager runs. Nothing composed here starts,
installs or removes a program or a model, and nothing asks the local AI
server: the program's state comes from the components role's quick status.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..application.components_operations import ProvisionOutcome
from ..application.dependency_contracts import DependencyItemKind
from ..application.local_reader import ProgramRow
from ..application.local_reader_report import (
    build_local_reader_report_definition,
    build_local_reader_report_registration,
)
from ..application.local_reader_status_operation import (
    build_local_reader_status_definition,
    build_local_reader_status_registration,
)
from ..application.operations.operation_definition import OperationDefinition
from ..application.operations.registry import OperationPublicDefinitionRegistrationV1

__all__ = ["LocalReaderOperations", "build_local_reader_operations", "read_local_ai_program"]


@dataclass(frozen=True, slots=True)
class LocalReaderOperations:
    """The definitions and public registrations of the local reader's operation family."""

    definitions: tuple[OperationDefinition, ...]
    registrations: tuple[OperationPublicDefinitionRegistrationV1, ...]


def read_local_ai_program() -> ProgramRow:
    """Read the local AI program's quick status row from the components role, or ``None`` when it cannot answer.

    A role that cannot start, breaks its protocol, does not answer in time or
    refuses the check reports no row, which the judgement treats as unknown.
    """
    # The component client loads only when a read asks for the program, not when operations are composed.
    from cadrumo_client.contracts.contracts import RefusalError

    from .components_operation_composition import read_component_status

    try:
        result = read_component_status((DependencyItemKind.LOCAL_AI,))
    except RefusalError:
        return None
    if result.outcome is not ProvisionOutcome.OK:
        return None
    return next((row for row in result.rows if row.kind is DependencyItemKind.LOCAL_AI), None)


def build_local_reader_operations() -> LocalReaderOperations:
    """Build the two ``local-reader`` operations."""
    status = build_local_reader_status_definition(read_local_ai_program)
    report = build_local_reader_report_definition()
    return LocalReaderOperations(
        definitions=(status, report),
        registrations=(
            build_local_reader_status_registration(status),
            build_local_reader_report_registration(report),
        ),
    )
