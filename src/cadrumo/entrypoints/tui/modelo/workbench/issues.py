"""Everything the filer should look at before filing, on one scale, with a way to act on each.

The list gathers the last check's findings and the boxes whose value was
assumed, grouped by one scale of levels, each with its glyph and words: what
blocks filing first, then the assumed values waiting for the filer's
confirmation, then what is worth checking, then what is only for the filer's
information. A finding takes its level from the form, which places it on that
scale. The title line counts each level that has anything in it, so the
check's verdict below it says what the check concluded without a count.

Every finding reads in three parts, all wrapped and never cut: where it is (a
box, or the whole declaration), what is wrong (the finding's own catalogue
message, rendered from its key and facts), and what to do (the sentence the
form names for that finding). The assumed values are one entry listing their
box numbers in at most two lines, then how many more there are; past twenty
boxes the entry lists the sections that hold them, with a count each, instead.

A declaration recorded as filed asks nothing more of the filer: its list has
no assumed values and counts nothing left to do.

Enter always acts. A finding that names a box on the form, the assumed values
and each of their sections return the first such box to the workbench; a
finding about the whole declaration opens its detail in place; a finding whose
box is not on the form says so there. Codes, facts and legal references never
reach the list: ``t`` shows them for the selected finding only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar, Final, override

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, OptionList, Static
from textual.widgets.option_list import Option

from .....application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
    section_fields,
)
from .....core.i18n.render import tr
from .....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
)
from ...components.theme import tokenised
from .casilla_list import AddressKey
from .dialog_width import fit_dialog_width
from .keys import describe_bindings
from .navigator import presented_form
from .page_items import workbench_pages
from .sources import BoxNumbers
from .vocabulary import BLOCKS_MARK, CHECK_MARK, CONFIRM_MARK, INFO_MARK, WorkbenchMark


class IssueLevel(StrEnum):
    """The one scale everything the filer should notice is placed on, most urgent first."""

    BLOCKS = "blocks"
    CONFIRM = "confirm"
    CHECK = "check"
    INFO = "info"


LEVEL_MARKS: Final[Mapping[IssueLevel, WorkbenchMark]] = MappingProxyType(
    {
        IssueLevel.BLOCKS: BLOCKS_MARK,
        IssueLevel.CONFIRM: CONFIRM_MARK,
        IssueLevel.CHECK: CHECK_MARK,
        IssueLevel.INFO: INFO_MARK,
    }
)
"""One mark per level, with its words, from the workbench's one vocabulary of marks."""

#: Levels that count as something left to do; a declaration recorded as filed counts none of them.
TO_DO_LEVELS: Final[frozenset[IssueLevel]] = frozenset({IssueLevel.BLOCKS, IssueLevel.CONFIRM})

_ATTENTION_LEVELS: Final[Mapping[ModeloFormAttention, IssueLevel]] = MappingProxyType(
    {
        ModeloFormAttention.BLOCKS: IssueLevel.BLOCKS,
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
        "section": "tui.modelo.workbench.issues.open_section",
        "more": "tui.modelo.workbench.issues.key.more",
        "less": "tui.modelo.workbench.issues.key.less",
    }
)
_SCREEN_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {"escape": "tui.modelo.workbench.key.back", "t": "tui.modelo.workbench.issues.technical"}
)
_BOX_NUMBER: Final[re.Pattern[str]] = re.compile(r"\d{1,4}[A-Z]?")
#: Past this many assumed boxes the list names the sections that hold them instead of their numbers.
ASSUMED_BOXES_BEFORE_SECTIONS: Final[int] = 20
_ASSUMED_ID: Final[str] = "assumed"
_ASSUMED_INTRO_ID: Final[str] = "assumed-intro"
_SECTION_ID_PREFIX: Final[str] = "assumed-section-"
_ISSUE_ID_PREFIX: Final[str] = "issue-"
_INDENT: Final[int] = 2


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

    @property
    def blocking(self) -> bool:
        """Whether this finding stops the declaration from being filed."""
        return self.level is IssueLevel.BLOCKS


@dataclass(frozen=True, slots=True)
class AssumedSection:
    """One section holding assumed values: its words and its assumed boxes, in form order."""

    title: str
    keys: tuple[AddressKey, ...]


@dataclass(frozen=True, slots=True)
class AssumedValues:
    """The boxes whose value nobody entered, listed as one entry, and the sections that hold them.

    ``boxes`` are their official numbers and ``unnumbered`` counts those that
    have none; ``keys`` are every one of them in form order, the first being
    where Enter goes.
    """

    boxes: tuple[str, ...]
    unnumbered: int
    keys: tuple[AddressKey, ...]
    sections: tuple[AssumedSection, ...]

    @property
    def by_section(self) -> bool:
        """Whether there are too many to list by number, so the list names their sections instead."""
        return len(self.keys) > ASSUMED_BOXES_BEFORE_SECTIONS


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


def issue_lines(form: ModeloWorkForm) -> tuple[IssueLine, ...]:
    """The form's findings on the scale, most urgent first, each rendered in the filer's language."""
    shown = {address_key(field.address): field for field in form.fields()}
    lines: list[IssueLine] = []
    for issue in form.issues:
        finding = issue.finding
        detail = tr(_DETAIL_LOCALE_KEYS[finding.kind])
        key: AddressKey | None = None
        box = issue.box or "·"
        if finding.casilla_id is None:
            where = tr("tui.modelo.workbench.issues.where.declaration")
        else:
            candidate = address_key(ModeloFormCasillaAddressV1(casilla_id=finding.casilla_id))
            field = shown.get(candidate)
            if field is None:
                box, where, missing = _not_on_form(issue.box, str(finding.casilla_id))
                detail = f"{missing} {detail}".strip()
            else:
                key = candidate
                where = _field_name(field) or f"[{box}]"
        lines.append(
            IssueLine(
                level=issue_level(issue),
                box=box,
                where=where,
                message=tr(finding.message_locale_key, **finding.message_facts),
                action=tr("tui.modelo.workbench.issues.what_to_do", action=tr(issue.action_locale_key)),
                detail=detail,
                technical=technical_text(finding),
                key=key,
            )
        )
    order = tuple(IssueLevel)
    return tuple(sorted(lines, key=lambda line: order.index(line.level)))


def _assumed_sections(form: ModeloWorkForm, assumed: frozenset[AddressKey]) -> tuple[AssumedSection, ...]:
    """The sections holding assumed values, under the words the navigator shows them with."""
    sections: list[AssumedSection] = []
    for page in workbench_pages(presented_form(form)):
        parts = [(section.heading.text, section_fields(section)) for section in page.sections]
        if page.details:
            parts.append((page.heading.text, page.details))
        for title, fields in parts:
            keys = tuple(key for key in (address_key(field.address) for field in fields) if key in assumed)
            if keys:
                sections.append(AssumedSection(title=title, keys=keys))
    return tuple(sections)


def assumed_values(form: ModeloWorkForm) -> AssumedValues | None:
    """The boxes whose value was assumed, or ``None`` when none waits for the filer.

    A declaration recorded as filed has none: nothing more is asked of it.
    """
    if form.filing is not None:
        return None
    fields = [field for field in form.fields() if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM]
    if not fields:
        return None
    keys = tuple(address_key(field.address) for field in fields)
    return AssumedValues(
        boxes=tuple(field.box for field in fields if field.box),
        unnumbered=sum(1 for field in fields if not field.box),
        keys=keys,
        sections=_assumed_sections(form, frozenset(keys)),
    )


def level_counts(lines: tuple[IssueLine, ...], assumed: AssumedValues | None) -> Mapping[IssueLevel, int]:
    """How many things sit at each level; the assumed values count one per box."""
    counts = dict.fromkeys(IssueLevel, 0)
    for line in lines:
        counts[line.level] += 1
    counts[IssueLevel.CONFIRM] += 0 if assumed is None else len(assumed.keys)
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
    return _entry(
        _paragraph(line.where, "bold"),
        _paragraph(line.message),
        _paragraph(line.action, "italic"),
        _paragraph(line.detail) if expanded else None,
        _paragraph(line.technical, "dim") if technical else None,
    )


def _assumed_prompt(assumed: AssumedValues) -> RenderableType:
    unnumbered = (
        tr("tui.modelo.workbench.issues.where.unnumbered", count=assumed.unnumbered) if assumed.unnumbered else ""
    )
    return _entry(
        BoxNumbers(assumed.boxes, style="bold") if assumed.boxes else None,
        _paragraph(unnumbered, "bold"),
        _paragraph(tr("tui.modelo.workbench.issues.assumed")),
        _paragraph(
            tr("tui.modelo.workbench.issues.what_to_do", action=tr("tui.modelo.workbench.issues.action.confirm")),
            "italic",
        ),
    )


def _assumed_intro() -> RenderableType:
    return _entry(
        _paragraph(tr("tui.modelo.workbench.issues.assumed")),
        _paragraph(
            tr(
                "tui.modelo.workbench.issues.what_to_do",
                action=tr("tui.modelo.workbench.issues.action.confirm_by_section"),
            ),
            "italic",
        ),
    )


def _section_prompt(section: AssumedSection) -> RenderableType:
    return _entry(_paragraph(f"{section.title} ({len(section.keys)})", "bold"))


class _IssueList(OptionList):
    """The grouped list, able to describe its own Enter key."""

    def describe_enter(self, locale_key: str) -> None:
        describe_bindings(self._bindings.key_to_bindings, {"enter": locale_key})
        self.refresh_bindings()


class WorkbenchIssuesScreen(ModalScreen[AddressKey | None]):
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
        WorkbenchIssuesScreen #issues-status {
            color: $foreground;
            margin-bottom: $cadrumo-stack;
        }
        WorkbenchIssuesScreen #issues-title {
            text-style: bold;
            color: $primary;
        }
        WorkbenchIssuesScreen #issues-verdict {
            color: $secondary;
            margin-bottom: $cadrumo-stack;
        }
        WorkbenchIssuesScreen #issues-list {
            height: 1fr;
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
    ]

    def __init__(self, form: ModeloWorkForm, *, status_line: str | None = None) -> None:
        """Hold the form whose findings and assumed values are listed.

        ``status_line`` is shown above everything else when given, so the
        declaration's result and deadline stay in view while the dialog covers
        the workbench's header.
        """
        super().__init__()
        self._form = form
        self._status_line = status_line
        self._recorded = form.filing is not None
        self._lines = issue_lines(form)
        self._assumed = assumed_values(form)
        self._expanded: set[int] = set()
        self._technical: set[int] = set()

    @override
    def compose(self) -> ComposeResult:
        with Container(id="issues-backdrop"), Vertical(id="issues-panel"):
            if self._status_line is not None:
                yield Static(self._status_line, id="issues-status", markup=False)
            title = title_text(level_counts(self._lines, self._assumed), recorded=self._recorded)
            yield Static(title, id="issues-title", markup=False)
            yield Static(verdict_text(self._form), id="issues-verdict", markup=False)
            yield _IssueList(*self._options(), id="issues-list")
            with Horizontal(id="issues-actions"):
                yield Button(tr("tui.modelo.workbench.result_diff.close"), id="issues-close", variant="primary")
        yield Footer(compact=True)

    def _assumed_options(self, assumed: AssumedValues) -> list[Option]:
        if not assumed.by_section:
            return [Option(_assumed_prompt(assumed), id=_ASSUMED_ID)]
        return [
            Option(_assumed_intro(), id=_ASSUMED_INTRO_ID, disabled=True),
            *(
                Option(_section_prompt(section), id=f"{_SECTION_ID_PREFIX}{index}")
                for index, section in enumerate(assumed.sections)
            ),
        ]

    def _options(self) -> list[Option]:
        options: list[Option] = []
        for level in IssueLevel:
            indexed = [(index, line) for index, line in enumerate(self._lines) if line.level is level]
            count = len(indexed)
            if level is IssueLevel.CONFIRM and self._assumed is not None:
                count += len(self._assumed.keys)
            if not count:
                continue
            heading = level_words(level)
            if not (self._recorded and level in TO_DO_LEVELS):
                heading = f"{heading} ({count})"
            options.append(Option(heading, id=f"level-{level.value}", disabled=True))
            if level is IssueLevel.CONFIRM and self._assumed is not None:
                options.extend(self._assumed_options(self._assumed))
            options.extend(
                Option(_issue_prompt(line, expanded=False, technical=False), id=f"{_ISSUE_ID_PREFIX}{index}")
                for index, line in indexed
            )
        if not options:
            options.append(Option(tr("tui.modelo.workbench.issues.empty"), id="empty", disabled=True))
        return options

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """Describe the keys and give the list the focus, on its first entry."""
        fit_dialog_width(self, self.app.size.width)
        describe_bindings(self._bindings.key_to_bindings, _SCREEN_LOCALE_KEYS)
        self.refresh_bindings()
        issues = self.query_one(_IssueList)
        issues.focus()
        self._describe_enter()

    def _issue_index(self, option_id: str | None) -> int | None:
        if option_id is None or not option_id.startswith(_ISSUE_ID_PREFIX):
            return None
        index = int(option_id.removeprefix(_ISSUE_ID_PREFIX))
        return index if index < len(self._lines) else None

    def _section(self, option_id: str | None) -> AssumedSection | None:
        if self._assumed is None or option_id is None or not option_id.startswith(_SECTION_ID_PREFIX):
            return None
        index = int(option_id.removeprefix(_SECTION_ID_PREFIX))
        sections = self._assumed.sections
        return sections[index] if index < len(sections) else None

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
        elif option_id == _ASSUMED_ID or (index is not None and self._lines[index].key is not None):
            choice = "go"
        elif index is not None and index in self._expanded:
            choice = "less"
        else:
            choice = "more"
        self.query_one(_IssueList).describe_enter(_ENTER_LOCALE_KEYS[choice])

    def _redraw(self, index: int) -> None:
        prompt = _issue_prompt(self._lines[index], expanded=index in self._expanded, technical=index in self._technical)
        self.query_one(_IssueList).replace_option_prompt(f"{_ISSUE_ID_PREFIX}{index}", prompt)

    def on_option_list_option_highlighted(self, _event: OptionList.OptionHighlighted) -> None:
        """Name what Enter does on the entry now under the cursor."""
        self._describe_enter()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Go to the chosen box or section, or open the chosen finding's detail where it has no box to go to."""
        event.stop()
        if event.option.id == _ASSUMED_ID and self._assumed is not None:
            self.dismiss(self._assumed.keys[0])
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


_require_total_tables()


__all__ = [
    "ASSUMED_BOXES_BEFORE_SECTIONS",
    "LEVEL_MARKS",
    "TO_DO_LEVELS",
    "AssumedSection",
    "AssumedValues",
    "IssueLevel",
    "IssueLine",
    "WorkbenchIssuesScreen",
    "assumed_values",
    "issue_level",
    "issue_lines",
    "level_counts",
    "level_words",
    "technical_text",
    "title_text",
    "verdict_text",
]
