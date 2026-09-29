"""The addressed cell stream every workbook transport writes.

A :class:`~application.storage.calc_sheets.records.SheetExportPlan` declares what
the workbook says; this module resolves where each declared and derived value
lands. The Google Sheets apply adapter maps each block onto a
``values.batchUpdate`` anchor entry, and the offline XLSX materializer writes
each block into a worksheet. Neither transport owns an address arithmetic of its
own: a transport that invented one would drift from the other the first time a
derived tab changed shape, and the operator would see two different workbooks
for one plan.

Every block is ONE ROW: the anchor addresses its leftmost cell and the values
extend rightwards, one column per value. That is the shape the Guide and
Evidencia tables already have, and the only shape either transport needs.

Values stay typed (``Decimal`` / ``str`` / ``bool`` / ``None``). Rendering a
``Decimal`` as text is a transport concern -- the online transport needs it so
Sheets parses the figure it was sent, the offline transport writes the number
itself -- so the coercion belongs to each transport and not here.

See Also:
    :func:`application.storage.calc_sheets.export_tables.evidence_table`
        The Evidencia value table this module addresses.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from .export_tables import evidence_table, guide_stamps
from .records import (
    SheetCellAddress,
    SheetExportPlan,
    SheetFormulaCell,
    SheetRowSet,
    SheetValueCell,
    TabName,
)

type SheetCellValue = Decimal | str | bool | None
"""One cell's value as the plan states it, before any transport coercion."""

EVIDENCE_FINGERPRINT_LABEL: Final[str] = "Snapshot fingerprint"
"""Label written beside the evidence snapshot fingerprint on ``Evidencia!A1``."""

_GUIDE_TITLE_ROW: Final[int] = 1
_GUIDE_FIRST_PARAGRAPH_ROW: Final[int] = 3
_GUIDE_STAMP_GAP: Final[int] = 2
_EVIDENCE_FINGERPRINT_ROW: Final[int] = 1
_EVIDENCE_HEADER_ROW: Final[int] = 3


@dataclass(frozen=True, slots=True)
class SheetCellBlock:
    """One row of workbook content: an anchor cell plus the values right of it."""

    anchor: SheetCellAddress
    values: tuple[SheetCellValue, ...]

    def addressed_values(self) -> Iterator[tuple[SheetCellAddress, SheetCellValue]]:
        """Yield each value paired with the address it occupies.

        Yields:
            tuple[:class:`~application.storage.calc_sheets.records.SheetCellAddress`, SheetCellValue]:
            The anchor and its value first, then each following value one column
            further right on the same row.
        """
        for offset, value in enumerate(self.values):
            yield (
                SheetCellAddress.at(self.anchor.tab, self.anchor.row, self.anchor.column + offset),
                value,
            )


def value_cell_blocks(value_cells: Iterable[SheetValueCell]) -> tuple[SheetCellBlock, ...]:
    """Address each literal plan value cell as a single-cell block."""
    return tuple(SheetCellBlock(anchor=cell.address, values=(cell.value,)) for cell in value_cells)


def formula_cell_blocks(formula_cells: Iterable[SheetFormulaCell]) -> tuple[SheetCellBlock, ...]:
    """Address each computed cell, carrying the formula with its leading ``=``.

    The plan stores formula bodies without the marker because it is not a Sheets
    payload; both transports need it, so it is prepended once here.
    """
    return tuple(SheetCellBlock(anchor=cell.address, values=(f"={cell.formula}",)) for cell in formula_cells)


def row_set_header_blocks(row_sets: Iterable[SheetRowSet]) -> tuple[SheetCellBlock, ...]:
    """Address the Detalle header label of every row-set column."""
    return tuple(
        SheetCellBlock(anchor=column.header_address, values=(column.header_label,))
        for row_set in row_sets
        for column in row_set.columns
    )


def guide_cell_blocks(plan: SheetExportPlan) -> tuple[SheetCellBlock, ...]:
    """Address the Guía title, prose paragraphs, and export identity stamps."""
    blocks: list[SheetCellBlock] = [
        SheetCellBlock(
            anchor=SheetCellAddress.at(TabName.GUIDE, _GUIDE_TITLE_ROW, 1),
            values=(plan.guide.title,),
        ),
    ]
    for index, paragraph in enumerate(plan.guide.paragraphs, start=_GUIDE_FIRST_PARAGRAPH_ROW):
        blocks.append(
            SheetCellBlock(anchor=SheetCellAddress.at(TabName.GUIDE, index, 1), values=(paragraph,)),
        )
    stamp_row = _GUIDE_FIRST_PARAGRAPH_ROW + len(plan.guide.paragraphs) + _GUIDE_STAMP_GAP
    for offset, (label, value) in enumerate(guide_stamps(plan)):
        blocks.append(
            SheetCellBlock(
                anchor=SheetCellAddress.at(TabName.GUIDE, stamp_row + offset, 1),
                values=(label, value),
            ),
        )
    return tuple(blocks)


def evidence_cell_blocks(plan: SheetExportPlan) -> tuple[SheetCellBlock, ...]:
    """Address the Evidencia fingerprint, header row, and one row per fact."""
    fingerprint, header, body = evidence_table(plan)
    blocks: list[SheetCellBlock] = [
        SheetCellBlock(
            anchor=SheetCellAddress.at(TabName.EVIDENCIA, _EVIDENCE_FINGERPRINT_ROW, 1),
            values=(EVIDENCE_FINGERPRINT_LABEL, fingerprint),
        ),
        SheetCellBlock(
            anchor=SheetCellAddress.at(TabName.EVIDENCIA, _EVIDENCE_HEADER_ROW, 1),
            values=tuple(header),
        ),
    ]
    for offset, row in enumerate(body):
        blocks.append(
            SheetCellBlock(
                anchor=SheetCellAddress.at(TabName.EVIDENCIA, _EVIDENCE_HEADER_ROW + 1 + offset, 1),
                values=tuple(row),
            ),
        )
    return tuple(blocks)


def plan_value_blocks(plan: SheetExportPlan) -> tuple[SheetCellBlock, ...]:
    """Address every non-formula value the plan writes, in canonical order.

    The order is the one both transports write in: literal plan cells, the Guía
    surface, the Detalle row-set headers, then the Evidencia surface. It is
    stable so a transport's own write sequence is reproducible.
    """
    return (
        value_cell_blocks(plan.value_cells)
        + guide_cell_blocks(plan)
        + row_set_header_blocks(plan.row_sets)
        + evidence_cell_blocks(plan)
    )


__all__ = [
    "EVIDENCE_FINGERPRINT_LABEL",
    "SheetCellBlock",
    "SheetCellValue",
    "evidence_cell_blocks",
    "formula_cell_blocks",
    "guide_cell_blocks",
    "plan_value_blocks",
    "row_set_header_blocks",
    "value_cell_blocks",
]
