"""Generic event vocabulary shared by operation public and owner contracts."""

from enum import StrEnum
from typing import Annotated

from pydantic import Field

from .models import OperationDiagnosticReference

OperationEventSequence = Annotated[int, Field(ge=1)]
OperationEventCode = Annotated[
    str,
    Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"),
]


class OperationLogSeverity(StrEnum):
    """Closed severity axis for safe operation log projections."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


__all__ = [
    "OperationDiagnosticReference",
    "OperationEventCode",
    "OperationEventSequence",
    "OperationLogSeverity",
]
