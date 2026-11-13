"""The report a persona world's materialisation prints: where the world is, and which returns the table runs on it.

The materialisation runs in an interpreter of its own, under the persona's frozen clock, and exits before the runtime
starts. This module is plain data with no import of the product, so the driver that reads the report needs none.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class ReportError(ValueError):
    """A world report the schema refuses."""


type ReturnKey = tuple[str, int, str]
"""``(modelo, year, period)``: the return of a persona on one world."""


class StatementKind(StrEnum):
    """What the table states about a return before or around its calculation, as the persona's facts give it."""

    PRIOR_CARRIES = "prior_carries"
    """The pending carries of earlier ejercicios a Modelo 100 reads and no earlier return supplies."""
    PRIOR_VALUE = "prior_value"
    """A figure the persona attests for a dependency on an earlier return the application does not hold."""
    WORK_INPUT = "work_input"
    """A casilla value the persona's operator types because no record the application holds produces it."""
    WORK_INCOME_NONE = "work_income_none"
    """The statement that the work-income boxes no payer certificate fills hold nothing."""
    RENTAL_CARRY = "rental_carry"
    """The statement that a let property's interest and repairs carry holds no amount on an origin year's opening."""


class Phase(StrEnum):
    """Where in the table's calculation of a return a statement is made; the members are in the table's order."""

    BEFORE_EVIDENCE = "before_evidence"
    """After the work unit is created, before the Modelo 303 annual-summary evidence is built."""
    AT_CALCULATION = "at_calculation"
    """Just before the first calculation, after that evidence."""
    AFTER_CALCULATION = "after_calculation"
    """After the first calculation; the return is calculated again when a statement of the phase was applied."""
    AFTER_RECALCULATION = "after_recalculation"
    """After that second step; the return is calculated again when a statement of the phase was applied."""


@dataclass(frozen=True, slots=True)
class Statement:
    """One statement the table makes about a return, with the operands its command line needs."""

    kind: StatementKind
    phase: Phase
    target: str = ""
    """The binding the statement is made on, or the casilla a work input is typed into."""
    value: str = ""
    """The amount stated, as text the command reads in English; empty where the statement carries none."""
    row: str | None = None
    families: tuple[str, ...] = ()
    amounts: tuple[tuple[str, str], ...] = ()
    """``(box, amount)`` for each carry the persona states an amount for."""
    gap: str | None = None
    """Why no command line can say this statement the way the table does; the return is then not driven."""
    refusal: str | None = None
    """The words in which the table itself refuses the statement before the application is asked."""


@dataclass(frozen=True, slots=True)
class RowPlan:
    """One return the table's replay runs, in chain order."""

    modelo: str
    year: int
    period: str
    owed: bool
    emitted: bool
    """Whether the table writes a row for it under the filters of the run; a replayed source return is not."""
    history_filed: bool
    """Whether the persona's history already filed it locally, so the table has nothing to compare."""
    last_owed_period: str
    """The year's last quarterly period the persona owes of this modelo, or the return's own period."""
    stated_refusal: str | None = None
    statements: tuple[Statement, ...] = ()
    """What the table states about the return, in the order it states it."""

    @property
    def key(self) -> ReturnKey:
        """The return's key, ``(modelo, year, period)``."""
        return (self.modelo, self.year, self.period)


@dataclass(frozen=True, slots=True)
class WorldReport:
    """A materialised persona world and the returns on it."""

    persona: str
    horizon: int
    storage_root: str
    profile_id: str
    authority_generation: str
    as_of: str
    scope: str
    actor: str
    aeat_filings_in_process: bool
    """Whether the recorded AEAT filings were captured in process; ``live.filed-capture.single`` has no CLI door."""
    rows: tuple[RowPlan, ...]


def _text(data: Mapping[str, object], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value:
        raise ReportError(f"world report field {name} must be non-empty text")
    return value


def _flag(data: Mapping[str, object], name: str) -> bool:
    value = data.get(name)
    if not isinstance(value, bool):
        raise ReportError(f"world report field {name} must be true or false")
    return value


def _number(data: Mapping[str, object], name: str) -> int:
    value = data.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ReportError(f"world report field {name} must be a whole number")
    return value


def statement_record(statement: Statement) -> dict[str, object]:
    """The JSON object that carries ``statement`` in a world report."""
    return {
        "kind": statement.kind.value,
        "phase": statement.phase.value,
        "target": statement.target,
        "value": statement.value,
        "row": statement.row,
        "families": list(statement.families),
        "amounts": [[box, amount] for box, amount in statement.amounts],
        "gap": statement.gap,
        "refusal": statement.refusal,
    }


def _optional_text(data: Mapping[str, object], name: str) -> str | None:
    value = data.get(name)
    if value is not None and not isinstance(value, str):
        raise ReportError(f"statement field {name} must be text or null")
    return value


def _texts(data: Mapping[str, object], name: str) -> tuple[str, ...]:
    value = data.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ReportError(f"statement field {name} must be a list of text")
    return tuple(str(item) for item in value)


def _amounts(data: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    value = data.get("amounts")
    pairs = value if isinstance(value, list) else None
    if pairs is None or not all(
        isinstance(pair, list) and len(pair) == 2 and all(isinstance(each, str) for each in pair) for pair in pairs
    ):
        raise ReportError("statement field amounts must be a list of [box, amount] text pairs")
    return tuple((str(pair[0]), str(pair[1])) for pair in pairs)


def _statement(raw: object) -> Statement:
    if not isinstance(raw, Mapping):
        raise ReportError("a world report statement must be an object")
    try:
        kind, phase = StatementKind(raw.get("kind")), Phase(raw.get("phase"))
    except ValueError as error:
        raise ReportError(f"a world report statement names an unknown kind or phase: {error}") from error
    return Statement(
        kind=kind,
        phase=phase,
        target=_optional_text(raw, "target") or "",
        value=_optional_text(raw, "value") or "",
        row=_optional_text(raw, "row"),
        families=_texts(raw, "families"),
        amounts=_amounts(raw),
        gap=_optional_text(raw, "gap"),
        refusal=_optional_text(raw, "refusal"),
    )


def _statements(raw: Mapping[str, object]) -> tuple[Statement, ...]:
    items = raw.get("statements")
    if not isinstance(items, list):
        raise ReportError("world report row field statements must be a list")
    return tuple(_statement(item) for item in items)


def _row(raw: object) -> RowPlan:
    if not isinstance(raw, Mapping):
        raise ReportError("a world report row must be an object")
    refusal = raw.get("stated_refusal")
    if refusal is not None and not isinstance(refusal, str):
        raise ReportError("stated_refusal must be text or null")
    return RowPlan(
        modelo=_text(raw, "modelo"),
        year=_number(raw, "year"),
        period=_text(raw, "period"),
        owed=_flag(raw, "owed"),
        emitted=_flag(raw, "emitted"),
        history_filed=_flag(raw, "history_filed"),
        last_owed_period=_text(raw, "last_owed_period"),
        stated_refusal=refusal,
        statements=_statements(raw),
    )


def parse_report(text: str) -> WorldReport:
    """The report ``text`` holds, refusing a missing or mistyped field."""
    try:
        data = json.loads(text)
    except ValueError as error:
        raise ReportError(f"the world report is not JSON: {error}") from error
    if not isinstance(data, dict):
        raise ReportError("the world report must be a JSON object")
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise ReportError("world report field rows must be a list")
    return WorldReport(
        persona=_text(data, "persona"),
        horizon=_number(data, "horizon"),
        storage_root=_text(data, "storage_root"),
        profile_id=_text(data, "profile_id"),
        authority_generation=_text(data, "authority_generation"),
        as_of=_text(data, "as_of"),
        scope=_text(data, "scope"),
        actor=_text(data, "actor"),
        aeat_filings_in_process=_flag(data, "aeat_filings_in_process"),
        rows=tuple(_row(item) for item in rows),
    )
