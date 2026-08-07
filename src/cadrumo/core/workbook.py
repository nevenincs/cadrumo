"""The workbook-reading policy every layer that opens a spreadsheet shares.

A cell carrying a formula states a computation, not a figure. Beside it a
workbook may cache whatever number was last computed into it, and that cached
number is not the formula's value: a sheet edited somewhere else and saved
without recalculating carries a figure nobody typed and the formula does not
produce. Reading it would take that number as fact.

So a formula cell is **refused, never read**, everywhere a spreadsheet is
treated as a source of financial or filing data — the bank-statement workbook
provider, the casilla-value spreadsheet, and the bulk invoice book each refuse
on this ground. The alternative, reading the cached value, fails in the
direction that matters: the wrong figure reaches a return as a number rather
than as any kind of failure, which is the one outcome no downstream check is
positioned to catch.

The detection and the sentence live here so the three readers cannot drift
apart on what a formula cell is or on what the operator is told about it. What
stays with each reader is the part that genuinely differs: which rows are in
scope (the statement provider ignores its preamble and header, the other two
read every row), and which error type its layer refuses with.

This module deliberately does not import ``openpyxl``. The cell is described
structurally instead, so resolving the policy never pulls a spreadsheet engine
into the innermost layer.

See Also:
    :class:`~core.tabular.NormalizedTable`
        The delimited-text counterpart. A workbook states its own cell types,
        so it has no dialect to detect and shares nothing with that module
        beyond both being tabular sources.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final, Protocol

__all__ = [
    "FORMULA_CELL_REFUSAL",
    "WorkbookCell",
    "first_formula_cell_column",
]

FORMULA_CELL_REFUSAL: Final[str] = "formula cached values are not accepted"
"""The clause every formula-cell refusal ends with, so all three read alike."""


class WorkbookCell(Protocol):
    """The one attribute the policy needs from a workbook cell.

    Structural rather than nominal so that ``openpyxl``'s ``Cell``,
    ``ReadOnlyCell`` and ``EmptyCell`` all satisfy it without this module
    importing the library. Every one of them exposes ``data_type``.
    """

    @property
    def data_type(self) -> str:
        """The cell's openpyxl type code; ``"f"`` marks a formula."""
        ...


def first_formula_cell_column(cells: Iterable[WorkbookCell]) -> int | None:
    """Return the 1-based column of the first formula cell in *cells*.

    Args:
        cells: One row's cells, in column order.

    Returns:
        The 1-based column number of the first cell stating a formula, or
        ``None`` when the row carries none. Reporting the position rather than
        raising leaves each caller free to refuse in its own layer's error type
        and to name its own artefact, while the test for what counts as a
        formula stays in one place.
    """
    for column_number, cell in enumerate(cells, start=1):
        if cell.data_type == "f":
            return column_number
    return None
