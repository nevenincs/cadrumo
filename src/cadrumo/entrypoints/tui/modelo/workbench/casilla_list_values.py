"""Formatting helpers for values and descriptions shown in the modelo workbench list.

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

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from rich.cells import cell_len

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
    ModeloFormTextDisclosure,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from ...components.cell_text import ellipsize
from .casilla_list_models import CasillaListEntry, CasillaListHeading, _Columns
from .vocabulary import (
    BLOCKS_MARK,
    CONFIRM_MARK,
    FAILED_MARK,
    MISSING_MARK,
    NOT_CALCULATED_MARK,
    NOT_IMPORTED_MARK,
    ColourRole,
    WorkbenchMark,
    field_counts,
    holds_nothing,
    holds_zero,
)

#: The cursor mark, the attention mark and the space after them.
_LEAD: Final[int] = 3
#: The widest value a column makes room for: the widest money figure, ``−99.999.999,99 €``, is 16 cells.
_VALUE_CAP: Final[int] = 17
_DETAIL_WIDTH: Final[int] = 32
FOLLOWING_MIN_VIEW: Final[int] = 6
"""The fewest lines the list must show before it gives any of them to the rows after the cursor's field."""
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


def _fit(text: str, width: int) -> str:
    """Pad or cut ``text`` to exactly ``width`` cells, marking a cut with an ellipsis."""
    if width <= 0:
        return ""
    fitted = ellipsize(text, width)
    return fitted + " " * (width - cell_len(fitted))


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
    """Whether a box shows its row's rate as its value, as the official form prints it.

    A box the design fixes holds nothing of its own, so it shows its row's
    rate. A calculated rate box in a row grounded on one rate shows that rate
    whatever the base, never a figure worked out from an empty base. Any other
    rate box, typed, failed or empty, or calculated in a row with no grounded
    rate, shows its own value, and its row's rate is said beside it.
    """
    if field.editability is ModeloFormEditability.DESIGN_CONSTANT:
        return shown_rate(field) is not None
    return field.origin is ModeloFormOrigin.CALCULATED and field.grounded_rate is not None


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
    special = _special_value_text(field, language)
    return special if special is not None else _ordinary_value_text(field, language)


def _special_value_text(field: ModeloFormField, language: OutputLanguage) -> str | None:
    if field.origin is ModeloFormOrigin.NOT_APPLICABLE:
        return tr(_NOT_APPLICABLE_VALUE_KEY)
    rate = shown_rate(field)
    if rate is not None and rate_is_value(field):
        return rate_text(rate, language)
    if field.editability is ModeloFormEditability.DESIGN_CONSTANT and field.value is None:
        return _EMPTY_VALUE
    if field.origin in {ModeloFormOrigin.NOT_CALCULATED_YET, ModeloFormOrigin.CALCULATION_FAILED}:
        return _PENDING_VALUE
    return None


def _ordinary_value_text(field: ModeloFormField, language: OutputLanguage) -> str:
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
    """Whether an entry is a row's rate box that shows no rate: it holds no value, or one worked out from no base.

    With no grounded rate, a rate the calculation works out of an empty base
    is no rate the row applies, so it is not shown as one.
    """
    field = entry.field
    if not entry.rate_of_row or shown_rate(field) is not None:
        return False
    return field.value is None or (field.origin is ModeloFormOrigin.CALCULATED and entry.row_base_empty is True)


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
