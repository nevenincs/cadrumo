"""How much of each screen's population sits in a revision that can be filed.

Every screen in this package reports a disagreement between declarations. Not
every disagreement costs the same. A revision below filing grade that cannot
state a deadline, or emits an amount at an undetermined magnitude, is declaring
incompletely about something it never does; the same gap in a filing-grade
revision is a defect a filer meets.

That question has been asked one screen at a time, by hand, four times in this
campaign - of the deadline conditions, the unscaled monetary fields, the
published trees and the grade findings - and each time it reordered what
mattered. This asks it of every condition at once.

A screen's entry point does not always return findings. Three shapes exist and
they are not distinguishable from the outside: most screens return findings; the
provenance screen returns findings that its runner entry projects onto a
different unit; and the wire-type screen returns a CENSUS of every
casilla-to-wire transition it examined, carrying a ``divergent`` flag, of which
13,624 rows are 29 findings. Counting a census as findings overstates that
screen by a factor of nearly five hundred, which the first version of this
report did.

The runner table now declares which shape each screen has, on
:attr:`ScreenEntry.entry_returns`, because it cannot be read from the outside and
guessing it produced the error above. A row from a screen declared ``census``
says so, and its exposure figure describes rows EXAMINED rather than defects met.
The runner's own count is carried beside the population either way, so the two
can be compared without trusting the declaration.

This is not a screen. It reports about the screens rather than about the
registry, its unit is a condition rather than a modelo, and it therefore
declares no screen entry point and is enrolled in no runner table. What it
produces is a reading order: a condition whose population is entirely below
filing grade can wait behind one whose population is not.

It reports and gates nothing. Filing-grade exposure is a priority, not an
invariant, and a corpus may legitimately carry a great deal of it while every
gate holds.
"""

from __future__ import annotations

import collections
import sys
from collections.abc import Iterable
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

from ..compiler.authority import compiled_bundled_authority
from .corpus import bundled_modelo_ids
from .screens import CorpusScreenEntry, ScreenEntry, screen_findings

__all__ = [
    "ConditionExposure",
    "RevisionPressure",
    "condition_exposure",
    "filing_grade_revisions",
    "revision_pressure",
]

_FILING = "filing"


def filing_grade_revisions(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> frozenset[tuple[str, str]]:
    """Return every ``(modelo, revision)`` declaring filing grade."""
    return frozenset(
        (modelo_id, str(revision_id))
        for modelo_id in modelo_ids
        for revision_id, revision in authority.modelo(modelo_id).revisions.items()
        if str(getattr(revision, "authority_grade", "")) == _FILING
    )


@dataclass(frozen=True, slots=True)
class ConditionExposure:
    """One screen condition, and how much of it a filer would meet."""

    screen: str
    kind: str
    findings: int
    #: Findings whose revision declares filing grade.
    filing_findings: int
    revisions: int
    filing_revisions: int
    #: What the runner reports for this screen, across all its conditions. A
    #: population far larger than this one means the entry point returned a
    #: census rather than findings, and the exposure above counts rows examined.
    runner_findings: int = 0
    #: What the screen's table entry declares its entry point returns, either
    #: ``findings`` or ``census``. Carried so a consumer reads the declaration
    #: rather than inferring one from the ratio between the two counts.
    entry_returns: str = "findings"
    #: Findings carrying no revision, which were never measured against grade.
    #: Kept separate from a measured zero: several screens report per modelo or
    #: per design because that is their unit - a continuity chain spans
    #: revisions and a design transcription belongs to none - and counting them
    #: as "not filing grade" would turn an unasked question into an answer.
    unmeasured: int = 0

    @property
    def wholly_below_filing(self) -> bool:
        """Whether this condition was measured and none of it can be filed.

        False when nothing was measurable, which is a refusal to claim rather
        than a claim of safety. Eleven conditions looked wholly below filing
        grade on the first run and eight of them had simply never been asked:
        their findings carry no revision at all.
        """
        return self.filing_findings == 0 and self.findings > self.unmeasured


def condition_exposure(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[ConditionExposure, ...]:
    """Return every screen condition with its filing-grade exposure.

    Findings are read from each screen's own entry point, never from the runner
    table: a table entry may project onto a subset, and a projection's exposure
    is the exposure of what survived it rather than of the condition.

    A finding carrying no revision is counted in the total and not in the filing
    figure - a continuity chain spans revisions, so asking which one it sits in
    has no answer, and guessing would report an exposure nobody measured.
    """
    from .screens import CORPUS_SCREENS, SCREENS

    runner, declared = _runner_screen_metadata(authority, modelo_ids, SCREENS, CORPUS_SCREENS)
    filing = filing_grade_revisions(authority, modelo_ids)
    totals: collections.Counter[tuple[str, str]] = collections.Counter()
    filing_totals: collections.Counter[tuple[str, str]] = collections.Counter()
    unmeasured: collections.Counter[tuple[str, str]] = collections.Counter()
    units: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    filing_units: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for name, findings in screen_findings(authority, modelo_ids):
        _count_exposure_findings(name, findings, filing, totals, filing_totals, unmeasured, units, filing_units)
    return _exposure_rows(totals, filing_totals, unmeasured, units, filing_units, runner, declared)


def _runner_screen_metadata(
    authority: ValidatedRegistryAuthority,
    modelo_ids: tuple[str, ...],
    screens: tuple[ScreenEntry, ...],
    corpus_screens: tuple[CorpusScreenEntry, ...],
) -> tuple[dict[str, int], dict[str, str]]:
    """Read runner counts and declared return shapes beside condition findings."""
    runner: dict[str, int] = {}
    declared: dict[str, str] = {}
    for entry in screens:
        runner[entry.name] = len(tuple(entry.run(authority, modelo_ids)))
        declared[entry.name] = entry.entry_returns
    for entry in corpus_screens:
        runner[entry.name] = len(tuple(entry.run()))
        declared[entry.name] = entry.entry_returns
    return runner, declared


def _count_exposure_findings(
    name: str,
    findings: Iterable[object],
    filing: frozenset[tuple[str, str]],
    totals: collections.Counter[tuple[str, str]],
    filing_totals: collections.Counter[tuple[str, str]],
    unmeasured: collections.Counter[tuple[str, str]],
    units: dict[tuple[str, str], set[tuple[str, str]]],
    filing_units: dict[tuple[str, str], set[tuple[str, str]]],
) -> None:
    """Accumulate one screen's findings, preserving unmeasured rows separately."""
    for finding in findings:
        kind = getattr(finding, "kind", name)
        if not isinstance(kind, str):
            kind = name
        key = (name, kind)
        totals[key] += 1
        modelo = getattr(finding, "modelo", None)
        revision = getattr(finding, "revision", None)
        if modelo is None or revision is None:
            unmeasured[key] += 1
            continue
        unit = (str(modelo), str(revision))
        units[key].add(unit)
        if unit in filing:
            filing_totals[key] += 1
            filing_units[key].add(unit)


def _exposure_rows(
    totals: collections.Counter[tuple[str, str]],
    filing_totals: collections.Counter[tuple[str, str]],
    unmeasured: collections.Counter[tuple[str, str]],
    units: dict[tuple[str, str], set[tuple[str, str]]],
    filing_units: dict[tuple[str, str], set[tuple[str, str]]],
    runner: dict[str, int],
    declared: dict[str, str],
) -> tuple[ConditionExposure, ...]:
    """Construct and order the condition-level report rows."""
    rows = (
        ConditionExposure(
            screen=screen,
            kind=kind,
            findings=count,
            filing_findings=filing_totals[(screen, kind)],
            revisions=len(units[(screen, kind)]),
            filing_revisions=len(filing_units[(screen, kind)]),
            unmeasured=unmeasured[(screen, kind)],
            runner_findings=runner.get(screen, 0),
            entry_returns=declared.get(screen, "findings"),
        )
        for (screen, kind), count in totals.items()
    )
    return tuple(sorted(rows, key=lambda item: (-item.filing_findings, item.screen, item.kind)))


@dataclass(frozen=True, slots=True)
class RevisionPressure:
    """One fileable revision, and how many distinct conditions it carries."""

    modelo: str
    revision: str
    conditions: tuple[str, ...]

    @property
    def count(self) -> int:
        """How many distinct screen conditions name this revision."""
        return len(self.conditions)


def revision_pressure(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[RevisionPressure, ...]:
    """Rank filing-grade revisions by how many distinct conditions name them.

    The other axis. Exposure asks which CONDITION a filer would meet; this asks
    which REVISION carries the most of them, and the two disagree about what to
    do first. Sixty-seven of the sixty-nine fileable revisions carry at least one
    condition, so choosing by condition means touching almost every revision;
    choosing by revision clears several conditions at a time.

    A count of conditions is not a severity. A revision carrying one
    filing-correctness defect is worse than one carrying four declaration
    untidinesses, and nothing here weighs them - the conditions are named on each
    row so a reader can see which they are rather than trusting the number.

    Census screens are excluded, for the reason their declaration exists: their
    rows are transitions examined, and counting them would rank a revision by how
    many fields it has. Screens declaring a source they derive from are excluded
    too: they re-describe that source's findings, so counting both makes one
    condition look like two, and modelo 200's leading revision was reported with
    nine conditions where seven are independent.
    """
    from .screens import CORPUS_SCREENS, SCREENS

    census, derived = _pressure_exclusions(SCREENS, CORPUS_SCREENS)
    filing = filing_grade_revisions(authority, modelo_ids)
    carried: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for name, findings in screen_findings(authority, modelo_ids):
        _count_pressure_findings(name, findings, census, derived, filing, carried)
    return _pressure_rows(carried)


def _pressure_exclusions(
    screens: tuple[ScreenEntry, ...],
    corpus_screens: tuple[CorpusScreenEntry, ...],
) -> tuple[set[str], set[str]]:
    """Identify census populations and derived views that cannot be ranked as independent defects."""
    census = {entry.name for entry in (*screens, *corpus_screens) if entry.entry_returns == "census"}
    # A screen built on another re-describes its findings, so counting both
    # reports a revision as carrying two conditions where it has one. Measured:
    # the grounding screen returns the same 41 cells the pointer screen does.
    derived = {entry.name for entry in screens if entry.derives_from is not None}
    return census, derived


def _count_pressure_findings(
    name: str,
    findings: Iterable[object],
    census: set[str],
    derived: set[str],
    filing: frozenset[tuple[str, str]],
    carried: dict[tuple[str, str], set[str]],
) -> None:
    """Add independent filing-grade condition names for one screen."""
    if name in census or name in derived:
        return
    for finding in findings:
        modelo = getattr(finding, "modelo", None)
        revision = getattr(finding, "revision", None)
        if modelo is None or revision is None:
            continue
        unit = (str(modelo), str(revision))
        if unit in filing:
            carried[unit].add(f"{name}.{getattr(finding, 'kind', name)}")


def _pressure_rows(carried: dict[tuple[str, str], set[str]]) -> tuple[RevisionPressure, ...]:
    """Construct and order one report row for each revision with measured pressure."""
    return tuple(
        sorted(
            (
                RevisionPressure(modelo=modelo, revision=revision, conditions=tuple(sorted(kinds)))
                for (modelo, revision), kinds in carried.items()
            ),
            key=lambda item: (-item.count, item.modelo, item.revision),
        )
    )


def main() -> int:
    """Print one row per condition, most filing-exposed first; always exit 0."""
    authority = compiled_bundled_authority()
    modelo_ids = bundled_modelo_ids()
    exposures = condition_exposure(authority, modelo_ids)
    pressures = revision_pressure(authority, modelo_ids)
    _print_exposure_rows(exposures)
    _print_pressure_rows(pressures)
    _print_summary(authority, modelo_ids, exposures)
    return 0


def _print_exposure_rows(exposures: tuple[ConditionExposure, ...]) -> None:
    """Print one exposure row per condition."""
    for item in exposures:
        sys.stdout.write(
            f"filing_exposure screen={item.screen} kind={item.kind} findings={item.findings} "
            f"filing_findings={item.filing_findings} revisions={item.revisions} "
            f"filing_revisions={item.filing_revisions} unmeasured={item.unmeasured} "
            f"runner_findings={item.runner_findings} entry_returns={item.entry_returns} "
            f"wholly_below_filing={str(item.wholly_below_filing).lower()}\n"
        )


def _print_pressure_rows(pressures: tuple[RevisionPressure, ...]) -> None:
    """Print one pressure row per filing-grade revision."""
    # Exposure summed over screens that return findings. A census's rows are
    # examined transitions, and adding them to a defect count is the error this
    # declaration exists to stop.
    for pressure in pressures:
        sys.stdout.write(
            f"revision_pressure modelo={pressure.modelo} revision={pressure.revision} "
            f"conditions={pressure.count} kinds={','.join(pressure.conditions)}\n"
        )


def _print_summary(
    authority: ValidatedRegistryAuthority,
    modelo_ids: tuple[str, ...],
    exposures: tuple[ConditionExposure, ...],
) -> None:
    """Print the exposure denominator and filing-grade revision count."""
    conditions = _summary_conditions(exposures)
    sys.stdout.write(
        f"summary conditions={len(exposures)} with_filing_exposure={len(conditions.exposed)} "
        f"filing_findings={conditions.filing_findings} "
        f"census_rows_examined={conditions.census_rows_examined} "
        f"wholly_below_filing={conditions.wholly_below_filing} "
        f"unmeasurable={conditions.unmeasurable} "
        f"filing_grade_revisions={len(filing_grade_revisions(authority, modelo_ids))}\n"
    )


@dataclass(frozen=True, slots=True)
class _SummaryConditions:
    """Derived counters for the report's final reading-order line."""

    exposed: tuple[ConditionExposure, ...]
    filing_findings: int
    census_rows_examined: int
    wholly_below_filing: int
    unmeasurable: int


def _summary_conditions(exposures: tuple[ConditionExposure, ...]) -> _SummaryConditions:
    """Aggregate the disjoint exposure populations for the CLI summary."""
    exposed = tuple(item for item in exposures if item.filing_findings and item.entry_returns == "findings")
    return _SummaryConditions(
        exposed=exposed,
        filing_findings=sum(item.filing_findings for item in exposed),
        census_rows_examined=sum(item.findings for item in exposures if item.entry_returns == "census"),
        wholly_below_filing=sum(item.wholly_below_filing for item in exposures),
        unmeasurable=sum(item.findings == item.unmeasured for item in exposures),
    )


if __name__ == "__main__":
    raise SystemExit(main())
