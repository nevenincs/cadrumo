"""The filing years the published authority supports and what each IVA coordinate reaches in each of them.

Years come only from the support envelope of the authority generation the journeys run against; this
module holds no year, year list or year count. For every supported year it records, per coordinate (the four
Modelo 303 quarters and the Modelo 390 annual summary), the revision the authority selects, whether that
revision is authored for the year or projected from a neighbouring edition, and the highest authority grade
the coordinate reaches. A tier then says which journey phases the year can run:

* ``FULL``: every coordinate reaches filing grade, so the chain runs end to end and the annual summary verifies.
* ``M390_CALCULATION``: the quarters reach filing grade and the annual summary reaches calculation grade only,
  so it is calculated against the oracle and its verification is expected not to be granted.
* ``M390_REFUSED``: the quarters reach filing grade and the annual summary is below calculation grade, so a
  typed refusal is expected.
* ``M303_CALCULATION_ONLY``: some quarter reaches calculation grade but not filing grade, so only a
  calculation-grade chain can run.
* ``M303_UNREACHABLE``: some quarter is below calculation grade, so no chain can run.

The strict gate that refuses any projected coordinate stays in :mod:`.filing_year`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority, PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.authority_store import AUTHORITY_DESCRIPTOR_FILENAME
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution

from .personas import QUARTERS, Modelo303Quarter, Modelo390Year

M303: Final = "303"
M390: Final = "390"
M390_ANNUAL_PERIOD: Final = "0A"

COORDINATES: Final[tuple[tuple[str, str], ...]] = (
    *((M303, quarter) for quarter in QUARTERS),
    (M390, M390_ANNUAL_PERIOD),
)

_LADDER: Final = tuple(RegistryAuthorityGrade)


def _box_numbers(record_type: type[Modelo303Quarter] | type[Modelo390Year]) -> tuple[str, ...]:
    return tuple(field.name.removeprefix("box_") for field in fields(record_type) if field.name.startswith("box_"))


#: The casilla numbers the oracle asserts, taken from its own records so the two cannot drift.
ORACLE_BOXES: Final[Mapping[str, tuple[str, ...]]] = {
    M303: _box_numbers(Modelo303Quarter),
    M390: _box_numbers(Modelo390Year),
}


class BoxResolutionError(LookupError):
    """A casilla number does not resolve to exactly one casilla of the selected revision."""


class YearTier(StrEnum):
    """Which journey phases a filing year can run."""

    FULL = "full"
    M390_CALCULATION = "m390-calculation"
    M390_REFUSED = "m390-refused"
    M303_CALCULATION_ONLY = "m303-calculation-only"
    M303_UNREACHABLE = "m303-unreachable"


def reaches(grade: RegistryAuthorityGrade, floor: RegistryAuthorityGrade) -> bool:
    """Return whether ``grade`` is at least ``floor`` on the authority ladder."""
    return _LADDER.index(grade) >= _LADDER.index(floor)


def classify_year(grades: Mapping[tuple[str, str], RegistryAuthorityGrade]) -> YearTier:
    """Classify one year from the reachable grade of each coordinate.

    Raises:
        KeyError: When a coordinate of :data:`COORDINATES` has no grade.
    """
    quarter_grades = [grades[(M303, quarter)] for quarter in QUARTERS]
    annual_grade = grades[(M390, M390_ANNUAL_PERIOD)]
    if any(not reaches(grade, RegistryAuthorityGrade.CALCULATION) for grade in quarter_grades):
        return YearTier.M303_UNREACHABLE
    if any(not reaches(grade, RegistryAuthorityGrade.FILING) for grade in quarter_grades):
        return YearTier.M303_CALCULATION_ONLY
    if reaches(annual_grade, RegistryAuthorityGrade.FILING):
        return YearTier.FULL
    if reaches(annual_grade, RegistryAuthorityGrade.CALCULATION):
        return YearTier.M390_CALCULATION
    return YearTier.M390_REFUSED


@dataclass(frozen=True, slots=True)
class CoordinateRecord:
    """What the authority answers for one ``(year, modelo, period)`` coordinate."""

    year: int
    modelo: str
    period: str
    revision_id: str
    projection_direction: TemporalProjectionDirection
    authored_filing_year: int
    reachable_grade: RegistryAuthorityGrade
    casilla_ids: tuple[tuple[str, str], ...]
    """``(casilla number, casilla id)`` for each oracle casilla the selected revision carries."""
    unresolved_boxes: tuple[str, ...]
    """Oracle casilla numbers the selected revision does not carry."""

    def casilla_id(self, number: str) -> str:
        """Return the id of the casilla printed with ``number`` in this coordinate's revision.

        Raises:
            BoxResolutionError: When the revision does not carry the number.
        """
        for candidate, casilla_id in self.casilla_ids:
            if candidate == number:
                return casilla_id
        raise BoxResolutionError(
            f"modelo {self.modelo} filing year {self.year} period {self.period} (revision {self.revision_id}) "
            f"carries no casilla numbered {number}"
        )


@dataclass(frozen=True, slots=True)
class YearRow:
    """One supported year with its coordinates and tier."""

    year: int
    records: tuple[CoordinateRecord, ...]
    tier: YearTier

    def record(self, modelo: str, period: str) -> CoordinateRecord:
        """Return the record of one coordinate."""
        for candidate in self.records:
            if (candidate.modelo, candidate.period) == (modelo, period):
                return candidate
        raise KeyError((modelo, period))


@dataclass(frozen=True, slots=True)
class YearMatrix:
    """Every supported year, oldest first."""

    rows: tuple[YearRow, ...]

    @property
    def years(self) -> tuple[int, ...]:
        """The supported years in the order the envelope enumerates them."""
        return tuple(row.year for row in self.rows)

    def row(self, year: int) -> YearRow:
        """Return the row of one supported year."""
        for candidate in self.rows:
            if candidate.year == year:
                return candidate
        raise KeyError(year)

    def years_with_tier(self, tier: YearTier) -> tuple[int, ...]:
        """Return the years whose tier is ``tier``."""
        return tuple(row.year for row in self.rows if row.tier is tier)

    def newest_full_year(self) -> int:
        """Return the newest year that runs end to end.

        Raises:
            LookupError: When no supported year is in the full tier.
        """
        full = self.years_with_tier(YearTier.FULL)
        if not full:
            raise LookupError("no supported filing year reaches filing grade for every IVA coordinate")
        return max(full)


def resolve_casilla_ids(
    revision_casillas: Iterable[tuple[str, str]], numbers: Iterable[str]
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """Map printed casilla numbers to casilla ids from ``(number, id)`` pairs of one revision.

    Returns the resolved ``(number, id)`` pairs and the numbers the revision does not carry.

    Raises:
        BoxResolutionError: When a number names more than one casilla.
    """
    by_number: dict[str, list[str]] = {}
    for number, casilla_id in revision_casillas:
        by_number.setdefault(number, []).append(casilla_id)
    resolved: list[tuple[str, str]] = []
    missing: list[str] = []
    for number in numbers:
        ids = by_number.get(number, [])
        if len(ids) > 1:
            raise BoxResolutionError(f"casilla number {number} names more than one casilla: {sorted(ids)}")
        if ids:
            resolved.append((number, ids[0]))
        else:
            missing.append(number)
    return tuple(resolved), tuple(missing)


def _record(operation: PinnedAuthorityOperation, *, year: int, modelo: str, period: str) -> CoordinateRecord:
    revision = operation.revision_for_context(modelo, filing_year=year, period=period)
    resolution = revision_temporal_resolution(
        revision, filing_year=year, period=period, support=operation.supported_filing_years()
    )
    resolved, missing = resolve_casilla_ids(
        ((casilla.number, str(casilla.id)) for casilla in revision.casillas), ORACLE_BOXES[modelo]
    )
    return CoordinateRecord(
        year=year,
        modelo=modelo,
        period=period,
        revision_id=str(revision.id),
        projection_direction=resolution.projection_direction,
        authored_filing_year=resolution.authored_filing_year,
        reachable_grade=operation.reachable_authority_grade(modelo, filing_year=year, period=period),
        casilla_ids=resolved,
        unresolved_boxes=missing,
    )


def matrix_from_operation(operation: PinnedAuthorityOperation) -> YearMatrix:
    """Build the matrix from one leased authority operation, so every answer reads one generation."""
    rows: list[YearRow] = []
    for year in operation.supported_filing_years().years:
        records = tuple(_record(operation, year=year, modelo=modelo, period=period) for modelo, period in COORDINATES)
        tier = classify_year({(record.modelo, record.period): record.reachable_grade for record in records})
        rows.append(YearRow(year=year, records=records, tier=tier))
    return YearMatrix(rows=tuple(rows))


def build_year_matrix(authority_root: Path) -> YearMatrix:
    """Open the published authority at ``authority_root`` and build the matrix for its support envelope."""
    authority = IndexedRegistryAuthority(authority_root.resolve(strict=True) / AUTHORITY_DESCRIPTOR_FILENAME)
    try:
        with authority.operation() as operation:
            return matrix_from_operation(operation)
    finally:
        authority.close()
