"""Rows of the persona table: which returns a persona owes, how each stage ended, and the row's verdict.

A row is one return, keyed persona | modelo | year | period. The rows a
persona owes come from its stated obligations and stated values; the years
come from replaying the persona with the registry horizon moved down to each
supported year, so a scenario written against ``horizon-1`` yields a row for
every year the envelope supports. No year is declared here.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from cadrumo.tests.personas import Persona, PersonaCatalogueError, YearEnvelope, YearToken


class Stage(StrEnum):
    """How one stage of a row ended."""

    PASSED = "pass"
    MISMATCH = "mismatch"
    """Calculate only: casillas differ from the persona's stated values."""
    CALCULATED = "calculated"
    """Calculate only: the return calculated, and the persona states no values to compare."""
    EXPECTED_REFUSAL = "expected-refusal"
    """Calculate only: the application refused with the code the persona states."""
    REFUSAL_NOT_RAISED = "refusal-not-raised"
    """Calculate only: the persona states a refusal, and the return calculated."""
    INCOMPLETE = "incomplete"
    """Verify only: verificado completo was not granted."""
    REFUSED = "refused"
    UNSUPPORTED = "unsupported"
    HISTORY_FILED = "history-filed"
    NOT_REACHED = "-"
    NOT_RUN = "not-run"


class Verdict(StrEnum):
    """What a row counts as in the summary; only ``pass`` is a live, grounded pass of all three stages."""

    PASSED = "pass"
    FAIL = "fail"
    EXPECTED_REFUSAL = "expected-refusal"
    HISTORY_FILED = "history-filed"
    UNVERIFIED = "unverified"
    NO_ORACLE = "no-oracle"
    UNSUPPORTED = "unsupported"
    NOT_RUN = "not-run"


VERDICT_MEANING: dict[Verdict, str] = {
    Verdict.PASSED: "a live calculation equals values grounded in an official source, verificado completo is granted "
    "and the fichero BOE is written",
    Verdict.FAIL: "a live calculation ran and at least one stage is red",
    Verdict.EXPECTED_REFUSAL: "the application refuses with the code the persona states for that return",
    Verdict.HISTORY_FILED: "filed by the persona's history replay; no value is asserted and nothing is exported",
    Verdict.UNVERIFIED: "the stated values cite no official source (grounding `unverified` or no legal_ref); "
    "stages are shown but the row is not a pass",
    Verdict.NO_ORACLE: "the persona owes the return but states no values for it; stages are shown, nothing compared",
    Verdict.UNSUPPORTED: "the application refuses the return as unsupported",
    Verdict.NOT_RUN: "the persona could not be replayed for that year, or the runner itself failed",
}

GREEN = frozenset({Verdict.PASSED})
"""Verdicts a row is green at; a diff reports a row entering or leaving this set."""

_UNSUPPORTED_MARKERS = ("UNSUPPORTED", "NOT_SUPPORTED")


@dataclass(frozen=True, slots=True)
class PlannedRow:
    """One return a persona owes in one replay, before it runs."""

    persona: str
    modelo: str
    year: int
    period: str
    horizon: int
    """The registry horizon the persona is replayed under for this row."""
    has_values: bool
    grounding: str
    """The stated values' grounding, ``none`` when the persona states none."""
    sources: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str, int, str]:
        """The row key ``(persona, modelo, year, period)``."""
        return (self.persona, self.modelo, self.year, self.period)


@dataclass(frozen=True, slots=True)
class TableRow:
    """One return and how it went."""

    persona: str
    modelo: str
    year: int
    period: str
    horizon: int
    grounding: str
    sources: tuple[str, ...]
    has_values: bool
    calculate: Stage
    verify: Stage = Stage.NOT_REACHED
    export: Stage = Stage.NOT_REACHED
    reason: str = ""
    export_detail: str = ""
    verdict: Verdict = field(init=False)

    def __post_init__(self) -> None:
        """Derive the verdict from the stages, the grounding and the oracle."""
        object.__setattr__(self, "verdict", classify(self))

    @property
    def key(self) -> tuple[str, str, int, str]:
        """The row key ``(persona, modelo, year, period)``."""
        return (self.persona, self.modelo, self.year, self.period)

    @classmethod
    def from_plan(
        cls,
        plan: PlannedRow,
        calculate: Stage,
        *,
        verify: Stage = Stage.NOT_REACHED,
        export: Stage = Stage.NOT_REACHED,
        reason: str = "",
        export_detail: str = "",
    ) -> TableRow:
        """The row of ``plan`` with the stages it reached."""
        return cls(
            persona=plan.persona,
            modelo=plan.modelo,
            year=plan.year,
            period=plan.period,
            horizon=plan.horizon,
            grounding=plan.grounding,
            sources=plan.sources,
            has_values=plan.has_values,
            calculate=calculate,
            verify=verify,
            export=export,
            reason=reason,
            export_detail=export_detail,
        )

    def to_json(self) -> str:
        """One JSON line; the verdict is written for readers and re-derived on load."""
        data = asdict(self)
        data["sources"] = list(self.sources)
        return json.dumps(data, ensure_ascii=False, sort_keys=True)

    def to_baseline_json(self, horizon: int) -> str:
        """One baseline line: years as tokens on ``horizon`` and no free text, so the ratchet holds no year."""
        data = {
            "persona": self.persona,
            "modelo": self.modelo,
            "year": _token(self.year, horizon),
            "period": self.period,
            "horizon": _token(self.horizon, horizon),
            "grounding": self.grounding,
            "sources": list(self.sources),
            "has_values": self.has_values,
            "calculate": self.calculate.value,
            "verify": self.verify.value,
            "export": self.export.value,
            "verdict": self.verdict.value,
        }
        return json.dumps(data, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, line: str, *, horizon: int | None = None) -> TableRow:
        """Read one line written by :meth:`to_json`, or by :meth:`to_baseline_json` given the ``horizon``."""
        data = json.loads(line)
        data.pop("verdict", None)
        for name in ("year", "horizon"):
            if isinstance(data[name], str):
                if horizon is None:
                    raise ValueError(f"a baseline row's {name} token needs the registry horizon")
                data[name] = _resolved(data[name], horizon)
        data["sources"] = tuple(data["sources"])
        for name in ("calculate", "verify", "export"):
            data[name] = Stage(data[name])
        return cls(**data)


def _token(year: int, horizon: int) -> str:
    return str(YearToken(anchor="horizon", offset=year - horizon))


def _resolved(text: str, horizon: int) -> int:
    token = YearToken.parse(text, where="persona table baseline")
    if token.anchor != "horizon":
        raise ValueError(f"a baseline year token is anchored on the horizon, not {token}")
    return horizon + token.offset


def classify(row: TableRow) -> Verdict:
    """The row's verdict: grounding and coverage first, then the stages."""
    if row.calculate is Stage.NOT_RUN:
        return Verdict.NOT_RUN
    if row.calculate is Stage.HISTORY_FILED:
        return Verdict.HISTORY_FILED
    if row.calculate is Stage.UNSUPPORTED:
        return Verdict.UNSUPPORTED
    if not row.has_values:
        return Verdict.NO_ORACLE
    if row.grounding == "unverified" or not row.sources:
        return Verdict.UNVERIFIED
    if row.calculate is Stage.EXPECTED_REFUSAL:
        return Verdict.EXPECTED_REFUSAL
    if row.calculate is Stage.PASSED and row.verify is Stage.PASSED and row.export is Stage.PASSED:
        return Verdict.PASSED
    return Verdict.FAIL


def is_unsupported(code: str) -> bool:
    """Whether a refusal code says the application does not support the return."""
    return any(marker in code for marker in _UNSUPPORTED_MARKERS)


def replay_horizons(envelope: YearEnvelope) -> tuple[int, ...]:
    """Every horizon a persona is replayed under: each supported year, newest first."""
    return tuple(range(envelope.horizon, envelope.floor - 1, -1))


def planned_rows(persona: Persona, horizon: int, envelope: YearEnvelope) -> list[PlannedRow]:
    """The returns ``persona`` owes when replayed under ``horizon``, one per modelo, year and period.

    A return is owed when an obligation states it applicable or a value is
    stated for it. Values stated per counterparty (informative returns) are
    not compared yet, so they do not make a row's oracle. ``persona`` is read under any envelope; its year tokens are
    resolved here against ``horizon``, and a return whose year falls outside
    ``envelope.floor..horizon`` is not a row of this replay.
    """
    shifted = dataclasses.replace(envelope, horizon=horizon)
    values = {}
    for value in persona.expectations.values:
        if value.counterparty is not None:
            continue
        values[(value.modelo, _year(value.year, shifted), value.period)] = value
    keys = {
        (item.modelo, _year(item.year, shifted), period)
        for item in persona.expectations.obligations
        if item.applicable is True
        for period in item.periods
    } | set(values)
    rows = []
    for modelo, year, period in sorted(keys, key=lambda key: (key[0], key[1] or 0, key[2])):
        if year is None:
            continue
        value = values.get((modelo, year, period))
        stated = value is not None and bool(value.casillas or value.not_sourced or value.refusal is not None)
        rows.append(
            PlannedRow(
                persona=persona.id,
                modelo=modelo,
                year=year,
                period=period,
                horizon=horizon,
                has_values=stated,
                grounding=value.grounding if value is not None else "none",
                sources=value.legal_ref if value is not None else (),
            )
        )
    return rows


def _year(token: YearToken, envelope: YearEnvelope) -> int | None:
    try:
        return token.resolve(envelope)
    except PersonaCatalogueError:
        return None


def select(
    rows: Iterable[PlannedRow],
    *,
    modelos: Sequence[str] = (),
    years: Sequence[int] = (),
) -> list[PlannedRow]:
    """The rows a filtered run takes; an empty filter takes every row."""
    return [row for row in rows if (not modelos or row.modelo in modelos) and (not years or row.year in years)]


def write_rows(path: Path, rows: Iterable[TableRow]) -> None:
    """Append ``rows`` to the JSON-lines file at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row.to_json() + "\n")


def read_rows(paths: Iterable[Path], *, horizon: int | None = None) -> Iterator[TableRow]:
    """Every row in the JSON-lines files at ``paths``, in file order; baseline tokens resolve on ``horizon``."""
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield TableRow.from_json(line, horizon=horizon)


def latest_rows(rows: Iterable[TableRow]) -> dict[tuple[str, str, int, str], TableRow]:
    """One row per key: the replay under the highest horizon wins, and a later row replaces an earlier one."""
    best: dict[tuple[str, str, int, str], TableRow] = {}
    for row in rows:
        held = best.get(row.key)
        if held is None or row.horizon >= held.horizon:
            best[row.key] = row
    return best


def not_run(plan: PlannedRow, reason: str) -> TableRow:
    """The row of a return its replay never reached."""
    return TableRow.from_plan(plan, Stage.NOT_RUN, reason=reason)


__all__ = [
    "GREEN",
    "VERDICT_MEANING",
    "PlannedRow",
    "Stage",
    "TableRow",
    "Verdict",
    "classify",
    "is_unsupported",
    "latest_rows",
    "not_run",
    "planned_rows",
    "read_rows",
    "replay_horizons",
    "select",
    "write_rows",
]
