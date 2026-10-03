"""Visible-line rendering for the virtual casilla list."""

from __future__ import annotations

from bisect import bisect_right
from typing import TYPE_CHECKING

from rich.cells import cell_len
from rich.style import Style
from rich.text import Text

from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.cell_text import wrap_words
from . import casilla_list_models as _models
from . import casilla_list_values as _values
from .grid import (
    GRID_GAP,
    GRID_LEAD,
    CasillaListRecords,
    cell_width,
)
from .vocabulary import (
    ATTENTION_GLYPHS,
    ATTENTION_ROLES,
    HERE_MARK,
    Attention,
    ColourRole,
    attention_words_key,
)

if TYPE_CHECKING:
    from .casilla_list import CasillaList


class CasillaListRenderingMixin:
    """Visible-line rendering for the virtual casilla list."""

    def _style(self: CasillaList, role: str) -> Style:
        return self.get_component_rich_style(f"casilla-list--{role}", partial=True)

    def _role_style(self: CasillaList, role: ColourRole) -> Style:
        return self._style(role.value)

    def _item_at_line(self: CasillaList, line: int) -> int | None:
        index = bisect_right(self._starts, line) - 1
        if index < 0 or index >= len(self._items) or line >= self._starts[index] + self._heights[index]:
            return None
        return index

    def _item_text(self: CasillaList, index: int, sub_line: int, width: int, *, focused: bool) -> Text:
        # A span-less Text drops its own style when rendered to segments, so
        # single-style lines are appended as one styled span.
        item = self._items[index]
        if index in self._tables:
            return self._table_line(index, sub_line)
        if isinstance(item, _models.CasillaListHeading):
            role = _values._heading_role(item)
            if item.row is not None:
                lines = wrap_words(self._stacked_label(item.row), width - _values._LEAD)
                return Text().append(
                    _values._fit(" " * _values._LEAD + lines[sub_line], width), style=self._style(role)
                )
            return Text().append(_values._fit(" " * (1 + 2 * item.level) + item.text, width), style=self._style(role))
        if isinstance(item, _models.CasillaListNote):
            return Text().append(_values._fit(" " * (3 + item.indent) + item.text, width), style=self._style("muted"))
        if isinstance(item, CasillaListRecords):
            text, role = self._records[index][sub_line]
            return Text().append(_values._fit(text, width), style=self._style(role))
        return self._entry_line(index, item, sub_line, width, focused=focused)

    def _table_line(self: CasillaList, index: int, sub_line: int) -> Text:
        """One line of a grid row drawn as its table: the column headings, or the row's label and cells."""
        row = self._tables[index]
        if sub_line < row.header_height:
            return self._table_heading_line(row, sub_line)
        return self._table_body_line(row, sub_line - row.header_height)

    def _table_heading_line(self: CasillaList, row: _models._TableRow, sub_line: int) -> Text:
        geometry = row.geometry
        text = Text()
        text.append(" " * (GRID_LEAD + geometry.label + 1))
        for column, heading in enumerate(geometry.header):
            offset = row.header_height - len(heading)
            words = heading[sub_line - offset] if sub_line >= offset else ""
            text.append((" " * GRID_GAP if column else "") + _values._right(words, geometry.widths[column]))
        text.stylize(self._style("subheading"))
        return text

    def _table_body_line(self: CasillaList, row: _models._TableRow, line: int) -> Text:
        cursor = self._cursor_index()
        here = cursor is not None and cursor in row.cells
        text = self._table_body_prefix(row, line, here)
        if line == 0:
            text.append(" ")
            for column, cell in enumerate(row.cells):
                if column:
                    text.append(" " * GRID_GAP)
                self._append_cell(text, row, column, cell, focused=here and cell == cursor)
        return text

    def _table_body_prefix(self: CasillaList, row: _models._TableRow, line: int, here: bool) -> Text:
        geometry = row.geometry
        text = Text()
        text.append(HERE_MARK.glyph if here and line == 0 else " ", style=self._style("staged") if here else Style())
        level = row.level if line == 0 else None
        text.append(
            " " if level is None else level.glyph,
            style=Style() if level is None else self._role_style(_values._LEVEL_ROLES[level.glyph]),
        )
        text.append(" ")
        label = row.labels[line] if line < len(row.labels) else ""
        text.append(_values._fit(label, geometry.label), style=self._style("subheading"))
        return text

    def _append_cell(
        self: CasillaList, text: Text, row: _models._TableRow, column: int, cell: int | None, *, focused: bool
    ) -> None:
        geometry = row.geometry
        width = geometry.widths[column]
        entry = None if cell is None else self._entry_at(cell)
        if entry is None:
            literal = row.literals[column] if column < len(row.literals) else None
            if literal is None:
                text.append(" " * width)
            else:
                text.append(_values._right(literal + "  ", width), style=self._style("muted"))
            return
        cursor = self._style("cursor") if focused else Style()
        text.append(" " * (width - cell_width(geometry.boxes[column], geometry.values[column])), style=cursor)
        attention = entry.attention
        text.append(
            ATTENTION_GLYPHS[attention] if attention is not None else " ",
            style=(self._role_style(ATTENTION_ROLES[attention]) if attention is not None else Style()) + cursor,
        )
        text.append(
            _values._right(_values._box_mark(entry.field), geometry.boxes[column]) + " ",
            style=self._style("box") + cursor,
        )
        role = ColourRole.STAGED if entry.staged_text is not None else entry.origin_role
        value = _values._right(_values.grid_value_text(entry, self._language), geometry.values[column])
        text.append(value, style=self._role_style(role) + cursor)
        text.append(" " + entry.origin_mark, style=self._role_style(entry.origin_role) + cursor)

    def _label(self: CasillaList, entry: _models.CasillaListEntry) -> str:
        field = entry.field
        label = entry.label or field.label.text
        if field.label.disclosure in _values._SPANISH_DISCLOSURES and self._language is not OutputLanguage.ES:
            return f"{label} {tr(_values._IN_SPANISH_LOCALE_KEY)}"
        return label

    def _entry_line(
        self: CasillaList, index: int, entry: _models.CasillaListEntry, sub_line: int, width: int, *, focused: bool
    ) -> Text:
        columns = self._columns(width)
        labels = self._label_lines(entry, columns)
        label_width = _values._label_width(entry, columns)
        if sub_line == 0:
            return self._entry_first_line(entry, columns, labels, label_width, focused=focused)
        return self._entry_wrapped_line(index, entry, columns, labels, label_width, sub_line, width)

    def _entry_first_line(
        self: CasillaList,
        entry: _models.CasillaListEntry,
        columns: _models._Columns,
        labels: tuple[str, ...],
        label_width: int,
        *,
        focused: bool,
    ) -> Text:
        field = entry.field
        attention = entry.attention
        text = Text()
        text.append(HERE_MARK.glyph if focused else " ", style=self._style("staged") if focused else Style())
        text.append(
            ATTENTION_GLYPHS[attention] if attention is not None else " ",
            style=self._role_style(ATTENTION_ROLES[attention]) if attention is not None else Style(),
        )
        text.append(" " + " " * entry.indent)
        text.append(_values._right(_values._box_mark(field), columns.box) + " ", style=self._style("box"))
        text.append(_values._fit(labels[0], label_width))
        role = ColourRole.STAGED if entry.staged_text is not None else entry.origin_role
        text.append(" " + _values._right(self._value(entry), columns.value), style=self._role_style(role))
        text.append(" " + entry.origin_mark, style=self._role_style(entry.origin_role))
        if columns.words:
            text.append(" " + _values._fit(entry.origin_words, columns.words), style=self._style("muted"))
        detail = self._detail(entry) if columns.detail else ""
        if detail:
            text.append(_values._SEPARATOR + _values._fit(detail, _values._DETAIL_WIDTH), style=self._style("muted"))
        return text

    def _entry_wrapped_line(
        self: CasillaList,
        index: int,
        entry: _models.CasillaListEntry,
        columns: _models._Columns,
        labels: tuple[str, ...],
        label_width: int,
        sub_line: int,
        width: int,
    ) -> Text:
        text = Text()
        text.append(" ")
        text.append(" " * (_values._LEAD - 1 + entry.indent + columns.box + 1))
        if sub_line < len(labels):
            text.append(_values._fit(labels[sub_line], label_width))
            return text
        note = self._note(index, entry, columns) or ""
        text.append(_values._fit(note, width - cell_len(text.plain)), style=self._style("muted"))
        return text

    def _detail(self: CasillaList, entry: _models.CasillaListEntry) -> str:
        if entry.previous_text is not None:
            return tr("tui.modelo.workbench.was", value=entry.previous_text)
        if entry.attention is Attention.BLOCKED:
            return tr(attention_words_key(Attention.BLOCKED))
        bindings = entry.field.bindings
        if bindings:
            return tr(bindings[0].policy.label_key)
        return ""
