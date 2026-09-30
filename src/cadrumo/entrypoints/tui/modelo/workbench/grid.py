"""The official grids and repeated records of a page, measured as the paper form's rows and columns.

A grid of the official form is a table: its rows are printed down the side and
its columns across, and each cell holds one box. The casilla list draws a grid
that way when the table fits the width it has, and otherwise stacks it, one row
heading over one line per box. The decision is taken per grid, from the widths
this module measures, never from a fixed breakpoint.

Nothing here decides what a box means. It lays out texts the list hands it: the
column headings, the row labels, and for each cell its box number and value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from rich.cells import cell_len

from .....application.modelo.work_form_models import (
    ModeloFormPrintedRate,
    ModeloFormRate,
    ModeloFormRepeatingRow,
)

type GridKey = tuple[str, str]
"""A cell's semantic address, as the casilla list keys its cursor."""

#: The cursor mark, the row's level mark and the space after them.
GRID_LEAD: Final[int] = 3
#: A row label is never wider than this; a longer heading wraps onto further lines.
GRID_LABEL_CAP: Final[int] = 32
#: A row label runs to at most this many lines; one that needs more stacks its grid.
GRID_LABEL_LINES: Final[int] = 3
#: The indent of a row label's second and later lines, so they never read as the next row's label.
GRID_LABEL_INDENT: Final[int] = 2
#: Cells between two columns.
GRID_GAP: Final[int] = 2
#: A money or text value column makes room for at least this many cells, so figures line up as they grow.
GRID_VALUE_FLOOR: Final[int] = 12
#: A record column makes room for this much of its heading, so a long heading takes few lines.
GRID_RECORD_HEADING_FLOOR: Final[int] = 16
#: A rate column makes room for at least this many cells.
GRID_RATE_FLOOR: Final[int] = 4
_BREAKABLE_SPACE: Final[re.Pattern[str]] = re.compile(r"[^\S\u00a0]+")
"""Where a text may break: any space except a no-break space, which holds "art. 71" or "1 000" together."""


def wrap_text(text: str, width: int) -> tuple[str, ...]:
    """Break ``text`` into lines of at most ``width`` cells, at spaces where it can; nothing is dropped."""
    width = max(width, 1)
    lines: list[str] = []
    line = ""
    for word in _BREAKABLE_SPACE.split(text.strip()):
        candidate = f"{line} {word}" if line else word
        if cell_len(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = word
        while cell_len(line) > width:
            cut = len(line)
            while cut > 1 and cell_len(line[:cut]) > width:
                cut -= 1
            lines.append(line[:cut])
            line = line[cut:]
    if line or not lines:
        lines.append(line)
    return tuple(lines)


def wrap_label(text: str, width: int) -> tuple[str, ...]:
    """Break a row label into lines of ``width`` cells, each line after the first indented under the first."""
    first = wrap_text(text, width)
    if len(first) == 1:
        return first
    rest = wrap_text(text[len(first[0]) :], max(width - GRID_LABEL_INDENT, 1))
    return (first[0], *(" " * GRID_LABEL_INDENT + line for line in rest))


def _whole(text: str, width: int) -> bool:
    """Whether every word of a label fits its column, the first line's own and the indented lines'."""
    return longest_word(text) <= max(width - GRID_LABEL_INDENT, 1) or cell_len(text) <= width


def longest_word(text: str) -> int:
    """The widest unbreakable run of ``text``, in cells."""
    return max((cell_len(word) for word in _BREAKABLE_SPACE.split(text.strip())), default=0)


@dataclass(frozen=True, slots=True, eq=False)
class GridShape:
    """One official grid, as the list shows it: the heading of each column.

    Two grids with the same headings are still two grids, so a shape compares
    by identity: the rows that name it are the rows of one table.
    """

    id: str
    headings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GridSlot:
    """One cell of a printed row: the box it shows, a literal the design prints, or an empty slot."""

    key: GridKey | None = None
    literal: str | None = None


@dataclass(frozen=True, slots=True)
class GridRowPlace:
    """Where a row heading stands in its grid, and which of the lines after it are its cells.

    ``span`` is how many list items after the heading belong to the row: its
    boxes, then any literal the design prints without a box. ``rate`` is the
    rate the row's one rate box shows, and ``boxes`` the row's box numbers, so
    a stacked row can say which row it is once the rate column is gone.
    """

    grid: GridShape
    heading: str
    slots: tuple[GridSlot, ...]
    span: int
    rate: ModeloFormRate | ModeloFormPrintedRate | None = None
    boxes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CasillaListRecords:
    """The records of a repeating group, shown read-only as a table with an index column."""

    headings: tuple[str, ...]
    data_types: tuple[str, ...]
    rows: tuple[ModeloFormRepeatingRow, ...]


@dataclass(frozen=True, slots=True)
class GridCellText:
    """The texts of one cell, measured before any is placed."""

    box: str
    value: str
    #: A rate column's floor applies only to a column whose every box is a rate.
    rate: bool = False


@dataclass(frozen=True, slots=True)
class TableGeometry:
    """Where every column of one grid sits at one width.

    ``widths`` is each column's full width; a cell reads, right-aligned in it,
    an overlay slot, the box number in ``boxes`` cells, a space, the value in
    ``values`` cells, a space and the origin mark. ``header`` holds each
    column's heading, broken into lines no wider than the column.
    """

    label: int
    boxes: tuple[int, ...]
    values: tuple[int, ...]
    widths: tuple[int, ...]
    header: tuple[tuple[str, ...], ...]

    @property
    def header_height(self) -> int:
        """The lines the column headings take."""
        return max((len(lines) for lines in self.header), default=0)

    def start(self, column: int) -> int:
        """The first cell of a column, counted from the left edge of the line."""
        return GRID_LEAD + self.label + 1 + sum(self.widths[:column]) + GRID_GAP * column

    def column_at(self, x: int) -> int | None:
        """The column a cell at ``x`` falls in, or ``None`` left of the first column."""
        for column in range(len(self.widths)):
            if x < self.start(column) + self.widths[column] + GRID_GAP:
                return column if x >= self.start(0) else None
        return len(self.widths) - 1 if self.widths else None


def cell_width(box: int, value: int) -> int:
    """A cell's width: the overlay slot, the box, a space, the value, a space and the origin mark."""
    return 1 + box + 1 + value + 2


def measure_table(
    headings: tuple[str, ...],
    columns: tuple[tuple[GridCellText, ...], ...],
    literals: tuple[tuple[str, ...], ...],
    labels: tuple[str, ...],
    width: int,
) -> TableGeometry | None:
    """Measure a grid as a table at ``width``, or ``None`` when it does not fit and must be stacked.

    Every row label must fit its column in at most :data:`GRID_LABEL_LINES`
    lines with no word cut, so a grid whose labels would lose a word, or run
    down the side far past its own cells, goes stacked rather than cut a row.
    """
    boxes: list[int] = []
    values: list[int] = []
    widths: list[int] = []
    for heading, cells, fixed in zip(headings, columns, literals, strict=True):
        box = max((cell_len(cell.box) for cell in cells), default=0)
        floor = GRID_RATE_FLOOR if cells and all(cell.rate for cell in cells) else GRID_VALUE_FLOOR
        widest = max((cell_len(text) for text in (*(cell.value for cell in cells), *fixed)), default=1)
        value = max(widest, floor if cells else 1)
        boxes.append(box)
        values.append(value)
        widths.append(max(cell_width(box, value), longest_word(heading)))
    cells_width = sum(widths) + GRID_GAP * max(len(widths) - 1, 0)
    room = width - GRID_LEAD - 1 - cells_width
    widest_label = max((cell_len(label) for label in labels), default=0)
    label = min(GRID_LABEL_CAP, widest_label, room)
    if label < 1 and widest_label:
        return None
    label = max(label, 1)
    if any(len(wrap_label(text, label)) > GRID_LABEL_LINES or not _whole(text, label) for text in labels):
        return None
    header = tuple(wrap_text(heading, column_width) for heading, column_width in zip(headings, widths, strict=True))
    return TableGeometry(label=label, boxes=tuple(boxes), values=tuple(values), widths=tuple(widths), header=header)


@dataclass(frozen=True, slots=True)
class RecordsGeometry:
    """How a repeating group's records sit at one width: as a table, or one line per record."""

    table: bool
    index: int
    widths: tuple[int, ...]
    header: tuple[tuple[str, ...], ...]

    @property
    def header_height(self) -> int:
        """The lines the column headings take; none when records are one line each."""
        return max((len(lines) for lines in self.header), default=0) if self.table else 0


def measure_records(
    headings: tuple[str, ...], indexes: tuple[str, ...], values: tuple[tuple[str, ...], ...], width: int
) -> RecordsGeometry:
    """Measure records as a table when every column fits whole, else as one line per record."""
    index = max((cell_len(text) for text in indexes), default=1)
    widths = tuple(
        max(
            longest_word(heading),
            min(cell_len(heading), GRID_RECORD_HEADING_FLOOR),
            max((cell_len(row[column]) for row in values), default=1),
        )
        for column, heading in enumerate(headings)
    )
    total = GRID_LEAD + index + sum(widths) + GRID_GAP * len(widths)
    if total > width:
        return RecordsGeometry(table=False, index=index, widths=widths, header=())
    header = tuple(wrap_text(heading, column_width) for heading, column_width in zip(headings, widths, strict=True))
    return RecordsGeometry(table=True, index=index, widths=widths, header=header)


def record_summary_columns(data_types: tuple[str, ...]) -> tuple[int, ...]:
    """The columns a one-line record shows: the first two and the last money column."""
    shown = list(range(min(2, len(data_types))))
    money = [column for column, data_type in enumerate(data_types) if data_type == "money"]
    if money and money[-1] not in shown:
        shown.append(money[-1])
    return tuple(shown)


__all__ = [
    "GRID_GAP",
    "GRID_LABEL_CAP",
    "GRID_LABEL_INDENT",
    "GRID_LABEL_LINES",
    "GRID_LEAD",
    "GRID_RATE_FLOOR",
    "GRID_RECORD_HEADING_FLOOR",
    "GRID_VALUE_FLOOR",
    "CasillaListRecords",
    "GridCellText",
    "GridKey",
    "GridRowPlace",
    "GridShape",
    "GridSlot",
    "RecordsGeometry",
    "TableGeometry",
    "cell_width",
    "longest_word",
    "measure_records",
    "measure_table",
    "record_summary_columns",
    "wrap_label",
    "wrap_text",
]
