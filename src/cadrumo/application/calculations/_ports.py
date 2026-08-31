"""Structural calculation ports for read-only filed declaration data.

These runtime-checkable protocols declare the subset of AEAT filed-declaration
records that the calculations application layer reads without importing the
Sede adapter. Concrete records such as
:class:`~adapters.outbound.aeat.sede.FiledDeclaracionObservation`,
:class:`~adapters.outbound.aeat.sede.FiledDeclaracionArtefact`, and
:class:`~adapters.outbound.aeat.sede.ObservedCasillaValue` satisfy these
ports structurally while remaining adapter-owned evidence records.

See Also:
    :mod:`application.calculations.iva_compensation_history`:
        Consumes :class:`FiledDeclaracionObservationProtocol` for Modelo 303
        period states and Modelo 390 annual cross-checks.
    :mod:`application.live`:
        Captures filed declarations and promotes registry-consumable
        observations into local encrypted stores.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from ...core.casilla_id import CasillaId
from ...core.casilla_value_kind import CasillaValueKind
from ...core.period import Period


@runtime_checkable
class FiledDeclaracionArtefactProtocol(Protocol):
    """Minimal artefact surface read by calculation evidence consumers.

    The concrete
    :class:`~adapters.outbound.aeat.sede.FiledDeclaracionArtefact`
    carries more capture metadata, but calculation history only needs the
    artefact kind and hash witness to choose submitted-file evidence where it is
    present.
    """

    @property
    def kind(self) -> str:
        """Artefact kind identifier, for example ``submitted_file``."""
        ...

    @property
    def sha256(self) -> str | None:
        """SHA-256 hex digest of the artefact, when available."""
        ...


@runtime_checkable
class ObservedCasillaValueProtocol(Protocol):
    """Minimal casilla-observation surface read by calculations.

    Values arrive as read-only evidence from an adapter-owned
    :class:`~adapters.outbound.aeat.sede.ObservedCasillaValue`. The
    application treats ``casilla_id`` as a canonical ``CasillaId`` string and
    validates it against the resolved registry snapshot before using the value.
    """

    @property
    def source_artefact_kind(self) -> str:
        """Source artefact kind that produced this observation."""
        ...

    @property
    def casilla_id(self) -> CasillaId:
        """Canonical ``CasillaId`` string observed in the filed artefact."""
        ...

    @property
    def value(self) -> str:
        """Raw string value for the casilla observation."""
        ...

    @property
    def value_kind(self) -> CasillaValueKind:
        """How :attr:`value` is meant to be read."""
        ...

    def decimal_value(self) -> Decimal:
        """Return the observed amount, refusing a casilla that is not numeric.

        Read amounts through this rather than converting :attr:`value`: a
        free-text casilla can hold a token that converts cleanly to a plausible
        wrong number, so a conversion attempt is not a type test.
        """
        ...


@runtime_checkable
class FiledDeclaracionObservationProtocol(Protocol):
    """Structural interface for a filed AEAT declaration observation.

    The application layer depends on this protocol rather than the concrete
    :class:`~adapters.outbound.aeat.sede.FiledDeclaracionObservation`
    model, eliminating the application-to-adapter import edge. The surface is
    intentionally limited to the fields consumed by
    :func:`~application.calculations.iva_compensation_history.iva_compensation_state_from_observation_envelope`
    and
    :func:`~application.calculations.iva_compensation_history.iva_compensation_annual_summary_from_filed_observation`.
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
        """Typed :class:`~core.Period` for the declaration."""
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
