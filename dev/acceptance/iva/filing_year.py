"""The filing year an IVA acceptance journey runs for, admitted by the published authority.

Every journey takes its filing year explicitly.  Before any side effect it asks
the same published authority it will run against whether each (modelo, period)
coordinate it exercises resolves to a filing-grade revision authored for that
year.  A coordinate the registry only projects from another year's edition
carries no review for the requested year, so a journey refuses it rather than
presenting an earlier design's proof as the requested year's.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection

# The DP30300 header byte ranges each official Modelo 303 record design reserves for the
# "Versión del Programa" and "NIF del desarrollador" fields, keyed by the registry revision
# that carries that design.  Each entry is read from the official design itself, independently
# of the registry, so a journey only checks an export refusal against a design listed here.
_M303_DEVELOPER_HEADER_POSITIONS: Final[Mapping[str, tuple[str, str, str]]] = {
    "2025": ("DP30300", "93-96", "101-109"),
}


class IvaFilingYearUnsupportedError(RuntimeError):
    """A journey cannot run for the requested filing year against the published authority."""


@dataclass(frozen=True, slots=True)
class IvaJourneyYear:
    """One filing year the published authority covers for every coordinate a journey exercises."""

    year: int
    revisions: tuple[tuple[str, str, str], ...]
    """``(modelo, period, revision_id)`` for each exercised coordinate, as the authority selected it."""

    def revision(self, modelo: str, period: str) -> str:
        """Return the authored revision the authority selected for one exercised coordinate."""
        for candidate_modelo, candidate_period, revision_id in self.revisions:
            if (candidate_modelo, candidate_period) == (modelo, period):
                return revision_id
        raise IvaFilingYearUnsupportedError(
            f"modelo {modelo} period {period} was not admitted for filing year {self.year}"
        )

    def iso_date(self, month: int, day: int) -> str:
        """Return the ISO calendar date of ``month``/``day`` inside this filing year."""
        return date(self.year, month, day).isoformat()

    def noon_utc(self, month: int, day: int) -> str:
        """Return an explicit observation instant at noon UTC on ``month``/``day`` of this filing year."""
        return f"{self.iso_date(month, day)}T12:00:00+00:00"


def require_journey_year(*, authority_root: Path, year: int, coordinates: Iterable[tuple[str, str]]) -> IvaJourneyYear:
    """Admit ``year`` only when every ``(modelo, period)`` resolves to a revision authored for it.

    Resolution is the authority's own filing-grade snapshot selection, the same
    call the journeys use to read an exported layout, so the support envelope,
    revision selectors and review gates decide coverage; nothing here encodes a
    year range.

    Raises:
        IvaFilingYearUnsupportedError: When a coordinate does not resolve, or
            resolves only by projecting another year's authored edition.
    """
    requested = tuple(dict.fromkeys(coordinates))
    if not requested:
        raise IvaFilingYearUnsupportedError("a journey must name at least one modelo coordinate to admit a year")
    authority = IndexedRegistryAuthority(authority_root.resolve(strict=True) / "authority.current.json")
    selected: list[tuple[str, str, str]] = []
    try:
        with authority.operation() as operation:
            for modelo, period in requested:
                try:
                    snapshot = operation.snapshot(modelo, filing_year=year, period=period)
                except RegistryError as exc:
                    raise IvaFilingYearUnsupportedError(
                        f"modelo {modelo} has no filing-grade revision for filing year {year} period {period} "
                        f"in the published authority: {type(exc).__name__}: {exc}"
                    ) from exc
                direction = snapshot.revision_projection_direction
                if direction is not TemporalProjectionDirection.AUTHORED:
                    raise IvaFilingYearUnsupportedError(
                        f"modelo {modelo} filing year {year} period {period} is not authored in the published "
                        f"authority: it resolves only by {direction.value} projection of the "
                        f"{snapshot.authored_filing_year} edition (revision {snapshot.revision.id})"
                    )
                selected.append((modelo, period, str(snapshot.revision.id)))
    finally:
        authority.close()
    return IvaJourneyYear(year=year, revisions=tuple(selected))


def require_m303_developer_header_positions(journey_year: IvaJourneyYear, *, period: str) -> tuple[str, str, str]:
    """Return the official DP30300 developer-header positions for the selected Modelo 303 design.

    Raises:
        IvaFilingYearUnsupportedError: When the year selects a record design
            whose positions no official source has supplied to the journey.
    """
    revision_id = journey_year.revision("303", period)
    positions = _M303_DEVELOPER_HEADER_POSITIONS.get(revision_id)
    if positions is None:
        raise IvaFilingYearUnsupportedError(
            f"modelo 303 filing year {journey_year.year} period {period} selects record design revision "
            f"{revision_id}; the journey holds official DP30300 developer-header positions only for revisions "
            f"{sorted(_M303_DEVELOPER_HEADER_POSITIONS)}"
        )
    return positions


__all__ = [
    "IvaFilingYearUnsupportedError",
    "IvaJourneyYear",
    "require_journey_year",
    "require_m303_developer_header_positions",
]
