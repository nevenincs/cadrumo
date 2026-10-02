"""Application-owned ports for live filed-declaration acquisition.

The filed-data use case coordinates register walks and persistence, but it does
not know how an authenticated Sede page is opened or how a browser adapter
captures one row.  Those transport details are supplied through this module's
small structural ports by an outer composition root.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Protocol

from ...core.period import Period
from .filed_observation_ports import (
    FiledDeclarationProtocol,
    FiledObservationArtefactProtocol,
    FiledObservationProtocol,
)
from .session import SessionWriteReporter

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
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
FiledEffectGuard = Callable[[], AbstractAsyncContextManager[None]]


class LocalEffectTracker:
    """Identify failures raised inside an authorized local persistence fence."""

    def __init__(self, guard: FiledEffectGuard) -> None:
        self._guard = guard
        self.failed = False
        self.started = False

    @asynccontextmanager
    async def enter(self) -> AsyncGenerator[None]:
        """Propagate local write failures instead of reporting a remote miss."""
        try:
            async with self._guard():
                self.started = True
                yield
        except BaseException:
            self.failed = True
            raise


class DeferredFiledObservation(Protocol):
    """Remote capture whose source bytes remain local until an authorized write."""

    def persist_artefacts(self, sink: FiledArtefactSink) -> FiledObservationProtocol:
        """Persist captured bytes and return the observation with secure references."""
        ...


class DeferredFiledObservations(Protocol):
    """A source capture batch whose artefact bytes await local authorization."""

    def persist_artefacts(self, sink: FiledArtefactSink) -> tuple[FiledObservationProtocol, ...]:
        """Persist the entire captured batch under one local effect fence."""
        ...


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

    async def capture_observation_deferred(
        self, declaration: FiledRegisterDeclarationProtocol
    ) -> DeferredFiledObservation:
        """Capture one row without writing local artefacts during remote I/O."""
        ...


class FiledDataCapturePort(Protocol):
    """Outer-composed Sede capability for filed-data acquisition."""

    def open_register(
        self,
        *,
        operation: str,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> AbstractAsyncContextManager[FiledDataRegisterPort]:
        """Open one reusable register session for a walk or capture sweep."""
        ...

    async def discover_availability(
        self,
        *,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
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
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> tuple[FiledObservationProtocol, ...]:
        """Capture registry-selected previous-filing and relation sources.

        Core types:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
        """
        ...

    async def capture_source_observations_deferred(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> DeferredFiledObservations:
        """Fetch source rows and bytes without any local artefact persistence."""
        ...


__all__ = [
    "DeferredFiledObservation",
    "DeferredFiledObservations",
    "FiledArtefactSink",
    "FiledDataCapturePort",
    "FiledDataRegisterPort",
    "FiledDeclarationAvailabilityProtocol",
    "FiledDeclarationAvailabilityReportProtocol",
    "FiledEffectGuard",
    "FiledRegisterDeclarationProtocol",
]
