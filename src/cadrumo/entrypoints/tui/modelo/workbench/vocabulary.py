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
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from .....application.modelo.edit_models import ModeloEditNonWritableReason
from .....application.modelo.source_policy import SourceFamily
from .....application.modelo.work_form_models import (
    ABSENT_FROM_ADMISSION,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
)
from .....core.i18n.render import tr
from .wording import period_words


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


#: Origins that ask the filer to act before the declaration is ready.
NEEDS_ATTENTION: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {
        ModeloFormOrigin.NEEDS_INPUT,
        ModeloFormOrigin.DEFAULT_TO_CONFIRM,
        ModeloFormOrigin.CALCULATION_FAILED,
        ModeloFormOrigin.NOT_IMPORTED_YET,
    }
)

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


def origin_words(field: ModeloFormField) -> str:
    """Say where one field's value stands, in the few words its row and help band share.

    A value from a source names the kind of place, and an earlier declaration by
    its modelo and period when exactly one is known; any other says its origin.
    A row too narrow for these words keeps only the glyph, so the help band
    calls this to say them for the field under the cursor.
    """
    source = field.source
    if field.origin not in SOURCE_WORDED_ORIGINS or source is None:
        return tr(origin_words_key(field.origin))
    if source.family is SourceFamily.EARLIER_FILINGS and len(source.earlier_filings) == 1:
        filing = source.earlier_filings[0]
        return tr(_NAMED_FILING_LOCALE_KEYS[field.origin], modelo=filing.modelo, period=period_words(filing.period))
    return tr(origin_source_words_key(field.origin, source.family))


def origin_glyph(field: ModeloFormField) -> str:
    """The mark a field's origin shows, with a value carried from an earlier declaration marked apart."""
    source = field.source
    if (
        field.origin is ModeloFormOrigin.IMPORTED
        and source is not None
        and source.family is SourceFamily.EARLIER_FILINGS
    ):
        return EARLIER_FILING_GLYPH
    return ORIGIN_GLYPHS[field.origin]


def origin_text(field: ModeloFormField) -> str:
    """The origin glyph followed by its words, as a help band or an editor states it."""
    return f"{origin_glyph(field)} {origin_words(field)}"


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
    require_one_meaning_per_glyph(WORKBENCH_MARKS)


_require_closed_and_distinct()


__all__ = [
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
    "HERE_MARK",
    "INFO_MARK",
    "MISSING_MARK",
    "NEEDS_ATTENTION",
    "NOT_WRITABLE_REASONS",
    "ORIGIN_GLYPHS",
    "ORIGIN_MARKS",
    "ORIGIN_ROLES",
    "SOURCE_WORDED_ORIGINS",
    "STALE_MARK",
    "TYPED_EDITABILITIES",
    "WORKBENCH_MARKS",
    "Attention",
    "ColourRole",
    "WorkbenchMark",
    "attention_words_key",
    "editability_text",
    "origin_glyph",
    "origin_source_words_key",
    "origin_text",
    "origin_words",
    "origin_words_key",
    "require_one_meaning_per_glyph",
]
