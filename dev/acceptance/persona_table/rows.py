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
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path

from cadrumo.domain.period import period_end_date
from cadrumo.tests.personas import (
    ExpectedValue,
    Persona,
    PersonaCatalogueError,
    YearEnvelope,
    YearToken,
    filed_period_order,
    values_in_force,
)

from .counterparties import is_compared
from .unchecked import persona_at, unchecked_by_key


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
    UNRESOLVED = "unresolved"
    """Calculate only: the calculation gives no value for a stated casilla, so nothing disagrees and nothing passes."""
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
    FLOOR_SOURCE = "floor-source"
    UNCHECKED = "unchecked"


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
    Verdict.FLOOR_SOURCE: "at this lowered horizon the floor dropped a record of the year before this return, "
    "and a stage refused; the row proves nothing either way",
    Verdict.UNCHECKED: "every stage ended as a pass or an expected refusal, but the persona states values the table "
    "does not compare (listed per row); the row is not a pass",
}

GREEN = frozenset({Verdict.PASSED})
"""Verdicts a row is green at; a diff reports a row entering or leaving this set."""

_STAGE_REFUSAL = re.compile(r"^(?:verify|export): \S+ \S+ (?P<code>[A-Z][A-Z0-9_]+)")
"""A verify or export reason as the runner writes it: the stage, the operation, how it settled, its code."""
_UNSUPPORTED_MARKERS = ("UNSUPPORTED", "NOT_SUPPORTED")
_ANNUAL = "0A"


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
    floor_source_dropped: bool = False
    """Whether the return is of the floor year and the replay's floor dropped a history record of the year before."""
    unchecked: tuple[str, ...] = ()
    """The stated values of the return the table does not compare."""

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
    floor_source_dropped: bool = False
    unchecked: tuple[str, ...] = ()
    """What the persona states for the return that the table cannot compare; see ``unchecked.unchecked_items``."""
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
            floor_source_dropped=plan.floor_source_dropped,
            unchecked=plan.unchecked,
        )

    def to_json(self) -> str:
        """One JSON line; the verdict is written for readers and re-derived on load."""
        data = asdict(self)
        data["sources"] = list(self.sources)
        data["unchecked"] = list(self.unchecked)
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
        if self.floor_source_dropped:
            data["floor_source_dropped"] = True
        if self.unchecked:
            data["unchecked"] = list(self.unchecked)
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
        data["unchecked"] = tuple(data.get("unchecked", ()))
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


_TERMINAL_VERDICTS = {
    Stage.NOT_RUN: Verdict.NOT_RUN,
    Stage.HISTORY_FILED: Verdict.HISTORY_FILED,
    Stage.UNSUPPORTED: Verdict.UNSUPPORTED,
}
"""Calculate stages that settle a row's verdict before its oracle is consulted."""


def classify(row: TableRow) -> Verdict:
    """The row's verdict: coverage first, then grounding, then the stages, then what the table could not compare."""
    terminal = _TERMINAL_VERDICTS.get(row.calculate)
    if terminal is not None:
        return terminal
    if not row.has_values:
        return _unless_unchecked(row, Verdict.NO_ORACLE)
    if row.grounding == "unverified" or not row.sources:
        return Verdict.UNVERIFIED
    if row.calculate is Stage.EXPECTED_REFUSAL:
        return _unless_unchecked(row, Verdict.EXPECTED_REFUSAL)
    if (row.calculate, row.verify, row.export) == (Stage.PASSED, Stage.PASSED, Stage.PASSED):
        return _unless_unchecked(row, Verdict.PASSED)
    return Verdict.FLOOR_SOURCE if _refused_for_dropped_source(row) else Verdict.FAIL


def _unless_unchecked(row: TableRow, verdict: Verdict) -> Verdict:
    """``verdict``, or ``unchecked`` when the persona states values of the return the table does not compare."""
    return Verdict.UNCHECKED if row.unchecked else verdict


_REFUSING_STAGES = frozenset({Stage.REFUSED, Stage.INCOMPLETE, Stage.UNRESOLVED})


def _refused_for_dropped_source(row: TableRow) -> bool:
    """Whether a red row is the application's correct refusal of a return whose prior-year source the floor dropped.

    A value mismatch is a finding whatever was dropped, so it keeps the row red.
    """
    stages = (row.calculate, row.verify, row.export)
    return row.floor_source_dropped and Stage.MISMATCH not in stages and any(s in _REFUSING_STAGES for s in stages)


def stage_refusal_codes(*reasons: str) -> set[str]:
    """The codes the verify and export stages settled with, read from the reasons the runner wrote for them."""
    return {match["code"] for reason in reasons if (match := _STAGE_REFUSAL.match(reason))}


def is_unsupported(code: str) -> bool:
    """Whether a refusal code says the application does not support the return."""
    return any(marker in code for marker in _UNSUPPORTED_MARKERS)


def replay_horizons(envelope: YearEnvelope) -> tuple[int, ...]:
    """Every horizon a persona is replayed under: each supported year, newest first."""
    return tuple(range(envelope.horizon, envelope.floor - 1, -1))


def planned_rows(persona: Persona, horizon: int, envelope: YearEnvelope) -> list[PlannedRow]:
    """The returns ``persona`` owes when replayed under ``horizon``, one per modelo, year and period.

    A return is owed when an obligation states it applicable, the persona's
    history files or calculates it, or a value is stated for it and no
    obligation states it not applicable. Values stated per counterparty are an
    oracle only for the informative returns whose type-2 record the table
    compares (``counterparties.DESIGNS``). ``persona`` is read under any envelope; its year
    tokens are resolved here against ``horizon``, and a return whose year falls
    outside ``envelope.floor..horizon`` is not a row of this replay.
    """
    shifted = dataclasses.replace(envelope, horizon=horizon)
    stated = _stated_values(persona, shifted)
    unchecked = unchecked_by_key(in_force(persona.expectations.values, shifted))
    stated_only = set(stated) - _obligation_keys(persona, shifted, applicable=False)
    keys = _obligation_keys(persona, shifted, applicable=True) | _history_keys(persona, shifted) | stated_only
    return [
        _planned(
            persona.id,
            horizon,
            (modelo, year, period),
            stated.get((modelo, year, period), []),
            unchecked=unchecked.get((modelo, year, period), ()),
            floor_source_dropped=year == shifted.floor and _history_dropped_before(persona, shifted, year - 1),
        )
        for modelo, year, period in sorted(keys, key=chain_order)
        if year is not None
    ]


def unchecked_items(persona: Persona, envelope: YearEnvelope, key: tuple[str, int | None, str]) -> tuple[str, ...]:
    """The sorted items the persona states for return ``key`` (modelo, year, period) that are not compared.

    ``envelope`` carries the replay horizon. Values are the in-force ones the planner takes, so a value a provision
    replaces is not listed; a ``not_sourced`` casilla is listed, since the return is known to lack the law's figure.
    """
    return unchecked_by_key(in_force(persona.expectations.values, envelope)).get(key, ())


def with_unchecked(rows: Iterable[TableRow], envelope: YearEnvelope) -> list[TableRow]:
    """``rows`` with their unchecked items read from the persona at each row's replay horizon.

    A persona the catalogue no longer holds keeps the items its row was written with.
    """
    personas: dict[tuple[str, int], Persona | None] = {}
    kept: list[TableRow] = []
    for row in rows:
        held = (row.persona, row.horizon)
        if held not in personas:
            personas[held] = _read_or_none(row.persona, row.horizon, envelope)
        persona = personas[held]
        if persona is None:
            kept.append(row)
            continue
        shifted = dataclasses.replace(envelope, horizon=row.horizon)
        items = unchecked_items(persona, shifted, (row.modelo, row.year, row.period))
        kept.append(dataclasses.replace(row, unchecked=items))
    return kept


def _read_or_none(persona_id: str, horizon: int, envelope: YearEnvelope) -> Persona | None:
    try:
        return persona_at(persona_id, horizon, envelope)
    except (PersonaCatalogueError, OSError):
        return None


def _stated_values(persona: Persona, envelope: YearEnvelope) -> dict[tuple[str, int | None, str], list[ExpectedValue]]:
    """The values in force per return, leaving out per-counterparty values the table cannot compare.

    A return with only concepts maps to none; a stated role is stated content even when it resolves to no casilla,
    which the unchecked items then name.
    """
    stated: dict[tuple[str, int | None, str], list[ExpectedValue]] = {}
    for year, value in in_force(persona.expectations.values, envelope):
        if value.counterparty is not None and not is_compared(value):
            continue
        found = stated.setdefault((value.modelo, year, value.period), [])
        if value.casillas or value.roles or value.not_sourced or value.refusal is not None or is_compared(value):
            found.append(value)
    return stated


def _obligation_keys(persona: Persona, envelope: YearEnvelope, *, applicable: bool) -> set[tuple[str, int | None, str]]:
    """The returns an obligation states applicable (or not), with years resolved on ``envelope``.

    A return stated not applicable does not exist, so a value stated for it is
    a cross-check rather than a filing and makes no row.
    """
    return {
        (item.modelo, _year(item.year, envelope), period)
        for item in persona.expectations.obligations
        if item.applicable is applicable
        for period in item.periods
    }


def _history_keys(persona: Persona, envelope: YearEnvelope) -> set[tuple[str, int | None, str]]:
    """The returns the persona's history files or calculates, which the table runs live in chain order."""
    return {
        (block.modelo, _year(block.year, envelope), period)
        for block in (*persona.filed_returns, *persona.calculated_returns)
        for period in block.periods
    }


def _history_dropped_before(persona: Persona, envelope: YearEnvelope, year: int) -> bool:
    """Whether the read left out a return-history record of ``year``, which lies below the floor."""
    return any(
        record.history and record.year.resolve(envelope, biographical=True) == year for record in persona.below_floor
    )


def _planned(
    persona_id: str,
    horizon: int,
    key: tuple[str, int, str],
    values: list[ExpectedValue],
    *,
    unchecked: tuple[str, ...] = (),
    floor_source_dropped: bool = False,
) -> PlannedRow:
    modelo, year, period = key
    return PlannedRow(
        persona=persona_id,
        modelo=modelo,
        year=year,
        period=period,
        horizon=horizon,
        has_values=bool(values),
        grounding=_grounding(values),
        sources=tuple(dict.fromkeys(source for value in values for source in value.legal_ref)),
        floor_source_dropped=floor_source_dropped,
        unchecked=unchecked,
    )


def ended(rows: Sequence[PlannedRow], today: date) -> list[PlannedRow]:
    """The rows whose period has ended by ``today``, the persona's scenario day.

    A return whose period has not ended at the scenario clock is not owed yet:
    no honest figures, attestation or filing exist for it, so it is not a row
    of that replay. A return whose period has ended is owed even before its
    filing window opens; only its local filing waits for the window.
    """
    return [row for row in rows if period_end_date(row.year, row.period) < today]


def chain_order(key: tuple[str, int | None, str]) -> tuple[int, int, str]:
    """The order a replay runs returns in: by year, each quarter before the annual returns, then by modelo.

    A quarter is filed locally before the next one calculates, and an annual
    summary (Modelo 180, 190, 390) or the annual Renta reads that year's filed
    quarters, so every quarter of a year runs before any annual return of it.
    """
    modelo, year, period = key
    try:
        position = filed_period_order(period)
    except ValueError:
        position = filed_period_order(_ANNUAL) + 1
    return (year or 0, position, modelo)


def in_force(values: Sequence[ExpectedValue], envelope: YearEnvelope) -> tuple[tuple[int, ExpectedValue], ...]:
    """The stated values whose year lies in ``envelope``, as the law of that year holds them, with that year."""
    inside = tuple(value for value in values if _year(value.year, envelope) is not None)
    return values_in_force(inside, envelope)


def _grounding(values: Sequence[ExpectedValue]) -> str:
    """The weakest grounding among the compared values; ``none`` when there is none."""
    if not values:
        return "none"
    for grounding in ("unverified", "cited", "verified"):
        if any(value.grounding == grounding for value in values):
            return grounding
    return values[0].grounding


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


def source_closure(modelos: Iterable[str], sources: Callable[[str], Iterable[str]]) -> frozenset[str]:
    """``modelos`` and every modelo they read, transitively, as ``sources`` declares each one's reads."""
    found: set[str] = set()
    pending = list(modelos)
    while pending:
        modelo = pending.pop()
        if modelo not in found:
            found.add(modelo)
            pending.extend(sources(modelo))
    return frozenset(found)


def replayed(
    rows: Sequence[PlannedRow], selected: Sequence[PlannedRow], sources: Callable[[str], Iterable[str]]
) -> list[PlannedRow]:
    """The rows a run replays, in ``rows``' chain order, so each selected row meets the world a full run gives it.

    The rows of one replay share a world: a verified return is filed locally,
    and a later return reads it (the annual Renta reads the year's Modelo 130
    quarters, a quarter reads the one before). A filtered run therefore also
    replays every earlier row of a modelo the selected ones read, directly or
    transitively, including earlier rows of the selected modelos themselves;
    only the selected rows are emitted.
    """
    if len(selected) == len(rows):
        return list(rows)
    wanted = {row.key for row in selected}
    if not wanted:
        return []
    needed = source_closure({row.modelo for row in selected}, sources)
    last = max(index for index, row in enumerate(rows) if row.key in wanted)
    return [row for index, row in enumerate(rows[: last + 1]) if row.key in wanted or row.modelo in needed]


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
    "chain_order",
    "classify",
    "in_force",
    "is_unsupported",
    "latest_rows",
    "not_run",
    "planned_rows",
    "read_rows",
    "replay_horizons",
    "select",
    "unchecked_items",
    "with_unchecked",
    "write_rows",
]
