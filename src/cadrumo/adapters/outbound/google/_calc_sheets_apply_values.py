"""Google Sheets value-write payload builders for calc sheet exports.

:mod:`adapters.outbound.google.calc_sheets_apply` creates a fresh workbook
and passes these payloads to the shared
:func:`adapters.outbound.google.api.execute_request` boundary for a
Sheets ``values.batchUpdate`` call. This module stays pure: it renders the
addressed cell blocks
:mod:`application.storage.calc_sheets.workbook_cells` resolves into A1 ranges
plus row values, and never opens a Google service object itself.

Which cell holds which value is the plan's business, so every builder here maps
one shared block onto one payload entry rather than computing an address of its
own. What stays transport-specific is the wire coercion: Sheets is sent
RAW values: text stays literal and decimals become numeric display cells.
The review plan separately carries exact decimal text. Only explicitly
generated formula cells use USER_ENTERED in a separate request.

See Also:
    :func:`application.storage.calc_sheets.workbook_cells.plan_value_blocks`
        The shared cell stream these payloads render.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ....application.storage.calc_sheets.records import (
    AnySheetExportPlan,
    SheetCellAddress,
    SheetFormulaCell,
    SheetRowSet,
    SheetValueCell,
    TabName,
    column_letters_to_index,
)
from ....application.storage.calc_sheets.workbook_cells import (
    SheetCellBlock,
    evidence_cell_blocks,
    formula_cell_blocks,
    guide_cell_blocks,
    row_set_header_blocks,
    value_cell_blocks,
)
from ....core.decimal.coercion import coerce_decimal

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.schemas import ValueRange

#: Matches the single-cell anchor of a ``values.batchUpdate`` entry range:
#: ``'Tab Name'!B4``. Every builder in this module emits an anchor plus a
#: values block rather than a rectangle, so the written extent is the anchor
#: offset by the block's own shape.
_ANCHOR_PATTERN = re.compile(r"^'(?P<tab>(?:[^']|'')+)'!(?P<letters>[A-Z]{1,3})(?P<row>\d+)$")


def coerce_cell_value(value: Decimal | str | bool | None) -> object:
    """Convert a :class:`application.storage.calc_sheets.records.SheetValueCell` value.

    ``None`` becomes an empty cell, booleans stay native, and
    :class:`~decimal.Decimal` values become finite numeric display values.
    Exact decimal text is a separate literal cell supplied by the review plan.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Sheets numeric display is outside its finite range")
        return number
    return str(value)


def _value_range(block: SheetCellBlock) -> ValueRange:
    """Render one shared cell block as a single ``values.batchUpdate`` entry."""
    return {
        "range": block.anchor.qualified(),
        "values": [[coerce_cell_value(value) for value in block.values]],
    }


def build_value_data(value_cells: Iterable[SheetValueCell]) -> list[ValueRange]:
    """Build ``values.batchUpdate`` entries for :class:`application.storage.calc_sheets.records.SheetValueCell`."""
    return [_value_range(block) for block in value_cell_blocks(value_cells)]


def build_formula_data(formula_cells: Iterable[SheetFormulaCell]) -> list[ValueRange]:
    """Build entries for :class:`application.storage.calc_sheets.records.SheetFormulaCell` records.

    The shared cell stream carries the leading ``=`` because
    :mod:`application.storage.calc_sheets` stores formula bodies without it and
    every transport needs it.
    """
    return [_value_range(block) for block in formula_cell_blocks(formula_cells)]


def build_row_set_header_data(row_sets: Iterable[SheetRowSet]) -> list[ValueRange]:
    """Emit Detalle-tab header cells for :class:`application.storage.calc_sheets.records.SheetRowSet`."""
    return [_value_range(block) for block in row_set_header_blocks(row_sets)]


def build_evidence_value_data(plan: AnySheetExportPlan) -> list[ValueRange]:
    """Build Evidencia-tab value writes for ``plan``.

    Renders :func:`application.storage.calc_sheets.workbook_cells.evidence_cell_blocks`,
    so the online fingerprint, header, and fact rows land exactly where the
    offline workbook puts them.
    """
    return [_value_range(block) for block in evidence_cell_blocks(plan)]


def build_guide_value_data(plan: AnySheetExportPlan) -> list[ValueRange]:
    """Build Guide-tab title, paragraph, and export-stamp rows for ``plan``."""
    return [_value_range(block) for block in guide_cell_blocks(plan)]


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets values.batchUpdate payload entries.
def _walk_payload_entries(data: Sequence[Mapping[str, Any]]) -> Iterator[tuple[str, object]]:
    """Walk a ``values.batchUpdate`` payload, yielding every ``(qualified_address, value)`` pair it writes.

    Each entry in ``data`` is an anchor range plus a values block, so the
    written extent is the anchor offset by that block's own shape: row ``r``
    of the block lands on ``anchor_row + r``, column ``c`` on
    ``anchor_column + c``. :func:`payload_written_addresses` and
    :func:`written_cell_values` both derive from this one walk so the address
    set and the value map can never drift against each other.

    Raises:
        ValueError: When an entry's range is not a single-cell anchor. The
            builders in this module only ever emit anchors, so a rectangle
            here means a new builder changed shape without this function
            being taught about it — and silently skipping it would
            under-report the written set, which is the direction that
            destroys data.
    """
    for entry in data:
        raw_range = str(entry.get("range", ""))
        match = _ANCHOR_PATTERN.match(raw_range)
        if match is None:
            message = f"values payload entry is not a single-cell anchor: {raw_range!r}"
            raise ValueError(message)
        tab = TabName(match.group("tab").replace("''", "'"))
        anchor_row = int(match.group("row"))
        anchor_column = column_letters_to_index(match.group("letters"))
        for row_offset, row_values in enumerate(entry.get("values", []) or []):
            for column_offset, cell in enumerate(row_values):
                address = SheetCellAddress.at(
                    tab,
                    anchor_row + row_offset,
                    anchor_column + column_offset,
                )
                yield address.qualified(), cell


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets values.batchUpdate payload entries.
def payload_written_addresses(data: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    """Return every qualified A1 address a ``values.batchUpdate`` payload writes.

    This is deliberately derived from the PAYLOAD rather than re-walked from
    the plan. Re-deriving the extent from the plan would be a second
    implementation of the layout the builders above already encode, and the
    two would drift — the stale-cell set would then name cells the write
    actually covered, and clearing them would blank live content.

    Raises:
        ValueError: See :func:`_walk_payload_entries`.
    """
    return frozenset(address for address, _ in _walk_payload_entries(data))


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets values.batchUpdate payload entries.
def written_cell_values(data: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    """Return every qualified address a payload writes, mapped to its target value.

    Companion to :func:`payload_written_addresses`, sharing the same walk so
    the address set and the value map cannot drift against each other. Values
    are the entry's raw cell content — the same shape :func:`coerce_cell_value`
    already produced for a real write — never re-derived from the plan. This is
    what an export preview diffs against a read-back of current content to
    answer "would this cell's value change".

    Raises:
        ValueError: See :func:`_walk_payload_entries`.
    """
    return dict(_walk_payload_entries(data))


def stale_addresses(*, occupied: frozenset[str], written: frozenset[str]) -> tuple[str, ...]:
    """Return the addresses a previous run filled that this write does not replace.

    The whole point of the clear step: a re-apply must not leave a longer
    previous run's trailing cells standing beside the new content. Only
    those cells are named — never a cell the write covers, and never a cell
    that was already empty — so a clear can no longer blank content the
    workbook is not about to receive.

    Sorted so the emitted request is deterministic and diffable.
    """
    return tuple(sorted(occupied - written))


def changed_cell_addresses(
    *,
    target: Mapping[str, object],
    current: Mapping[str, object],
) -> tuple[str, ...]:
    """Return the addresses in ``target`` whose value would actually change.

    ``target`` is :func:`written_cell_values` for the non-formula value
    payload; ``current`` is a read-back of the same addresses' present
    content. An address absent from ``current`` reads as blank, matching how
    a value cell's coerced blank (``""``) compares against nothing having been
    read there before. Both sides are normalised through
    :func:`~core.decimal.coercion.coerce_decimal` where possible so a Decimal written as
    fixed-point text (``"1234.50"``) is compared against the number Sheets
    already stores (``1234.5``) rather than failing every numeric cell on
    string shape alone.

    Sorted so the result is deterministic and diffable, matching
    :func:`stale_addresses`.
    """
    return tuple(
        sorted(address for address, value in target.items() if not _cell_values_match(current.get(address), value)),
    )


def _cell_values_match(current: object, target: object) -> bool:
    """Whether a current read-back value already equals a payload's target value."""
    if current is None:
        # Nothing was read at this address: it matches only a blank target,
        # the coerced form of a ``None`` source value.
        return target == ""
    if isinstance(current, bool) or isinstance(target, bool):
        return current == target
    target_decimal = coerce_decimal(target) if isinstance(target, (str, int, float, Decimal)) else None
    current_decimal = coerce_decimal(current) if isinstance(current, (str, int, float, Decimal)) else None
    if target_decimal is not None and current_decimal is not None:
        return target_decimal == current_decimal
    return str(current) == str(target)
