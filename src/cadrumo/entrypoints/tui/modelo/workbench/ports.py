"""What the workbench asks of the application, supplied by the composition root.

The screen holds no repository, registry or operation service. It is handed an
object that answers these questions, calls it off the event loop, and renders
the answers. Each answer is a frozen application read model, so the screen can
never observe it change mid-render.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.work_form_models import ModeloWorkForm
from .....core.casilla_id import CasillaId
from .....core.external_constants import OutputLanguage


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


__all__ = ["ModeloWorkbenchReaderV1", "WorkbenchLoadV1"]
