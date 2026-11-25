"""Coverage of the persona table against what the application itself projects as owed.

The table's rows come from each persona's expectations (``rows.owed_rows``).
This audit reads, at the registry's own horizon only, the overview calendar of
each materialised persona with suppressed obligations shown, and compares its
projection per return ``(modelo, year, period)`` with the rows the table runs:

* ``covered``: the calendar shows a filing window and the table runs the return;
* ``gaps``: the calendar shows a window and the table does not run the return;
* ``table_only``: the table runs a return the calendar does not show a window for,
  with what the calendar says of it instead;
* ``undecided``: the calendar cannot decide the obligation (``incomplete``), so the
  table may need a row stating the refusal;
* ``not_ended``: a window whose period had not ended on the persona's scenario day,
  which no replay owes yet;
* ``refused``: a persona whose calendar read was refused, left out of the comparison.

No year is declared here: the years are the envelope's.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from pathlib import Path

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.period import calculation_filing_date

OUT_ENV = "PERSONA_COVERAGE_OUT"
"""The JSON-lines file the calendar collector appends its observations to."""
PERSONAS_ENV = "PERSONA_COVERAGE_PERSONAS"
"""The comma-separated personas the calendar collector reads; empty reads every one."""

type ReturnKey = tuple[str, int, str]
"""``(modelo, year, period)``."""

APPLICABLE = "applicable"
"""The projection of a return the calendar shows a filing window for."""
ABSENT = "absent"
"""What the calendar says of a return it neither shows nor suppresses."""
_DECIDED = frozenset({APPLICABLE, "not_applicable", "attribution_pass_through"})
"""Verdicts that settle an obligation; any other suppressed verdict leaves it undecided."""


@dataclass(frozen=True, slots=True)
class CalendarObservation:
    """One return as the calendar of one persona projects it."""

    persona: str
    modelo: str
    year: int
    period: str
    verdict: str
    """``applicable`` for a window row, else the suppressed row's applicability verdict."""
    reason: str = ""

    @property
    def key(self) -> ReturnKey:
        """The return ``(modelo, year, period)``."""
        return (self.modelo, self.year, self.period)

    def to_json(self) -> str:
        """One JSON line."""
        return json.dumps(
            {
                "persona": self.persona,
                "modelo": self.modelo,
                "year": self.year,
                "period": self.period,
                "verdict": self.verdict,
                "reason": self.reason,
            },
            ensure_ascii=False,
            sort_keys=True,
        )


@dataclass(frozen=True, slots=True)
class CalendarRefusal:
    """A persona whose materialisation or calendar read was refused."""

    persona: str
    reason: str

    def to_json(self) -> str:
        """One JSON line."""
        return json.dumps({"persona": self.persona, "refused": self.reason}, ensure_ascii=False, sort_keys=True)


def read_observations(path: Path) -> tuple[list[CalendarObservation], list[CalendarRefusal]]:
    """The observations and refusals in the JSON-lines file the calendar collector wrote."""
    observations: list[CalendarObservation] = []
    refusals: list[CalendarRefusal] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if "refused" in data:
            refusals.append(CalendarRefusal(persona=data["persona"], reason=data["refused"]))
        else:
            observations.append(CalendarObservation(**data))
    return observations, refusals


def projection(observations: Iterable[CalendarObservation]) -> dict[ReturnKey, CalendarObservation]:
    """One observation per return: a window row wins over a suppressed row, then the first suppressed row."""
    found: dict[ReturnKey, CalendarObservation] = {}
    for observation in observations:
        held = found.get(observation.key)
        if held is None or (observation.verdict == APPLICABLE and held.verdict != APPLICABLE):
            found[observation.key] = observation
    return found


@cache
def period_end(year: int, period: str) -> date:
    """The last day of the period of return ``(year, period)``.

    A Modelo 202 instalment has no date span: its end is that of its payment
    month, which the published authority declares, so it is read under the
    pinned generation rather than a governed-fact scope that a bare helper lacks.
    """
    with bundled_indexed_authority().operation() as operation:
        return calculation_filing_date(Period.from_year_and_code(year, period), authority=operation)


def _ended(key: ReturnKey, today: date) -> bool:
    """Whether the return's period ended before ``today``, as ``rows.ended`` takes it; an unknown token counts."""
    _, year, period = key
    try:
        return period_end(year, period) < today
    except ValueError:
        return True


@dataclass(slots=True)
class CoverageReport:
    """The comparison of the calendar's projection with the table's rows, at one horizon."""

    horizon: int
    personas: list[str] = field(default_factory=list)
    covered: list[tuple[str, str, int, str]] = field(default_factory=list)
    gaps: list[dict[str, object]] = field(default_factory=list)
    table_only: list[dict[str, object]] = field(default_factory=list)
    undecided: list[dict[str, object]] = field(default_factory=list)
    not_ended: list[dict[str, object]] = field(default_factory=list)
    refused: list[dict[str, object]] = field(default_factory=list)

    def to_json(self) -> str:
        """The report as one JSON document."""
        data = {
            "horizon": self.horizon,
            "personas": self.personas,
            "covered": [list(item) for item in self.covered],
            "gaps": self.gaps,
            "table_only": self.table_only,
            "undecided": self.undecided,
            "not_ended": self.not_ended,
            "refused": self.refused,
        }
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def compare(
    horizon: int,
    table: Mapping[str, Iterable[ReturnKey]],
    observations: Iterable[CalendarObservation],
    scenario_days: Mapping[str, date],
    refusals: Iterable[CalendarRefusal] = (),
) -> CoverageReport:
    """Compare, per persona of ``table``, the returns the table runs with the calendar's projection.

    ``table`` maps each persona to the returns its replay under ``horizon`` runs;
    ``scenario_days`` gives each persona's scenario day, before which a period
    must have ended for a window to be owed. A persona in ``refusals`` is listed
    as refused and not compared.
    """
    refused = {refusal.persona: refusal.reason for refusal in refusals}
    by_persona = _group_by_persona(observations)
    report = CoverageReport(horizon=horizon, personas=sorted(table))
    for persona in report.personas:
        if persona in refused:
            report.refused.append({"persona": persona, "reason": refused[persona]})
            continue
        _compare_persona(
            report, persona, set(table[persona]), projection(by_persona.get(persona, ())), scenario_days[persona]
        )
    return report


def _group_by_persona(observations: Iterable[CalendarObservation]) -> dict[str, list[CalendarObservation]]:
    """The observations split by the persona whose calendar showed them."""
    by_persona: dict[str, list[CalendarObservation]] = {}
    for observation in observations:
        by_persona.setdefault(observation.persona, []).append(observation)
    return by_persona


def _compare_persona(
    report: CoverageReport,
    persona: str,
    runs: set[ReturnKey],
    shown: Mapping[ReturnKey, CalendarObservation],
    today: date,
) -> None:
    """File each return of one persona, shown or run, under the report's buckets."""
    for key in sorted(set(shown) | runs):
        modelo, year, period = key
        where: dict[str, object] = {"persona": persona, "modelo": modelo, "year": year, "period": period}
        observed = shown.get(key)
        verdict = observed.verdict if observed is not None else ABSENT
        _file_verdict(report, where, key, verdict, key in runs, today)
        if observed is not None and verdict not in _DECIDED:
            report.undecided.append(where | {"reason": f"{verdict}: {observed.reason}", "in_table": key in runs})


def _file_verdict(
    report: CoverageReport, where: dict[str, object], key: ReturnKey, verdict: str, in_table: bool, today: date
) -> None:
    """Place one return as covered, gap, not ended or table only, by the calendar's verdict and the table."""
    if verdict == APPLICABLE:
        if in_table:
            report.covered.append((str(where["persona"]), key[0], key[1], key[2]))
        elif _ended(key, today):
            report.gaps.append(where | {"source": "calendar_applicable"})
        else:
            report.not_ended.append(where | {"source": "calendar_applicable"})
    elif in_table:
        report.table_only.append(where | {"app_verdict": verdict})


def render_markdown(report: CoverageReport) -> str:
    """The report grouped by persona, for a reader."""
    lines = [
        f"# Persona table coverage against the calendar (horizon {report.horizon} only)",
        "",
        "Rows the table runs at the newest replay horizon, compared with the overview calendar's projection "
        "(windows applicable; suppressed rows with their verdict) for every envelope year.",
        "",
        f"covered {len(report.covered)}, gaps {len(report.gaps)}, table only {len(report.table_only)}, "
        f"undecided {len(report.undecided)}, not ended {len(report.not_ended)}, refused {len(report.refused)}",
        "",
    ]
    for persona in report.personas:
        lines += _persona_section(report, persona)
    return "\n".join(lines)


def _persona_section(report: CoverageReport, persona: str) -> list[str]:
    """The markdown lines of one persona: its refusal, or its covered count and each bucket."""
    lines: list[str] = [f"## {persona}", ""]
    refusal = next((item for item in report.refused if item["persona"] == persona), None)
    if refusal is not None:
        return [*lines, f"- calendar refused: {refusal['reason']}", ""]
    lines.append(f"- covered: {sum(1 for item in report.covered if item[0] == persona)}")
    sections = (
        ("gaps (calendar applicable, not run)", report.gaps, None),
        ("table only (run, calendar does not show a window)", report.table_only, "app_verdict"),
        ("undecided (calendar cannot decide)", report.undecided, "reason"),
        ("not ended at the scenario day", report.not_ended, None),
    )
    for title, items, detail in sections:
        lines += _bucket_lines(title, items, persona, detail)
    lines.append("")
    return lines


def _bucket_lines(title: str, items: list[dict[str, object]], persona: str, detail: str | None) -> list[str]:
    """The lines for one bucket's items of one persona; none when it has none."""
    mine = [item for item in items if item["persona"] == persona]
    if not mine:
        return []
    lines = [f"- {title}: {len(mine)}"]
    for item in mine:
        suffix = f" — {item[detail]}" if detail is not None else ""
        lines.append(f"  - {item['modelo']} {item['year']} {item['period']}{suffix}")
    return lines


__all__ = [
    "ABSENT",
    "APPLICABLE",
    "OUT_ENV",
    "PERSONAS_ENV",
    "CalendarObservation",
    "CalendarRefusal",
    "CoverageReport",
    "compare",
    "period_end",
    "projection",
    "read_observations",
    "render_markdown",
]
