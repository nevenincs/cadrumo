"""Compose the operations that judge and report on the local document reader.

The two operations share one subject, the local reader of this machine. Nothing
composed here starts, installs or removes a program or a model, and nothing
asks the local AI server.
"""

from __future__ import annotations

from dataclasses import dataclass

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

__all__ = ["LocalReaderOperations", "build_local_reader_operations"]


@dataclass(frozen=True, slots=True)
class LocalReaderOperations:
    """The definitions and public registrations of the local reader's operation family."""

    definitions: tuple[OperationDefinition, ...]
    registrations: tuple[OperationPublicDefinitionRegistrationV1, ...]


def build_local_reader_operations() -> LocalReaderOperations:
    """Build the two ``local-reader`` operations."""
    status = build_local_reader_status_definition()
    report = build_local_reader_report_definition()
    return LocalReaderOperations(
        definitions=(status, report),
        registrations=(
            build_local_reader_status_registration(status),
            build_local_reader_report_registration(report),
        ),
    )
