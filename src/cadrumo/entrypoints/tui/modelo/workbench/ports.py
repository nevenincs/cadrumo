"""What the workbench asks of the application, supplied by the composition root.

The screen holds no repository, registry or operation service. It is handed an
object that answers these questions, calls it off the event loop, and renders
the answers. Each answer is a frozen application read model, so the screen can
never observe it change mid-render.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.work_form_models import (
    ModeloFormAddressV1,
    ModeloFormField,
    ModeloFormScalar,
    ModeloWorkForm,
)
from .....core.casilla_id import CasillaId
from .....core.external_constants import OutputLanguage

if TYPE_CHECKING:
    from ...operations.controller import OperationController


@dataclass(frozen=True, slots=True)
class WorkbenchLoadV1:
    """One read of a declaration: its form and the lifecycle facts the journey needs."""

    form: ModeloWorkForm
    verified: bool
    filed: bool


class ModeloWorkbenchReaderV1(Protocol):
    """Reads one declaration's form and the help of its casillas."""

    def load(self, language: OutputLanguage) -> WorkbenchLoadV1:
        """Read the declaration's current form in ``language``."""
        ...

    def help_card(self, casilla_id: CasillaId, language: OutputLanguage) -> ModeloCasillaHelpCardV1:
        """Assemble the mechanical help of one casilla in ``language``."""
        ...


class WorkbenchChangeKind(StrEnum):
    """What one staged change asks the application to do with an address."""

    #: Declare this value.
    SET = "set"
    #: Remove the value the filer declared; nothing replaces it.
    CLEAR = "clear"
    #: Stop replacing the source's value; the source wins again.
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class WorkbenchChange:
    """One staged change, addressed semantically and typed, never a raw lexeme."""

    address: ModeloFormAddressV1
    kind: WorkbenchChangeKind
    value: ModeloFormScalar = None


@dataclass(frozen=True, slots=True)
class WorkbenchParsed:
    """A lexeme the application read as a typed value, and how that value reads back."""

    value: ModeloFormScalar
    display: str


@dataclass(frozen=True, slots=True)
class WorkbenchRefused:
    """A lexeme the application could not read, with a sentence saying how to fix it."""

    message: str


type WorkbenchParseOutcome = WorkbenchParsed | WorkbenchRefused


class ModeloWorkbenchActionsV1(Protocol):
    """Parses the filer's typing and runs the declaration's operations."""

    def parse(self, field: ModeloFormField, lexeme: str, language: OutputLanguage) -> WorkbenchParseOutcome:
        """Read what the filer typed for one field, in the language they typed it in."""
        ...

    async def apply(self, changes: tuple[WorkbenchChange, ...]) -> OperationController:
        """Submit the staged changes and recalculate, through the supervised operation."""
        ...

    async def calculate(self) -> OperationController:
        """Recalculate the declaration, keeping the filer's values."""
        ...

    async def verify(self) -> OperationController:
        """Verify the current calculation."""
        ...

    async def file(self) -> OperationController:
        """Record the verified calculation as filed locally."""
        ...


__all__ = [
    "ModeloWorkbenchActionsV1",
    "ModeloWorkbenchReaderV1",
    "WorkbenchChange",
    "WorkbenchChangeKind",
    "WorkbenchLoadV1",
    "WorkbenchParseOutcome",
    "WorkbenchParsed",
    "WorkbenchRefused",
]
