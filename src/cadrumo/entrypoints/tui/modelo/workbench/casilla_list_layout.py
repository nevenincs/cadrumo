"""Grid and record layout for the virtual casilla list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.cells import cell_len
from textual.geometry import Size

from .....application.modelo.edit_value_grammar import ratio_unit
from .....application.modelo.value_presentation import (
    format_casilla_value,
)
from .....application.modelo.work_form_models import (
    ModeloFormScalar,
)
from .....core.i18n.render import tr
from ...components.cell_text import wrap_words
from . import casilla_list_models as _models
from . import casilla_list_values as _values
from .grid import (
    GRID_GAP,
    GRID_LEAD,
    CasillaListRecords,
    GridCellText,
    GridRowPlace,
    GridShape,
    RecordsGeometry,
    TableGeometry,
    measure_records,
    measure_table,
    stacked_record_lines,
    wrap_label,
)
from .vocabulary import (
    Attention,
    attention_words_key,
)

if TYPE_CHECKING:
    from .casilla_list import CasillaList


class CasillaListLayoutMixin:
    """Grid and record layout for the virtual casilla list."""

    def _content_width(self: CasillaList) -> int:
        return max(self.scrollable_content_region.width, 20)

    def _measure(self: CasillaList, drawn_in_tables: frozenset[int]) -> _models._Measures:
        entries = [
            item
            for index, item in enumerate(self._items)
            if isinstance(item, _models.CasillaListEntry) and index not in drawn_in_tables
        ]
        if not entries:
            return _models._Measures()
        return _models._Measures(
            box=max(cell_len(_values._box_mark(entry.field)) for entry in entries),
            label=min(max(entry.indent + cell_len(self._label(entry)) for entry in entries), _values._LABEL_CAP),
            value=min(max(cell_len(self._value(entry)) for entry in entries), _values._VALUE_CAP),
            words=max(cell_len(entry.origin_words) for entry in entries),
        )

    def _value(self: CasillaList, entry: _models.CasillaListEntry) -> str:
        """The value a line shows: a grid cell never says the design fixes it."""
        if entry.row_label is not None:
            return _values.grid_value_text(entry, self._language)
        return _values.row_value_text(entry, self._language)

    def _columns(self: CasillaList, width: int) -> _models._Columns:
        """Share one width out: the box whole, then the value, the label, and the origin words where they fit."""
        measures = self._measures
        # What is left once the lead, the box and its space, the space before
        # the value and the space and glyph after it are placed.
        room = width - (_values._LEAD + measures.box + 1 + 1 + 2)
        words_cells = 1 + measures.words
        # The words take room only while the label keeps as much as it needs,
        # or at least as much as the value and the words it would give way to.
        needed = min(measures.label, measures.value + measures.words)
        show_words = measures.words > 0 and room - measures.value - words_cells >= needed
        if show_words:
            room -= words_cells
        value = min(measures.value, max(room - min(measures.label, _values._LABEL_FLOOR), 1))
        label = max(min(measures.label, room - value), 1)
        detail = (
            show_words
            and width >= _values._WIDEST
            and room - value - label >= cell_len(_values._SEPARATOR) + _values._DETAIL_WIDTH
        )
        return _models._Columns(
            box=measures.box, label=label, value=value, words=measures.words if show_words else 0, detail=detail
        )

    def _label_lines(self: CasillaList, entry: _models.CasillaListEntry, columns: _models._Columns) -> tuple[str, ...]:
        return wrap_words(self._label(entry), _values._label_width(entry, columns))

    def _note(self: CasillaList, index: int, entry: _models.CasillaListEntry, columns: _models._Columns) -> str | None:
        """The optional line under a field: what a change replaces, a blocker, or where the description starts.

        A box of a stacked grid shows no description; the help band carries it.
        """
        if self._density == "compact":
            return None
        if entry.previous_text is not None and not columns.detail:
            return tr("tui.modelo.workbench.was", value=entry.previous_text)
        if entry.attention is Attention.BLOCKED and not columns.detail:
            return tr(attention_words_key(Attention.BLOCKED))
        if index in self._stacked:
            return None
        description = _values.description_text(entry.field)
        return description.split(". ")[0] if description else None

    def _rated_label(self: CasillaList, place: GridRowPlace) -> str:
        """A row's heading with the rate its row is taxed at, when it has one."""
        if place.rate is not None:
            return _values._SEPARATOR.join((place.heading, _values.rate_text(place.rate, self._language)))
        return place.heading

    def _stacked_label(self: CasillaList, place: GridRowPlace) -> str:
        """A stacked row's heading, told apart from its neighbours by its rate or by the boxes it holds."""
        if place.rate is None and len(place.boxes) > 1:
            return tr(_values._ROW_BOXES_KEY, heading=place.heading, first=place.boxes[0], last=place.boxes[-1])
        return self._rated_label(place)

    def _height(self: CasillaList, index: int, item: _models.CasillaListItem, width: int) -> int:
        if index in self._tables:
            row = self._tables[index]
            return row.header_height + len(row.labels)
        if self._owner[index] != index:
            return 0
        if isinstance(item, _models.CasillaListHeading):
            if item.row is not None:
                return len(wrap_words(self._stacked_label(item.row), width - _values._LEAD))
            return 1
        if isinstance(item, CasillaListRecords):
            return len(self._records.get(index, ()))
        if not isinstance(item, _models.CasillaListEntry):
            return 1
        columns = self._columns(width)
        return len(self._label_lines(item, columns)) + (1 if self._note(index, item, columns) else 0)

    def _grid_rows(self: CasillaList) -> dict[GridShape, list[int]]:
        """The index of every grid row heading, grouped by the grid it belongs to, in list order."""
        grids: dict[GridShape, list[int]] = {}
        for index, item in enumerate(self._items):
            if isinstance(item, _models.CasillaListHeading) and item.row is not None:
                grids.setdefault(item.row.grid, []).append(index)
        return grids

    def _owned(self: CasillaList, heading: int) -> range:
        """The items a grid row heading owns: its boxes and any literal the design prints without one."""
        item = self._items[heading]
        span = item.row.span if isinstance(item, _models.CasillaListHeading) and item.row is not None else 0
        return range(heading + 1, min(heading + 1 + span, len(self._items)))

    def _row_cells(self: CasillaList, heading: int) -> tuple[int | None, ...]:
        item = self._items[heading]
        if not isinstance(item, _models.CasillaListHeading) or item.row is None:
            return ()
        owned = {
            entry.key: index
            for index in self._owned(heading)
            if isinstance(entry := self._items[index], _models.CasillaListEntry)
        }
        return tuple(None if slot.key is None else owned.get(slot.key) for slot in item.row.slots)

    def _lay_out_grids(self: CasillaList, width: int) -> None:
        """Decide for each grid whether it is drawn as a table at ``width``, and place its rows and cells."""
        self._tables = {}
        self._cell_of = {}
        stacked: set[int] = set()
        self._owner = list(range(len(self._items)))
        for grid, headings in self._grid_rows().items():
            self._lay_out_grid(grid, headings, width, stacked)
        self._stacked = frozenset(stacked)

    def _lay_out_grid(self: CasillaList, grid: GridShape, headings: list[int], width: int, stacked: set[int]) -> None:
        rows, places = self._grid_cells_and_places(headings)
        texts = self._grid_column_texts(grid, rows)
        literals = self._grid_column_literals(grid, places)
        labels = self._shown_labels(places)
        geometry = measure_table(grid.headings, texts, literals, labels, width)
        if geometry is None:
            for heading in headings:
                stacked.update(self._owned(heading))
            return
        self._lay_out_grid_table(headings, rows, places, labels, geometry)

    def _grid_cells_and_places(
        self: CasillaList, headings: list[int]
    ) -> tuple[list[tuple[int | None, ...]], list[GridRowPlace | None]]:
        rows = [self._row_cells(heading) for heading in headings]
        places = [
            item.row for heading in headings if isinstance(item := self._items[heading], _models.CasillaListHeading)
        ]
        return rows, places

    def _grid_column_texts(
        self: CasillaList, grid: GridShape, rows: list[tuple[int | None, ...]]
    ) -> tuple[tuple[GridCellText, ...], ...]:
        return tuple(
            tuple(self._cell_text(index) for row in rows if (index := row[column]) is not None)
            for column in range(len(grid.headings))
        )

    @staticmethod
    def _grid_column_literals(grid: GridShape, places: list[GridRowPlace | None]) -> tuple[tuple[str, ...], ...]:
        return tuple(
            tuple(literal for place in places if place is not None and (literal := place.slots[column].literal))
            for column in range(len(grid.headings))
        )

    def _lay_out_grid_table(
        self: CasillaList,
        headings: list[int],
        rows: list[tuple[int | None, ...]],
        places: list[GridRowPlace | None],
        labels: tuple[str, ...],
        geometry: TableGeometry,
    ) -> None:
        for position, (heading, cells, place) in enumerate(zip(headings, rows, places, strict=True)):
            self._own_table_cells(heading, cells)
            entries = [
                entry
                for index in cells
                if index is not None and isinstance(entry := self._items[index], _models.CasillaListEntry)
            ]
            self._tables[heading] = _models._TableRow(
                geometry=geometry,
                cells=cells,
                literals=() if place is None else tuple(slot.literal for slot in place.slots),
                labels=wrap_label(labels[position], geometry.label) if labels[position] else ("",),
                header=position == 0,
                level=_values._row_level(entries),
            )

    def _own_table_cells(self: CasillaList, heading: int, cells: tuple[int | None, ...]) -> None:
        for index in self._owned(heading):
            self._owner[index] = heading
        for column, index in enumerate(cells):
            if index is not None:
                self._cell_of[index] = (heading, column)

    def _shown_labels(self: CasillaList, places: list[GridRowPlace | None]) -> tuple[str, ...]:
        """Each row's label: its heading, with its rate when it has one, on every row it heads.

        The paper form prints a heading such as "General regime" once over the
        rows it spans, but a row read on its own, as a terminal line is, needs
        its own name, as the stacked form of the grid gives it.
        """
        return tuple("" if place is None else self._rated_label(place) for place in places)

    def _cell_text(self: CasillaList, index: int) -> GridCellText:
        item = self._items[index]
        if not isinstance(item, _models.CasillaListEntry):
            return GridCellText(box="", value="")
        return GridCellText(
            box=_values._box_mark(item.field),
            value=_values.grid_value_text(item, self._language),
            rate=item.field.data_type == _values._RATIO_DATA_TYPE,
        )

    def _record_value(self: CasillaList, value: ModeloFormScalar, data_type: str) -> str:
        if value is None:
            return _values._EMPTY_VALUE
        return format_casilla_value(
            value, data_type=data_type, language=self._language, ratio_unit=ratio_unit(data_type, None)
        )

    def _record_lines(self: CasillaList, item: CasillaListRecords, width: int) -> tuple[tuple[str, str], ...]:
        """A repeating group's records: a table when it fits, otherwise every labelled value stacked."""
        indexes = tuple(str(row.index) for row in item.rows)
        values = tuple(
            tuple(
                self._record_value(value, data_type)
                for value, data_type in zip(row.values, item.data_types, strict=True)
            )
            for row in item.rows
        )
        geometry = measure_records(item.headings, indexes, values, width)
        if not geometry.table:
            return self._stacked_record_lines(item, indexes, values, width, geometry.index)
        return self._tabular_record_lines(item, indexes, values, geometry)

    def _stacked_record_lines(
        self: CasillaList,
        item: CasillaListRecords,
        indexes: tuple[str, ...],
        values: tuple[tuple[str, ...], ...],
        width: int,
        index_width: int,
    ) -> tuple[tuple[str, str], ...]:
        lines = [
            (line, "value")
            for index, row in zip(indexes, values, strict=True)
            for line in stacked_record_lines(item.headings, index, row, index_width=index_width, width=width)
        ]
        return tuple(lines)

    def _tabular_record_lines(
        self: CasillaList,
        item: CasillaListRecords,
        indexes: tuple[str, ...],
        values: tuple[tuple[str, ...], ...],
        geometry: RecordsGeometry,
    ) -> tuple[tuple[str, str], ...]:
        lines: list[tuple[str, str]] = []
        height = geometry.header_height
        for line in range(height):
            parts = [" " * (GRID_LEAD + geometry.index)]
            for column, heading in enumerate(geometry.header):
                offset = height - len(heading)
                text = heading[line - offset] if line >= offset else ""
                parts.append(" " * GRID_GAP + self._record_cell(text, geometry.widths[column], item, column))
            lines.append(("".join(parts), "subheading"))
        for index, row in zip(indexes, values, strict=True):
            parts = [" " * GRID_LEAD + _values._right(index, geometry.index)]
            parts.extend(
                " " * GRID_GAP + self._record_cell(text, geometry.widths[column], item, column)
                for column, text in enumerate(row)
            )
            lines.append(("".join(parts), "value"))
        return tuple(lines)

    def _record_cell(self: CasillaList, text: str, width: int, item: CasillaListRecords, column: int) -> str:
        """An amount is right-aligned under its heading, anything else left-aligned."""
        if item.data_types[column] == _values._MONEY_DATA_TYPE:
            return _values._right(text, width)
        return _values._fit(text, width)

    def _layout(self: CasillaList) -> None:
        width = self._content_width()
        if width == self._laid_out_width and len(self._starts) == len(self._items):
            return
        self._laid_out_width = width
        self._lay_out_grids(width)
        self._records = {
            index: self._record_lines(item, width)
            for index, item in enumerate(self._items)
            if isinstance(item, CasillaListRecords)
        }
        self._measures = self._measure(frozenset(self._cell_of))
        starts: list[int] = []
        heights: list[int] = []
        line = 0
        for index, item in enumerate(self._items):
            starts.append(line)
            height = self._height(index, item, width)
            heights.append(height)
            line += height
        self._starts = starts
        self._heights = heights
        self.virtual_size = Size(width, line)
        if self.is_mounted:
            # A newly visible scrollbar changes content width without changing
            # this widget's size. Reveal against the resulting wrapped rows,
            # after scrolling has become available for the new virtual size.
            self.call_after_refresh(self.reveal_highlighted)
