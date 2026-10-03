"""Issue levels, counts and shared words shown across the workbench."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from textual.content import Content

from .....application.modelo.source_policy import SourceSurface
from .....application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloWorkForm,
    address_key,
    section_fields,
)
from .....core.i18n.render import tr
from .....domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
)
from .casilla_list_models import AddressKey
from .navigator import applicable_fields, presented_form
from .page_items import workbench_pages
from .sources import OpenSourceSurface
from .vocabulary import (
    ATTENTION_ROLES,
    BLOCKS_MARK,
    CHECK_MARK,
    CONFIRM_MARK,
    INFO_MARK,
    MISSING_MARK,
    Attention,
    WorkbenchMark,
)

if TYPE_CHECKING:
    pass


class IssueLevel(StrEnum):
    """The one scale everything the filer should notice is placed on, most urgent first."""

    BLOCKS = "blocks"
    MISSING = "missing"
    CONFIRM = "confirm"
    CHECK = "check"
    INFO = "info"


LEVEL_MARKS: Final[Mapping[IssueLevel, WorkbenchMark]] = MappingProxyType(
    {
        IssueLevel.BLOCKS: BLOCKS_MARK,
        IssueLevel.MISSING: MISSING_MARK,
        IssueLevel.CONFIRM: CONFIRM_MARK,
        IssueLevel.CHECK: CHECK_MARK,
        IssueLevel.INFO: INFO_MARK,
    }
)

"""One mark per level, with its words, from the workbench's one vocabulary of marks."""

TO_DO_LEVELS: Final[frozenset[IssueLevel]] = frozenset({IssueLevel.BLOCKS, IssueLevel.MISSING, IssueLevel.CONFIRM})

_ATTENTION_LEVELS: Final[Mapping[ModeloFormAttention, IssueLevel]] = MappingProxyType(
    {
        ModeloFormAttention.BLOCKS: IssueLevel.BLOCKS,
        ModeloFormAttention.MISSING: IssueLevel.MISSING,
        ModeloFormAttention.CONFIRM: IssueLevel.CONFIRM,
        ModeloFormAttention.CHECK: IssueLevel.CHECK,
        ModeloFormAttention.INFO: IssueLevel.INFO,
    }
)

_DETAIL_LOCALE_KEYS: Final[Mapping[ModeloVerificationFindingKind, str]] = MappingProxyType(
    {
        ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA: (
            "tui.modelo.workbench.issues.detail.missing_required_casilla"
        ),
        ModeloVerificationFindingKind.RECONCILIATION_MISMATCH: (
            "tui.modelo.workbench.issues.detail.reconciliation_mismatch"
        ),
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN: (
            "tui.modelo.workbench.issues.detail.cross_period_dependency_unclean"
        ),
        ModeloVerificationFindingKind.BLOCKING_RULE: "tui.modelo.workbench.issues.detail.blocking_rule",
        ModeloVerificationFindingKind.ADVISORY: "tui.modelo.workbench.issues.detail.advisory",
        ModeloVerificationFindingKind.STALE_CALCULATION: "tui.modelo.workbench.issues.detail.stale_calculation",
    }
)

_VERDICT_LOCALE_KEYS: Final[Mapping[VerificationCompletenessStatus, str]] = MappingProxyType(
    {
        VerificationCompletenessStatus.COMPLETE: "tui.modelo.workbench.issues.verdict.complete",
        VerificationCompletenessStatus.INCOMPLETE: "tui.modelo.workbench.issues.verdict.incomplete",
        VerificationCompletenessStatus.BLOCKED: "tui.modelo.workbench.issues.verdict.blocked",
    }
)

ASSUMED_BOXES_BEFORE_SECTIONS: Final[int] = 20

_UNENTERED_ORIGINS: Final[Mapping[IssueLevel, ModeloFormOrigin]] = MappingProxyType(
    {IssueLevel.MISSING: ModeloFormOrigin.NEEDS_INPUT, IssueLevel.CONFIRM: ModeloFormOrigin.DEFAULT_TO_CONFIRM}
)

"""The levels that list boxes nobody has entered, and the origin that places a box at each."""

_UNENTERED_LOCALE_KEYS: Final[Mapping[IssueLevel, tuple[str, str, str]]] = MappingProxyType(
    {
        IssueLevel.MISSING: (
            "tui.modelo.workbench.issues.missing",
            "tui.modelo.workbench.issues.action.fill",
            "tui.modelo.workbench.issues.action.fill_by_section",
        ),
        IssueLevel.CONFIRM: (
            "tui.modelo.workbench.issues.assumed",
            "tui.modelo.workbench.issues.action.confirm",
            "tui.modelo.workbench.issues.action.confirm_by_section",
        ),
    }
)

"""Per level that lists boxes: what the boxes are, what to do with each, and what to do section by section."""

_BLOCKS_STYLE: Final[str] = f"${ATTENTION_ROLES[Attention.BLOCKED].value}"

"""The style of every blocking mark: the error role the mark registry gives it, as the active theme resolves it."""


@dataclass(frozen=True, slots=True)
class IssueLine:
    """One finding as the filer reads it: where, what is wrong, what to do, and where Enter leads.

    ``key`` names the finding's box when the form shows it, so Enter can go
    there; ``box`` is the official box number, or ``"·"`` when there is none.
    """

    level: IssueLevel
    box: str
    where: str
    message: str
    action: str
    detail: str
    technical: str
    key: AddressKey | None
    #: Whether ``key`` is a value of a table's records, so Enter leads to the table rather than a box.
    in_records: bool = False
    #: The area of the application that owns the finding's value, when one does and can be opened.
    area: SourceSurface | None = None
    #: Whether the latest calculation noticed this, rather than the check.
    from_calculation: bool = False
    #: Whether calculating again is what puts this right, so ``c`` does it from the list.
    recalculates: bool = False
    #: Whether this action inspects the named box through Enter, rather than opening its source area.
    action_targets_box: bool = False

    @property
    def blocking(self) -> bool:
        """Whether this finding stops the declaration from being filed."""
        return self.level is IssueLevel.BLOCKS


@dataclass(frozen=True, slots=True)
class ConfirmAssumedValues:
    """The filer asked, from the findings list, to confirm the assumed values of one part of the form.

    ``at`` is a box in that part: the workbench puts its cursor there and
    offers the assumed values of the box's section, or of its page when the
    page has no sections, exactly as its own bulk confirm does.
    """

    at: AddressKey


@dataclass(frozen=True, slots=True)
class CalculateAgain:
    """The filer asked, from the findings list, to calculate the declaration again."""


type IssuesChoice = AddressKey | OpenSourceSurface | ConfirmAssumedValues | CalculateAgain

"""Where the findings list leads: a box, the area that owns a value, confirming the assumed values, or calculating."""


@dataclass(frozen=True, slots=True)
class UnenteredSection:
    """One section holding boxes nobody entered at one level: its words and those boxes, in form order."""

    title: str
    keys: tuple[AddressKey, ...]


@dataclass(frozen=True, slots=True)
class UnenteredBoxes:
    """The boxes at one level whose value nobody entered, listed as one entry, and the sections that hold them.

    ``level`` is missing or assumed. ``boxes`` are their official numbers and
    ``unnumbered`` counts those that have none; ``keys`` are every one of them
    in form order, the first being where Enter goes.
    """

    level: IssueLevel
    boxes: tuple[str, ...]
    unnumbered: int
    keys: tuple[AddressKey, ...]
    sections: tuple[UnenteredSection, ...]

    @property
    def by_section(self) -> bool:
        """Whether there are too many to list by number, so the list names their sections instead."""
        return len(self.keys) > ASSUMED_BOXES_BEFORE_SECTIONS


_LEVEL_GLYPH_STYLES: Final[tuple[tuple[str, str], ...]] = (
    (r"(?:^|(?<=\s))" + re.escape(BLOCKS_MARK.glyph) + r"(?=\s)", _BLOCKS_STYLE),
    (r"(?:^|(?<=\s))" + re.escape(MISSING_MARK.glyph) + r"(?=\s)", _BLOCKS_STYLE),
    (r"(?:^|(?<=\s))" + re.escape(CONFIRM_MARK.glyph) + r"(?=\s)", "$warning"),
    (r"(?:^|(?<=\s))" + re.escape(CHECK_MARK.glyph) + r"(?=\s)", "$warning"),
    (r"^" + re.escape(INFO_MARK.glyph) + r"(?=\s)|(?<=\s)" + re.escape(INFO_MARK.glyph) + r"(?=\s\d)", "$secondary"),
)

"""Each level's glyph where it marks a level, in its one colour: what blocks and what is missing as an error,
what is assumed and what is worth checking as a warning, what is for information muted."""


def levels_marked(text: str) -> Content:
    """``text`` as a heading, a title or a chip draws it: each level's glyph in that level's colour.

    Only a glyph standing on its own is a mark: the information mark only
    where it opens the text or stands before a count, so a word "i" in prose
    is never coloured.
    """
    content = Content(text)
    for pattern, style in _LEVEL_GLYPH_STYLES:
        content = content.highlight_regex(pattern, style=style)
    return content


def blocks_marked(text: str) -> Content:
    """``text`` as drawn, every blocking mark in it in the theme's error colour."""
    return Content(text).highlight_regex(re.escape(BLOCKS_MARK.glyph), style=_BLOCKS_STYLE)


def issue_level(issue: ModeloFormIssue) -> IssueLevel:
    """Place one finding on the scale by the attention the form gives it."""
    return _ATTENTION_LEVELS[issue.attention]


def _unentered_sections(form: ModeloWorkForm, wanted: frozenset[AddressKey]) -> tuple[UnenteredSection, ...]:
    """The sections holding the wanted boxes, under the words the navigator shows them with."""
    sections: list[UnenteredSection] = []
    for page in workbench_pages(presented_form(form)):
        parts = [(section.heading.text, section_fields(section)) for section in page.sections]
        if page.details:
            parts.append((page.heading.text, page.details))
        for title, fields in parts:
            keys = tuple(key for key in (address_key(field.address) for field in fields) if key in wanted)
            if keys:
                sections.append(UnenteredSection(title=title, keys=keys))
    return tuple(sections)


def unentered_boxes(form: ModeloWorkForm, level: IssueLevel) -> UnenteredBoxes | None:
    """The missing or assumed boxes the header counts, or ``None`` when none waits for the filer.

    A box on a page that does not apply this period is not asked for, and a
    declaration recorded as filed asks for nothing more, so neither lists any.
    """
    origin = _UNENTERED_ORIGINS[level]
    if form.filing is not None:
        return None
    fields = [field for field in applicable_fields(form) if field.origin is origin]
    if not fields:
        return None
    keys = tuple(address_key(field.address) for field in fields)
    return UnenteredBoxes(
        level=level,
        boxes=tuple(field.box for field in fields if field.box),
        unnumbered=sum(1 for field in fields if not field.box),
        keys=keys,
        sections=_unentered_sections(form, frozenset(keys)),
    )


def unentered_levels(form: ModeloWorkForm) -> tuple[UnenteredBoxes, ...]:
    """The missing boxes, then the assumed ones, each only when there are any."""
    return tuple(boxes for level in _UNENTERED_ORIGINS if (boxes := unentered_boxes(form, level)) is not None)


def level_counts(lines: tuple[IssueLine, ...], unentered: tuple[UnenteredBoxes, ...] = ()) -> Mapping[IssueLevel, int]:
    """How many things sit at each level; missing and assumed values count one per box."""
    counts = dict.fromkeys(IssueLevel, 0)
    for line in lines:
        counts[line.level] += 1
    for boxes in unentered:
        counts[boxes.level] += len(boxes.keys)
    return MappingProxyType(counts)


def level_words(level: IssueLevel) -> str:
    """One level's glyph and words, as every surface shows it."""
    mark = LEVEL_MARKS[level]
    return f"{mark.glyph} {tr(mark.translation_key)}"


def title_text(counts: Mapping[IssueLevel, int], *, recorded: bool = False) -> str:
    """The list's name followed by a count for each level that has anything in it.

    A declaration recorded as filed has nothing left to do, so its title counts
    only what is worth checking and what is for information.
    """
    chips = "   ".join(
        f"{LEVEL_MARKS[level].glyph} {count}"
        for level, count in counts.items()
        if count and not (recorded and level in TO_DO_LEVELS)
    )
    title = tr("tui.modelo.workbench.issues.title")
    return f"{title}   {chips}" if chips else title


def verdict_text(form: ModeloWorkForm, *, changes_unapplied: bool = False) -> str:
    """Say what the last check concluded, or that the declaration has not been checked."""
    if form.verification is None:
        return tr("tui.modelo.workbench.issues.verdict.none")
    if changes_unapplied and form.verification is VerificationCompletenessStatus.COMPLETE:
        return tr("tui.modelo.workbench.issues.verdict.saved_with_changes")
    return tr(_VERDICT_LOCALE_KEYS[form.verification])


def _require_total_tables() -> None:
    """Refuse a scale or a finding kind that has no mark, level or sentence."""
    if set(LEVEL_MARKS) != set(IssueLevel):
        raise ValueError("every issue level needs one mark")
    if set(_ATTENTION_LEVELS) != set(ModeloFormAttention):
        raise ValueError("every attention the form gives a finding needs a level")
    if set(_DETAIL_LOCALE_KEYS) != set(ModeloVerificationFindingKind):
        raise ValueError("every finding kind needs a detail")
    if set(_UNENTERED_LOCALE_KEYS) != set(_UNENTERED_ORIGINS):
        raise ValueError("every level that lists boxes nobody entered needs its sentences")


_require_total_tables()

__all__ = (
    "ASSUMED_BOXES_BEFORE_SECTIONS",
    "LEVEL_MARKS",
    "TO_DO_LEVELS",
    "CalculateAgain",
    "ConfirmAssumedValues",
    "IssueLevel",
    "IssueLine",
    "IssuesChoice",
    "UnenteredBoxes",
    "UnenteredSection",
    "blocks_marked",
    "issue_level",
    "level_counts",
    "level_words",
    "levels_marked",
    "title_text",
    "unentered_boxes",
    "unentered_levels",
    "verdict_text",
)
