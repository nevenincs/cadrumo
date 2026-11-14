"""The row figures of a return, read from the saved repeating records the ``work form`` command prints.

The calculation the CLI prints holds column totals only, while a casilla a repeating-row group stores per row (a let
property's rendimientos) is answered by its row. ``aeat app modelo work form <work>`` prints the form's repeating blocks
and their saved records: as TAB lines (header lines, ``block<TAB>id<TAB>known<TAB>n`` or ``...<TAB>unknown<TAB>words``,
then ``record<TAB>block<TAB>row index<TAB>casilla id<TAB>value`` per value) and as a JSON envelope whose ``blocks``
carry ``block_id``, ``rows_known`` and ``records`` of ``index`` and ``values`` (``casilla_id``, ``value``). This
module is pure: it parses either form, fails closed (an output it cannot read whole gives no value, never a guessed
one), and maps the values to figures with the table's own single-row rule (:mod:`..row_figures`), which it reuses and
does not restate. A block whose rows are not known contributes no value: its records are unknown, never empty. A
cell no casilla owns is not a figure of any casilla and is skipped.
A value the central privacy boundary printed redacted (``sha256:<8 hex>``, see :func:`..frontend.is_redacted`, e.g.
the tenant NIF 0091) is kept as the text it was printed. It is a figure of a casilla held by exactly one row, and
fills the merge only where the printed figure is absent or zero; the single-row and conflict rules of the table stay
those of numeric casillas, and the merge names the casillas kept redacted.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import typer
from typer.core import TyperGroup

from ..frontend import is_redacted
from ..row_figures import merge_row_figures, single_row_figures
from ..rows import canonical_figures

FORM_PATH = ("app", "modelo", "work", "form")
"""The command that prints the saved repeating records of one work unit."""
_FIELDS = 5
_BLOCKS = "blocks"


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


_RECORD = "record"
_SKIPPED_LINES = frozenset(
    {
        "operation",
        "work_unit_id",
        "modelo",
        "filing_year",
        "period",
        "registry_revision_id",
        "calculation_revision_id",
        "block",
        "record_column",
    }
)


def parse_form_lines(text: str) -> tuple[FormValue, ...]:
    """The values of the TAB form; empty unless every non-blank line is a known header, block or record line.

    A ``record`` line is five well-formed fields; header, ``block`` and ``record_column`` lines carry no casilla value.
    """
    found: list[FormValue] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.rstrip("\r").split("\t")
        if parts[0] in _SKIPPED_LINES:
            continue
        item = (
            None
            if parts[0] != _RECORD or len(parts) != _FIELDS
            else _row_value(parts[0], parts[1], parts[2], parts[3], parts[4])
        )
        if item is None:
            return ()
        found.append(item)
    return tuple(found)


def _cell_value(block: str, index: object, cell: object) -> FormValue | None:
    """The cell's value; ``None`` when the cell is malformed."""
    if not isinstance(cell, Mapping) or "casilla_id" not in cell or "value" not in cell:
        return None
    casilla = cell["casilla_id"]
    if not isinstance(casilla, str):
        return None
    return _row_value(_RECORD, block, index, casilla, cell["value"])


def _block_values(block: object) -> list[FormValue] | None:
    """The values of one block of the JSON form; none when the block is malformed, empty when its rows are unknown."""
    if not isinstance(block, Mapping) or not isinstance(block.get("block_id"), str):
        return None
    known, records = block.get("rows_known"), block.get("records")
    if not isinstance(known, bool) or not isinstance(records, list):
        return None
    if not known:
        return [] if not records else None
    found: list[FormValue] = []
    for record in records:
        cells = record.get("values") if isinstance(record, Mapping) else None
        if not isinstance(cells, list) or not isinstance(record, Mapping):
            return None
        for cell in cells:
            if isinstance(cell, Mapping) and "casilla_id" in cell and cell["casilla_id"] is None:
                continue
            item = _cell_value(str(block["block_id"]), record.get("index"), cell)
            if item is None:
                return None
            found.append(item)
    return found


def parse_form_result(result: Mapping[str, object]) -> tuple[FormValue, ...]:
    """The values of the JSON form's ``result``; empty unless every block, record and cell is well formed."""
    blocks = result.get(_BLOCKS)
    if not isinstance(blocks, list):
        return ()
    found: list[FormValue] = []
    for block in blocks:
        values = _block_values(block)
        if values is None:
            return ()
        found.extend(values)
    return tuple(found)


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
    amounts, except a redacted value, which a casilla held by exactly one row keeps as printed. The one-row rule of
    the numeric casillas is the table's :func:`..row_figures.single_row_figures`.
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
    numeric = dict(canonical_figures({casilla: Decimal(text) for casilla, text in single.items()}))
    return numeric | _redacted_figures(values)


def _redacted_figures(values: Sequence[FormValue]) -> dict[str, str]:
    """The redacted value of each casilla held by exactly one printed value, as printed."""
    held = Counter(item.casilla for item in values)
    return {item.casilla: item.value for item in values if held[item.casilla] == 1 and is_redacted(item.value)}


def merge_form_figures(
    figures: tuple[tuple[str, str], ...], rows: Mapping[str, str]
) -> tuple[tuple[tuple[str, str], ...], list[str]]:
    """The ``figures`` with each row figure filled where the printed one is zero or absent, and every conflict.

    The table's :func:`..row_figures.merge_row_figures` decides for the numeric row figures; a redacted row figure
    is filled by the same rule and conflicts only with a different redacted figure. The result is written as
    canonical figures again. When any figure of the result is redacted, a last entry ``redacted: <casilla ids>``
    names the casillas kept redacted, so the caller's reason says that they were not compared by content.
    """
    numeric = {casilla: text for casilla, text in rows.items() if not is_redacted(text)}
    merged, conflicts = merge_row_figures(dict(figures), numeric)
    for casilla, text in rows.items():
        if is_redacted(text):
            conflicts += _fill_redacted(merged, casilla, text)
    result = canonical_figures(merged)
    kept = [casilla for casilla, text in result if is_redacted(text)]
    return result, [*conflicts, f"redacted: {', '.join(kept)}"] if kept else conflicts


def _fill_redacted(merged: dict[str, object], casilla: str, text: str) -> list[str]:
    """Fill ``casilla`` with a redacted row figure where nothing is printed; name a different redacted figure."""
    printed = merged.get(casilla)
    shown = "" if printed is None else str(printed).strip()
    if not shown or _number(shown) == 0:
        merged[casilla] = text
    elif is_redacted(shown) and shown != text:
        return [f"casilla {casilla} scalar {shown} differs from its row figure {text}"]
    return []


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
