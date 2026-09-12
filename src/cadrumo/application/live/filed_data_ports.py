"""Application-owned ports for live filed-declaration acquisition.

The filed-data use case coordinates register walks and persistence, but it does
not know how an authenticated Sede page is opened or how a browser adapter
captures one row.  Those transport details are supplied through this module's
small structural ports by an outer composition root.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from ...core.period import Period
from .filed_observation_ports import (
    FiledDeclarationProtocol,
    FiledObservationArtefactProtocol,
    FiledObservationProtocol,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import ModeloRevision


class FiledRegisterDeclarationProtocol(FiledDeclarationProtocol, Protocol):
    """Full register-row view needed by listing and capture orchestration."""

    @property
    def ejercicio(self) -> int:
        """Return the filing year carried by the register row."""
        ...

    @property
    def tipo_solicitud(self) -> str | None:
        """Return the optional AEAT request type text."""
        ...

    @property
    def observaciones(self) -> str | None:
        """Return optional register observations text."""
        ...

    @property
    def justificante_link_text(self) -> str | None:
        """Return the receipt-link label when AEAT exposed one."""
        ...

    @property
    def archive_link_text(self) -> str | None:
        """Return the submitted-file link label when AEAT exposed one."""
        ...

    @property
    def declaration_copy_link_text(self) -> str | None:
        """Return the declaration-copy link label when AEAT exposed one."""
        ...

    @property
    def justificante_cell_index(self) -> int:
        """Return the register cell containing the receipt link."""
        ...

    @property
    def archive_cell_index(self) -> int | None:
        """Return the register cell containing the submitted-file link."""
        ...

    @property
    def declaration_copy_cell_index(self) -> int | None:
        """Return the register cell containing the declaration-copy link."""
        ...


class FiledDeclarationAvailabilityProtocol(Protocol):
    """One modelo and the years the external register offered for it."""

    @property
    def modelo(self) -> str:
        """Return the offered modelo code."""
        ...

    @property
    def ejercicios(self) -> Sequence[int]:
        """Return offered filing years in register order."""
        ...


class FiledDeclarationAvailabilityReportProtocol(Protocol):
    """Read-only offered-option report returned by the acquisition port."""

    @property
    def items(self) -> Sequence[FiledDeclarationAvailabilityProtocol]:
        """Return one offered-year record per register modelo option."""
        ...

    @property
    def offered_pairs(self) -> tuple[tuple[str, int], ...]:
        """Return the offered ``(modelo, ejercicio)`` pairs."""
        ...


FiledArtefactSink = Callable[..., FiledObservationArtefactProtocol]


class FiledDataRegisterPort(Protocol):
    """Authenticated register session used by one filed-data operation."""

    @property
    def walk_timeout_ms(self) -> int:
        """Return the configured timeout for one register walk."""
        ...

    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[FiledRegisterDeclarationProtocol, ...]:
        """Read one modelo/year register result."""
        ...

    async def capture_observation(
        self,
        declaration: FiledRegisterDeclarationProtocol,
        *,
        artefact_sink: FiledArtefactSink | None = None,
    ) -> FiledObservationProtocol:
        """Capture one register row's evidence through the authenticated session."""
        ...


class FiledDataCapturePort(Protocol):
    """Outer-composed Sede capability for filed-data acquisition."""

    def open_register(self, *, operation: str) -> AbstractAsyncContextManager[FiledDataRegisterPort]:
        """Open one reusable register session for a walk or capture sweep."""
        ...

    async def discover_availability(
        self,
        *,
        operation: str,
    ) -> FiledDeclarationAvailabilityReportProtocol:
        """Read the register's offered modelo/year options."""
        ...

    async def capture_source_observations(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        artefact_sink: FiledArtefactSink | None = None,
        operation: str,
    ) -> tuple[FiledObservationProtocol, ...]:
        """Capture registry-selected previous-filing and relation sources."""
        ...


__all__ = [
    "FiledArtefactSink",
    "FiledDataCapturePort",
    "FiledDataRegisterPort",
    "FiledDeclarationAvailabilityProtocol",
    "FiledDeclarationAvailabilityReportProtocol",
    "FiledRegisterDeclarationProtocol",
]
