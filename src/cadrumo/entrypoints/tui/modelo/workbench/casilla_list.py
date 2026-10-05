"""A virtual list of one page's casillas that renders only the lines on screen.

Mounting one widget per casilla costs seconds at the size of the largest
modelos, so a page is one widget that lays out each visible line on demand.
The cursor is held as a field's semantic address, never a position: rebuilding
the list after an edit, a refresh, a filter or a language switch keeps the same
casilla under the cursor when it is still there.

Each field reads, left to right: the cursor mark, an attention mark (a staged
change or a verification blocker), the official box number, the label, the
value right-aligned with its unit, the origin glyph, and where they fit the
origin in words and a detail column. Every column is measured from the lines
being shown: the box column is as wide as the widest box number, so a number is
never cut, and the label column no wider than the longest label nor than sixty
cells, so the value and its origin sit next to the words they belong to and a
wide terminal leaves the rest of the line empty. Headings carry the strongest
weight and descriptions the weakest. A label too long for its
column wraps onto further lines and is never cut; only the one optional line
under it, the start of the box's description, may be. Every mark comes from
:mod:`.vocabulary`, so the list never invents a state.

An official grid is drawn as the paper form draws it, its rows down the side
and its columns across, when the table fits the width; the cursor then moves
from cell to cell, and the row's left edge carries the most severe mark among
its cells. A grid too wide for the width is stacked instead, each row under a
heading that tells it apart from its neighbours. The records of a repeating
group are a read-only table with an index column.

The list decides nothing. It posts a message naming the address the filer
acted on -- edit, clear, revert, show the source -- and the screen owning the
edit session answers it.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import ClassVar, override

from rich.style import Style
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from .....core.external_constants import OutputLanguage
from ...components.app_access import TypedAppAccess
from ...components.theme import tokenised
from . import casilla_list_models as _models
from . import casilla_list_values as _values
from .casilla_list_layout import CasillaListLayoutMixin
from .casilla_list_navigation import CasillaListNavigationMixin
from .casilla_list_rendering import CasillaListRenderingMixin
from .grid import (
    CasillaListRecords,
)
from .keys import describe_bindings


class CasillaList(
    CasillaListLayoutMixin,
    CasillaListRenderingMixin,
    CasillaListNavigationMixin,
    TypedAppAccess,
    ScrollView,
    can_focus=True,
):
    """One page of casillas, rendered line by line, with the cursor held by address."""

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "casilla-list--cursor",
        "casilla-list--heading",
        "casilla-list--heading-warning",
        "casilla-list--heading-error",
        "casilla-list--subheading",
        "casilla-list--box",
        "casilla-list--muted",
        "casilla-list--value",
        "casilla-list--entered",
        "casilla-list--warning",
        "casilla-list--error",
        "casilla-list--staged",
    }

    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        CasillaList {
            height: 1fr;
            background: $background;
            scrollbar-size-vertical: $cadrumo-scrollbar;
        }
        CasillaList > .casilla-list--cursor {
            background: $surface;
        }
        CasillaList:focus > .casilla-list--cursor {
            background: $panel;
            text-style: bold;
        }
        CasillaList > .casilla-list--heading {
            color: $foreground;
            text-style: bold underline;
        }
        CasillaList > .casilla-list--heading-warning {
            color: $warning;
            text-style: bold underline;
        }
        CasillaList > .casilla-list--heading-error {
            color: $error;
            text-style: bold underline;
        }
        CasillaList > .casilla-list--subheading {
            color: $foreground;
            text-style: bold;
        }
        CasillaList > .casilla-list--box {
            color: $secondary;
        }
        CasillaList > .casilla-list--muted {
            color: $secondary;
        }
        CasillaList > .casilla-list--value {
            color: $foreground;
        }
        CasillaList > .casilla-list--entered {
            color: $success;
        }
        CasillaList > .casilla-list--warning {
            color: $warning;
        }
        CasillaList > .casilla-list--error {
            color: $error;
            text-style: bold;
        }
        CasillaList > .casilla-list--staged {
            color: $accent;
            text-style: bold;
        }
        """
    )

    BINDINGS: ClassVar = [
        Binding("up,k", "move(-1)", "", show=False, key_display="↑↓"),
        Binding("down,j", "move(1)", "", show=False),
        Binding("pageup", "page(-1)", "", show=False),
        Binding("pagedown", "page(1)", "", show=False),
        Binding("home", "ends(-1)", "", show=False),
        Binding("end", "ends(1)", "", show=False),
        # Only while the cursor is on a table's row; elsewhere these keys fall through to the screen.
        Binding("left,h", "cell(-1)", "", show=False),
        Binding("right,l", "cell(1)", "", show=False),
        Binding("enter", "edit", "", show=False),
        Binding("x,delete", "clear", "", show=False),
        Binding("u", "revert", "", show=False),
        Binding("n", "attention(1)", "", show=False),
        Binding("N", "attention(-1)", "", show=False),
        Binding("s", "source", "", show=False),
    ]

    class Highlighted(Message):
        """The cursor now rests on a field, or on nothing."""

        def __init__(self, entry: _models.CasillaListEntry | None) -> None:
            """Carry the field now under the cursor."""
            super().__init__()
            self.entry = entry

    class _AddressMessage(Message):
        def __init__(self, entry: _models.CasillaListEntry) -> None:
            """Carry the field the filer acted on."""
            super().__init__()
            self.entry = entry

    class EditRequested(_AddressMessage):
        """The filer asked to edit the field under the cursor."""

    class ClearRequested(_AddressMessage):
        """The filer asked to clear the field under the cursor."""

    class RevertRequested(_AddressMessage):
        """The filer asked to undo the change staged on the field under the cursor."""

    class SourceRequested(_AddressMessage):
        """The filer asked where the value under the cursor comes from."""

    def __init__(
        self,
        items: tuple[_models.CasillaListItem, ...] = (),
        *,
        language: OutputLanguage,
        density: _models.Density = "comfortable",
        id: str | None = None,
    ) -> None:
        """Hold the page's items; lines are laid out when the width is known."""
        super().__init__(id=id)
        self._items: tuple[_models.CasillaListItem, ...] = items
        self._language = language
        self._density: _models.Density = density
        self._cursor: _models.AddressKey | None = None
        #: Rows after the cursor's field kept in view when the list scrolls down to it.
        self._following = 0
        #: The grid column the cursor keeps while it moves up and down through a table.
        self._column: int | None = None
        self._starts: list[int] = []
        self._heights: list[int] = []
        self._owner: list[int] = []
        self._tables: dict[int, _models._TableRow] = {}
        self._cell_of: dict[int, tuple[int, int]] = {}
        self._stacked: frozenset[int] = frozenset()
        self._records: dict[int, tuple[tuple[str, str], ...]] = {}
        self._laid_out_width = -1
        self._measures = self._measure(frozenset())
        self._select_first_entry()

    # ── public surface ───────────────────────────────────────────────────

    @property
    def items(self) -> tuple[_models.CasillaListItem, ...]:
        """The items currently shown."""
        return self._items

    @property
    def highlighted(self) -> _models.CasillaListEntry | None:
        """The field under the cursor, if any."""
        index = self._cursor_index()
        return None if index is None else self._entry_at(index)

    @property
    def on_grid_row(self) -> bool:
        """Whether the cursor rests on a cell of a grid drawn as a table, where the side arrows move between cells."""
        self._layout()
        index = self._cursor_index()
        return index is not None and index in self._cell_of

    @property
    def density(self) -> _models.Density:
        """Whether fields take one line or two."""
        return self._density

    def set_items(self, items: tuple[_models.CasillaListItem, ...], *, language: OutputLanguage | None = None) -> None:
        """Replace the items, keeping the cursor on the same address when it is still shown."""
        self._items = items
        if language is not None:
            self._language = language
        if self._cursor_index() is None:
            self._select_first_entry()
        self._laid_out_width = -1
        self._layout()
        self._scroll_to_cursor()
        self.refresh()
        self.post_message(self.Highlighted(self.highlighted))

    def set_density(self, density: _models.Density) -> None:
        """Show fields on one line or two."""
        self._density = density
        self._laid_out_width = -1
        self._layout()
        self._scroll_to_cursor()
        self.refresh()

    def describe_keys(self, descriptions: Mapping[str, str], *, shown: Collection[str] | None = None) -> None:
        """Describe this list's own keys in the language now on screen, showing ``shown`` in the footer."""
        describe_bindings(self._bindings.key_to_bindings, descriptions, shown=shown)
        self.refresh_bindings()

    def binding_for(self, key: str) -> Binding | None:
        """The binding this list declares for ``key``, if any."""
        bindings = self._bindings.key_to_bindings.get(key)
        return bindings[0] if bindings else None

    def focus_address(self, key: _models.AddressKey) -> bool:
        """Put the cursor on one address, or bring the table of records showing it into view.

        A column of a repeating group's records is no field the cursor rests
        on, so a casilla one of its columns shows scrolls to the group's
        records heading, or to the note standing in for records whose number
        is unknown. ``False`` when this page shows the address nowhere.
        """
        for index, item in enumerate(self._items):
            if isinstance(item, _models.CasillaListEntry) and item.key == key:
                self._move_cursor_to(index)
                return True
        records = self._records_showing(key)
        if records is None:
            return False
        self._layout()
        if records < len(self._starts):
            self.scroll_to(y=max(self._starts[records] - 1, 0), animate=False)
        self.refresh()
        return True

    def _records_showing(self, key: _models.AddressKey) -> int | None:
        """The line a group's records start at, when one of its columns shows the casilla ``key`` names."""
        kind, identifier = key
        if kind != _values._CASILLA_KIND:
            return None
        for index, item in enumerate(self._items):
            if isinstance(item, CasillaListRecords | _models.CasillaListNote) and identifier in item.column_casilla_ids:
                heading = index - 1
                before = self._items[heading] if heading >= 0 else None
                return heading if isinstance(before, _models.CasillaListHeading) else index
        return None

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Take the side arrows only on a table's row, so elsewhere they reach the screen's own keys."""
        if action == "cell":
            return self.on_grid_row
        return True

    # ── layout ───────────────────────────────────────────────────────────

    def on_resize(self, event: events.Resize) -> None:
        """Lay the lines out again for the new width and keep the cursor in view."""
        self._layout()
        self._scroll_to_cursor()

    # ── rendering ────────────────────────────────────────────────────────

    @override
    def render_line(self, y: int) -> Strip:
        self._layout()
        width = self._content_width()
        line = y + int(self.scroll_offset.y)
        index = self._item_at_line(line)
        if index is None:
            return Strip.blank(width, self.rich_style)
        sub_line = line - self._starts[index]
        focused = index == self._cursor_index() and index not in self._cell_of
        text = self._item_text(index, sub_line, width, focused=focused)
        base = self.rich_style + (self._style("cursor") if focused else Style())
        return Strip(list(text.render(self.app.console))).adjust_cell_length(width, base).apply_style(base)

    # ── cursor ───────────────────────────────────────────────────────────

    def action_move(self, delta: int) -> None:
        """Move among fields, or scroll a read-only view without selectable fields."""
        stops, position, column = self._current_stop()
        if not stops:
            self.scroll_to(y=self.scroll_y + delta, animate=False)
            return
        target = (0 if delta > 0 else len(stops) - 1) if position is None else position + delta
        if 0 <= target < len(stops):
            self._go_to_stop(stops[target], column)

    def action_cell(self, delta: int) -> None:
        """Move to the previous or next cell of a table's row, stopping at its edge."""
        self._layout()
        current = self._cursor_index()
        if current is None or current not in self._cell_of:
            return
        heading, column = self._cell_of[current]
        row = self._tables[heading]
        following = [candidate for candidate in row.focusable() if (candidate - column) * delta > 0]
        if not following:
            return
        target = min(following, key=lambda candidate: abs(candidate - column))
        cell = row.cells[target]
        if cell is not None:
            self._move_cursor_to(cell, column=target)

    def action_page(self, direction: int) -> None:
        """Move the cursor about one screen, or scroll read-only content by that distance."""
        stops, position, column = self._current_stop()
        remaining = max(self.scrollable_content_region.height - 2, 1)
        if not stops:
            self.scroll_to(y=self.scroll_y + direction * remaining, animate=False)
            return
        if position is None:
            return
        target = position
        while remaining > 0 and 0 <= target + direction < len(stops):
            target += direction
            remaining -= max(self._heights[stops[target]], 1)
        self._go_to_stop(stops[target], column)

    def action_ends(self, direction: int) -> None:
        """Move to an end field or cell; a view without fields scrolls to its content's start or end."""
        self._layout()
        if not self._stops():
            self.scroll_to(y=0 if direction < 0 else self.max_scroll_y, animate=False)
            return
        current = self._cursor_index()
        if current is not None and current in self._cell_of:
            row = self._tables[self._cell_of[current][0]]
            focusable = row.focusable()
            column = focusable[0] if direction < 0 else focusable[-1]
            cell = row.cells[column]
            if cell is not None:
                self._move_cursor_to(cell, column=column)
            return
        target = self._step(-1, 1) if direction < 0 else self._step(len(self._items), -1)
        if target is not None:
            self._move_cursor_to(target)

    def action_attention(self, direction: int) -> None:
        """Move to the next or previous field that needs the filer, a staged change or a blocker.

        A table's cells are visited row by row, left to right.
        """
        current = self._cursor_index()
        index = -1 if current is None else current
        while True:
            following = self._step(index, direction)
            if following is None:
                return
            entry = self._entry_at(following)
            if entry is not None and entry.needs_filer:
                self._move_cursor_to(following)
                return
            index = following

    def _post_for_highlighted(self, message: type[CasillaList._AddressMessage]) -> None:
        entry = self.highlighted
        if entry is not None:
            self.post_message(message(entry))

    def action_edit(self) -> None:
        """Ask to edit the field under the cursor."""
        self._post_for_highlighted(self.EditRequested)

    def action_clear(self) -> None:
        """Ask to clear the field under the cursor."""
        self._post_for_highlighted(self.ClearRequested)

    def action_revert(self) -> None:
        """Ask to undo the change staged on the field under the cursor."""
        self._post_for_highlighted(self.RevertRequested)

    def action_source(self) -> None:
        """Ask where the value under the cursor comes from."""
        self._post_for_highlighted(self.SourceRequested)

    def on_click(self, event: events.Click) -> None:
        """Put the cursor on the clicked field or table cell; a double click edits it."""
        self._layout()
        index = self._item_at_line(event.y + int(self.scroll_offset.y))
        if index is None:
            return
        row = self._tables.get(index)
        if row is not None:
            column = row.geometry.column_at(event.x)
            self._go_to_stop(index, 0 if column is None else column)
        elif self._entry_at(index) is not None:
            self._move_cursor_to(index)
        else:
            return
        if event.chain >= 2:
            self.action_edit()


__all__ = ["CasillaList"]
