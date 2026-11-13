"""The report a persona world's materialisation prints: where the world is, and which returns the table runs on it.

The materialisation runs in an interpreter of its own, under the persona's frozen clock, and exits before the runtime
starts. This module is plain data with no import of the product, so the driver that reads the report needs none.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass


class ReportError(ValueError):
    """A world report the schema refuses."""


type ReturnKey = tuple[str, int, str]
"""``(modelo, year, period)``: the return of a persona on one world."""


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
    needs_statements: bool
    """Whether the persona states values, prior figures or income statements the table enters before it calculates."""
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
        needs_statements=_flag(data, "needs_statements"),
        rows=tuple(_row(item) for item in rows),
    )
