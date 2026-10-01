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

from bisect import bisect_right
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from decimal import Decimal
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
    ModeloFormPrintedRate,
    ModeloFormRate,
    ModeloFormRateUnit,
    ModeloFormScalar,
    ModeloFormTextDisclosure,
    address_key,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from ...components.app_access import TypedAppAccess
from ...components.theme import tokenised
from .grid import (
    GRID_GAP,
    GRID_LEAD,
    CasillaListRecords,
    GridCellText,
    GridRowPlace,
    GridShape,
    TableGeometry,
    cell_width,
    measure_records,
    measure_table,
    record_summary_columns,
    wrap_label,
    wrap_text,
)
from .keys import describe_bindings
from .vocabulary import (
    ASKS_FOR_A_VALUE,
    ATTENTION_GLYPHS,
    ATTENTION_ROLES,
    BLOCKS_MARK,
    CONFIRM_MARK,
    FAILED_MARK,
    HERE_MARK,
    MISSING_MARK,
    NEEDS_ATTENTION,
    NOT_CALCULATED_MARK,
    NOT_IMPORTED_MARK,
    ORIGIN_ROLES,
    Attention,
    ColourRole,
    WorkbenchMark,
    attention_words_key,
    field_counts,
    field_needs_filer,
    holds_nothing,
    holds_zero,
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
#: The kind of address that names a casilla, as a finding about a record column names it.
_CASILLA_KIND: Final[str] = "casilla"
_PENDING_VALUE: Final[str] = "…"
_EMPTY_VALUE: Final[str] = "·"
_SEPARATOR: Final[str] = " · "
_RATIO_DATA_TYPE: Final[str] = "ratio"
_MONEY_DATA_TYPE: Final[str] = "money"
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
_IN_SPANISH_LOCALE_KEY: Final[str] = "tui.modelo.workbench.in_spanish"
_RATE_NOT_GROUNDED_KEY: Final[str] = "tui.modelo.workbench.rate.not_grounded"
_RATE_PRINTED_KEY: Final[str] = "tui.modelo.workbench.rate.printed_by_form"
_RATE_ROW_KEY: Final[str] = "tui.modelo.workbench.rate.of_row"
_RATE_ROW_PRINTED_KEY: Final[str] = "tui.modelo.workbench.rate.of_row_printed"
_ROW_BOXES_KEY: Final[str] = "tui.modelo.workbench.grid.row_boxes"
_RATE_UNITS: Final[Mapping[ModeloFormRateUnit, ModeloEditRatioUnit]] = MappingProxyType(
    {ModeloFormRateUnit.FRACTION: ModeloEditRatioUnit.FRACTION}
)
"""How each unit a grounded rate is stated in reads as a percentage."""
_RATE_READINGS: Final[frozenset[ModeloEditRatioUnit]] = frozenset(
    {ModeloEditRatioUnit.PERCENT, ModeloEditRatioUnit.FRACTION}
)
"""The units a ratio's own figure can be read in as a percentage."""
_SPANISH_DISCLOSURES: Final[frozenset[ModeloFormTextDisclosure]] = frozenset(
    {ModeloFormTextDisclosure.SPANISH_FALLBACK, ModeloFormTextDisclosure.OFFICIAL_SPANISH}
)
_BOX_OPENING_LOCALE_KEY: Final[str] = "tui.modelo.workbench.help.box_opening"
"""How a description opens by naming its box, in each language the catalogue writes: the row already shows it."""


@dataclass(frozen=True, slots=True)
class CasillaListHeading:
    """A section or row heading line; never under the cursor.

    A row heading of an official grid carries its place in the grid, so the
    list can draw the row as a line of the grid's table. A section heading
    carries the most severe thing its section still holds, and takes that
    level's colour: a blocker reads as an error, a missing or assumed value as
    a warning, and a section with nothing to do in the plain text colour.
    """

    text: str
    level: int = 0
    row: GridRowPlace | None = None
    mark: WorkbenchMark | None = None


@dataclass(frozen=True, slots=True)
class CasillaListNote:
    """An informational line, such as a value the official design fixes.

    A note standing in for a repeating group's records carries the group's
    column casillas, so a finding about one of them can be placed on it.
    """

    text: str
    indent: int = 0
    column_casilla_ids: tuple[str | None, ...] = ()


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
    #: The declaration is recorded as filed: its values are facts, and nothing on it asks for the filer.
    recorded: bool = False
    #: ``False`` on a page the read model states does not apply this period, which asks for no value.
    applies: bool = True
    #: In an official grid, the heading of the row the box sits in, and of its column.
    row_label: str | None = None
    column_label: str | None = None

    @property
    def key(self) -> AddressKey:
        """The field's semantic identity."""
        return address_key(self.field.address)

    @property
    def attention(self) -> Attention | None:
        """The mark that draws the eye: a staged change first, then a blocker."""
        if self.staged_text is not None:
            return Attention.STAGED
        if self.field.blockers and not self.recorded:
            return Attention.BLOCKED
        return None

    @property
    def needs_filer(self) -> bool:
        """Whether the filer can act on the field now: a staged change, or what the shared classing says.

        A box waiting on an import or a calculation is not one, and nothing on
        a recorded declaration is; ``n`` visits exactly these.
        """
        if self.staged_text is not None:
            return True
        return field_needs_filer(self.field, recorded=self.recorded, applies=self.applies)

    @property
    def origin_mark(self) -> str:
        """The origin glyph the row draws; a recorded declaration draws no to-do mark, only its words."""
        if self.recorded and self.field.origin in ASKS_FOR_A_VALUE:
            return " "
        return origin_glyph(self.field)

    @property
    def origin_words(self) -> str:
        """The origin in words, as the row and the box panel say it; a recorded declaration asks nothing."""
        return origin_words(self.field, recorded=self.recorded)

    @property
    def origin_role(self) -> ColourRole:
        """The colour of the origin; a recorded declaration's origins are all plain facts."""
        if self.recorded and self.field.origin in NEEDS_ATTENTION:
            return ColourRole.MUTED
        return ORIGIN_ROLES[self.field.origin]


type CasillaListItem = CasillaListHeading | CasillaListNote | CasillaListEntry | CasillaListRecords
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


@dataclass(frozen=True, slots=True)
class _TableRow:
    """One grid row drawn as a line of its table: where its cells are and what its label reads."""

    geometry: TableGeometry
    #: The item index of the field in each column, or ``None`` for an empty slot.
    cells: tuple[int | None, ...]
    literals: tuple[str | None, ...]
    labels: tuple[str, ...]
    #: Whether the column headings are drawn above this row: the first row of its grid on screen.
    header: bool
    level: WorkbenchMark | None

    @property
    def header_height(self) -> int:
        """The lines the column headings take above this row."""
        return self.geometry.header_height if self.header else 0

    def focusable(self) -> tuple[int, ...]:
        """The columns whose cell holds a field the cursor can rest on."""
        return tuple(column for column, index in enumerate(self.cells) if index is not None)


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


def description_text(field: ModeloFormField) -> str | None:
    """A field's description as a person reads it, without an opening that only names its box."""
    text = field.help
    if not text:
        return None
    stated = text.strip()
    if field.box:
        for language in OutputLanguage:
            opening = tr(_BOX_OPENING_LOCALE_KEY, locale=language.value, box=field.box)
            if stated.startswith(opening):
                rest = stated.removeprefix(opening).lstrip()
                return rest[:1].upper() + rest[1:] if rest else None
    return text


def _label_width(entry: CasillaListEntry, columns: _Columns) -> int:
    """The cells an entry's label gets: the label column less its indent, so every value lines up."""
    return max(columns.label - entry.indent, 1)


def _box_mark(field: ModeloFormField) -> str:
    return f"[{field.box}]" if field.box else _NO_BOX


def shown_rate(field: ModeloFormField) -> ModeloFormRate | ModeloFormPrintedRate | None:
    """The rate a rate box's row is taxed at: the grounded one, else the one the design prints; ``None`` else."""
    if field.origin is ModeloFormOrigin.NOT_APPLICABLE:
        return None
    return field.grounded_rate or field.printed_rate


def rate_is_value(field: ModeloFormField) -> bool:
    """Whether a box shows its row's rate as its value: only a box the design fixes, which holds nothing of its own.

    Any other rate box, typed, calculated, failed or empty, shows its own
    value, and its row's rate is said beside it rather than in its place.
    """
    return field.editability is ModeloFormEditability.DESIGN_CONSTANT and shown_rate(field) is not None


def own_ratio_unit(field: ModeloFormField) -> ModeloEditRatioUnit | None:
    """How a box's own figure reads as a rate: its declared unit, else what its figure and its row's rate establish.

    A ratio whose bounds declare no unit is still read as a rate when the
    figure leaves no doubt: a zero reads the same at any scale, and a figure
    equal to its row's grounded or printed rate at exactly one scale is at that
    scale. Any other undeclared figure keeps its unit undeclared, never guessed.
    ``None`` for a box that is not a ratio.
    """
    maximum = field.constraints.max_value if field.constraints is not None else None
    unit = ratio_unit(field.data_type, maximum)
    if unit is not ModeloEditRatioUnit.UNDECLARED:
        return unit
    value = field.value
    if not isinstance(value, Decimal | int) or isinstance(value, bool):
        return unit
    if holds_zero(value):
        return ModeloEditRatioUnit.PERCENT
    rate = field.grounded_rate or field.printed_rate
    if rate is None:
        return unit
    if value == rate.ratio:
        return ModeloEditRatioUnit.FRACTION
    if value == rate.ratio.scaleb(2):
        return ModeloEditRatioUnit.PERCENT
    return unit


def value_text(entry: CasillaListEntry, language: OutputLanguage) -> str:
    """Return the text of a field's value cell, with absence spoken in words.

    A rate box's own figure reads in its rate unit wherever that is
    established; one whose unit nothing establishes shows only a dot, never a
    bare figure a filer could read a hundredfold wrong. A box the design fixes
    and prints nothing for shows only a dot, since the origin beside it says
    the form sets it.
    """
    if entry.staged_text is not None:
        return entry.staged_text
    field = entry.field
    if field.origin is ModeloFormOrigin.NOT_APPLICABLE:
        return tr(_NOT_APPLICABLE_VALUE_KEY)
    rate = shown_rate(field)
    if rate is not None and rate_is_value(field):
        return rate_text(rate, language)
    if field.editability is ModeloFormEditability.DESIGN_CONSTANT and field.value is None:
        return _EMPTY_VALUE
    if field.origin in {ModeloFormOrigin.NOT_CALCULATED_YET, ModeloFormOrigin.CALCULATION_FAILED}:
        return _PENDING_VALUE
    if field.value is None or field.origin in {ModeloFormOrigin.CLEARED, ModeloFormOrigin.NOT_IMPORTED_YET}:
        return absent_value_text(language)
    unit = own_ratio_unit(field)
    if _bare_rate(field):
        return _EMPTY_VALUE
    value = field.value
    if unit in _RATE_READINGS and isinstance(value, Decimal):
        # A rate reads as the printed form writes one, "2 %" rather than "2.00 %"; dropping zeros rounds nothing.
        value = _without_trailing_zeros(value)
    return format_casilla_value(value, data_type=field.data_type, language=language, ratio_unit=unit)


def _without_trailing_zeros(value: Decimal) -> Decimal:
    """The same figure without the zeros that end its fraction, and a zero without a sign."""
    if value == 0:
        return Decimal(0)
    return value.quantize(Decimal(1)) if value == value.to_integral_value() else value.normalize()


def rate_text(rate: ModeloFormRate | ModeloFormPrintedRate, language: OutputLanguage) -> str:
    """Return a rate as the printed form states it, a percentage in the filer's language."""
    return format_casilla_value(
        rate.ratio, data_type=_RATIO_DATA_TYPE, language=language, ratio_unit=_RATE_UNITS[rate.unit]
    )


def _bare_rate(field: ModeloFormField) -> bool:
    """Whether a rate box holds a figure that no declared or grounded unit lets be read as a percentage."""
    return (
        field.data_type == _RATIO_DATA_TYPE
        and field.value is not None
        and not rate_is_value(field)
        and own_ratio_unit(field) not in _RATE_READINGS
    )


def _ungrounded_rate(entry: CasillaListEntry) -> bool:
    """Whether an entry is a row's rate box that holds no value and shows no rate."""
    field = entry.field
    return entry.rate_of_row and shown_rate(field) is None and field.value is None


def rate_note(entry: CasillaListEntry, language: OutputLanguage | None = None) -> str | None:
    """Say the rate a rate box's row is taxed at, and where it comes from, when that needs saying; ``None`` else.

    A box whose value is its row's rate needs only to say when the design
    merely prints it, which is not a rate the calculation is shown to apply.
    A rate box that shows its own value says its row's rate here instead. A
    row's rate box with no rate at all, or a rate box whose own figure cannot
    be read as a rate, says why none is shown. ``language`` formats the rate,
    the active output language when not given.
    """
    field = entry.field
    rate = shown_rate(field)
    if rate is None:
        return tr(_RATE_NOT_GROUNDED_KEY) if _ungrounded_rate(entry) or _bare_rate(field) else None
    printed = field.grounded_rate is None
    if rate_is_value(field):
        return tr(_RATE_PRINTED_KEY) if printed else None
    words = rate_text(rate, OutputLanguage(output_language()) if language is None else language)
    if printed:
        return tr(_RATE_ROW_PRINTED_KEY, rate=words)
    return tr(_RATE_ROW_KEY, rate=words)


def grid_cell_title(entry: CasillaListEntry) -> str | None:
    """Name a grid cell as the paper form places it: its row, its column, then its own precise label.

    ``None`` for a box that is not in an official grid.
    """
    if entry.row_label is None or entry.column_label is None:
        return None
    return _SEPARATOR.join((entry.row_label, entry.column_label, entry.field.label.text))


def _origin_says_absence(field: ModeloFormField) -> bool:
    """Whether a field's origin words already say its value is not there.

    A held zero is a value, of a rate box as of any other: it is shown, and
    the origin words say it was left at zero rather than that the box is empty.
    """
    if field.origin in _ABSENT_BY_ORIGIN:
        return True
    return field.origin in _ABSENT_WHEN_NONE and holds_nothing(field.value)


def row_value_text(entry: CasillaListEntry, language: OutputLanguage) -> str:
    """Return the value cell of a row, where an origin that says the value is absent leaves only a dot.

    The row's origin column says the absence in words, so the value column
    does not say it a second time. A rate box the design fixes shows the rate
    its row is grounded on, or the rate the design prints, or only a dot when
    there is neither, since claiming a rate the row does not establish would be
    a fact nobody established; any other rate box shows its own value like any
    box. Every other surface, which shows the value without the origin words
    beside it, uses :func:`value_text`.
    """
    field = entry.field
    if entry.staged_text is not None or rate_is_value(field):
        return value_text(entry, language)
    if _ungrounded_rate(entry) or _origin_says_absence(field):
        return _EMPTY_VALUE
    return value_text(entry, language)


def stated_value_text(entry: CasillaListEntry, language: OutputLanguage) -> str | None:
    """Return the value a panel or a search hit states beside the origin words; ``None`` when the box holds nothing.

    The words beside it already say the value is absent, so absence is not
    said a second time, while a held zero is stated as the figure it is.
    """
    text = row_value_text(entry, language)
    return None if text == _EMPTY_VALUE else text


def grid_value_text(entry: CasillaListEntry, language: OutputLanguage) -> str:
    """Return a grid cell's value: a row's value, with a box the design fixes and prints nothing for as a dot.

    A grid never says a value is fixed: its rate column prints a rate or
    nothing, and the help band says what the design does with the box.
    """
    field = entry.field
    if (
        entry.staged_text is None
        and field.editability is ModeloFormEditability.DESIGN_CONSTANT
        and field.value is None
        and shown_rate(field) is None
    ):
        return _EMPTY_VALUE
    return row_value_text(entry, language)


def _row_level(entries: list[CasillaListEntry]) -> WorkbenchMark | None:
    """The most severe thing a grid row's cells hold, on the scale its section heading and the navigator share.

    ``None`` when nothing in the row is to do and nothing waits.
    """
    if not entries:
        return None
    first = entries[0]
    return field_counts((entry.field for entry in entries), recorded=first.recorded, applies=first.applies).level


_LEVEL_ROLES: Final[Mapping[str, ColourRole]] = MappingProxyType(
    {
        BLOCKS_MARK.glyph: ColourRole.ERROR,
        MISSING_MARK.glyph: ColourRole.ERROR,
        FAILED_MARK.glyph: ColourRole.ERROR,
        CONFIRM_MARK.glyph: ColourRole.WARNING,
        NOT_IMPORTED_MARK.glyph: ColourRole.MUTED,
        NOT_CALCULATED_MARK.glyph: ColourRole.MUTED,
    }
)
_SECTION_ROLES: Final[Mapping[str, str]] = MappingProxyType(
    {
        BLOCKS_MARK.glyph: "heading-error",
        MISSING_MARK.glyph: "heading-warning",
        FAILED_MARK.glyph: "heading-error",
        CONFIRM_MARK.glyph: "heading-warning",
    }
)
"""The style of a section heading by the most severe thing its section holds; what only waits reads plainly."""


def _heading_role(heading: CasillaListHeading) -> str:
    if heading.level:
        return "subheading"
    return "heading" if heading.mark is None else _SECTION_ROLES.get(heading.mark.glyph, "heading")


class CasillaList(TypedAppAccess, ScrollView, can_focus=True):
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
        Binding("up,k", "move(-1)", "", show=False),
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

    class ScrolledDownToCursor(Message):
        """The list has scrolled down to bring the cursor's field into view, leaving it on the last line."""

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
        #: The grid column the cursor keeps while it moves up and down through a table.
        self._column: int | None = None
        self._starts: list[int] = []
        self._heights: list[int] = []
        self._owner: list[int] = []
        self._tables: dict[int, _TableRow] = {}
        self._cell_of: dict[int, tuple[int, int]] = {}
        self._stacked: frozenset[int] = frozenset()
        self._records: dict[int, tuple[tuple[str, str], ...]] = {}
        self._laid_out_width = -1
        self._measures = self._measure(frozenset())
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
    def on_grid_row(self) -> bool:
        """Whether the cursor rests on a cell of a grid drawn as a table, where the side arrows move between cells."""
        self._layout()
        index = self._cursor_index()
        return index is not None and index in self._cell_of

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

    def describe_keys(self, descriptions: Mapping[str, str], *, shown: Collection[str] | None = None) -> None:
        """Describe this list's own keys in the language now on screen, showing ``shown`` in the footer."""
        describe_bindings(self._bindings.key_to_bindings, descriptions, shown=shown)
        self.refresh_bindings()

    def binding_for(self, key: str) -> Binding | None:
        """The binding this list declares for ``key``, if any."""
        bindings = self._bindings.key_to_bindings.get(key)
        return bindings[0] if bindings else None

    def focus_address(self, key: AddressKey) -> bool:
        """Put the cursor on one address, or bring the table of records showing it into view.

        A column of a repeating group's records is no field the cursor rests
        on, so a casilla one of its columns shows scrolls to the group's
        records heading, or to the note standing in for records whose number
        is unknown. ``False`` when this page shows the address nowhere.
        """
        for index, item in enumerate(self._items):
            if isinstance(item, CasillaListEntry) and item.key == key:
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

    def _records_showing(self, key: AddressKey) -> int | None:
        """The line a group's records start at, when one of its columns shows the casilla ``key`` names."""
        kind, identifier = key
        if kind != _CASILLA_KIND:
            return None
        for index, item in enumerate(self._items):
            if isinstance(item, CasillaListRecords | CasillaListNote) and identifier in item.column_casilla_ids:
                heading = index - 1
                before = self._items[heading] if heading >= 0 else None
                return heading if isinstance(before, CasillaListHeading) else index
        return None

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Take the side arrows only on a table's row, so elsewhere they reach the screen's own keys."""
        if action == "cell":
            return self.on_grid_row
        return True

    # ── layout ───────────────────────────────────────────────────────────

    def _content_width(self) -> int:
        return max(self.scrollable_content_region.width, 20)

    def _measure(self, drawn_in_tables: frozenset[int]) -> _Measures:
        entries = [
            item
            for index, item in enumerate(self._items)
            if isinstance(item, CasillaListEntry) and index not in drawn_in_tables
        ]
        if not entries:
            return _Measures()
        return _Measures(
            box=max(cell_len(_box_mark(entry.field)) for entry in entries),
            label=min(max(entry.indent + cell_len(self._label(entry)) for entry in entries), _LABEL_CAP),
            value=min(max(cell_len(self._value(entry)) for entry in entries), _VALUE_CAP),
            words=max(cell_len(entry.origin_words) for entry in entries),
        )

    def _value(self, entry: CasillaListEntry) -> str:
        """The value a line shows: a grid cell never says the design fixes it."""
        if entry.row_label is not None:
            return grid_value_text(entry, self._language)
        return row_value_text(entry, self._language)

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
        return wrap_text(self._label(entry), _label_width(entry, columns))

    def _note(self, index: int, entry: CasillaListEntry, columns: _Columns) -> str | None:
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
        description = description_text(entry.field)
        return description.split(". ")[0] if description else None

    def _rated_label(self, place: GridRowPlace) -> str:
        """A row's heading with the rate its row is taxed at, when it has one."""
        if place.rate is not None:
            return _SEPARATOR.join((place.heading, rate_text(place.rate, self._language)))
        return place.heading

    def _stacked_label(self, place: GridRowPlace) -> str:
        """A stacked row's heading, told apart from its neighbours by its rate or by the boxes it holds."""
        if place.rate is None and len(place.boxes) > 1:
            return tr(_ROW_BOXES_KEY, heading=place.heading, first=place.boxes[0], last=place.boxes[-1])
        return self._rated_label(place)

    def _height(self, index: int, item: CasillaListItem, width: int) -> int:
        if index in self._tables:
            row = self._tables[index]
            return row.header_height + len(row.labels)
        if self._owner[index] != index:
            return 0
        if isinstance(item, CasillaListHeading):
            if item.row is not None:
                return len(wrap_text(self._stacked_label(item.row), width - _LEAD))
            return 1
        if isinstance(item, CasillaListRecords):
            return len(self._records.get(index, ()))
        if not isinstance(item, CasillaListEntry):
            return 1
        columns = self._columns(width)
        return len(self._label_lines(item, columns)) + (1 if self._note(index, item, columns) else 0)

    def _grid_rows(self) -> dict[GridShape, list[int]]:
        """The index of every grid row heading, grouped by the grid it belongs to, in list order."""
        grids: dict[GridShape, list[int]] = {}
        for index, item in enumerate(self._items):
            if isinstance(item, CasillaListHeading) and item.row is not None:
                grids.setdefault(item.row.grid, []).append(index)
        return grids

    def _owned(self, heading: int) -> range:
        """The items a grid row heading owns: its boxes and any literal the design prints without one."""
        item = self._items[heading]
        span = item.row.span if isinstance(item, CasillaListHeading) and item.row is not None else 0
        return range(heading + 1, min(heading + 1 + span, len(self._items)))

    def _row_cells(self, heading: int) -> tuple[int | None, ...]:
        item = self._items[heading]
        if not isinstance(item, CasillaListHeading) or item.row is None:
            return ()
        owned = {
            entry.key: index
            for index in self._owned(heading)
            if isinstance(entry := self._items[index], CasillaListEntry)
        }
        return tuple(None if slot.key is None else owned.get(slot.key) for slot in item.row.slots)

    def _lay_out_grids(self, width: int) -> None:
        """Decide for each grid whether it is drawn as a table at ``width``, and place its rows and cells."""
        self._tables = {}
        self._cell_of = {}
        stacked: set[int] = set()
        self._owner = list(range(len(self._items)))
        for grid, headings in self._grid_rows().items():
            rows = [self._row_cells(heading) for heading in headings]
            places = [item.row for heading in headings if isinstance(item := self._items[heading], CasillaListHeading)]
            texts = tuple(
                tuple(self._cell_text(index) for row in rows if (index := row[column]) is not None)
                for column in range(len(grid.headings))
            )
            literals = tuple(
                tuple(literal for place in places if place is not None and (literal := place.slots[column].literal))
                for column in range(len(grid.headings))
            )
            labels = self._shown_labels(places)
            geometry = measure_table(grid.headings, texts, literals, labels, width)
            if geometry is None:
                for heading in headings:
                    stacked.update(self._owned(heading))
                continue
            for position, (heading, cells, place) in enumerate(zip(headings, rows, places, strict=True)):
                for index in self._owned(heading):
                    self._owner[index] = heading
                for column, index in enumerate(cells):
                    if index is not None:
                        self._cell_of[index] = (heading, column)
                entries = [
                    entry
                    for index in cells
                    if index is not None and isinstance(entry := self._items[index], CasillaListEntry)
                ]
                self._tables[heading] = _TableRow(
                    geometry=geometry,
                    cells=cells,
                    literals=() if place is None else tuple(slot.literal for slot in place.slots),
                    labels=wrap_label(labels[position], geometry.label) if labels[position] else ("",),
                    header=position == 0,
                    level=_row_level(entries),
                )
        self._stacked = frozenset(stacked)

    def _shown_labels(self, places: list[GridRowPlace | None]) -> tuple[str, ...]:
        """Each row's label: its heading, with its rate when it has one, on every row it heads.

        The paper form prints a heading such as "General regime" once over the
        rows it spans, but a row read on its own, as a terminal line is, needs
        its own name, as the stacked form of the grid gives it.
        """
        return tuple("" if place is None else self._rated_label(place) for place in places)

    def _cell_text(self, index: int) -> GridCellText:
        item = self._items[index]
        if not isinstance(item, CasillaListEntry):
            return GridCellText(box="", value="")
        return GridCellText(
            box=_box_mark(item.field),
            value=grid_value_text(item, self._language),
            rate=item.field.data_type == _RATIO_DATA_TYPE,
        )

    def _record_value(self, value: ModeloFormScalar, data_type: str) -> str:
        if value is None:
            return _EMPTY_VALUE
        return format_casilla_value(
            value, data_type=data_type, language=self._language, ratio_unit=ratio_unit(data_type, None)
        )

    def _record_lines(self, item: CasillaListRecords, width: int) -> tuple[tuple[str, str], ...]:
        """A repeating group's records as lines: a table with an index column, or one line per record."""
        indexes = tuple(str(row.index) for row in item.rows)
        values = tuple(
            tuple(
                self._record_value(value, data_type)
                for value, data_type in zip(row.values, item.data_types, strict=True)
            )
            for row in item.rows
        )
        geometry = measure_records(item.headings, indexes, values, width)
        lines: list[tuple[str, str]] = []
        if not geometry.table:
            shown = record_summary_columns(item.data_types)
            for index, row in zip(indexes, values, strict=True):
                summary = (" " * GRID_GAP).join(row[column] for column in shown)
                lines.append((_fit(" " * GRID_LEAD + _right(index, geometry.index) + "  " + summary, width), "value"))
            return tuple(lines)
        height = geometry.header_height
        for line in range(height):
            parts = [" " * (GRID_LEAD + geometry.index)]
            for column, heading in enumerate(geometry.header):
                offset = height - len(heading)
                text = heading[line - offset] if line >= offset else ""
                parts.append(" " * GRID_GAP + self._record_cell(text, geometry.widths[column], item, column))
            lines.append(("".join(parts), "subheading"))
        for index, row in zip(indexes, values, strict=True):
            parts = [" " * GRID_LEAD + _right(index, geometry.index)]
            parts.extend(
                " " * GRID_GAP + self._record_cell(text, geometry.widths[column], item, column)
                for column, text in enumerate(row)
            )
            lines.append(("".join(parts), "value"))
        return tuple(lines)

    def _record_cell(self, text: str, width: int, item: CasillaListRecords, column: int) -> str:
        """An amount is right-aligned under its heading, anything else left-aligned."""
        if item.data_types[column] == _MONEY_DATA_TYPE:
            return _right(text, width)
        return _fit(text, width)

    def _layout(self) -> None:
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

    def on_resize(self, event: events.Resize) -> None:
        """Lay the lines out again for the new width and keep the cursor in view."""
        self._layout()
        self._scroll_to_cursor()

    # ── rendering ────────────────────────────────────────────────────────

    def _style(self, role: str) -> Style:
        return self.get_component_rich_style(f"casilla-list--{role}", partial=True)

    def _role_style(self, role: ColourRole) -> Style:
        return self._style(role.value)

    def _item_at_line(self, line: int) -> int | None:
        index = bisect_right(self._starts, line) - 1
        if index < 0 or index >= len(self._items) or line >= self._starts[index] + self._heights[index]:
            return None
        return index

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

    def _item_text(self, index: int, sub_line: int, width: int, *, focused: bool) -> Text:
        # A span-less Text drops its own style when rendered to segments, so
        # single-style lines are appended as one styled span.
        item = self._items[index]
        if index in self._tables:
            return self._table_line(index, sub_line)
        if isinstance(item, CasillaListHeading):
            role = _heading_role(item)
            if item.row is not None:
                lines = wrap_text(self._stacked_label(item.row), width - _LEAD)
                return Text().append(_fit(" " * _LEAD + lines[sub_line], width), style=self._style(role))
            return Text().append(_fit(" " * (1 + 2 * item.level) + item.text, width), style=self._style(role))
        if isinstance(item, CasillaListNote):
            return Text().append(_fit(" " * (3 + item.indent) + item.text, width), style=self._style("muted"))
        if isinstance(item, CasillaListRecords):
            text, role = self._records[index][sub_line]
            return Text().append(_fit(text, width), style=self._style(role))
        return self._entry_line(index, item, sub_line, width, focused=focused)

    def _table_line(self, index: int, sub_line: int) -> Text:
        """One line of a grid row drawn as its table: the column headings, or the row's label and cells."""
        row = self._tables[index]
        geometry = row.geometry
        text = Text()
        if sub_line < row.header_height:
            text.append(" " * (GRID_LEAD + geometry.label + 1))
            for column, heading in enumerate(geometry.header):
                offset = row.header_height - len(heading)
                words = heading[sub_line - offset] if sub_line >= offset else ""
                text.append((" " * GRID_GAP if column else "") + _right(words, geometry.widths[column]))
            text.stylize(self._style("subheading"))
            return text
        line = sub_line - row.header_height
        cursor = self._cursor_index()
        here = cursor is not None and cursor in row.cells
        text.append(HERE_MARK.glyph if here and line == 0 else " ", style=self._style("staged") if here else Style())
        level = row.level if line == 0 else None
        text.append(
            " " if level is None else level.glyph,
            style=Style() if level is None else self._role_style(_LEVEL_ROLES[level.glyph]),
        )
        text.append(" ")
        label = row.labels[line] if line < len(row.labels) else ""
        text.append(_fit(label, geometry.label), style=self._style("subheading"))
        if line:
            return text
        text.append(" ")
        for column, cell in enumerate(row.cells):
            if column:
                text.append(" " * GRID_GAP)
            self._append_cell(text, row, column, cell, focused=here and cell == cursor)
        return text

    def _append_cell(self, text: Text, row: _TableRow, column: int, cell: int | None, *, focused: bool) -> None:
        geometry = row.geometry
        width = geometry.widths[column]
        entry = None if cell is None else self._entry_at(cell)
        if entry is None:
            literal = row.literals[column] if column < len(row.literals) else None
            if literal is None:
                text.append(" " * width)
            else:
                text.append(_right(literal + "  ", width), style=self._style("muted"))
            return
        cursor = self._style("cursor") if focused else Style()
        text.append(" " * (width - cell_width(geometry.boxes[column], geometry.values[column])), style=cursor)
        attention = entry.attention
        text.append(
            ATTENTION_GLYPHS[attention] if attention is not None else " ",
            style=(self._role_style(ATTENTION_ROLES[attention]) if attention is not None else Style()) + cursor,
        )
        text.append(_right(_box_mark(entry.field), geometry.boxes[column]) + " ", style=self._style("box") + cursor)
        role = ColourRole.STAGED if entry.staged_text is not None else entry.origin_role
        value = _right(grid_value_text(entry, self._language), geometry.values[column])
        text.append(value, style=self._role_style(role) + cursor)
        text.append(" " + entry.origin_mark, style=self._role_style(entry.origin_role) + cursor)

    def _label(self, entry: CasillaListEntry) -> str:
        field = entry.field
        label = entry.label or field.label.text
        if field.label.disclosure in _SPANISH_DISCLOSURES and self._language is not OutputLanguage.ES:
            return f"{label} {tr(_IN_SPANISH_LOCALE_KEY)}"
        return label

    def _entry_line(self, index: int, entry: CasillaListEntry, sub_line: int, width: int, *, focused: bool) -> Text:
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
            role = ColourRole.STAGED if entry.staged_text is not None else entry.origin_role
            text.append(" " + _right(self._value(entry), columns.value), style=self._role_style(role))
            text.append(" " + entry.origin_mark, style=self._role_style(entry.origin_role))
            if columns.words:
                text.append(" " + _fit(entry.origin_words, columns.words), style=self._style("muted"))
            if columns.detail:
                text.append(" " + _fit(self._detail(entry), _DETAIL_WIDTH), style=self._style("muted"))
            return text
        text.append(" " * (_LEAD - 1 + entry.indent + columns.box + 1))
        if sub_line < len(labels):
            text.append(_fit(labels[sub_line], label_width))
            return text
        note = self._note(index, entry, columns) or ""
        text.append(_fit(note, width - cell_len(text.plain)), style=self._style("muted"))
        return text

    def _detail(self, entry: CasillaListEntry) -> str:
        if entry.previous_text is not None:
            return tr("tui.modelo.workbench.was", value=entry.previous_text)
        if entry.attention is Attention.BLOCKED:
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

    def _move_cursor_to(self, index: int, *, column: int | None = None) -> None:
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

    def _owner_of(self, index: int) -> int:
        return self._owner[index] if 0 <= index < len(self._owner) else index

    def _scroll_to_cursor(self) -> None:
        index = self._cursor_index()
        if index is None or not self._starts or index >= len(self._starts):
            return
        owner = self._owner_of(index)
        top = self._starts[owner]
        bottom = top + self._heights[owner]
        view_top = int(self.scroll_offset.y)
        view_height = max(self.scrollable_content_region.height, 1)
        if top < view_top:
            self.scroll_to(y=max(top - 1, 0), animate=False)
        elif bottom > view_top + view_height:
            # Said once the scroll has landed, so whoever follows it reads where the list now stands.
            self.scroll_to(
                y=bottom - view_height,
                animate=False,
                on_complete=self._say_scrolled_down,
            )

    def _say_scrolled_down(self) -> None:
        self.post_message(self.ScrolledDownToCursor())

    def _step(self, start: int, delta: int) -> int | None:
        index = start + delta
        while 0 <= index < len(self._items):
            if isinstance(self._items[index], CasillaListEntry):
                return index
            index += delta
        return None

    def _stops(self) -> list[int]:
        """Where the cursor can rest moving up and down, in line order: each field, and each table row with a box."""
        stops: list[int] = []
        for index, item in enumerate(self._items):
            if index in self._tables:
                if self._tables[index].focusable():
                    stops.append(index)
            elif isinstance(item, CasillaListEntry) and index not in self._cell_of:
                stops.append(index)
        return stops

    def _land(self, stop: int, column: int | None) -> int:
        """The field to rest on at a stop: a table row's cell nearest ``column``, skipping empty slots."""
        row = self._tables.get(stop)
        if row is None:
            return stop
        focusable = row.focusable()
        wanted = focusable[0] if column is None else column
        nearest = min(focusable, key=lambda candidate: (abs(candidate - wanted), candidate))
        cell = row.cells[nearest]
        return stop if cell is None else cell

    def _go_to_stop(self, stop: int, column: int | None) -> None:
        target = self._land(stop, column)
        self._move_cursor_to(target, column=column if stop in self._tables else None)

    def _current_stop(self) -> tuple[list[int], int | None, int | None]:
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

    def action_move(self, delta: int) -> None:
        """Move the cursor to the field above or below; in a table, to the same column of the next row."""
        stops, position, column = self._current_stop()
        if not stops:
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
        """Move the cursor about one screen of lines."""
        stops, position, column = self._current_stop()
        if position is None:
            return
        remaining = max(self.scrollable_content_region.height - 2, 1)
        target = position
        while remaining > 0 and 0 <= target + direction < len(stops):
            target += direction
            remaining -= max(self._heights[stops[target]], 1)
        self._go_to_stop(stops[target], column)

    def action_ends(self, direction: int) -> None:
        """Move the cursor to the first or last field; in a table's row, to its first or last cell."""
        self._layout()
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


__all__ = [
    "AddressKey",
    "CasillaList",
    "CasillaListEntry",
    "CasillaListHeading",
    "CasillaListItem",
    "CasillaListNote",
    "Density",
    "description_text",
    "grid_cell_title",
    "grid_value_text",
    "own_ratio_unit",
    "rate_note",
    "rate_text",
    "row_value_text",
    "shown_rate",
    "stated_value_text",
    "value_text",
]
