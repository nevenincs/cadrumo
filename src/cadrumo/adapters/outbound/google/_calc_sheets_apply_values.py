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
    ``anchor_column + c``. :func:`written_cell_values` derives the addressed
    publication baseline from this walk.

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
def written_cell_values(data: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    """Return every qualified address a payload writes, mapped to its target value.

    Values are the literal payload content produced by :func:`coerce_cell_value`.
    Local preview counts this inventory, and publication verifies its selected
    baseline against the provider's acknowledged cells.

    Raises:
        ValueError: See :func:`_walk_payload_entries`.
    """
    return dict(_walk_payload_entries(data))
