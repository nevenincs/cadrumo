"""A virtual list of one page's casillas that renders only the lines on screen.

Mounting one widget per casilla costs seconds at the size of the largest
modelos, so a page is one widget that lays out each visible line on demand.
The cursor is held as a field's semantic address, never a position: rebuilding
the list after an edit, a refresh, a filter or a language switch keeps the same
casilla under the cursor when it is still there.

Each field line reads, left to right: the cursor mark, an attention mark (a
staged change or a verification blocker), the official box number, the label,
the value right-aligned, the origin glyph, and on wider terminals the origin in
words and a detail column. A second line carries the rest of a long label or
the first sentence of the help. Every mark comes from
:mod:`.vocabulary`, so the list never invents a state.

The list decides nothing. It posts a message naming the address the filer
acted on -- edit, clear, revert, show the source -- and the screen owning the
edit session answers it.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import ClassVar, Final, Literal, override

from rich.cells import cell_len
from rich.style import Style
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from .....application.modelo.value_presentation import (
    absent_value_text,
    format_casilla_value,
)
from .....application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormTextDisclosure,
    address_key,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.app_access import TypedAppAccess
from ...components.theme import tokenised
from .vocabulary import (
    ATTENTION_GLYPHS,
    ATTENTION_ROLES,
    NEEDS_ATTENTION,
    ORIGIN_GLYPHS,
    ORIGIN_ROLES,
    Attention,
    ColourRole,
    origin_words_key,
)

type AddressKey = tuple[str, str]

_BOX_WIDTH: Final[int] = 6
_VALUE_WIDTH: Final[int] = 18
_STATE_WIDTH: Final[int] = 28
_DETAIL_WIDTH: Final[int] = 32
_WIDE: Final[int] = 110
_WIDEST: Final[int] = 150
_PENDING_VALUE: Final[str] = "…"
_NOT_APPLICABLE_VALUE_KEY: Final[str] = "tui.modelo.workbench.value.not_applicable"


@dataclass(frozen=True, slots=True)
class CasillaListHeading:
    """A section or row heading line; never under the cursor."""

    text: str
    level: int = 0


@dataclass(frozen=True, slots=True)
class CasillaListNote:
    """An informational line, such as a value the official design fixes."""

    text: str
    indent: int = 0


@dataclass(frozen=True, slots=True)
class CasillaListEntry:
    """One field line, with any change the filer has staged but not applied."""

    field: ModeloFormField
    indent: int = 0
    label: str | None = None
    staged_text: str | None = None
    previous_text: str | None = None

    @property
    def key(self) -> AddressKey:
        """The field's semantic identity."""
        return address_key(self.field.address)

    @property
    def attention(self) -> Attention | None:
        """The mark that draws the eye: a staged change first, then a blocker."""
        if self.staged_text is not None:
            return Attention.STAGED
        if self.field.blockers:
            return Attention.BLOCKED
        return None


type CasillaListItem = CasillaListHeading | CasillaListNote | CasillaListEntry
type Density = Literal["comfortable", "compact"]


def _fit(text: str, width: int) -> str:
    """Pad or cut ``text`` to exactly ``width`` cells, marking a cut with an ellipsis."""
    if width <= 0:
        return ""
    if cell_len(text) <= width:
        return text + " " * (width - cell_len(text))
    cut = text
    while cell_len(cut) > width - 1:
        cut = cut[:-1]
    return cut + "…"


def _right(text: str, width: int) -> str:
    fitted = _fit(text, width).rstrip()
    return " " * (width - cell_len(fitted)) + fitted


def _split(text: str, width: int) -> tuple[str, str]:
    """Split a label at the last space that fits, keeping the rest for the second line."""
    if cell_len(text) <= width:
        return text, ""
    head = text[:width]
    cut = head.rfind(" ")
    if cut <= width // 3:
        cut = width
    return text[:cut].rstrip(), text[cut:].strip()


def value_text(entry: CasillaListEntry, language: OutputLanguage) -> str:
    """Return the text of a field's value cell, with absence spoken in words."""
    if entry.staged_text is not None:
        return entry.staged_text
    field = entry.field
    if field.origin is ModeloFormOrigin.NOT_APPLICABLE:
        return tr(_NOT_APPLICABLE_VALUE_KEY)
    if field.origin in {ModeloFormOrigin.NOT_CALCULATED_YET, ModeloFormOrigin.CALCULATION_FAILED}:
        return _PENDING_VALUE
    if field.value is None or field.origin in {ModeloFormOrigin.CLEARED, ModeloFormOrigin.NOT_IMPORTED_YET}:
        return absent_value_text(language)
    return format_casilla_value(field.value, data_type=field.data_type, language=language)


class CasillaList(TypedAppAccess, ScrollView, can_focus=True):
    """One page of casillas, rendered line by line, with the cursor held by address."""

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "casilla-list--cursor",
        "casilla-list--heading",
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
            color: $primary;
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
        Binding("up,k", "move(-1)", "", show=False),
        Binding("down,j", "move(1)", "", show=False),
        Binding("pageup", "page(-1)", "", show=False),
        Binding("pagedown", "page(1)", "", show=False),
        Binding("home", "ends(-1)", "", show=False),
        Binding("end", "ends(1)", "", show=False),
        Binding("enter", "edit", "", show=False),
        Binding("x,delete", "clear", "", show=False),
        Binding("u", "revert", "", show=False),
        Binding("n", "attention(1)", "", show=False),
        Binding("N", "attention(-1)", "", show=False),
        Binding("s", "source", "", show=False),
    ]

    class Highlighted(Message):
        """The cursor now rests on a field, or on nothing."""

        def __init__(self, entry: CasillaListEntry | None) -> None:
            """Carry the field now under the cursor."""
            super().__init__()
            self.entry = entry

    class _AddressMessage(Message):
        def __init__(self, entry: CasillaListEntry) -> None:
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
        items: tuple[CasillaListItem, ...] = (),
        *,
        language: OutputLanguage,
        density: Density = "comfortable",
        id: str | None = None,
    ) -> None:
        """Hold the page's items; lines are laid out when the width is known."""
        super().__init__(id=id)
        self._items: tuple[CasillaListItem, ...] = items
        self._language = language
        self._density: Density = density
        self._cursor: AddressKey | None = None
        self._starts: list[int] = []
        self._heights: list[int] = []
        self._laid_out_width = -1
        self._select_first_entry()

    # ── public surface ───────────────────────────────────────────────────

    @property
    def items(self) -> tuple[CasillaListItem, ...]:
        """The items currently shown."""
        return self._items

    @property
    def highlighted(self) -> CasillaListEntry | None:
        """The field under the cursor, if any."""
        index = self._cursor_index()
        return None if index is None else self._entry_at(index)

    @property
    def density(self) -> Density:
        """Whether fields take one line or two."""
        return self._density

    def set_items(self, items: tuple[CasillaListItem, ...], *, language: OutputLanguage | None = None) -> None:
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

    def set_density(self, density: Density) -> None:
        """Show fields on one line or two."""
        self._density = density
        self._laid_out_width = -1
        self._layout()
        self._scroll_to_cursor()
        self.refresh()

    def focus_address(self, key: AddressKey) -> bool:
        """Put the cursor on one address; ``False`` when this page does not show it."""
        for index, item in enumerate(self._items):
            if isinstance(item, CasillaListEntry) and item.key == key:
                self._move_cursor_to(index)
                return True
        return False

    # ── layout ───────────────────────────────────────────────────────────

    def _content_width(self) -> int:
        return max(self.scrollable_content_region.width, 20)

    def _height(self, item: CasillaListItem, width: int) -> int:
        if not isinstance(item, CasillaListEntry) or self._density == "compact":
            return 1
        return 2 if self._second_line(item, width) else 1

    def _layout(self) -> None:
        width = self._content_width()
        if width == self._laid_out_width and len(self._starts) == len(self._items):
            return
        self._laid_out_width = width
        starts: list[int] = []
        heights: list[int] = []
        line = 0
        for item in self._items:
            starts.append(line)
            height = self._height(item, width)
            heights.append(height)
            line += height
        self._starts = starts
        self._heights = heights
        self.virtual_size = Size(width, line)

    def on_resize(self, event: events.Resize) -> None:
        """Lay the lines out again for the new width and keep the cursor in view."""
        self._layout()
        self._scroll_to_cursor()

    # ── rendering ────────────────────────────────────────────────────────

    def _style(self, role: str) -> Style:
        return self.get_component_rich_style(f"casilla-list--{role}", partial=True)

    def _role_style(self, role: ColourRole) -> Style:
        return self._style(role.value)

    @override
    def render_line(self, y: int) -> Strip:
        self._layout()
        width = self._content_width()
        line = y + int(self.scroll_offset.y)
        index = bisect_right(self._starts, line) - 1
        if index < 0 or index >= len(self._items) or line >= self._starts[index] + self._heights[index]:
            return Strip.blank(width, self.rich_style)
        item = self._items[index]
        sub_line = line - self._starts[index]
        focused = index == self._cursor_index()
        text = self._item_text(item, sub_line, width, focused=focused)
        base = self.rich_style + (self._style("cursor") if focused else Style())
        return Strip(list(text.render(self.app.console))).adjust_cell_length(width, base).apply_style(base)

    def _item_text(self, item: CasillaListItem, sub_line: int, width: int, *, focused: bool) -> Text:
        if isinstance(item, CasillaListHeading):
            return Text(_fit(" " * (1 + 2 * item.level) + item.text, width), style=self._style("heading"))
        if isinstance(item, CasillaListNote):
            return Text(_fit(" " * (3 + item.indent) + item.text, width), style=self._style("muted"))
        return self._entry_line(item, sub_line, width, focused=focused)

    def _columns(self, width: int, indent: int) -> tuple[int, bool, bool]:
        wide = width >= _WIDE
        widest = width >= _WIDEST
        fixed = 3 + indent + _BOX_WIDTH + _VALUE_WIDTH + 2 + (_STATE_WIDTH + 1 if wide else 0)
        fixed += _DETAIL_WIDTH + 1 if widest else 0
        return max(width - fixed, 8), wide, widest

    def _label(self, entry: CasillaListEntry) -> str:
        field = entry.field
        label = entry.label or field.label.text
        if (
            field.label.disclosure
            in {
                ModeloFormTextDisclosure.SPANISH_FALLBACK,
                ModeloFormTextDisclosure.OFFICIAL_SPANISH,
            }
            and self._language is not OutputLanguage.ES
        ):
            return f"{label} (es)"
        return label

    def _second_line(self, entry: CasillaListEntry, width: int) -> str:
        label_width, wide, widest = self._columns(width, entry.indent)
        _, rest = _split(self._label(entry), label_width)
        if rest:
            return rest
        if entry.previous_text is not None and not widest:
            return tr("tui.modelo.workbench.was", value=entry.previous_text)
        if not wide:
            return " "
        help_text = entry.field.help
        if help_text:
            return help_text.split(". ")[0]
        return ""

    def _entry_line(self, entry: CasillaListEntry, sub_line: int, width: int, *, focused: bool) -> Text:
        field = entry.field
        label_width, wide, widest = self._columns(width, entry.indent)
        attention = entry.attention
        text = Text()
        text.append("▸" if focused and sub_line == 0 else " ", style=self._style("staged") if focused else Style())
        if sub_line == 0:
            text.append(
                ATTENTION_GLYPHS[attention] if attention is not None else " ",
                style=self._role_style(ATTENTION_ROLES[attention]) if attention is not None else Style(),
            )
            text.append(" " + " " * entry.indent)
            text.append(_right(f"[{field.box}]" if field.box else "·", _BOX_WIDTH - 1) + " ", style=self._style("box"))
            head, _ = _split(self._label(entry), label_width)
            text.append(_fit(head, label_width))
            role = ColourRole.STAGED if entry.staged_text is not None else ORIGIN_ROLES[field.origin]
            text.append(" " + _right(value_text(entry, self._language), _VALUE_WIDTH - 1), style=self._role_style(role))
            text.append(" " + ORIGIN_GLYPHS[field.origin], style=self._role_style(ORIGIN_ROLES[field.origin]))
            if wide:
                text.append(" " + _fit(tr(origin_words_key(field.origin)), _STATE_WIDTH), style=self._style("muted"))
            if widest:
                text.append(" " + _fit(self._detail(entry), _DETAIL_WIDTH), style=self._style("muted"))
            return text
        text.append(" " * (2 + entry.indent + _BOX_WIDTH))
        second = self._second_line(entry, width)
        if not wide:
            words = tr(origin_words_key(field.origin))
            if attention is not None:
                words = tr(f"tui.modelo.workbench.attention.{attention.value}")
            rest_width = max(width - cell_len(text.plain) - 1, 0)
            words_width = min(cell_len(words), max(rest_width // 2, 12))
            text.append(_fit(second.strip(), rest_width - words_width - 1), style=self._style("muted"))
            text.append(" " + _right(words, words_width), style=self._role_style(ORIGIN_ROLES[field.origin]))
            return text
        text.append(_fit(second, label_width), style=self._style("muted"))
        return text

    def _detail(self, entry: CasillaListEntry) -> str:
        if entry.previous_text is not None:
            return tr("tui.modelo.workbench.was", value=entry.previous_text)
        if entry.field.blockers:
            return tr("tui.modelo.workbench.attention.blocked")
        bindings = entry.field.bindings
        if bindings:
            return tr(bindings[0].policy.label_key)
        return ""

    # ── cursor ───────────────────────────────────────────────────────────

    def _entry_at(self, index: int) -> CasillaListEntry | None:
        item = self._items[index] if 0 <= index < len(self._items) else None
        return item if isinstance(item, CasillaListEntry) else None

    def _cursor_index(self) -> int | None:
        if self._cursor is None:
            return None
        for index, item in enumerate(self._items):
            if isinstance(item, CasillaListEntry) and item.key == self._cursor:
                return index
        return None

    def _select_first_entry(self) -> None:
        first = next((item for item in self._items if isinstance(item, CasillaListEntry)), None)
        self._cursor = None if first is None else first.key

    def _move_cursor_to(self, index: int) -> None:
        entry = self._entry_at(index)
        if entry is None:
            return
        self._cursor = entry.key
        self._scroll_to_cursor()
        self.refresh()
        self.post_message(self.Highlighted(entry))

    def _scroll_to_cursor(self) -> None:
        index = self._cursor_index()
        if index is None or not self._starts or index >= len(self._starts):
            return
        top = self._starts[index]
        bottom = top + self._heights[index]
        view_top = int(self.scroll_offset.y)
        view_height = max(self.scrollable_content_region.height, 1)
        if top < view_top:
            self.scroll_to(y=max(top - 1, 0), animate=False)
        elif bottom > view_top + view_height:
            self.scroll_to(y=bottom - view_height, animate=False)

    def _step(self, start: int, delta: int) -> int | None:
        index = start + delta
        while 0 <= index < len(self._items):
            if isinstance(self._items[index], CasillaListEntry):
                return index
            index += delta
        return None

    def action_move(self, delta: int) -> None:
        """Move the cursor to the next or previous field."""
        current = self._cursor_index()
        target = self._step(-1 if current is None else current, delta)
        if target is not None:
            self._move_cursor_to(target)

    def action_page(self, direction: int) -> None:
        """Move the cursor about one screen of lines."""
        current = self._cursor_index()
        if current is None:
            return
        remaining = max(self.scrollable_content_region.height - 2, 1)
        target = current
        while remaining > 0:
            following = self._step(target, direction)
            if following is None:
                break
            remaining -= self._heights[following] if following < len(self._heights) else 1
            target = following
        self._move_cursor_to(target)

    def action_ends(self, direction: int) -> None:
        """Move the cursor to the first or last field."""
        target = self._step(-1, 1) if direction < 0 else self._step(len(self._items), -1)
        if target is not None:
            self._move_cursor_to(target)

    def action_attention(self, direction: int) -> None:
        """Move to the next or previous field that needs the filer, a staged change or a blocker."""
        current = self._cursor_index()
        index = -1 if current is None else current
        while True:
            following = self._step(index, direction)
            if following is None:
                return
            entry = self._entry_at(following)
            if entry is not None and (entry.attention is not None or entry.field.origin in NEEDS_ATTENTION):
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
        """Put the cursor on the clicked field; a double click edits it."""
        self._layout()
        line = event.y + int(self.scroll_offset.y)
        index = bisect_right(self._starts, line) - 1
        if self._entry_at(index) is None:
            return
        self._move_cursor_to(index)
        if event.chain >= 2:
            self.action_edit()


__all__ = [
    "AddressKey",
    "CasillaList",
    "CasillaListEntry",
    "CasillaListHeading",
    "CasillaListItem",
    "CasillaListNote",
    "Density",
    "value_text",
]
