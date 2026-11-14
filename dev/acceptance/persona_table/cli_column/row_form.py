"""The row figures of a return, read from the saved repeating records the ``work form`` command prints.

The calculation the CLI prints holds column totals only, while a casilla a repeating-row group stores per row (a let
property's rendimientos) is answered by its row. ``aeat app modelo work form <work>`` prints those records one value
per line, ``record<TAB>block<TAB>row index<TAB>casilla id<TAB>value``, and as a JSON envelope. This module is pure: it
parses either form, fails closed (an output it cannot read whole gives no value, never a guessed one), and maps the
values to figures with the table's own single-row rule (:mod:`..row_figures`), which it reuses and does not restate.

The JSON form is read as a ``values`` list of objects with the same five names (``record``, ``block``, ``row``,
``casilla_id``, ``value``); that shape follows the TAB columns and is not yet confirmed against the command.
TODO: confirm the envelope's field names once the leaf is on the tree and adjust :func:`parse_form_result`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import typer
from typer.core import TyperGroup

from ..row_figures import merge_row_figures, single_row_figures
from ..rows import canonical_figures

FORM_PATH = ("app", "modelo", "work", "form")
"""The command that prints the saved repeating records of one work unit."""
_FIELDS = 5
_VALUES = "values"
_ROW_NAMES = ("record", "block", "row", "casilla_id", "value")


@dataclass(frozen=True, slots=True)
class FormValue:
    """One value of one saved row, as the command printed it."""

    record: str
    block: str
    row: int
    casilla: str
    value: str


def _row_index(row: object) -> int | None:
    number = int(row) if isinstance(row, str) and row.isascii() and row.isdigit() else row
    if isinstance(number, bool) or not isinstance(number, int):
        return None
    return number if number >= 1 else None


def _printed(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, str | int | float | Decimal):
        return None
    return str(value)


def _row_value(record: str, block: str, row: object, casilla: str, value: object) -> FormValue | None:
    """The value, or ``None`` when a part is missing, mistyped or not a positive row index."""
    index, text = _row_index(row), _printed(value)
    if not (record and block and casilla) or index is None or text is None:
        return None
    return FormValue(record, block, index, casilla, text)


def parse_form_lines(text: str) -> tuple[FormValue, ...]:
    """The values of the TAB form; empty unless every non-blank line is five well-formed fields."""
    found: list[FormValue] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.rstrip("\r").split("\t")
        item = None if len(parts) != _FIELDS else _row_value(parts[0], parts[1], parts[2], parts[3], parts[4])
        if item is None:
            return ()
        found.append(item)
    return tuple(found)


def _entry_value(entry: object) -> FormValue | None:
    if not isinstance(entry, Mapping) or any(name not in entry for name in _ROW_NAMES):
        return None
    record, block, casilla = entry["record"], entry["block"], entry["casilla_id"]
    if not (isinstance(record, str) and isinstance(block, str) and isinstance(casilla, str)):
        return None
    return _row_value(record, block, entry["row"], casilla, entry["value"])


def parse_form_result(result: Mapping[str, object]) -> tuple[FormValue, ...]:
    """The values of the JSON form's ``result``; empty unless every entry is an object of the five names."""
    entries = result.get(_VALUES)
    if not isinstance(entries, list):
        return ()
    found = [_entry_value(entry) for entry in entries]
    return () if any(item is None for item in found) else tuple(item for item in found if item is not None)


def _number(text: str) -> Decimal | None:
    try:
        number = Decimal(text.strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def form_row_figures(values: Sequence[FormValue]) -> Mapping[str, str]:
    """The figure of each casilla held by exactly one saved row, by casilla id, as canonical text.

    Every printed value of a casilla is one row, whichever record and block it is in, so a casilla in two rows has no
    single figure. A casilla any of whose values is not a number is left out, since its rows cannot be counted as
    amounts. The one-row rule is the table's :func:`..row_figures.single_row_figures`.
    """
    printed: dict[str, dict[str, Decimal | None]] = {}
    for position, item in enumerate(values):
        printed.setdefault(item.casilla, {})[str(position)] = _number(item.value)
    rows = {
        casilla: {key: number for key, number in held.items() if number is not None}
        for casilla, held in printed.items()
        if all(number is not None for number in held.values())
    }
    single = single_row_figures(rows, {casilla: casilla for casilla in rows})
    return dict(canonical_figures({casilla: Decimal(text) for casilla, text in single.items()}))


def merge_form_figures(
    figures: tuple[tuple[str, str], ...], rows: Mapping[str, str]
) -> tuple[tuple[tuple[str, str], ...], list[str]]:
    """The ``figures`` with each row figure filled where the printed one is zero or absent, and every conflict.

    The table's :func:`..row_figures.merge_row_figures` decides; its result is written as canonical figures again.
    """
    merged, conflicts = merge_row_figures(dict(figures), rows)
    return canonical_figures(merged), conflicts


def form_leaf_present(root: object) -> bool:
    """Whether the live command tree ``root`` has the ``work form`` leaf; a group of that name is not the leaf."""
    command = root
    for word in FORM_PATH:
        if not isinstance(command, TyperGroup):
            return False
        child = command.get_command(typer.Context(command, info_name=command.name), word)
        if child is None:
            return False
        command = child
    return not isinstance(command, TyperGroup)
