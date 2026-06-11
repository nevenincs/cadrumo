"""Protocol definitions for application-layer calculations boundary ports.

These protocols declare the interfaces the calculations application layer
depends on for filed declaration data.  Concrete implementations live in
the adapter layer and satisfy these protocols structurally.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from ...core import Period


@runtime_checkable
class FiledDeclaracionArtefactProtocol(Protocol):
    """Minimal surface the application reads from a filed declaration artefact."""

    @property
    def kind(self) -> str:
        """Artefact kind identifier (e.g. 'submitted_file')."""
        ...

    @property
    def sha256(self) -> str | None:
        """SHA-256 hex digest of the artefact, when available."""
        ...


@runtime_checkable
class ObservedCasillaValueProtocol(Protocol):
    """Minimal surface the application reads from an observed casilla value."""

    @property
    def source_artefact_kind(self) -> str:
        """Source artefact kind that produced this observation."""
        ...

    @property
    def casilla_id(self) -> str:
        """Casilla identifier string."""
        ...

    @property
    def value(self) -> str:
        """Raw string value for the casilla observation."""
        ...


@runtime_checkable
class FiledDeclaracionObservationProtocol(Protocol):
    """Structural interface for a filed AEAT declaration observation.

    The application layer depends on this protocol rather than the concrete
    ``FiledDeclaracionObservation`` model from
    ``adapters/outbound/aeat/sede/_schema.py``, eliminating the
    application -> adapters import edge at
    ``application/calculations/_iva_compensation_history.py:13``.
    """

    @property
    def modelo(self) -> str:
        """AEAT modelo identifier (e.g. '303')."""
        ...

    @property
    def ejercicio(self) -> int:
        """Tax year (fiscal year) for this declaration."""
        ...

    @property
    def period(self) -> Period:
        """Typed filing period for the declaration."""
        ...

    @property
    def expediente_id(self) -> str:
        """AEAT expediente identifier."""
        ...

    @property
    def status(self) -> str:
        """Filing status string."""
        ...

    @property
    def presented_at(self) -> datetime:
        """Timestamp when the declaration was presented to AEAT."""
        ...

    @property
    def authenticated_identity(self) -> str:
        """NIF of the authenticated taxpayer who presented the declaration."""
        ...

    @property
    def artefacts(self) -> Sequence[FiledDeclaracionArtefactProtocol]:
        """Sequence of artefacts attached to this declaration.

        Each element satisfies :class:`FiledDeclaracionArtefactProtocol`.
        """
        ...

    @property
    def casillas(self) -> Sequence[ObservedCasillaValueProtocol]:
        """Sequence of :class:`ObservedCasillaValueProtocol` values extracted from the declaration."""
        ...


__all__ = [
    "FiledDeclaracionArtefactProtocol",
    "FiledDeclaracionObservationProtocol",
    "ObservedCasillaValueProtocol",
]
