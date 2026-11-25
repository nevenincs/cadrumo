"""How a surface's figures stand against a table row's: numbers as numbers, text as text, redacted values by presence.

The central privacy boundary of the CLI prints some values (a NIF) as ``sha256:<8 hex>``. Such a figure is redacted
when its value is exactly ``sha256:`` and eight lowercase hexadecimal characters (any casilla, any surface); it equals
the casilla's value whenever the table row holds a non-empty one, either as its figure or as its text figure (the plain
text the backend read from the same run's saved records). Without either, the row differs.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

_REDACTED = re.compile(r"sha256:[0-9a-f]{8}")


def _number(text: str) -> Decimal | None:
    try:
        number = Decimal(text.strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _equal(table: str, shown: str) -> bool:
    """Whether two figure texts are equal: redacted by presence, numbers as numbers, else as text."""
    if is_redacted(shown):
        return bool(table.strip())
    first, second = _number(table), _number(shown)
    return first == second if first is not None and second is not None else table == shown


def _is_zero(text: str) -> bool:
    number = _number(text)
    return number is not None and number == 0


def is_redacted(text: str) -> bool:
    """Whether a figure text is a redacted value: exactly ``sha256:`` and eight lowercase hexadecimal characters."""
    return _REDACTED.fullmatch(text) is not None


def figure_causes(
    surface: str, table: Mapping[str, str], shown: Mapping[str, str], held: Mapping[str, str] | None = None
) -> list[str]:
    """Each way the figures ``shown`` by a surface miss or disagree with the table row's ``table`` figures.

    The table row is the oracle for calculated values, so a casilla shown beyond ``table`` is not a cause. A redacted
    figure compares by presence (see the module docstring): it needs a non-empty value of its casilla in ``table`` or
    in ``held``, the text figures the backend read from the same run's saved records, and is a cause otherwise.
    ``table`` holds only the casillas the revision's form places; the row's internal figures (working figures and
    unplaced casillas, which no surface is held to show) are never compared and are not extras when shown.
    """
    backend = held or {}
    causes: list[str] = []
    for casilla in sorted(table):
        if casilla not in shown:
            causes.append(f"casilla {casilla} not shown")
        elif is_redacted(shown[casilla]) and not table[casilla].strip():
            continue
        elif not _equal(table[casilla], shown[casilla]):
            causes.append(f"casilla {casilla} {surface} {shown[casilla]}, table {table[casilla]}")
    causes.extend(
        f"casilla {casilla} redacted but the backend row has no value for it"
        for casilla in redacted_casillas(shown)
        if not table.get(casilla, "").strip() and not backend.get(casilla, "").strip()
    )
    return causes


def redacted_casillas(shown: Mapping[str, str]) -> tuple[str, ...]:
    """The casillas ``shown`` redacted, sorted."""
    return tuple(casilla for casilla in sorted(shown) if is_redacted(shown[casilla]))


def extra_figures(table: Mapping[str, str], shown: Mapping[str, str]) -> tuple[str, ...]:
    """The non-zero casillas ``shown`` that the table row has no figure for, sorted."""
    return tuple(casilla for casilla in sorted(set(shown) - set(table)) if not _is_zero(shown[casilla]))
