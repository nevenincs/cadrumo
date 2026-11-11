"""Gate: every supported period resolves to exactly one edition.

The publication proof sweep skips a period no edition covers and never
exercises a date overlap. This audit asks the canonical selector for every
period a modelo prints, in every supported filing year, and fails on a period
it cannot place (no edition) and on a period it cannot choose between (two
editions). A year before the modelo's declared inception is not owed an edition.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.errors import AmbiguousRevisionSelectionError, NoRevisionForPeriodError
from cadrumo.domain.calculations.registry.modelo_inception import DeclaredInception
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.temporal import select_revision

__all__ = ("PeriodCoverageFinding", "period_coverage_findings")


@dataclass(frozen=True, slots=True)
class PeriodCoverageFinding:
    """A supported period no edition covers, or two editions both cover."""

    modelo: str
    period: str
    year: int
    outcome: str

    @property
    def key(self) -> str:
        """Return the stable baseline key."""
        return f"period-{self.outcome}|{self.modelo}|{self.period}|{self.year}"


def _printed_periods(modelo: ModeloDefinition) -> tuple[str, ...]:
    tokens = {period for revision in modelo.revisions.values() for period in revision.period_selector.declared_periods}
    return tuple(sorted(tokens))


def _first_owed_year(modelo: ModeloDefinition, floor: int) -> int:
    inception = modelo.inception
    return max(floor, inception.filing_year) if isinstance(inception, DeclaredInception) else floor


def _outcome(modelo: ModeloDefinition, year: int, period: str, support: SupportedFilingYearsCatalogue) -> str | None:
    try:
        select_revision(modelo, filing_year=year, period=period, support=support)
    except AmbiguousRevisionSelectionError:
        return "overlap"
    except NoRevisionForPeriodError:
        return "uncovered"
    return None


def period_coverage_findings(
    modelos: Iterable[ModeloDefinition], support: SupportedFilingYearsCatalogue
) -> tuple[PeriodCoverageFinding, ...]:
    """Return every (modelo, period, year) the selector cannot place or choose."""
    found: list[PeriodCoverageFinding] = []
    for modelo in modelos:
        first = _first_owed_year(modelo, support.floor)
        for period in _printed_periods(modelo):
            for year in (year for year in support.years if year >= first):
                outcome = _outcome(modelo, year, period, support)
                if outcome is not None:
                    found.append(PeriodCoverageFinding(str(modelo.id), period, year, outcome))
    return tuple(sorted(found, key=lambda item: item.key))
