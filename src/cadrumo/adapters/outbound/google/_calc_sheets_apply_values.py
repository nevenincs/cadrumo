"""Google Sheets value-write payload builders for calc sheet exports.

:mod:`adapters.outbound.google._calc_sheets_apply` clears the workbook
tabs and passes these payloads to the shared
:func:`adapters.outbound.google._api.execute_request` boundary for a
Sheets ``values.batchUpdate`` call. This module stays pure: it maps
:class:`application.storage.calc_sheets.SheetExportPlan` facets into A1
ranges plus row values and never opens a Google service object itself.

See Also:
    :func:`_build_value_data` and :func:`_build_formula_data` emit the main
    workbook grid, while :func:`_build_evidence_value_data` mirrors
    :func:`application.storage.calc_sheets.evidence_table` so the online
    Evidencia tab stays aligned with the offline workbook renderer.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from ....application.storage.calc_sheets import (
    SheetCellAddress,
    SheetExportPlan,
    SheetFormulaCell,
    SheetRowSet,
    SheetValueCell,
    TabName,
    column_letters_to_index,
    evidence_table,
    guide_stamps,
)

#: Matches the single-cell anchor of a ``values.batchUpdate`` entry range:
#: ``'Tab Name'!B4``. Every builder in this module emits an anchor plus a
#: values block rather than a rectangle, so the written extent is the anchor
#: offset by the block's own shape.
_ANCHOR_PATTERN = re.compile(r"^'(?P<tab>(?:[^']|'')+)'!(?P<letters>[A-Z]{1,3})(?P<row>\d+)$")


def _coerce_cell_value(value: Decimal | str | bool | None) -> object:
    """Convert a :class:`application.storage.calc_sheets.SheetValueCell` value.

    ``None`` becomes an empty cell, booleans stay native, and
    :class:`~decimal.Decimal` values are rendered with fixed-point text so
    Sheets does not receive rounded binary floats.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        # Sheets accepts plain floats; render the Decimal as a fixed
        # decimal string so very small/very large values do not round.
        return format(value, "f")
    return str(value)


def _build_value_data(value_cells: Iterable[SheetValueCell]) -> list[dict[str, Any]]:
    """Build ``values.batchUpdate`` entries for :class:`application.storage.calc_sheets.SheetValueCell`."""
    data: list[dict[str, Any]] = []
    for cell in value_cells:
        data.append(
            {
                "range": cell.address.qualified(),
                "values": [[_coerce_cell_value(cell.value)]],
            },
        )
    return data


def _build_formula_data(formula_cells: Iterable[SheetFormulaCell]) -> list[dict[str, Any]]:
    """Build entries for :class:`application.storage.calc_sheets.SheetFormulaCell` records.

    Formula text is prefixed with ``=`` because
    :mod:`application.storage.calc_sheets` stores formula bodies without
    the leading Sheets marker.
    """
    data: list[dict[str, Any]] = []
    for cell in formula_cells:
        data.append(
            {
                "range": cell.address.qualified(),
                "values": [[f"={cell.formula}"]],
            },
        )
    return data


def _build_row_set_header_data(row_sets: Iterable[SheetRowSet]) -> list[dict[str, Any]]:
    """Emit Detalle-tab header cells for :class:`application.storage.calc_sheets.SheetRowSet`."""
    data: list[dict[str, Any]] = []
    for row_set in row_sets:
        for column in row_set.columns:
            data.append(
                {
                    "range": column.header_address.qualified(),
                    "values": [[column.header_label]],
                },
            )
    return data


def _build_evidence_value_data(plan: SheetExportPlan) -> list[dict[str, Any]]:
    """Build Evidencia-tab value writes for ``plan``.

    Uses :func:`application.storage.calc_sheets.evidence_table`, the same
    source used by the offline workbook renderer, so online Sheets output and
    offline XLSX output stay cell-for-cell aligned.
    """
    fingerprint, header, body = evidence_table(plan)
    tab = TabName.EVIDENCIA.value
    data: list[dict[str, Any]] = [
        {"range": f"'{tab}'!A1", "values": [["Snapshot fingerprint", fingerprint]]},
        {"range": f"'{tab}'!A3", "values": [list(header)]},
    ]
    for offset, row in enumerate(body):
        data.append({"range": f"'{tab}'!A{4 + offset}", "values": [list(row)]})
    return data


def _build_guide_value_data(plan: SheetExportPlan) -> list[dict[str, Any]]:
    """Build Guide-tab title, paragraph, and export-stamp rows for ``plan``."""
    data: list[dict[str, Any]] = [
        {"range": f"'{TabName.GUIDE.value}'!A1", "values": [[plan.guide.title]]},
    ]
    for index, paragraph in enumerate(plan.guide.paragraphs, start=3):
        data.append({"range": f"'{TabName.GUIDE.value}'!A{index}", "values": [[paragraph]]})
    base_row = 3 + len(plan.guide.paragraphs) + 2
    for offset, (label, value) in enumerate(guide_stamps(plan)):
        data.append(
            {
                "range": f"'{TabName.GUIDE.value}'!A{base_row + offset}",
                "values": [[label, value]],
            },
        )
    return data


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets values.batchUpdate payload entries.
def payload_written_addresses(data: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    """Return every qualified A1 address a ``values.batchUpdate`` payload writes.

    Each entry in ``data`` is an anchor range plus a values block, so the
    written extent is the anchor offset by that block's own shape: row ``r``
    of the block lands on ``anchor_row + r``, column ``c`` on
    ``anchor_column + c``.

    This is deliberately derived from the PAYLOAD rather than re-walked from
    the plan. Re-deriving the extent from the plan would be a second
    implementation of the layout the builders above already encode, and the
    two would drift — the stale-cell set would then name cells the write
    actually covered, and clearing them would blank live content.

    Raises:
        ValueError: When an entry's range is not a single-cell anchor. The
            builders in this module only ever emit anchors, so a rectangle
            here means a new builder changed shape without this function
            being taught about it — and silently skipping it would
            under-report the written set, which is the direction that
            destroys data.
    """
    written: set[str] = set()
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
            for column_offset, _cell in enumerate(row_values):
                address = SheetCellAddress.at(
                    tab,
                    anchor_row + row_offset,
                    anchor_column + column_offset,
                )
                written.add(address.qualified())
    return frozenset(written)


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
