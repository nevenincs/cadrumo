"""The workbench's closed visual vocabulary: one glyph, one colour role and words per state.

Every field shows exactly one origin (where its value stands) and at most one
attention mark (a staged change, or a verification blocker). A state is always
a glyph from the pinned terminal font together with its words, and colour only
reinforces it, so a greyscale screenshot and a colour one read the same.

A value that comes from somewhere else also says which kind of place: the
filer's records, a register they keep, their profile, an earlier declaration,
the AEAT tax data or the form itself. The origin keeps its glyph; only a value
carried from an earlier declaration takes a mark of its own, so it never reads
like one fetched from the filer's records.

Every mark any workbench surface draws is declared here once, with the
catalogue key of what it means: the origins and attention marks of a row, the
stepper's, the navigator's, the issue levels and the staleness mark. Other
modules take their glyphs from these constants and define none of their own.
The tables are total over the application's closed enums, and a glyph may
repeat only where it means the same thing, which the module refuses at import
rather than leaving two meanings to look alike on screen.

Every origin also has one standing, shared by the navigator, the list's
section headings, a grid row's edge, the header and ``n``: the filer has
something to do about it (a missing, assumed or failed value), it waits on an
import or a calculation the filer runs, or it is done. Only a missing value
reads "needs your input", and done never stands over a value that was not
imported or calculated.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from rich.text import Text

from .....application.modelo.edit_models import ModeloEditNonWritableReason
from .....application.modelo.source_policy import SourceFamily
from .....application.modelo.work_form_models import (
    ABSENT_FROM_ADMISSION,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloWorkForm,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .wording import date_text, period_words


class ColourRole(StrEnum):
    """The colour a state reinforces its glyph and words with."""

    MUTED = "muted"
    VALUE = "value"
    ENTERED = "entered"
    WARNING = "warning"
    ERROR = "error"
    STAGED = "staged"


class Attention(StrEnum):
    """What draws the eye to a field beyond its origin."""

    STAGED = "staged"
    BLOCKED = "blocked"


ORIGIN_GLYPHS: Final[Mapping[ModeloFormOrigin, str]] = MappingProxyType(
    {
        ModeloFormOrigin.NOT_APPLICABLE: "-",
        ModeloFormOrigin.OVERRIDES_SOURCE: "≠",
        ModeloFormOrigin.CALCULATED: "=",
        ModeloFormOrigin.NOT_CALCULATED_YET: "◌",
        ModeloFormOrigin.CALCULATION_FAILED: "×",
        ModeloFormOrigin.INFORMATIONAL: "◇",
        ModeloFormOrigin.NEEDS_INPUT: "!",
        ModeloFormOrigin.IMPORTED: "↓",
        ModeloFormOrigin.NOT_IMPORTED_YET: "⇣",
        ModeloFormOrigin.OPTIONAL_EMPTY: "○",
        ModeloFormOrigin.CLEARED: "□",
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: "◐",
        ModeloFormOrigin.ENTERED: "●",
    }
)
"""One mark per origin, every one present in the pinned font."""

ORIGIN_ROLES: Final[Mapping[ModeloFormOrigin, ColourRole]] = MappingProxyType(
    {
        ModeloFormOrigin.NOT_APPLICABLE: ColourRole.MUTED,
        ModeloFormOrigin.OVERRIDES_SOURCE: ColourRole.WARNING,
        ModeloFormOrigin.CALCULATED: ColourRole.VALUE,
        ModeloFormOrigin.NOT_CALCULATED_YET: ColourRole.MUTED,
        ModeloFormOrigin.CALCULATION_FAILED: ColourRole.ERROR,
        ModeloFormOrigin.INFORMATIONAL: ColourRole.MUTED,
        ModeloFormOrigin.NEEDS_INPUT: ColourRole.ERROR,
        ModeloFormOrigin.IMPORTED: ColourRole.VALUE,
        ModeloFormOrigin.NOT_IMPORTED_YET: ColourRole.MUTED,
        ModeloFormOrigin.OPTIONAL_EMPTY: ColourRole.MUTED,
        ModeloFormOrigin.CLEARED: ColourRole.MUTED,
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: ColourRole.WARNING,
        ModeloFormOrigin.ENTERED: ColourRole.ENTERED,
    }
)

ATTENTION_GLYPHS: Final[Mapping[Attention, str]] = MappingProxyType({Attention.STAGED: "Δ", Attention.BLOCKED: "▲"})
ATTENTION_ROLES: Final[Mapping[Attention, ColourRole]] = MappingProxyType(
    {Attention.STAGED: ColourRole.STAGED, Attention.BLOCKED: ColourRole.ERROR}
)
_ATTENTION_WORDS_LOCALE_KEYS: Final[Mapping[Attention, str]] = MappingProxyType(
    {
        Attention.STAGED: "tui.modelo.workbench.attention.staged",
        # A blocker reads with the same words as the blocking level of every
        # issue list and header chip, so the row never names it differently.
        Attention.BLOCKED: "tui.modelo.workbench.level.blocks",
    }
)


def origin_words_key(origin: ModeloFormOrigin) -> str:
    """The catalogue key naming one origin in a few words."""
    return f"tui.modelo.workbench.origin.{origin.value}"


@dataclass(frozen=True, slots=True)
class WorkbenchMark:
    """One glyph the workbench draws and the catalogue key of what it means."""

    glyph: str
    translation_key: str


ORIGIN_MARKS: Final[Mapping[ModeloFormOrigin, WorkbenchMark]] = MappingProxyType(
    {origin: WorkbenchMark(glyph, translation_key=origin_words_key(origin)) for origin, glyph in ORIGIN_GLYPHS.items()}
)
ATTENTION_MARKS: Final[Mapping[Attention, WorkbenchMark]] = MappingProxyType(
    {
        attention: WorkbenchMark(ATTENTION_GLYPHS[attention], translation_key=key)
        for attention, key in _ATTENTION_WORDS_LOCALE_KEYS.items()
    }
)

#: Something that must be fixed before the filing can be recorded: a row, a step, a note or an issue.
BLOCKS_MARK: Final[WorkbenchMark] = ATTENTION_MARKS[Attention.BLOCKED]
#: A value the declaration needs and nobody has given, wherever it is counted.
MISSING_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.NEEDS_INPUT]
#: A value Cadrumo assumed and only the filer can confirm, wherever it is counted.
CONFIRM_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.DEFAULT_TO_CONFIRM]
#: A warning that does not stop the filing.
CHECK_MARK: Final[WorkbenchMark] = WorkbenchMark("◆", translation_key="tui.modelo.workbench.level.check")
#: An explanation for the filer's information.
INFO_MARK: Final[WorkbenchMark] = WorkbenchMark("i", translation_key="tui.modelo.workbench.level.info")
#: A value carried from an earlier declaration, in place of the imported glyph.
EARLIER_FILING_MARK: Final[WorkbenchMark] = WorkbenchMark(
    "«", translation_key="tui.modelo.workbench.legend.name.earlier"
)
#: A step or section with nothing left to do.
DONE_MARK: Final[WorkbenchMark] = WorkbenchMark("✓", translation_key="tui.modelo.workbench.legend.name.done")
#: Where the filer is: the selected box, the page or the step they are on.
HERE_MARK: Final[WorkbenchMark] = WorkbenchMark("▸", translation_key="tui.modelo.workbench.legend.name.here")
#: A navigator section that is closed.
COLLAPSED_MARK: Final[WorkbenchMark] = WorkbenchMark("▹", translation_key="tui.modelo.workbench.legend.name.collapsed")
#: A navigator section that is open.
EXPANDED_MARK: Final[WorkbenchMark] = WorkbenchMark("▿", translation_key="tui.modelo.workbench.legend.name.expanded")
#: A result that does not include the latest changes yet.
STALE_MARK: Final[WorkbenchMark] = WorkbenchMark("◷", translation_key="tui.modelo.workbench.legend.name.stale")

WORKBENCH_MARKS: Final[tuple[WorkbenchMark, ...]] = (
    *ORIGIN_MARKS.values(),
    *ATTENTION_MARKS.values(),
    CHECK_MARK,
    INFO_MARK,
    EARLIER_FILING_MARK,
    DONE_MARK,
    HERE_MARK,
    COLLAPSED_MARK,
    EXPANDED_MARK,
    STALE_MARK,
)
"""Every mark the workbench draws on any surface; a step not started carries none."""


def require_one_meaning_per_glyph(marks: Iterable[WorkbenchMark]) -> None:
    """Refuse marks where one glyph means two things, or one meaning is drawn two ways."""
    meanings: defaultdict[str, set[str]] = defaultdict(set)
    glyphs: defaultdict[str, set[str]] = defaultdict(set)
    for mark in marks:
        meanings[mark.glyph].add(mark.translation_key)
        glyphs[mark.translation_key].add(mark.glyph)
    shared = {glyph: sorted(keys) for glyph, keys in meanings.items() if len(keys) > 1}
    if shared:
        raise ValueError(f"a workbench glyph means more than one thing: {shared}")
    split = {key: sorted(drawn) for key, drawn in glyphs.items() if len(drawn) > 1}
    if split:
        raise ValueError(f"a workbench meaning is drawn with more than one glyph: {split}")


class Standing(StrEnum):
    """Where one box stands on the filing journey, as every surface that counts boxes classes it."""

    #: The filer has something to do about it: give a value, confirm one, or resolve why it failed.
    NEEDS_YOU = "needs_you"
    #: It waits on a step the filer runs, an import or a calculation, not on anything typed into it.
    WAITING = "waiting"
    #: Nothing is left to do about it.
    DONE = "done"


ORIGIN_STANDINGS: Final[Mapping[ModeloFormOrigin, Standing]] = MappingProxyType(
    {
        ModeloFormOrigin.NEEDS_INPUT: Standing.NEEDS_YOU,
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: Standing.NEEDS_YOU,
        ModeloFormOrigin.CALCULATION_FAILED: Standing.NEEDS_YOU,
        ModeloFormOrigin.NOT_IMPORTED_YET: Standing.WAITING,
        ModeloFormOrigin.NOT_CALCULATED_YET: Standing.WAITING,
        ModeloFormOrigin.NOT_APPLICABLE: Standing.DONE,
        ModeloFormOrigin.OVERRIDES_SOURCE: Standing.DONE,
        ModeloFormOrigin.CALCULATED: Standing.DONE,
        ModeloFormOrigin.INFORMATIONAL: Standing.DONE,
        ModeloFormOrigin.IMPORTED: Standing.DONE,
        ModeloFormOrigin.OPTIONAL_EMPTY: Standing.DONE,
        ModeloFormOrigin.CLEARED: Standing.DONE,
        ModeloFormOrigin.ENTERED: Standing.DONE,
    }
)
"""The one classing of every origin that the navigator, the list headings, a grid row and ``n`` share."""

#: Origins that ask the filer to act before the declaration is ready.
NEEDS_ATTENTION: Final[frozenset[ModeloFormOrigin]] = frozenset(
    origin for origin, standing in ORIGIN_STANDINGS.items() if standing is Standing.NEEDS_YOU
)
#: Origins that ask the filer for a value, which neither a filed declaration nor a page that does not apply does.
ASKS_FOR_A_VALUE: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.NEEDS_INPUT, ModeloFormOrigin.DEFAULT_TO_CONFIRM}
)
#: A box the calculation could not produce, wherever it is counted.
FAILED_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.CALCULATION_FAILED]
#: A box waiting on an import, wherever it is counted.
NOT_IMPORTED_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.NOT_IMPORTED_YET]
#: A box waiting on a calculation, wherever it is counted.
NOT_CALCULATED_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.NOT_CALCULATED_YET]


def field_needs_filer(field: ModeloFormField, *, recorded: bool = False, applies: bool = True) -> bool:
    """Whether the filer can act on a box now: a blocker, a value to give or confirm, or a failure to resolve.

    A box waiting on an import or a calculation is not one: running that step
    fills it, not anything the filer types into it. Nothing on a declaration
    recorded as filed is one, and a page that does not apply asks for no value.
    """
    if recorded:
        return False
    if field.blockers:
        return True
    if not applies and field.origin in ASKS_FOR_A_VALUE:
        return False
    return ORIGIN_STANDINGS[field.origin] is Standing.NEEDS_YOU


_DIMMED: Final[str] = "dim"


@dataclass(frozen=True, slots=True)
class AttentionCounts:
    """What one part of the form holds on the one attention scale, most severe first.

    Blockers, missing values, failed calculations and assumed values are to
    do; boxes waiting on an import or a calculation are not to do but are not
    done either; what the last check found worth checking is only counted.
    ``pending`` counts the boxes with anything to do, each once.
    """

    blocks: int = 0
    missing: int = 0
    failed: int = 0
    confirm: int = 0
    not_imported: int = 0
    not_calculated: int = 0
    check: int = 0
    pending: int = 0

    @property
    def to_do(self) -> int:
        """What must be done before filing: blockers, missing, failed and assumed values."""
        return self.blocks + self.missing + self.failed + self.confirm

    @property
    def waiting(self) -> int:
        """The boxes waiting on an import or a calculation."""
        return self.not_imported + self.not_calculated

    def __add__(self, other: AttentionCounts) -> AttentionCounts:
        """Add two parts' counts."""
        return AttentionCounts(
            self.blocks + other.blocks,
            self.missing + other.missing,
            self.failed + other.failed,
            self.confirm + other.confirm,
            self.not_imported + other.not_imported,
            self.not_calculated + other.not_calculated,
            self.check + other.check,
            self.pending + other.pending,
        )

    def _levels(self) -> tuple[tuple[WorkbenchMark, int], ...]:
        return (
            (BLOCKS_MARK, self.blocks),
            (MISSING_MARK, self.missing),
            (FAILED_MARK, self.failed),
            (CONFIRM_MARK, self.confirm),
            (NOT_IMPORTED_MARK, self.not_imported),
            (NOT_CALCULATED_MARK, self.not_calculated),
        )

    @property
    def level(self) -> WorkbenchMark | None:
        """The most severe level present, or ``None`` when nothing is to do and nothing waits."""
        return next((mark for mark, count in self._levels() if count), None)

    @property
    def mark(self) -> WorkbenchMark:
        """The most severe level present, or done only when nothing is to do and nothing waits."""
        level = self.level
        return DONE_MARK if level is None else level

    def chips(self) -> tuple[tuple[WorkbenchMark, int], ...]:
        """The levels to do with anything in them, most severe first."""
        return tuple((mark, count) for mark, count in self._levels()[:4] if count)

    def waiting_chips(self) -> tuple[tuple[WorkbenchMark, int], ...]:
        """The waiting levels with anything in them, imports before calculations."""
        return tuple((mark, count) for mark, count in self._levels()[4:] if count)

    def text(self) -> Text:
        """The counts as compact chips; what waits and what is worth checking dimmed."""
        line = Text(" ".join(f"{mark.glyph}{count}" for mark, count in self.chips()))
        dimmed = [f"{mark.glyph}{count}" for mark, count in self.waiting_chips()]
        if self.check:
            dimmed.append(f"{CHECK_MARK.glyph}{self.check}")
        if dimmed:
            line.append(f"{' ' if line.plain else ''}{' '.join(dimmed)}", style=_DIMMED)
        return line

    def drawn(self) -> tuple[WorkbenchMark, ...]:
        """The marks these counts draw as chips."""
        return (
            *(mark for mark, _ in self.chips()),
            *(mark for mark, _ in self.waiting_chips()),
            *((CHECK_MARK,) if self.check else ()),
        )


_ORIGIN_TALLIES: Final[Mapping[ModeloFormOrigin, str]] = MappingProxyType(
    {
        ModeloFormOrigin.NEEDS_INPUT: "missing",
        ModeloFormOrigin.CALCULATION_FAILED: "failed",
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: "confirm",
        ModeloFormOrigin.NOT_IMPORTED_YET: "not_imported",
        ModeloFormOrigin.NOT_CALCULATED_YET: "not_calculated",
    }
)
"""The level each origin that is not done counts at; the tallies are the fields of :class:`AttentionCounts`."""


def field_counts(
    fields: Iterable[ModeloFormField],
    checked_boxes: Mapping[str, int] | None = None,
    *,
    recorded: bool = False,
    applies: bool = True,
) -> AttentionCounts:
    """Count what the fields hold on the attention scale, with the check findings that name their boxes.

    A declaration recorded as filed has nothing blocking, missing or assumed
    left, and a page that does not apply asks for no value; what failed or
    still waits stays counted on either, since it is a fact about the box,
    not a request.
    """
    checked = checked_boxes or {}
    tallies = dict.fromkeys(("blocks", "missing", "failed", "confirm", "not_imported", "not_calculated"), 0)
    check = pending = 0
    asked = not recorded and applies
    for item in fields:
        if item.blockers and not recorded:
            tallies["blocks"] += 1
        bucket = _ORIGIN_TALLIES.get(item.origin)
        if bucket is not None and (asked or item.origin not in ASKS_FOR_A_VALUE):
            tallies[bucket] += 1
        if field_needs_filer(item, recorded=recorded, applies=applies):
            pending += 1
        if item.box is not None:
            check += checked.get(item.box, 0)
    return AttentionCounts(**tallies, check=check, pending=pending)


#: Editabilities under which the filer may stage a typed value on the field itself.
TYPED_EDITABILITIES: Final[frozenset[ModeloFormEditability]] = frozenset(
    {
        ModeloFormEditability.EDITABLE_VALUE,
        ModeloFormEditability.EDITABLE_OVERRIDE,
        ModeloFormEditability.OVERRIDABLE_SOURCE,
    }
)


#: Origins whose value comes from a source, so their words name the kind of place it is.
SOURCE_WORDED_ORIGINS: Final[tuple[ModeloFormOrigin, ...]] = (
    ModeloFormOrigin.IMPORTED,
    ModeloFormOrigin.NOT_IMPORTED_YET,
    ModeloFormOrigin.OVERRIDES_SOURCE,
)

#: The mark of a value carried from an earlier declaration, in place of the imported glyph.
EARLIER_FILING_GLYPH: Final[str] = EARLIER_FILING_MARK.glyph
#: The mark of a value the official form sets, whether it reaches the box as a design constant or through a binding.
FORM_SET_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.INFORMATIONAL]
_FORM_SET_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.IMPORTED, ModeloFormOrigin.INFORMATIONAL}
)
"""Origins whose value, when the form's own design is the source, is the value the form sets."""
_FORM_SET_WORDS_KEY: Final[str] = "tui.modelo.workbench.origin_source.imported.fixed_by_design"
_HELD_ZERO_LOCALE_KEYS: Final[Mapping[ModeloFormOrigin, str]] = MappingProxyType(
    {ModeloFormOrigin.OPTIONAL_EMPTY: "tui.modelo.workbench.origin_held_zero.optional_empty"}
)
"""Words for an origin that says nobody entered the box, when the box still holds a zero: never "empty"."""
_AEAT_IMPORTED_ON_KEY: Final[str] = "tui.modelo.workbench.origin_source.aeat_imported_on"


def holds_zero(value: ModeloFormScalar) -> bool:
    """Whether a value is an amount of exactly zero: a figure the form holds, which is not the same as nothing."""
    return isinstance(value, Decimal | int) and not isinstance(value, bool) and value == 0


def holds_nothing(value: ModeloFormScalar) -> bool:
    """Whether a box holds no value at all: nothing, an unmarked choice or blank text, but never a zero amount."""
    if value is None or value is False:
        return True
    return isinstance(value, str) and not value.strip()


def set_by_form(field: ModeloFormField) -> bool:
    """Whether the value a field shows is one the official form itself sets."""
    source = field.source
    return field.origin in _FORM_SET_ORIGINS and source is not None and source.family is SourceFamily.FIXED_BY_DESIGN


def aeat_imported_on(form: ModeloWorkForm | None) -> date | None:
    """The day the AEAT tax data the current calculation took values from was imported; ``None`` when not known."""
    data = None if form is None else form.aeat_data
    imported_at = None if data is None else data.imported_at
    if imported_at is None:
        return None
    return imported_at.astimezone().date() if imported_at.tzinfo is not None else imported_at.date()


def _from_aeat_data(field: ModeloFormField) -> bool:
    source = field.source
    return field.origin is ModeloFormOrigin.IMPORTED and source is not None and source.family is SourceFamily.AEAT_DRAFT


_NAMED_FILING_LOCALE_KEYS: Final[Mapping[ModeloFormOrigin, str]] = MappingProxyType(
    {
        ModeloFormOrigin.IMPORTED: "tui.modelo.workbench.origin_source.imported.named_filing",
        ModeloFormOrigin.NOT_IMPORTED_YET: "tui.modelo.workbench.origin_source.not_imported_yet.named_filing",
        ModeloFormOrigin.OVERRIDES_SOURCE: "tui.modelo.workbench.origin_source.overrides_source.named_filing",
    }
)
"""Words for a value tied to one named earlier declaration, per origin; they take ``{modelo}`` and ``{period}``."""


def origin_source_words_key(origin: ModeloFormOrigin, family: SourceFamily) -> str:
    """The catalogue key naming an origin together with the kind of place its value comes from."""
    return f"tui.modelo.workbench.origin_source.{origin.value}.{family.value}"


_FILED_LOCALE_KEYS: Final[Mapping[ModeloFormOrigin, str]] = MappingProxyType(
    {
        ModeloFormOrigin.NEEDS_INPUT: "tui.modelo.workbench.origin_filed.needs_input",
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: "tui.modelo.workbench.origin_filed.default_to_confirm",
    }
)
"""Words for an origin that asks for a value, on a declaration recorded as filed: what the value is, not a request."""


def origin_words(
    field: ModeloFormField,
    *,
    recorded: bool = False,
    aeat_imported: date | None = None,
    language: OutputLanguage | None = None,
) -> str:
    """Say where one field's value stands, in the few words its row, help band and panel share.

    A value from a source names the kind of place, and an earlier declaration by
    its modelo and period when exactly one is known; a value the official form
    sets says so, whatever carries it to the box; any other says its origin. An
    optional box nobody entered that still holds a zero says it was left at
    zero, never that it is empty. On a declaration ``recorded`` as filed nothing
    is asked any more, so a box that would ask for a value says what it holds
    instead. Given the day ``aeat_imported`` the AEAT tax data was imported, a
    value taken from it names that day, written for ``language``. A row too
    narrow for these words keeps only the glyph, so the help band calls this to
    say them for the field under the cursor.
    """
    if recorded and field.origin in _FILED_LOCALE_KEYS:
        return tr(_FILED_LOCALE_KEYS[field.origin])
    if field.origin in _HELD_ZERO_LOCALE_KEYS and holds_zero(field.value):
        return tr(_HELD_ZERO_LOCALE_KEYS[field.origin])
    if set_by_form(field):
        return tr(_FORM_SET_WORDS_KEY)
    if aeat_imported is not None and language is not None and _from_aeat_data(field):
        return tr(_AEAT_IMPORTED_ON_KEY, date=date_text(aeat_imported, language))
    source = field.source
    if field.origin not in SOURCE_WORDED_ORIGINS or source is None:
        return tr(origin_words_key(field.origin))
    if source.family is SourceFamily.EARLIER_FILINGS and len(source.earlier_filings) == 1:
        filing = source.earlier_filings[0]
        return tr(_NAMED_FILING_LOCALE_KEYS[field.origin], modelo=filing.modelo, period=period_words(filing.period))
    return tr(origin_source_words_key(field.origin, source.family))


def origin_glyph(field: ModeloFormField) -> str:
    """The mark a field's origin shows; a value carried from an earlier declaration or set by the form is marked apart.

    A value the form sets draws the form's mark wherever it is shown, so a
    row and the sources view never draw it two ways.
    """
    if set_by_form(field):
        return FORM_SET_MARK.glyph
    source = field.source
    if (
        field.origin is ModeloFormOrigin.IMPORTED
        and source is not None
        and source.family is SourceFamily.EARLIER_FILINGS
    ):
        return EARLIER_FILING_GLYPH
    return ORIGIN_GLYPHS[field.origin]


def origin_text(
    field: ModeloFormField,
    *,
    recorded: bool = False,
    aeat_imported: date | None = None,
    language: OutputLanguage | None = None,
) -> str:
    """The origin glyph followed by its words, as a help band or an editor states it.

    On a declaration ``recorded`` as filed a box that would ask for a value
    draws no glyph, as its row draws none, and says only what it holds.
    ``aeat_imported`` and ``language`` date a value taken from imported AEAT
    tax data, as :func:`origin_words` does.
    """
    if recorded and field.origin in ASKS_FOR_A_VALUE:
        return origin_words(field, recorded=True)
    return f"{origin_glyph(field)} {origin_words(field, aeat_imported=aeat_imported, language=language)}"


NOT_WRITABLE_REASONS: Final[tuple[str, ...]] = (
    *(reason.value for reason in ModeloEditNonWritableReason),
    ABSENT_FROM_ADMISSION,
)
"""Every reason a field that cannot be edited here gives for it."""


def editability_text(field: ModeloFormField) -> str:
    """Say what may be done about a field; one that cannot be edited here says why."""
    if field.editability is ModeloFormEditability.NOT_WRITABLE and field.not_writable_reason is not None:
        return tr(f"tui.modelo.workbench.not_writable.{field.not_writable_reason}")
    return tr(f"tui.modelo.workbench.editability.{field.editability.value}")


def attention_words_key(attention: Attention) -> str:
    """The catalogue key naming one attention mark."""
    return _ATTENTION_WORDS_LOCALE_KEYS[attention]


def _require_closed_and_distinct() -> None:
    """Refuse a vocabulary that misses a state or lets two states share a mark."""
    if set(ORIGIN_GLYPHS) != set(ModeloFormOrigin) or set(ORIGIN_ROLES) != set(ModeloFormOrigin):
        raise ValueError("every origin needs exactly one glyph and one colour role")
    if set(ATTENTION_GLYPHS) != set(Attention) or set(ATTENTION_ROLES) != set(Attention):
        raise ValueError("every attention mark needs exactly one glyph and one colour role")
    if set(_ATTENTION_WORDS_LOCALE_KEYS) != set(Attention):
        raise ValueError("every attention mark needs its words")
    if set(_NAMED_FILING_LOCALE_KEYS) != set(SOURCE_WORDED_ORIGINS):
        raise ValueError("every origin worded by its source needs words for a named earlier declaration")
    if set(ORIGIN_STANDINGS) != set(ModeloFormOrigin):
        raise ValueError("every origin needs exactly one standing")
    if set(_ORIGIN_TALLIES) != {
        origin for origin, standing in ORIGIN_STANDINGS.items() if standing is not Standing.DONE
    }:
        raise ValueError("every origin that is not done needs a level to count at, and only those")
    if set(_FILED_LOCALE_KEYS) != ASKS_FOR_A_VALUE:
        raise ValueError("every origin that asks for a value needs words for a declaration recorded as filed")
    require_one_meaning_per_glyph(WORKBENCH_MARKS)


_require_closed_and_distinct()


__all__ = [
    "ASKS_FOR_A_VALUE",
    "ATTENTION_GLYPHS",
    "ATTENTION_MARKS",
    "ATTENTION_ROLES",
    "BLOCKS_MARK",
    "CHECK_MARK",
    "COLLAPSED_MARK",
    "CONFIRM_MARK",
    "DONE_MARK",
    "EARLIER_FILING_GLYPH",
    "EARLIER_FILING_MARK",
    "EXPANDED_MARK",
    "FAILED_MARK",
    "FORM_SET_MARK",
    "HERE_MARK",
    "INFO_MARK",
    "MISSING_MARK",
    "NEEDS_ATTENTION",
    "NOT_CALCULATED_MARK",
    "NOT_IMPORTED_MARK",
    "NOT_WRITABLE_REASONS",
    "ORIGIN_GLYPHS",
    "ORIGIN_MARKS",
    "ORIGIN_ROLES",
    "ORIGIN_STANDINGS",
    "SOURCE_WORDED_ORIGINS",
    "STALE_MARK",
    "TYPED_EDITABILITIES",
    "WORKBENCH_MARKS",
    "Attention",
    "AttentionCounts",
    "ColourRole",
    "Standing",
    "WorkbenchMark",
    "aeat_imported_on",
    "attention_words_key",
    "editability_text",
    "field_counts",
    "field_needs_filer",
    "holds_nothing",
    "holds_zero",
    "origin_glyph",
    "origin_source_words_key",
    "origin_text",
    "origin_words",
    "origin_words_key",
    "require_one_meaning_per_glyph",
    "set_by_form",
]
