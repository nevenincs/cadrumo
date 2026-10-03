"""Interactive workbench screen for reviewing findings and choosing where to act."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, OptionList, Static
from textual.widgets.option_list import Option

from .....application.modelo.source_policy import SourceSurface
from .....application.modelo.work_form_models import (
    ModeloWorkForm,
)
from .....core.i18n.render import tr
from ...components.theme import tokenised
from .casilla_list import AddressKey
from .dialog_width import fit_dialog_height, fit_dialog_width
from .editor import area_words
from .keys import describe_bindings
from .sources import OpenSourceSurface
from .status_bar import StatusBar

if TYPE_CHECKING:
    from .header import StatusLine

from .issue_projection import issue_lines
from .issue_scale import (
    CalculateAgain,
    ConfirmAssumedValues,
    IssueLevel,
    IssueLine,
    IssuesChoice,
    UnenteredBoxes,
    UnenteredSection,
    level_counts,
    levels_marked,
    title_text,
    unentered_levels,
    verdict_text,
)
from .issue_screen_components import (
    _BOXES_SUFFIX,
    _CONFIRM_SCOPE_KEY,
    _ISSUE_ID_PREFIX,
    _SECTION_INFIX,
    _issue_prompt,
    _IssueList,
    footer_keys_for_width,
    options_for_screen,
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


"""What ``b`` does, in full, where the list has room to say it; the footer says it in two words."""

_FOOTER_PRIORITY: Final[tuple[str, ...]] = ("enter", "escape", "a", _CONFIRM_SCOPE_KEY, "t")

"""The list's footer keys, most needed first; those that do not fit the width are left to the help."""

_FOOTER_KEY_GAP: Final[int] = 1

_OPEN_AREA_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.open_area"


"""Where a finding about the filer's records, rather than a box, sits: in those records."""


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

    def __init__(
        self,
        form: ModeloWorkForm,
        *,
        status_line: StatusLine | None = None,
        additional_lines: tuple[IssueLine, ...] = (),
        changes_unapplied: bool = False,
    ) -> None:
        """Hold the form whose findings and missing and assumed values are listed.

        ``status_line`` is shown above everything else when given, so the
        declaration's result and deadline stay in view while the dialog covers
        the workbench's header.
        """
        super().__init__()
        self._form = form
        self._status_line = status_line
        self._changes_unapplied = changes_unapplied
        self._recorded = form.filing is not None
        self._lines = (*additional_lines, *issue_lines(form))
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
            yield Static(
                verdict_text(self._form, changes_unapplied=self._changes_unapplied), id="issues-verdict", markup=False
            )
            yield _IssueList(*self._options(), id="issues-list")
            with Horizontal(id="issues-actions"):
                yield Button(tr("tui.modelo.workbench.result_diff.close"), id="issues-close", variant="primary")
        yield Footer(compact=True)

    def _options(self) -> list[Option]:
        return options_for_screen(self._form, self._lines, self._unentered, recorded=self._recorded)

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
        shown = footer_keys_for_width(
            _FOOTER_PRIORITY,
            self.app.size.width,
            issues.enter_binding(),
            self._bindings.key_to_bindings,
            self.app.get_key_display,
            has_open_area=self._highlighted_area() is not None,
            has_confirm_target=self._confirm_target() is not None,
            gap=_FOOTER_KEY_GAP,
        )
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


__all__ = ("WorkbenchIssuesScreen",)
