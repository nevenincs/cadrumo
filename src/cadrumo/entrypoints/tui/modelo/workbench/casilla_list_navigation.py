"""Address-based cursor movement for the virtual casilla list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import casilla_list_models as _models
from . import casilla_list_values as _values

if TYPE_CHECKING:
    from .casilla_list import CasillaList


class CasillaListNavigationMixin:
    """Address-based cursor movement for the virtual casilla list."""

    def _entry_at(self: CasillaList, index: int) -> _models.CasillaListEntry | None:
        item = self._items[index] if 0 <= index < len(self._items) else None
        return item if isinstance(item, _models.CasillaListEntry) else None

    def _cursor_index(self: CasillaList) -> int | None:
        if self._cursor is None:
            return None
        for index, item in enumerate(self._items):
            if isinstance(item, _models.CasillaListEntry) and item.key == self._cursor:
                return index
        return None

    def _select_first_entry(self: CasillaList) -> None:
        first = next((item for item in self._items if isinstance(item, _models.CasillaListEntry)), None)
        self._cursor = None if first is None else first.key

    def _move_cursor_to(self: CasillaList, index: int, *, column: int | None = None) -> None:
        """Rest the cursor on the field at ``index``; in a table, ``column`` is the column to keep moving in."""
        entry = self._entry_at(index)
        if entry is None:
            return
        self._cursor = entry.key
        self._layout()
        cell = self._cell_of.get(index)
        self._column = None if cell is None else (cell[1] if column is None else column)
        self._scroll_to_cursor()
        self.refresh()
        self.post_message(self.Highlighted(entry))

    def _owner_of(self: CasillaList, index: int) -> int:
        return self._owner[index] if 0 <= index < len(self._owner) else index

    def _scroll_to_cursor(self: CasillaList) -> None:
        index = self._cursor_index()
        if index is None or not self._starts or index >= len(self._starts):
            return
        owner = self._owner_of(index)
        top = self._starts[owner]
        bottom = top + self._heights[owner]
        view_top = int(self.scroll_offset.y)
        view_height = max(self.scrollable_content_region.height, 1)
        following = self._following if view_height >= _values.FOLLOWING_MIN_VIEW else 0
        if top < view_top:
            self.scroll_to(y=max(top - 1, 0), animate=False)
        elif bottom + following > view_top + view_height:
            self.scroll_to(y=bottom + following - view_height, animate=False)

    def reveal_highlighted(self: CasillaList) -> None:
        """Reveal the current field again after its surrounding layout has settled."""
        self._layout()
        self._scroll_to_cursor()
        self.refresh()

    def keep_following(self: CasillaList, lines: int) -> None:
        """Keep ``lines`` rows after the cursor's field in view whenever the list scrolls down to it, or ``0`` for none.

        The list keeps them itself, every time it brings the field into view,
        so no resize or refill can leave the field on the last line again; it
        gives them only while it shows at least :data:`FOLLOWING_MIN_VIEW` lines,
        so the field itself always stays in view.
        """
        self._following = max(lines, 0)
        self._scroll_to_cursor()

    def _step(self: CasillaList, start: int, delta: int) -> int | None:
        index = start + delta
        while 0 <= index < len(self._items):
            if isinstance(self._items[index], _models.CasillaListEntry):
                return index
            index += delta
        return None

    def _stops(self: CasillaList) -> list[int]:
        """Where the cursor can rest moving up and down, in line order: each field, and each table row with a box."""
        stops: list[int] = []
        for index, item in enumerate(self._items):
            if index in self._tables:
                if self._tables[index].focusable():
                    stops.append(index)
            elif isinstance(item, _models.CasillaListEntry) and index not in self._cell_of:
                stops.append(index)
        return stops

    def _land(self: CasillaList, stop: int, column: int | None) -> int:
        """The field to rest on at a stop: a table row's cell nearest ``column``, skipping empty slots."""
        row = self._tables.get(stop)
        if row is None:
            return stop
        focusable = row.focusable()
        wanted = focusable[0] if column is None else column
        nearest = min(focusable, key=lambda candidate: (abs(candidate - wanted), candidate))
        cell = row.cells[nearest]
        return stop if cell is None else cell

    def _go_to_stop(self: CasillaList, stop: int, column: int | None) -> None:
        target = self._land(stop, column)
        self._move_cursor_to(target, column=column if stop in self._tables else None)

    def _current_stop(self: CasillaList) -> tuple[list[int], int | None, int | None]:
        """The stops, the position of the cursor's among them, and the column the cursor keeps."""
        self._layout()
        stops = self._stops()
        current = self._cursor_index()
        if current is None:
            return stops, None, None
        stop = self._owner_of(current)
        column = self._column
        if column is None and current in self._cell_of:
            column = self._cell_of[current][1]
        return stops, (stops.index(stop) if stop in stops else None), column
