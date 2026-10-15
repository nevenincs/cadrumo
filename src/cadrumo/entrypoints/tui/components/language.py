"""Retain canonical message identities for mounted, stateful TUI controls."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from weakref import WeakKeyDictionary

from textual.widget import Widget
from textual.widgets import Button, DataTable, Input, Static

from ....core.i18n.render import tr

_COPY: WeakKeyDictionary[Widget, tuple[str, dict[str, object], str]] = WeakKeyDictionary()


def localized[W: Static | Button | Input](widget: W, key: str, /, **values: object) -> W:
    """Remember a catalogue key beside a widget without changing its identity.

    Translation still belongs to ``tr``. Only canonical keys and interpolation
    data are retained, never a parallel table of translated strings.
    """
    _COPY[widget] = (key, values, tr(key, **values))
    return widget


def refresh_localized_widgets(scope: Widget) -> None:
    """Reword unchanged authored copy, preserving controls and all their state.

    A status line replaced after composition belongs to its screen's renderer;
    its original placeholder must not overwrite newer operation information.
    """
    for widget in scope.walk_children(Widget):
        held = _COPY.get(widget)
        if held is None:
            continue
        key, values, previous = held
        current = (
            str(widget.label)
            if isinstance(widget, Button)
            else widget.placeholder
            if isinstance(widget, Input)
            else str(cast(Static, widget).content)
        )
        if current != previous:
            continue
        text = tr(key, **values)
        if isinstance(widget, Button):
            widget.label = text
        elif isinstance(widget, Input):
            widget.placeholder = text
        elif isinstance(widget, Static):
            widget.update(text)
        _COPY[widget] = (key, values, text)


def repaint_tables(scope: Widget, paint: Callable[[], None]) -> None:
    """Repaint projection tables while retaining semantic cursors and focus."""
    tables = tuple(scope.query(DataTable))
    positions = {
        table: (
            table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value if table.row_count else None,
            table.scroll_offset,
            table.cursor_row,
        )
        for table in tables
    }
    focused = scope.screen.focused
    for table in tables:
        table.clear(columns=True)
    paint()
    for table, (key, scroll, previous_row) in positions.items():
        row = next((index for index, item in enumerate(table.ordered_rows) if item.key.value == key), None)
        if row is not None or table.row_count:
            table.move_cursor(
                row=row if row is not None else min(previous_row, table.row_count - 1), animate=False, scroll=False
            )
        table.scroll_to(scroll.x, scroll.y, animate=False, force=True)
    scope.screen.set_focus(focused, scroll_visible=False)
    scope.call_after_refresh(scope.screen.set_focus, focused, scroll_visible=False)
