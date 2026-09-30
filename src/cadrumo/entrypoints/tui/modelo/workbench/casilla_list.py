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

The list decides nothing. It posts a message naming the address the filer
acted on -- edit, clear, revert, show the source -- and the screen owning the
edit session answers it.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from types import MappingProxyType
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

from .....application.modelo.edit_value_grammar import ModeloEditRatioUnit, ratio_unit
from .....application.modelo.value_presentation import (
    absent_value_text,
    format_casilla_value,
)
from .....application.modelo.work_form_models import (
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormRate,
    ModeloFormRateUnit,
    ModeloFormTextDisclosure,
    address_key,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.app_access import TypedAppAccess
from ...components.theme import tokenised
from .keys import describe_bindings
from .vocabulary import (
    ATTENTION_GLYPHS,
    ATTENTION_ROLES,
    HERE_MARK,
    NEEDS_ATTENTION,
    ORIGIN_ROLES,
    Attention,
    ColourRole,
    attention_words_key,
    origin_glyph,
    origin_words,
)

type AddressKey = tuple[str, str]

#: The cursor mark, the attention mark and the space after them.
_LEAD: Final[int] = 3
#: The widest value a column makes room for: the widest money figure, ``−99.999.999,99 €``, is 16 cells.
_VALUE_CAP: Final[int] = 17
_DETAIL_WIDTH: Final[int] = 32
_WIDEST: Final[int] = 150
#: The label keeps at least this much room before a value gives up any of its own.
_LABEL_FLOOR: Final[int] = 8
#: The label column is never wider than this, so on a wide terminal the value stays beside its label.
_LABEL_CAP: Final[int] = 60
_NO_BOX: Final[str] = "·"
_PENDING_VALUE: Final[str] = "…"
_EMPTY_VALUE: Final[str] = "·"
_RATIO_DATA_TYPE: Final[str] = "ratio"
_ABSENT_BY_ORIGIN: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {
        ModeloFormOrigin.NOT_APPLICABLE,
        ModeloFormOrigin.NOT_CALCULATED_YET,
        ModeloFormOrigin.CALCULATION_FAILED,
        ModeloFormOrigin.NOT_IMPORTED_YET,
        ModeloFormOrigin.CLEARED,
    }
)
"""Origins whose words say there is no value, whatever the field still holds."""
_ABSENT_WHEN_NONE: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.OPTIONAL_EMPTY, ModeloFormOrigin.NEEDS_INPUT}
)
"""Origins whose words say there is no value only when the field holds none; a held zero is still shown."""
_NOT_APPLICABLE_VALUE_KEY: Final[str] = "tui.modelo.workbench.value.not_applicable"
_FIXED_BY_DESIGN_VALUE_KEY: Final[str] = "tui.modelo.workbench.value.fixed_by_design"
_IN_SPANISH_LOCALE_KEY: Final[str] = "tui.modelo.workbench.in_spanish"
_RATE_NOT_GROUNDED_KEY: Final[str] = "tui.modelo.workbench.rate.not_grounded"
_RATE_UNITS: Final[Mapping[ModeloFormRateUnit, ModeloEditRatioUnit]] = MappingProxyType(
    {ModeloFormRateUnit.FRACTION: ModeloEditRatioUnit.FRACTION}
)
"""How each unit a grounded rate is stated in reads as a percentage."""
_SPANISH_DISCLOSURES: Final[frozenset[ModeloFormTextDisclosure]] = frozenset(
    {ModeloFormTextDisclosure.SPANISH_FALLBACK, ModeloFormTextDisclosure.OFFICIAL_SPANISH}
)
_BOX_PREFIXES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^(?:Box|Casilla|Casella)\s+\d[\w.-]*\s*:\s*"),
    re.compile(r"^\d[\w-]*\.\s+mező\s*:\s*"),
)
"""A description that opens by naming its box, in each language the catalogue writes: the row already shows it."""
_BREAKABLE_SPACE: Final[re.Pattern[str]] = re.compile(r"[^\S\u00a0]+")
"""Where a label may break: any space except a no-break space, which holds "art. 71" or "1 000" together."""


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
    #: The one rate box of an official row, which prints the rate the row's base is taxed at.
    rate_of_row: bool = False

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


@dataclass(frozen=True, slots=True)
class _Measures:
    """The widest box number, label, value and origin words among the fields shown, in cells."""

    box: int = 1
    label: int = 0
    value: int = 1
    words: int = 0


@dataclass(frozen=True, slots=True)
class _Columns:
    """The cells each column gets at one width; ``label`` is an unindented field's."""

    box: int
    label: int
    value: int
    words: int
    detail: bool


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


def _wrap(text: str, width: int) -> tuple[str, ...]:
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


def description_text(field: ModeloFormField) -> str | None:
    """A field's description as a person reads it, without an opening that only names its box."""
    text = field.help
    if not text:
        return None
    for prefix in _BOX_PREFIXES:
        stripped = prefix.sub("", text.strip(), count=1)
        if stripped != text.strip():
            return stripped[:1].upper() + stripped[1:] if stripped else None
    return text


def _label_width(entry: CasillaListEntry, columns: _Columns) -> int:
    """The cells an entry's label gets: the label column less its indent, so every value lines up."""
    return max(columns.label - entry.indent, 1)


def _box_mark(field: ModeloFormField) -> str:
    return f"[{field.box}]" if field.box else _NO_BOX


def value_text(entry: CasillaListEntry, language: OutputLanguage) -> str:
    """Return the text of a field's value cell, with absence spoken in words."""
    if entry.staged_text is not None:
        return entry.staged_text
    field = entry.field
    if field.origin is ModeloFormOrigin.NOT_APPLICABLE:
        return tr(_NOT_APPLICABLE_VALUE_KEY)
    if field.grounded_rate is not None:
        return rate_text(field.grounded_rate, language)
    if field.editability is ModeloFormEditability.DESIGN_CONSTANT and field.value is None:
        # A rate the form leaves to the filer's own operations is not fixed,
        # so only a box that is not a rate says the design fixes it.
        if field.data_type == _RATIO_DATA_TYPE:
            return absent_value_text(language)
        return tr(_FIXED_BY_DESIGN_VALUE_KEY)
    if field.origin in {ModeloFormOrigin.NOT_CALCULATED_YET, ModeloFormOrigin.CALCULATION_FAILED}:
        return _PENDING_VALUE
    if field.value is None or field.origin in {ModeloFormOrigin.CLEARED, ModeloFormOrigin.NOT_IMPORTED_YET}:
        return absent_value_text(language)
    maximum = field.constraints.max_value if field.constraints is not None else None
    return format_casilla_value(
        field.value, data_type=field.data_type, language=language, ratio_unit=ratio_unit(field.data_type, maximum)
    )


def rate_text(rate: ModeloFormRate, language: OutputLanguage) -> str:
    """Return a grounded rate as the printed form states it, a percentage in the filer's language."""
    return format_casilla_value(
        rate.ratio, data_type=_RATIO_DATA_TYPE, language=language, ratio_unit=_RATE_UNITS[rate.unit]
    )


def _ungrounded_rate(entry: CasillaListEntry) -> bool:
    """Whether an entry is a row's rate box that holds no value and has no rate Cadrumo grounded."""
    field = entry.field
    return entry.rate_of_row and field.grounded_rate is None and field.value is None


def rate_note(entry: CasillaListEntry) -> str | None:
    """Say why a row's rate box shows no rate, or ``None`` for any other box."""
    return tr(_RATE_NOT_GROUNDED_KEY) if _ungrounded_rate(entry) else None


def _origin_says_absence(field: ModeloFormField) -> bool:
    """Whether a field's origin words already say its value is not there."""
    if field.origin in _ABSENT_BY_ORIGIN:
        return True
    return field.value is None and field.origin in _ABSENT_WHEN_NONE


def row_value_text(entry: CasillaListEntry, language: OutputLanguage) -> str:
    """Return the value cell of a row, where an origin that says the value is absent leaves only a dot.

    The row's origin column says the absence in words, so the value column
    does not say it a second time. A row's rate box shows the rate its base is
    grounded on, or only a dot when there is none, since claiming a rate the
    row does not ground would be a fact nobody established. Every other
    surface, which shows the value without the origin words beside it, uses
    :func:`value_text`.
    """
    field = entry.field
    showing_rate = field.grounded_rate is not None and field.origin is not ModeloFormOrigin.NOT_APPLICABLE
    if entry.staged_text is not None or showing_rate:
        return value_text(entry, language)
    if _ungrounded_rate(entry) or _origin_says_absence(field):
        return _EMPTY_VALUE
    return value_text(entry, language)


class CasillaList(TypedAppAccess, ScrollView, can_focus=True):
    """One page of casillas, rendered line by line, with the cursor held by address."""

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "casilla-list--cursor",
        "casilla-list--heading",
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
        self._measures = self._measure()
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
        self._measures = self._measure()
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

    def describe_keys(self, descriptions: Mapping[str, str], *, shown: Collection[str] | None = None) -> None:
        """Describe this list's own keys in the language now on screen, showing ``shown`` in the footer."""
        describe_bindings(self._bindings.key_to_bindings, descriptions, shown=shown)
        self.refresh_bindings()

    def binding_for(self, key: str) -> Binding | None:
        """The binding this list declares for ``key``, if any."""
        bindings = self._bindings.key_to_bindings.get(key)
        return bindings[0] if bindings else None

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

    def _measure(self) -> _Measures:
        entries = [item for item in self._items if isinstance(item, CasillaListEntry)]
        if not entries:
            return _Measures()
        return _Measures(
            box=max(cell_len(_box_mark(entry.field)) for entry in entries),
            label=min(max(entry.indent + cell_len(self._label(entry)) for entry in entries), _LABEL_CAP),
            value=min(max(cell_len(row_value_text(entry, self._language)) for entry in entries), _VALUE_CAP),
            words=max(cell_len(origin_words(entry.field)) for entry in entries),
        )

    def _columns(self, width: int) -> _Columns:
        """Share one width out: the box whole, then the value, the label, and the origin words where they fit."""
        measures = self._measures
        # What is left once the lead, the box and its space, the space before
        # the value and the space and glyph after it are placed.
        room = width - (_LEAD + measures.box + 1 + 1 + 2)
        words_cells = 1 + measures.words
        # The words take room only while the label keeps as much as it needs,
        # or at least as much as the value and the words it would give way to.
        needed = min(measures.label, measures.value + measures.words)
        show_words = measures.words > 0 and room - measures.value - words_cells >= needed
        if show_words:
            room -= words_cells
        value = min(measures.value, max(room - min(measures.label, _LABEL_FLOOR), 1))
        label = max(min(measures.label, room - value), 1)
        detail = show_words and width >= _WIDEST and room - value - label >= 1 + _DETAIL_WIDTH
        return _Columns(
            box=measures.box, label=label, value=value, words=measures.words if show_words else 0, detail=detail
        )

    def _label_lines(self, entry: CasillaListEntry, columns: _Columns) -> tuple[str, ...]:
        return _wrap(self._label(entry), _label_width(entry, columns))

    def _note(self, entry: CasillaListEntry, columns: _Columns) -> str | None:
        """The optional line under a field: what a change replaces, a blocker, or where the description starts."""
        if self._density == "compact":
            return None
        if entry.previous_text is not None and not columns.detail:
            return tr("tui.modelo.workbench.was", value=entry.previous_text)
        if entry.field.blockers and not columns.detail:
            return tr(attention_words_key(Attention.BLOCKED))
        description = description_text(entry.field)
        return description.split(". ")[0] if description else None

    def _height(self, item: CasillaListItem, width: int) -> int:
        if not isinstance(item, CasillaListEntry):
            return 1
        columns = self._columns(width)
        return len(self._label_lines(item, columns)) + (1 if self._note(item, columns) else 0)

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
        # A span-less Text drops its own style when rendered to segments, so
        # single-style lines are appended as one styled span.
        if isinstance(item, CasillaListHeading):
            role = "heading" if item.level == 0 else "subheading"
            return Text().append(_fit(" " * (1 + 2 * item.level) + item.text, width), style=self._style(role))
        if isinstance(item, CasillaListNote):
            return Text().append(_fit(" " * (3 + item.indent) + item.text, width), style=self._style("muted"))
        return self._entry_line(item, sub_line, width, focused=focused)

    def _label(self, entry: CasillaListEntry) -> str:
        field = entry.field
        label = entry.label or field.label.text
        if field.label.disclosure in _SPANISH_DISCLOSURES and self._language is not OutputLanguage.ES:
            return f"{label} {tr(_IN_SPANISH_LOCALE_KEY)}"
        return label

    def _entry_line(self, entry: CasillaListEntry, sub_line: int, width: int, *, focused: bool) -> Text:
        field = entry.field
        columns = self._columns(width)
        labels = self._label_lines(entry, columns)
        label_width = _label_width(entry, columns)
        attention = entry.attention
        text = Text()
        text.append(
            HERE_MARK.glyph if focused and sub_line == 0 else " ", style=self._style("staged") if focused else Style()
        )
        if sub_line == 0:
            text.append(
                ATTENTION_GLYPHS[attention] if attention is not None else " ",
                style=self._role_style(ATTENTION_ROLES[attention]) if attention is not None else Style(),
            )
            text.append(" " + " " * entry.indent)
            text.append(_right(_box_mark(field), columns.box) + " ", style=self._style("box"))
            text.append(_fit(labels[0], label_width))
            role = ColourRole.STAGED if entry.staged_text is not None else ORIGIN_ROLES[field.origin]
            text.append(
                " " + _right(row_value_text(entry, self._language), columns.value), style=self._role_style(role)
            )
            text.append(" " + origin_glyph(field), style=self._role_style(ORIGIN_ROLES[field.origin]))
            if columns.words:
                text.append(" " + _fit(origin_words(field), columns.words), style=self._style("muted"))
            if columns.detail:
                text.append(" " + _fit(self._detail(entry), _DETAIL_WIDTH), style=self._style("muted"))
            return text
        text.append(" " * (_LEAD - 1 + entry.indent + columns.box + 1))
        if sub_line < len(labels):
            text.append(_fit(labels[sub_line], label_width))
            return text
        note = self._note(entry, columns) or ""
        text.append(_fit(note, width - cell_len(text.plain)), style=self._style("muted"))
        return text

    def _detail(self, entry: CasillaListEntry) -> str:
        if entry.previous_text is not None:
            return tr("tui.modelo.workbench.was", value=entry.previous_text)
        if entry.field.blockers:
            return tr(attention_words_key(Attention.BLOCKED))
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
    "description_text",
    "rate_note",
    "rate_text",
    "row_value_text",
    "value_text",
]
