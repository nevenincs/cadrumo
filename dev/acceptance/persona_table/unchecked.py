"""What a persona states for a return that the table cannot compare.

The table compares each casilla of an in-force value, and for a counterparty
value of a designed modelo the identity and the concepts the design maps. Any
other stated content (a concept of a value with no counterparty, a
counterparty value of a modelo without a design, a counterparty concept the
design does not map) is named here so the row cannot be green on a value
nothing checked.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

from cadrumo.tests.personas import ExpectedValue, Persona, PersonaCatalogueError, YearEnvelope, read_persona

from .counterparties import DESIGNS, is_compared

_DECLARED = "declared"
"""The one concept besides the mapped ones the counterparty comparison reads: whether a record may exist."""

type ReturnKey = tuple[str, int | None, str]


def value_unchecked(value: ExpectedValue) -> set[str]:
    """The items one in-force value states that the table does not compare."""
    if value.refusal is not None or not (value.casillas or value.concepts):
        return set()
    role = value.counterparty
    if role is None:
        return {f"concept:{name}" for name, _ in value.concepts}
    if not is_compared(value):
        return {f"counterparty:{role}"}
    mapped = DESIGNS[value.modelo].concepts
    return {f"counterparty:{role}:{name}" for name, _ in value.concepts if name != _DECLARED and name not in mapped}


def unchecked_by_key(in_force_values: Iterable[tuple[int, ExpectedValue]]) -> dict[ReturnKey, tuple[str, ...]]:
    """The sorted unchecked items per return ``(modelo, year, period)``; a return with none is left out."""
    found: dict[ReturnKey, set[str]] = {}
    for year, value in in_force_values:
        items = value_unchecked(value)
        if items:
            found.setdefault((value.modelo, year, value.period), set()).update(items)
    return {key: tuple(sorted(items)) for key, items in found.items()}


def persona_at(persona_id: str, horizon: int, envelope: YearEnvelope) -> Persona:
    """The persona as the replay under ``horizon`` reads it: records below the floor left out and listed.

    A persona that cannot be read at that horizon is read at the envelope's own horizon, as the replay plans it.
    """
    shifted = dataclasses.replace(envelope, horizon=horizon)
    try:
        return read_persona(persona_id, envelope=shifted, omit_below_floor=horizon != envelope.horizon)
    except PersonaCatalogueError:
        return read_persona(persona_id, envelope=envelope)
