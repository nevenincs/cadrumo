"""Everything the filer should look at before filing, on one scale, with a way to act on each.

The list gathers the last check's findings and the boxes whose value was
assumed, grouped by one scale of levels, each with its glyph and words: what
blocks filing first, then the assumed values waiting for the filer's
confirmation, then what is worth checking. The title line counts each level
that has anything in it.

Every finding reads in three parts, all wrapped and never cut: where it is (a
box, or the whole declaration), what is wrong (the finding's own catalogue
message, rendered from its key and facts), and what to do (a sentence for the
finding's kind, or a general one where nothing more specific is grounded). The
assumed values are one entry listing their boxes.

Enter always acts. A finding that names a box on the form, and the assumed
values, return that box to the workbench; a finding about the whole
declaration opens its detail in place; a finding whose box is not on the form
says so there. Codes and legal references never reach the list: ``t`` shows
them for the selected finding only.
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
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
)
from .....core.i18n.render import tr
from .....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ...components.theme import tokenised
from .casilla_list import AddressKey
from .dialog_width import fit_dialog_width
from .keys import describe_bindings


class IssueLevel(StrEnum):
    """The one scale everything the filer should notice is placed on, most urgent first."""

    BLOCKS = "blocks"
    CONFIRM = "confirm"
    CHECK = "check"
    INFO = "info"


LEVEL_GLYPHS: Final[Mapping[IssueLevel, str]] = MappingProxyType(
    {IssueLevel.BLOCKS: "▲", IssueLevel.CONFIRM: "◐", IssueLevel.CHECK: "◆", IssueLevel.INFO: "i"}
)
"""One mark per level, every one present in the pinned font."""

_LEVEL_LOCALE_KEYS: Final[Mapping[IssueLevel, str]] = MappingProxyType(
    {
        IssueLevel.BLOCKS: "tui.modelo.workbench.level.blocks",
        IssueLevel.CONFIRM: "tui.modelo.workbench.origin.default_to_confirm",
        IssueLevel.CHECK: "tui.modelo.workbench.level.check",
        IssueLevel.INFO: "tui.modelo.workbench.level.info",
    }
)
_SEVERITY_LEVELS: Final[Mapping[ModeloVerificationFindingSeverity, IssueLevel]] = MappingProxyType(
    {
        ModeloVerificationFindingSeverity.BLOCKING: IssueLevel.BLOCKS,
        ModeloVerificationFindingSeverity.WARNING: IssueLevel.CHECK,
    }
)
_ACTION_LOCALE_KEYS: Final[Mapping[ModeloVerificationFindingKind, str]] = MappingProxyType(
    {
        ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA: (
            "tui.modelo.workbench.issues.action.missing_required_casilla"
        ),
        ModeloVerificationFindingKind.RECONCILIATION_MISMATCH: (
            "tui.modelo.workbench.issues.action.reconciliation_mismatch"
        ),
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN: (
            "tui.modelo.workbench.issues.action.cross_period_dependency_unclean"
        ),
        ModeloVerificationFindingKind.BLOCKING_RULE: "tui.modelo.workbench.issues.action.generic",
        ModeloVerificationFindingKind.ADVISORY: "tui.modelo.workbench.issues.action.advisory",
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
        "more": "tui.modelo.workbench.issues.key.more",
        "less": "tui.modelo.workbench.issues.key.less",
    }
)
_SCREEN_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {"escape": "tui.modelo.workbench.key.back", "t": "tui.modelo.workbench.issues.technical"}
)
_BOX_NUMBER: Final[re.Pattern[str]] = re.compile(r"\d{1,4}[A-Z]?")
_ASSUMED_ID: Final[str] = "assumed"
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
class AssumedValues:
    """The boxes whose value nobody entered, listed as one entry, and the first box to go to."""

    where: str
    keys: tuple[AddressKey, ...]


def issue_level(finding: ModeloVerificationFinding) -> IssueLevel:
    """Place one finding on the scale by its severity."""
    return _SEVERITY_LEVELS[finding.severity]


def _field_name(field: ModeloFormField) -> str:
    parts: list[str] = [f"[{field.box}]"] if field.box else []
    if field.label.disclosure is not ModeloFormTextDisclosure.TECHNICAL:
        parts.append(field.label.text)
    return " ".join(parts)


def _technical_text(finding: ModeloVerificationFinding) -> str:
    codes = [
        finding.kind.value,
        finding.severity.value,
        *([] if finding.casilla_id is None else [str(finding.casilla_id)]),
        *([] if finding.expectation_id is None else [str(finding.expectation_id)]),
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
                level=issue_level(finding),
                box=box,
                where=where,
                message=tr(finding.message_locale_key, **finding.message_facts),
                action=tr("tui.modelo.workbench.issues.what_to_do", action=tr(_ACTION_LOCALE_KEYS[finding.kind])),
                detail=detail,
                technical=_technical_text(finding),
                key=key,
            )
        )
    order = tuple(IssueLevel)
    return tuple(sorted(lines, key=lambda line: order.index(line.level)))


def assumed_values(form: ModeloWorkForm) -> AssumedValues | None:
    """The boxes whose value was assumed, or ``None`` when the filer has confirmed or entered every one."""
    fields = [field for field in form.fields() if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM]
    if not fields:
        return None
    numbered = " ".join(f"[{field.box}]" for field in fields if field.box)
    unnumbered = sum(1 for field in fields if not field.box)
    parts = [numbered] if numbered else []
    if unnumbered:
        parts.append(tr("tui.modelo.workbench.issues.where.unnumbered", count=unnumbered))
    return AssumedValues(where=" · ".join(parts), keys=tuple(address_key(field.address) for field in fields))


def level_counts(lines: tuple[IssueLine, ...], assumed: AssumedValues | None) -> Mapping[IssueLevel, int]:
    """How many things sit at each level; the assumed values count one per box."""
    counts = dict.fromkeys(IssueLevel, 0)
    for line in lines:
        counts[line.level] += 1
    counts[IssueLevel.CONFIRM] += 0 if assumed is None else len(assumed.keys)
    return MappingProxyType(counts)


def level_words(level: IssueLevel) -> str:
    """One level's glyph and words, as every surface shows it."""
    return f"{LEVEL_GLYPHS[level]} {tr(_LEVEL_LOCALE_KEYS[level])}"


def title_text(counts: Mapping[IssueLevel, int]) -> str:
    """The list's name followed by a count for each level that has anything in it."""
    chips = "   ".join(f"{LEVEL_GLYPHS[level]} {count}" for level, count in counts.items() if count)
    title = tr("tui.modelo.workbench.issues.title")
    return f"{title}   {chips}" if chips else title


def verdict_text(form: ModeloWorkForm) -> str:
    """Say what the last check concluded, or that the declaration has not been checked."""
    if form.verification is None:
        return tr("tui.modelo.workbench.issues.verdict.none")
    return tr(_VERDICT_LOCALE_KEYS[form.verification], count=len(form.issues))


def _entry(*paragraphs: tuple[str, str]) -> RenderableType:
    """Wrap each paragraph under the level heading; the style marks what each one says."""
    return Padding(
        Group(*(Text(text, style=style) for text, style in paragraphs if text)),
        (0, 0, 0, _INDENT),
    )


def _issue_prompt(line: IssueLine, *, expanded: bool, technical: bool) -> RenderableType:
    return _entry(
        (line.where, "bold"),
        (line.message, ""),
        (line.action, "italic"),
        (line.detail if expanded else "", ""),
        (line.technical if technical else "", "dim"),
    )


def _assumed_prompt(assumed: AssumedValues) -> RenderableType:
    return _entry(
        (assumed.where, "bold"),
        (tr("tui.modelo.workbench.issues.assumed"), ""),
        (
            tr("tui.modelo.workbench.issues.what_to_do", action=tr("tui.modelo.workbench.issues.action.confirm")),
            "italic",
        ),
    )


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

    def __init__(self, form: ModeloWorkForm) -> None:
        """Hold the form whose findings and assumed values are listed."""
        super().__init__()
        self._form = form
        self._lines = issue_lines(form)
        self._assumed = assumed_values(form)
        self._expanded: set[int] = set()
        self._technical: set[int] = set()

    @override
    def compose(self) -> ComposeResult:
        with Container(id="issues-backdrop"), Vertical(id="issues-panel"):
            title = title_text(level_counts(self._lines, self._assumed))
            yield Static(title, id="issues-title", markup=False)
            yield Static(verdict_text(self._form), id="issues-verdict", markup=False)
            yield _IssueList(*self._options(), id="issues-list")
            with Horizontal(id="issues-actions"):
                yield Button(tr("tui.modelo.workbench.result_diff.close"), id="issues-close", variant="primary")
        yield Footer(compact=True)

    def _options(self) -> list[Option]:
        options: list[Option] = []
        for level in IssueLevel:
            indexed = [(index, line) for index, line in enumerate(self._lines) if line.level is level]
            count = len(indexed)
            if level is IssueLevel.CONFIRM and self._assumed is not None:
                count += len(self._assumed.keys)
            if not count:
                continue
            options.append(Option(f"{level_words(level)} ({count})", id=f"level-{level.value}", disabled=True))
            if level is IssueLevel.CONFIRM and self._assumed is not None:
                options.append(Option(_assumed_prompt(self._assumed), id=_ASSUMED_ID))
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

    def _highlighted_id(self) -> str | None:
        issues = self.query_one(_IssueList)
        if issues.highlighted is None:
            return None
        return issues.get_option_at_index(issues.highlighted).id

    def _describe_enter(self) -> None:
        option_id = self._highlighted_id()
        index = self._issue_index(option_id)
        if option_id == _ASSUMED_ID or (index is not None and self._lines[index].key is not None):
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
        """Go to the chosen box, or open the chosen finding's detail where it has no box to go to."""
        event.stop()
        if event.option.id == _ASSUMED_ID and self._assumed is not None:
            self.dismiss(self._assumed.keys[0])
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
        """Show or hide the codes and legal references of the finding under the cursor."""
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
    """Refuse a scale or a finding kind that has no words, glyph or sentence."""
    if set(LEVEL_GLYPHS) != set(IssueLevel) or set(_LEVEL_LOCALE_KEYS) != set(IssueLevel):
        raise ValueError("every issue level needs one glyph and one name")
    if set(_SEVERITY_LEVELS) != set(ModeloVerificationFindingSeverity):
        raise ValueError("every finding severity needs a level")
    kinds = set(ModeloVerificationFindingKind)
    if set(_ACTION_LOCALE_KEYS) != kinds or set(_DETAIL_LOCALE_KEYS) != kinds:
        raise ValueError("every finding kind needs a sentence saying what to do and a detail")


_require_total_tables()


__all__ = [
    "LEVEL_GLYPHS",
    "AssumedValues",
    "IssueLevel",
    "IssueLine",
    "WorkbenchIssuesScreen",
    "assumed_values",
    "issue_level",
    "issue_lines",
    "level_counts",
    "level_words",
    "title_text",
    "verdict_text",
]
