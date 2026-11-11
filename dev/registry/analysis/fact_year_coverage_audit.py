"""Gate: a governed fact family must answer every supported filing year or none.

A fact track (same date axis and selectors) whose variant windows reach some
supported filing years and miss others is a year-dependent result: the law
either changed or the declaration was authored for the years someone happened
to test. Standing rates are exempt because the resolver answers every date from
the nearest edition. Years come only from the registry support envelope.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cadrumo.domain.calculations.registry.facts.schema import GovernedFact
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue

from ..compiler.fact_providers import compile_registered_fact_providers

__all__ = (
    "FactYearFinding",
    "TrackView",
    "YearValuedFinding",
    "fact_year_findings",
    "render_fact_year_findings",
    "render_year_valued_findings",
    "track_findings",
    "year_valued_findings",
)


@dataclass(frozen=True, slots=True)
class TrackView:
    """One fact track with its variant windows as ``(valid_from, valid_to)`` pairs."""

    fact_id: str
    family: str
    track: str
    windows: tuple[tuple[date, date | None], ...]
    standing: bool = False


@dataclass(frozen=True, slots=True)
class FactYearFinding:
    """A fact track answering some supported years and not others."""

    fact_id: str
    family: str
    track: str
    covered_years: tuple[int, ...]
    missing_years: tuple[int, ...]

    @property
    def key(self) -> str:
        """Return the stable baseline key."""
        return f"fact-year-gap|{self.fact_id}|{self.track}"


@dataclass(frozen=True, slots=True)
class YearValuedFinding:
    """A scalar fact whose value is a supported filing year its sources do not state."""

    fact_id: str
    variant_id: str
    value: int

    @property
    def key(self) -> str:
        """Return the stable baseline key."""
        return f"year-valued-fact|{self.fact_id}|{self.variant_id}|{self.value}"


def _year_value(value: object, years: Sequence[int]) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value in years:
        return value
    return None


def _quotes_year(citations: Iterable[tuple[str, ...]], value: int) -> bool:
    return any(str(value) in text for required in citations for text in required)


def year_valued_findings(facts: Iterable[GovernedFact], years: Sequence[int]) -> tuple[YearValuedFinding, ...]:
    """Return scalar variants whose value is a supported year, unless a citation quotes that year.

    A fact whose value is a year makes a result depend on a particular year; it
    is acceptable only when the official text it is grounded in states that year.
    """
    found: list[YearValuedFinding] = []
    for fact in facts:
        for variant in fact.variants:
            value = _year_value(getattr(variant.payload, "value", None), years)
            if value is None or _quotes_year((c.required_text for c in variant.source_citations), value):
                continue
            found.append(YearValuedFinding(fact.fact_id, variant.variant_id, value))
    return tuple(sorted(found, key=lambda item: (item.fact_id, item.variant_id)))


def render_year_valued_findings(findings: Sequence[YearValuedFinding]) -> list[str]:
    """Render the year-valued facts."""
    lines = [f"facts whose value is a supported filing year not quoted by a citation: {len(findings)}"]
    lines.extend(f"  {item.fact_id} variant={item.variant_id} value={item.value}" for item in findings)
    return lines


def _year_covered(year: int, windows: Iterable[tuple[date, date | None]]) -> bool:
    start, end = date(year, 1, 1), date(year, 12, 31)
    return any(valid_from <= end and (valid_to is None or valid_to >= start) for valid_from, valid_to in windows)


def track_findings(tracks: Iterable[TrackView], years: Sequence[int]) -> tuple[FactYearFinding, ...]:
    """Return tracks whose windows cover a strict, non-empty subset of ``years``."""
    findings: list[FactYearFinding] = []
    for track in tracks:
        if track.standing:
            continue
        covered = tuple(year for year in years if _year_covered(year, track.windows))
        missing = tuple(year for year in years if year not in covered)
        if covered and missing:
            findings.append(FactYearFinding(track.fact_id, track.family, track.track, covered, missing))
    return tuple(sorted(findings, key=lambda item: (item.fact_id, item.track)))


def _track_key(selectors: Iterable[object], axis: str) -> str:
    return f"{axis}|" + ",".join(sorted(f"{getattr(s, 'name', '')}={getattr(s, 'value', None)!r}" for s in selectors))


def _fact_tracks(fact: GovernedFact, support: SupportedFilingYearsCatalogue) -> list[TrackView]:
    windows = fact.materialized_windows(support.date_envelope())
    grouped: dict[str, list[tuple[date, date | None]]] = defaultdict(list)
    standing: dict[str, bool] = {}
    for variant in fact.variants:
        key = _track_key(variant.selectors, variant.date_axis.value)
        window = windows[variant.variant_id]
        grouped[key].append((window.valid_from, window.valid_to))
        standing[key] = fact.stands_for(variant.selectors)
    return [
        TrackView(fact.fact_id, fact.family.value, key, tuple(items), standing[key]) for key, items in grouped.items()
    ]


def fact_year_findings(
    registry_root: Path, modelos: Iterable[ModeloDefinition], support: SupportedFilingYearsCatalogue
) -> tuple[tuple[FactYearFinding, ...], tuple[YearValuedFinding, ...]]:
    """Compile the registered facts; report partially covered tracks and year-valued facts."""
    catalogue = compile_registered_fact_providers(registry_root, modelos=modelos)
    facts = tuple(catalogue.facts.values())
    tracks = [track for fact in facts for track in _fact_tracks(fact, support)]
    return track_findings(tracks, support.years), year_valued_findings(facts, support.years)


def render_fact_year_findings(findings: Sequence[FactYearFinding]) -> list[str]:
    """Render a per-fact summary followed by one line per partially covered track."""
    per_fact: dict[str, int] = defaultdict(int)
    for finding in findings:
        per_fact[finding.fact_id] += 1
    lines = [f"fact tracks answering some supported years and not others: {len(findings)} in {len(per_fact)} facts"]
    lines.extend(f"  count fact={fact_id} tracks={n}" for fact_id, n in sorted(per_fact.items()))
    lines.extend(
        f"  {item.fact_id} [{item.family}] track={item.track} missing={list(item.missing_years)} "
        f"covered={list(item.covered_years)}"
        for item in findings
    )
    return lines
