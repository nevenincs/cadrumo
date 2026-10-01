"""Everything the filer should look at before filing, on one scale, with a way to act on each.

The list gathers the last check's findings and the boxes the filer still has
to fill in or confirm, grouped by one scale of levels, each with its glyph and
words: what blocks filing first, then the missing values the header counts,
then the assumed values waiting for the filer's confirmation, then what is
worth checking, then what is only for the filer's information. A finding takes
its level from the form, which places it on that scale. The title line counts
each level that has anything in it, so the check's verdict below it says what
the check concluded without a count.

Every finding reads in three parts, all wrapped and never cut: where it is (a
box, or the whole declaration), what is wrong (the finding's own catalogue
message, rendered from its key and facts), and what to do (the sentence the
form names for that finding). The missing values are one entry, and the
assumed values another, listing their box numbers in at most two lines, then
how many more there are; past twenty boxes the entry lists the sections that
hold them, with a count each, instead. Both count exactly the boxes the header
counts: none on a page that does not apply this period.

A declaration recorded as filed asks nothing more of the filer: its list has
no missing or assumed values and counts nothing left to do.

A required value that is missing sits with the missing values rather than
with what blocks filing, since giving it is all it asks; a box the missing
values already list is not listed a second time for its finding. A finding
about one value of a table's records, such as a Modelo 349 operator's country
code, is named by that value's heading, says whether the table has any records,
and says to change them where they come from.

What the latest calculation noticed joins the check's findings on the same
scale and in the same three parts, worded from the catalogue by its reason,
without repeating a finding about the same box and cause. While the
calculation is out of date the list says its notes come from the last
calculation; on a declaration opened afresh, whose calculation this session
did not run, it says to calculate again to see them.

Every fact in a finding's sentence reads in words: a period by its name, a date
in the language's order, an amount with the language's marks, a box by its
number or the words the form gives it. Every blocking mark is drawn in the
theme's error colour.

Enter always acts. A finding that names a box on the form, the missing or
assumed values and each of their sections return the first such box to the
workbench, and a finding about a table's records returns the value's address,
which leads to the table; a finding about the whole declaration opens its
detail in place; a finding whose box is not on the form says so there. A
finding whose value comes from another area of the application, such as the
filer's records or profile, offers ``a`` to open that area, and while assumed
values wait ``b`` offers to confirm those of the selected row's section, or
page, as the workbench's own bulk confirm does; either closes the list with
that choice for the workbench to act on. Codes, facts and legal references never
reach the list: ``t`` shows them for the selected finding only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final, override

from rich.cells import cell_len
from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, OptionList, Static
from textual.widgets.option_list import Option

from .....application.modelo.calculation_notes import (
    RECORDS_REASONS,
    REOPEN_HINT_LOCALE_KEY,
    STALE_LOCALE_KEY,
    what_locale_key,
    what_to_do_locale_key,
)
from .....application.modelo.finding_message_text import finding_message_text
from .....application.modelo.source_policy import SourceSurface
from .....application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormCalculationNote,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloFormRepeatingBlock,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
    section_fields,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from .....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
)
from ...components.theme import tokenised
from .casilla_list import AddressKey
from .dialog_width import fit_dialog_height, fit_dialog_width
from .editor import area_words, open_area_target
from .keys import describe_bindings
from .navigator import applicable_fields, presented_form
from .page_items import workbench_pages
from .sources import BoxNumbers, OpenSourceSurface
from .status_bar import StatusBar
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
    from .header import StatusLine


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

#: Levels that count as something left to do; a declaration recorded as filed counts none of them.
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
_ENTER_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "go": "tui.modelo.workbench.issues.go_to_box",
        "records": "tui.modelo.workbench.issues.open_records",
        "section": "tui.modelo.workbench.issues.open_section",
        "more": "tui.modelo.workbench.issues.key.more",
        "less": "tui.modelo.workbench.issues.key.less",
    }
)
_SCREEN_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "escape": "tui.modelo.workbench.key.back",
        "t": "tui.modelo.workbench.issues.technical",
        "b": "tui.modelo.workbench.key.confirm_section",
    }
)
_CONFIRM_SCOPE_KEY: Final[str] = "b"
_CALCULATE_KEY: Final[str] = "c"
_OPEN_AREA_KEY: Final[str] = "a"
_CONFIRM_SCOPE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.confirm_all"
"""What ``b`` does, in full, where the list has room to say it; the footer says it in two words."""
_FOOTER_PRIORITY: Final[tuple[str, ...]] = ("enter", "escape", "a", _CONFIRM_SCOPE_KEY, "t")
"""The list's footer keys, most needed first; those that do not fit the width are left to the help."""
_FOOTER_KEY_GAP: Final[int] = 1
_OPEN_AREA_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.open_area"
_BOX_NUMBER: Final[re.Pattern[str]] = re.compile(r"\d{1,4}[A-Z]?")
#: Past this many missing or assumed boxes the list names the sections that hold them instead of their numbers.
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
_BOXES_SUFFIX: Final[str] = "-boxes"
_INTRO_SUFFIX: Final[str] = "-intro"
_SECTION_INFIX: Final[str] = "-section-"
_ISSUE_ID_PREFIX: Final[str] = "issue-"
_INDENT: Final[int] = 2
_BLOCKS_STYLE: Final[str] = f"${ATTENTION_ROLES[Attention.BLOCKED].value}"
"""The style of every blocking mark: the error role the mark registry gives it, as the active theme resolves it."""
_RECORDS_NONE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.records.none"
_RECORDS_FIELD_MISSING_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.records.field_missing"
_RECORDS_ACTION_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.action.records_at_source"
_RECORD_VALUE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.where.record_value"
_RECORDS_WHERE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.where.records"
_UNNUMBERED_BOX_LOCALE_KEY: Final[str] = "application.modelo.finding_fact.box_unnumbered"
_STALE_ID: Final[str] = "calculation-stale"
_REOPEN_ID: Final[str] = "calculation-reopen"
"""Where a finding about the filer's records, rather than a box, sits: in those records."""


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


@dataclass(frozen=True, slots=True)
class _RecordValue:
    """One value every record of a table carries: its heading and whether the table holds any record."""

    heading: str
    has_records: bool


def _record_values(form: ModeloWorkForm) -> dict[str, _RecordValue]:
    """Every value a table of records carries, by the casilla its column shows."""
    values: dict[str, _RecordValue] = {}
    for page in form.pages:
        for section in page.sections:
            for block in section.blocks:
                if not isinstance(block, ModeloFormRepeatingBlock):
                    continue
                for column, casilla_id in zip(block.columns, block.column_casilla_ids, strict=True):
                    if casilla_id is None:
                        continue
                    heading = (
                        tr(_RECORD_VALUE_LOCALE_KEY)
                        if column.heading.disclosure is ModeloFormTextDisclosure.TECHNICAL
                        else column.heading.text
                    )
                    values.setdefault(casilla_id, _RecordValue(heading=heading, has_records=bool(block.rows)))
    return values


def _box_words(form: ModeloWorkForm, records: Mapping[str, _RecordValue]) -> dict[str, str]:
    """How a finding's sentence names each box: its printed number, else the words the form shows it with."""
    words = {casilla_id: value.heading for casilla_id, value in records.items()}
    for field in form.fields():
        if not isinstance(field.address, ModeloFormCasillaAddressV1):
            continue
        if field.box:
            words[str(field.address.casilla_id)] = field.box
        elif field.label.disclosure is not ModeloFormTextDisclosure.TECHNICAL:
            words.setdefault(str(field.address.casilla_id), field.label.text)
    return words


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


def _field_name(field: ModeloFormField) -> str:
    parts: list[str] = [f"[{field.box}]"] if field.box else []
    if field.label.disclosure is not ModeloFormTextDisclosure.TECHNICAL:
        parts.append(field.label.text)
    return " ".join(parts)


def technical_text(finding: ModeloVerificationFinding) -> str:
    """The finding's codes, facts and references, for the filer who asks for technical details."""
    codes = [
        finding.kind.value,
        finding.severity.value,
        *([] if finding.casilla_id is None else [str(finding.casilla_id)]),
        *([] if finding.expectation_id is None else [str(finding.expectation_id)]),
        *(f"{name}={value}" for name, value in finding.message_facts.items()),
        *(str(ref) for ref in finding.legal_refs),
        *(str(ref) for ref in finding.source_refs),
        finding.message_locale_key,
    ]
    label = tr("tui.modelo.workbench.issues.technical")
    return f"{label}: {' · '.join(codes)}"


def _not_on_form(finding_box: str | None, casilla_id: str) -> tuple[str, str, str]:
    """The box column, where words and detail of a finding whose box the form does not show."""
    number = finding_box or (casilla_id if _BOX_NUMBER.fullmatch(casilla_id) else None)
    if number is None:
        return "·", tr("tui.modelo.workbench.issues.where.not_on_form"), ""
    return number, f"[{number}]", tr("tui.modelo.workbench.issues.box_not_on_form", box=f"[{number}]")


def _record_issue_line(issue: ModeloFormIssue, value: _RecordValue, *, message: str) -> IssueLine:
    """A finding about one value of a table's records, named by that value's heading, leading to the table."""
    finding = issue.finding
    action_key = issue.action_locale_key
    if finding.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA:
        message = tr(_RECORDS_FIELD_MISSING_LOCALE_KEY if value.has_records else _RECORDS_NONE_LOCALE_KEY)
        action_key = _RECORDS_ACTION_LOCALE_KEY
    key = None if finding.casilla_id is None else address_key(ModeloFormCasillaAddressV1(casilla_id=finding.casilla_id))
    return IssueLine(
        level=issue_level(issue),
        box="·",
        where=value.heading,
        message=message,
        action=tr("tui.modelo.workbench.issues.what_to_do", action=tr(action_key)),
        detail=tr(_DETAIL_LOCALE_KEYS[finding.kind]),
        technical=technical_text(finding),
        key=key,
        in_records=True,
    )


def _note_line(
    note: ModeloFormCalculationNote,
    *,
    on_pages: Mapping[AddressKey, ModeloFormField],
    box_words: Mapping[str, str],
) -> IssueLine:
    """One thing the latest calculation noticed, in the same three parts as a finding."""
    casilla_id = None if note.casilla_id is None else str(note.casilla_id)
    candidate = None if casilla_id is None else address_key(ModeloFormCasillaAddressV1(casilla_id=casilla_id))
    field = None if candidate is None else on_pages.get(candidate)
    named = None if casilla_id is None else (note.box or box_words.get(casilla_id))
    box_text = named or tr(_UNNUMBERED_BOX_LOCALE_KEY)
    if field is not None:
        where = _field_name(field) or f"[{note.box}]"
    elif note.box is not None:
        where = f"[{note.box}]"
    elif note.reason in RECORDS_REASONS:
        where = tr(_RECORDS_WHERE_LOCALE_KEY)
    else:
        where = tr("tui.modelo.workbench.issues.where.declaration")
    technical_codes = [note.reason, *([] if casilla_id is None else [casilla_id])]
    return IssueLine(
        level=_ATTENTION_LEVELS[note.attention],
        box=note.box or "·",
        where=where,
        message=tr(what_locale_key(note.reason), box=box_text),
        action=tr(
            "tui.modelo.workbench.issues.what_to_do", action=tr(what_to_do_locale_key(note.reason), box=box_text)
        ),
        detail="",
        technical=f"{tr('tui.modelo.workbench.issues.technical')}: {' · '.join(technical_codes)}",
        key=candidate if field is not None else None,
        area=SourceSurface.LEDGER if note.reason in RECORDS_REASONS else None,
        from_calculation=True,
    )


def issue_lines(form: ModeloWorkForm) -> tuple[IssueLine, ...]:
    """The form's findings on the scale, most urgent first, each rendered in the filer's language.

    A missing value's finding whose box the missing values already list is
    left out: that entry names the box, and Enter there leads to it.
    """
    language = OutputLanguage(output_language())
    shown = {address_key(field.address): field for field in form.fields()}
    on_pages = frozenset(
        address_key(field.address) for page in workbench_pages(presented_form(form)) for field in page.fields()
    )
    records = _record_values(form)
    box_words = _box_words(form, records)
    missing = unentered_boxes(form, IssueLevel.MISSING)
    listed = frozenset(() if missing is None else missing.keys)
    lines: list[IssueLine] = []
    for issue in form.issues:
        finding = issue.finding
        message = finding_message_text(finding, language, box_words=box_words)
        detail = tr(_DETAIL_LOCALE_KEYS[finding.kind])
        key: AddressKey | None = None
        box = issue.box or "·"
        field: ModeloFormField | None = None
        if finding.casilla_id is None:
            where = tr(
                _RECORDS_WHERE_LOCALE_KEY
                if finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION
                else "tui.modelo.workbench.issues.where.declaration"
            )
        else:
            candidate = address_key(ModeloFormCasillaAddressV1(casilla_id=finding.casilla_id))
            record = records.get(str(finding.casilla_id))
            if record is not None:
                lines.append(_record_issue_line(issue, record, message=message))
                continue
            if issue_level(issue) is IssueLevel.MISSING and candidate in listed:
                continue
            field = shown.get(candidate)
            if field is None or candidate not in on_pages:
                # A box the form defines but shows on no page reads as not on the form, with its number when it has one.
                box, where, not_shown = _not_on_form(
                    issue.box or (None if field is None else field.box), str(finding.casilla_id)
                )
                detail = f"{not_shown} {detail}".strip()
            else:
                key = candidate
                box = field.box or box
                where = _field_name(field) or f"[{box}]"
        lines.append(
            IssueLine(
                level=issue_level(issue),
                box=box,
                where=where,
                message=message,
                action=tr("tui.modelo.workbench.issues.what_to_do", action=tr(issue.action_locale_key)),
                detail=detail,
                technical=technical_text(finding),
                key=key,
                area=None if field is None else open_area_target(field),
                recalculates=finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION,
            )
        )
    pages = {
        address_key(field.address): field for page in workbench_pages(presented_form(form)) for field in page.fields()
    }
    lines.extend(_note_line(note, on_pages=pages, box_words=box_words) for note in form.calculation_notes)
    order = tuple(IssueLevel)
    return tuple(sorted(lines, key=lambda line: order.index(line.level)))


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


def verdict_text(form: ModeloWorkForm) -> str:
    """Say what the last check concluded, or that the declaration has not been checked."""
    if form.verification is None:
        return tr("tui.modelo.workbench.issues.verdict.none")
    return tr(_VERDICT_LOCALE_KEYS[form.verification])


def _entry(*parts: RenderableType | None) -> RenderableType:
    """Wrap each part of an entry under its level heading."""
    return Padding(Group(*(part for part in parts if part is not None)), (0, 0, 0, _INDENT))


def _paragraph(text: str, style: str = "") -> Text | None:
    return Text(text, style=style) if text else None


def _issue_prompt(line: IssueLine, *, expanded: bool, technical: bool) -> RenderableType:
    action = None if line.level is IssueLevel.INFO else _action_with_key(line)
    return _entry(
        _paragraph(line.where, "bold"),
        _paragraph(line.message),
        _paragraph(action or "", "italic"),
        _paragraph(line.detail) if expanded else None,
        _paragraph(line.technical, "dim") if technical else None,
    )


def _action_with_key(line: IssueLine) -> str:
    """What to do, with the key that does it from this list where there is one."""
    if line.recalculates:
        return f"{line.action} [{_CALCULATE_KEY}]"
    if line.area is not None:
        return f"{line.action} [{_OPEN_AREA_KEY}]"
    return line.action


def _what_to_do(key: str) -> Text | None:
    return _paragraph(tr("tui.modelo.workbench.issues.what_to_do", action=tr(key)), "italic")


def _unentered_prompt(boxes: UnenteredBoxes) -> RenderableType:
    what, action, _ = _UNENTERED_LOCALE_KEYS[boxes.level]
    unnumbered = tr("tui.modelo.workbench.issues.where.unnumbered", count=boxes.unnumbered) if boxes.unnumbered else ""
    return _entry(
        BoxNumbers(boxes.boxes, style="bold") if boxes.boxes else None,
        _paragraph(unnumbered, "bold"),
        _paragraph(tr(what)),
        _what_to_do(action),
        _confirm_key_line(boxes),
    )


def _unentered_intro(boxes: UnenteredBoxes) -> RenderableType:
    what, _, by_section = _UNENTERED_LOCALE_KEYS[boxes.level]
    return _entry(_paragraph(tr(what)), _what_to_do(by_section), _confirm_key_line(boxes))


def _confirm_key_line(boxes: UnenteredBoxes) -> Text | None:
    """Under the assumed values, the key that confirms those of a part of the form, in full words."""
    if boxes.level is not IssueLevel.CONFIRM:
        return None
    return _paragraph(f"[{_CONFIRM_SCOPE_KEY}] {tr(_CONFIRM_SCOPE_LOCALE_KEY)}", "italic")


def _section_prompt(section: UnenteredSection) -> RenderableType:
    return _entry(_paragraph(f"{section.title} ({len(section.keys)})", "bold"))


class _IssueList(OptionList):
    """The grouped list, able to describe its own Enter key."""

    def describe_enter(self, locale_key: str) -> None:
        describe_bindings(self._bindings.key_to_bindings, {"enter": locale_key})
        self.refresh_bindings()

    def enter_binding(self) -> Binding | None:
        """Its Enter key's binding, with what it now says."""
        entries = self._bindings.key_to_bindings.get("enter")
        return entries[0] if entries else None

    def show_enter(self, shown: bool) -> None:
        """Show or leave out its Enter key in the footer, keeping what it says."""
        table = self._bindings.key_to_bindings
        entries = table.get("enter")
        if entries:
            table["enter"] = [replace(binding, show=shown) for binding in entries]
            self.refresh_bindings()


class WorkbenchIssuesScreen(ModalScreen[IssuesChoice | None]):
    """Everything to look at before filing; choosing a box returns it to the workbench."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        WorkbenchIssuesScreen #issues-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        WorkbenchIssuesScreen #issues-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        WorkbenchIssuesScreen.-narrow #issues-panel {
            width: 100%;
        }
        WorkbenchIssuesScreen.-short #issues-panel {
            height: 100%;
        }
        WorkbenchIssuesScreen #issues-status {
            color: $foreground;
            margin-bottom: $cadrumo-stack;
        }
        WorkbenchIssuesScreen #issues-title {
            text-style: bold;
            color: $foreground;
        }
        WorkbenchIssuesScreen #issues-verdict {
            color: $secondary;
            margin-bottom: $cadrumo-stack;
        }
        WorkbenchIssuesScreen #issues-list {
            height: 1fr;
        }
        WorkbenchIssuesScreen #issues-list > .option-list--option-disabled {
            color: $foreground;
        }
        WorkbenchIssuesScreen #issues-list > .option-list--option-highlighted,
        WorkbenchIssuesScreen #issues-list:focus > .option-list--option-highlighted {
            background: $panel;
            color: $foreground;
            text-style: bold;
        }
        WorkbenchIssuesScreen #issues-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        """
    )

    BINDINGS: ClassVar = [
        Binding("escape", "close", "", show=False),
        Binding("t", "technical", "", show=False),
        Binding("c", "calculate", "", show=False),
        Binding("a", "open_area", "", show=False),
        Binding("b", "confirm_scope", "", show=False),
    ]

    def __init__(self, form: ModeloWorkForm, *, status_line: StatusLine | None = None) -> None:
        """Hold the form whose findings and missing and assumed values are listed.

        ``status_line`` is shown above everything else when given, so the
        declaration's result and deadline stay in view while the dialog covers
        the workbench's header.
        """
        super().__init__()
        self._form = form
        self._status_line = status_line
        self._recorded = form.filing is not None
        self._lines = issue_lines(form)
        self._unentered = {boxes.level: boxes for boxes in unentered_levels(form)}
        self._expanded: set[int] = set()
        self._technical: set[int] = set()

    @override
    def compose(self) -> ComposeResult:
        with Container(id="issues-backdrop"), Vertical(id="issues-panel"):
            if self._status_line is not None:
                yield StatusBar(self._status_line, id="issues-status")
            title = title_text(level_counts(self._lines, tuple(self._unentered.values())), recorded=self._recorded)
            yield Static(levels_marked(title), id="issues-title", markup=False)
            yield Static(verdict_text(self._form), id="issues-verdict", markup=False)
            yield _IssueList(*self._options(), id="issues-list")
            with Horizontal(id="issues-actions"):
                yield Button(tr("tui.modelo.workbench.result_diff.close"), id="issues-close", variant="primary")
        yield Footer(compact=True)

    @staticmethod
    def _unentered_options(boxes: UnenteredBoxes) -> list[Option]:
        level = boxes.level.value
        if not boxes.by_section:
            return [Option(_unentered_prompt(boxes), id=f"{level}{_BOXES_SUFFIX}")]
        return [
            Option(_unentered_intro(boxes), id=f"{level}{_INTRO_SUFFIX}", disabled=True),
            *(
                Option(_section_prompt(section), id=f"{level}{_SECTION_INFIX}{index}")
                for index, section in enumerate(boxes.sections)
            ),
        ]

    def _options(self) -> list[Option]:
        options: list[Option] = []
        for level in IssueLevel:
            indexed = [(index, line) for index, line in enumerate(self._lines) if line.level is level]
            unentered = self._unentered.get(level)
            count = len(indexed) + (0 if unentered is None else len(unentered.keys))
            if not count:
                continue
            heading = level_words(level)
            if not (self._recorded and level in TO_DO_LEVELS):
                heading = f"{heading} ({count})"
            options.append(Option(levels_marked(heading).stylize("bold"), id=f"level-{level.value}", disabled=True))
            if unentered is not None:
                options.extend(self._unentered_options(unentered))
            options.extend(
                Option(_issue_prompt(line, expanded=False, technical=False), id=f"{_ISSUE_ID_PREFIX}{index}")
                for index, line in indexed
            )
        if self._form.calculation_notes and self._form.calculation_out_of_date:
            options.insert(0, Option(Text(tr(STALE_LOCALE_KEY), style="italic"), id=_STALE_ID, disabled=True))
        if self._reopen_hint():
            options.append(Option(Text(tr(REOPEN_HINT_LOCALE_KEY), style="italic"), id=_REOPEN_ID, disabled=True))
        if not options:
            options.append(Option(tr("tui.modelo.workbench.issues.empty"), id="empty", disabled=True))
        return options

    def _reopen_hint(self) -> bool:
        """Whether this session did not run the latest calculation, so its passing notes are not known here."""
        form = self._form
        return not form.calculation_notes_held and form.calculation_revision_id is not None and not self._recorded

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal, and the whole height on a short one."""
        fit_dialog_width(self, event.size.width)
        fit_dialog_height(self, event.size.height)
        if self.is_mounted:
            self._fit_footer()

    def on_mount(self) -> None:
        """Describe the keys and give the list the focus, on its first entry, with its group heading in view."""
        fit_dialog_width(self, self.app.size.width)
        fit_dialog_height(self, self.app.size.height)
        describe_bindings(self._bindings.key_to_bindings, _SCREEN_LOCALE_KEYS)
        self.refresh_bindings()
        issues = self.query_one(_IssueList)
        issues.focus()
        self._describe_enter()
        # The first entry sits under its group heading: start at the top so the heading says what it is.
        self.call_after_refresh(issues.scroll_home, animate=False, immediate=True)

    def _issue_index(self, option_id: str | None) -> int | None:
        if option_id is None or not option_id.startswith(_ISSUE_ID_PREFIX):
            return None
        index = int(option_id.removeprefix(_ISSUE_ID_PREFIX))
        return index if index < len(self._lines) else None

    def _section(self, option_id: str | None) -> UnenteredSection | None:
        if option_id is None:
            return None
        for boxes in self._unentered.values():
            prefix = f"{boxes.level.value}{_SECTION_INFIX}"
            if option_id.startswith(prefix):
                index = int(option_id.removeprefix(prefix))
                return boxes.sections[index] if index < len(boxes.sections) else None
        return None

    def _listed(self, option_id: str | None) -> UnenteredBoxes | None:
        """The missing or assumed boxes an entry lists by number, when it is that entry."""
        return next(
            (boxes for boxes in self._unentered.values() if option_id == f"{boxes.level.value}{_BOXES_SUFFIX}"),
            None,
        )

    def _highlighted_id(self) -> str | None:
        issues = self.query_one(_IssueList)
        if issues.highlighted is None:
            return None
        return issues.get_option_at_index(issues.highlighted).id

    def _describe_enter(self) -> None:
        option_id = self._highlighted_id()
        index = self._issue_index(option_id)
        if self._section(option_id) is not None:
            choice = "section"
        elif index is not None and self._lines[index].in_records:
            choice = "records"
        elif self._listed(option_id) is not None or (index is not None and self._lines[index].key is not None):
            choice = "go"
        elif index is not None and index in self._expanded:
            choice = "less"
        else:
            choice = "more"
        self.query_one(_IssueList).describe_enter(_ENTER_LOCALE_KEYS[choice])
        self._describe_open_area(None if index is None else self._lines[index].area)
        self._fit_footer()

    def _fit_footer(self) -> None:
        """Show the keys that fit the footer side by side, most needed first, so none is cut at the edge."""
        issues = self.query_one(_IssueList)
        budget = self.app.size.width
        shown: set[str] = set()
        for key in _FOOTER_PRIORITY:
            if key == "enter":
                binding = issues.enter_binding()
            else:
                entries = self._bindings.key_to_bindings.get(key)
                binding = entries[0] if entries else None
            if binding is None or not binding.description:
                continue
            if key == "a" and self._highlighted_area() is None:
                continue
            if key == "b" and self._confirm_target() is None:
                continue
            cost = cell_len(f"{self.app.get_key_display(binding)} {binding.description}") + _FOOTER_KEY_GAP
            if cost > budget:
                break
            shown.add(key)
            budget -= cost
        issues.show_enter("enter" in shown)
        table = self._bindings.key_to_bindings
        for key in ("escape", "a", "b", "t"):
            entries = table.get(key)
            if entries:
                table[key] = [replace(binding, show=key in shown) for binding in entries]
        self.refresh_bindings()

    def _describe_open_area(self, area: SourceSurface | None) -> None:
        """Name the area ``a`` opens for the finding under the cursor, and show the key only when there is one."""
        table = self._bindings.key_to_bindings
        entries = table.get("a")
        if entries:
            label = "" if area is None else tr(_OPEN_AREA_LOCALE_KEY, area=area_words(area))
            table["a"] = [replace(binding, description=label, show=area is not None) for binding in entries]
        self.refresh_bindings()

    def _confirm_target(self) -> AddressKey | None:
        """A box in the part of the form whose assumed values ``b`` confirms, or ``None`` when none wait.

        The part is the selected row's: its box, the first box a listed entry
        or a section line names; a row with no box leads to the first assumed
        value's part.
        """
        assumed = None if self._recorded else self._unentered.get(IssueLevel.CONFIRM)
        if assumed is None:
            return None
        option_id = self._highlighted_id()
        listed = self._listed(option_id)
        section = self._section(option_id)
        index = self._issue_index(option_id)
        if listed is not None:
            return listed.keys[0]
        if section is not None:
            return section.keys[0]
        if index is not None and self._lines[index].key is not None and not self._lines[index].in_records:
            return self._lines[index].key
        return assumed.keys[0]

    def _highlighted_area(self) -> SourceSurface | None:
        index = self._issue_index(self._highlighted_id())
        return None if index is None else self._lines[index].area

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Offer ``a`` only on a finding whose value an area owns, and ``b`` only while assumed values wait."""
        if action == "open_area":
            return self._highlighted_area() is not None
        if action == "confirm_scope":
            return self._confirm_target() is not None
        if action == "calculate":
            return not self._recorded and any(line.recalculates for line in self._lines)
        return True

    def action_calculate(self) -> None:
        """Close the list asking the workbench to calculate the declaration again, as a finding here says to."""
        if not self._recorded and any(line.recalculates for line in self._lines):
            self.dismiss(CalculateAgain())

    def action_open_area(self) -> None:
        """Close the list asking the workbench to open the area that owns the selected finding's value."""
        area = self._highlighted_area()
        if area is not None:
            self.dismiss(OpenSourceSurface(area))

    def action_confirm_scope(self) -> None:
        """Close the list asking the workbench to confirm the assumed values of the selected row's part of the form."""
        target = self._confirm_target()
        if target is not None:
            self.dismiss(ConfirmAssumedValues(at=target))

    def _redraw(self, index: int) -> None:
        prompt = _issue_prompt(self._lines[index], expanded=index in self._expanded, technical=index in self._technical)
        self.query_one(_IssueList).replace_option_prompt(f"{_ISSUE_ID_PREFIX}{index}", prompt)

    def on_option_list_option_highlighted(self, _event: OptionList.OptionHighlighted) -> None:
        """Name what Enter does on the entry now under the cursor."""
        self._describe_enter()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Go to the chosen box or section, or open the chosen finding's detail where it has no box to go to."""
        event.stop()
        listed = self._listed(event.option.id)
        if listed is not None:
            self.dismiss(listed.keys[0])
            return
        section = self._section(event.option.id)
        if section is not None:
            self.dismiss(section.keys[0])
            return
        index = self._issue_index(event.option.id)
        if index is None:
            return
        key = self._lines[index].key
        if key is not None:
            self.dismiss(key)
            return
        self._expanded.symmetric_difference_update({index})
        self._redraw(index)
        self._describe_enter()

    def action_technical(self) -> None:
        """Show or hide the codes, facts and legal references of the finding under the cursor."""
        index = self._issue_index(self._highlighted_id())
        if index is None:
            return
        self._technical.symmetric_difference_update({index})
        self._redraw(index)

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        """Return to the workbench."""
        self.dismiss(None)

    def action_close(self) -> None:
        """Return to the workbench."""
        self.dismiss(None)


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


__all__ = [
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
    "WorkbenchIssuesScreen",
    "blocks_marked",
    "issue_level",
    "issue_lines",
    "level_counts",
    "level_words",
    "levels_marked",
    "technical_text",
    "title_text",
    "unentered_boxes",
    "unentered_levels",
    "verdict_text",
]
