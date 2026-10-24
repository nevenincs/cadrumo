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
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from rich.text import Text

from .....application.modelo.source_policy import SourceFamily
from .....application.modelo.work_form_models import (
    ASKS_FOR_A_VALUE,
    ORIGIN_STANDINGS,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormStanding,
    field_needs_filer,
)
from .....application.modelo.work_form_wording import origin_words, origin_words_key, set_by_form
from .....core.external_constants import OutputLanguage


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
        # Not the imported arrow in a lighter stroke, which reads the same at terminal size: a value still to come.
        ModeloFormOrigin.NOT_IMPORTED_YET: "…",
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


#: A box the calculation could not produce, wherever it is counted.
FAILED_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.CALCULATION_FAILED]
#: A box waiting on an import, wherever it is counted.
NOT_IMPORTED_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.NOT_IMPORTED_YET]
#: A box waiting on a calculation, wherever it is counted.
NOT_CALCULATED_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.NOT_CALCULATED_YET]


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


def _field_attention_increments(
    item: ModeloFormField,
    checked_boxes: Mapping[str, int],
    *,
    asked: bool,
    recorded: bool,
    applies: bool,
) -> tuple[int, str | None, int, int]:
    blocks = int(bool(item.blockers) and not recorded)
    bucket = _ORIGIN_TALLIES.get(item.origin)
    counted_bucket = bucket if bucket is not None and (asked or item.origin not in ASKS_FOR_A_VALUE) else None
    pending = int(field_needs_filer(item, recorded=recorded, applies=applies))
    checked = 0 if item.box is None else checked_boxes.get(item.box, 0)
    return blocks, counted_bucket, pending, checked


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
    checks = checked_boxes or {}
    tallies = dict.fromkeys(("blocks", "missing", "failed", "confirm", "not_imported", "not_calculated"), 0)
    check = pending = 0
    asked = not recorded and applies
    for item in fields:
        blocks, bucket, pending_boxes, checked_count = _field_attention_increments(
            item,
            checks,
            asked=asked,
            recorded=recorded,
            applies=applies,
        )
        tallies["blocks"] += blocks
        if bucket is not None:
            tallies[bucket] += 1
        pending += pending_boxes
        check += checked_count
    return AttentionCounts(**tallies, check=check, pending=pending)


#: Editabilities under which the filer may stage a typed value on the field itself.
TYPED_EDITABILITIES: Final[frozenset[ModeloFormEditability]] = frozenset(
    {
        ModeloFormEditability.EDITABLE_VALUE,
        ModeloFormEditability.EDITABLE_OVERRIDE,
        ModeloFormEditability.OVERRIDABLE_SOURCE,
    }
)


#: The mark of a value carried from an earlier declaration, in place of the imported glyph.
EARLIER_FILING_GLYPH: Final[str] = EARLIER_FILING_MARK.glyph
#: The mark of a value the official form sets, whether it reaches the box as a design constant or through a binding.
FORM_SET_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.INFORMATIONAL]


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


def attention_words_key(attention: Attention) -> str:
    """The catalogue key naming one attention mark."""
    return _ATTENTION_WORDS_LOCALE_KEYS[attention]


def _require_origin_marks() -> None:
    if set(ORIGIN_GLYPHS) != set(ModeloFormOrigin) or set(ORIGIN_ROLES) != set(ModeloFormOrigin):
        raise ValueError("every origin needs exactly one glyph and one colour role")


def _require_attention_marks() -> None:
    if set(ATTENTION_GLYPHS) != set(Attention) or set(ATTENTION_ROLES) != set(Attention):
        raise ValueError("every attention mark needs exactly one glyph and one colour role")
    if set(_ATTENTION_WORDS_LOCALE_KEYS) != set(Attention):
        raise ValueError("every attention mark needs its words")


def _require_attention_counts() -> None:
    if set(ORIGIN_STANDINGS) != set(ModeloFormOrigin):
        raise ValueError("every origin needs exactly one standing")
    expected_tallies = {
        origin for origin, standing in ORIGIN_STANDINGS.items() if standing is not ModeloFormStanding.DONE
    }
    if set(_ORIGIN_TALLIES) != expected_tallies:
        raise ValueError("every origin that is not done needs a level to count at, and only those")


def _require_closed_and_distinct() -> None:
    """Refuse a vocabulary that misses a state or lets two states share a mark."""
    _require_origin_marks()
    _require_attention_marks()
    _require_attention_counts()
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
    "FAILED_MARK",
    "FORM_SET_MARK",
    "HERE_MARK",
    "INFO_MARK",
    "MISSING_MARK",
    "NOT_CALCULATED_MARK",
    "NOT_IMPORTED_MARK",
    "ORIGIN_GLYPHS",
    "ORIGIN_MARKS",
    "ORIGIN_ROLES",
    "STALE_MARK",
    "TYPED_EDITABILITIES",
    "WORKBENCH_MARKS",
    "Attention",
    "AttentionCounts",
    "ColourRole",
    "WorkbenchMark",
    "attention_words_key",
    "field_counts",
    "origin_glyph",
    "origin_text",
    "require_one_meaning_per_glyph",
]
