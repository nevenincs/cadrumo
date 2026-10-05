"""Shared prompts and option-list controls for the workbench issue screen."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Final

from rich.cells import cell_len
from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.text import Text
from textual.binding import Binding
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from .....application.modelo.calculation_notes import REOPEN_HINT_LOCALE_KEY, STALE_LOCALE_KEY
from .....application.modelo.work_form_models import ModeloWorkForm
from .....core.i18n.render import tr
from .issue_scale import (
    _UNENTERED_LOCALE_KEYS,
    TO_DO_LEVELS,
    IssueLevel,
    IssueLine,
    UnenteredBoxes,
    UnenteredSection,
    level_words,
    levels_marked,
)
from .keys import describe_bindings
from .sources import BoxNumbers

_CONFIRM_SCOPE_KEY: Final[str] = "b"

_CALCULATE_KEY: Final[str] = "c"

_OPEN_AREA_KEY: Final[str] = "a"

_CONFIRM_SCOPE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.issues.confirm_all"

_BOXES_SUFFIX: Final[str] = "-boxes"

_INTRO_SUFFIX: Final[str] = "-intro"

_SECTION_INFIX: Final[str] = "-section-"

_ISSUE_ID_PREFIX: Final[str] = "issue-"

_INDENT: Final[int] = 2

_STALE_ID: Final[str] = "calculation-stale"

_REOPEN_ID: Final[str] = "calculation-reopen"


def _entry(*parts: RenderableType | None) -> RenderableType:
    """Wrap each part of an entry under its level heading."""
    return Padding(Group(*(part for part in parts if part is not None)), (0, 0, 0, _INDENT))


def _paragraph(text: str, style: str = "") -> Text | None:
    return Text(text, style=style) if text else None


def _issue_prompt(line: IssueLine, *, expanded: bool, technical: bool) -> RenderableType:
    action = None if line.level is IssueLevel.INFO else _action_with_key(line)
    return _entry(
        _paragraph(f"[{line.box}] {line.where}" if line.action_targets_box and line.box != "·" else line.where, "bold"),
        _paragraph(line.message),
        _paragraph(action or "", "italic"),
        _paragraph(line.detail) if expanded else None,
        _paragraph(line.technical, "dim") if technical else None,
    )


def _action_with_key(line: IssueLine) -> str:
    """What to do, with the key that does it from this list where there is one."""
    if line.recalculates:
        return f"{line.action} [{_CALCULATE_KEY}]"
    if line.action_targets_box and line.key is not None:
        return f"{line.action} [Enter]"
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


def unentered_options(boxes: UnenteredBoxes) -> list[Option]:
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


def options_for_screen(
    form: ModeloWorkForm,
    lines: tuple[IssueLine, ...],
    unentered: Mapping[IssueLevel, UnenteredBoxes],
    *,
    recorded: bool,
) -> list[Option]:
    """Build the grouped options, preserving level order and recorded-filing counts."""
    options: list[Option] = []
    for level in IssueLevel:
        options.extend(_level_options(level, lines, unentered.get(level), recorded=recorded))
    if form.calculation_notes and form.calculation_out_of_date:
        options.insert(0, Option(Text(tr(STALE_LOCALE_KEY), style="italic"), id=_STALE_ID, disabled=True))
    reopen_hint = not form.calculation_notes_held and form.calculation_revision_id is not None and not recorded
    if reopen_hint:
        options.append(Option(Text(tr(REOPEN_HINT_LOCALE_KEY), style="italic"), id=_REOPEN_ID, disabled=True))
    if not options:
        options.append(Option(tr("tui.modelo.workbench.issues.empty"), id="empty", disabled=True))
    return options


def _level_options(
    level: IssueLevel,
    lines: tuple[IssueLine, ...],
    boxes: UnenteredBoxes | None,
    *,
    recorded: bool,
) -> list[Option]:
    indexed = [(index, line) for index, line in enumerate(lines) if line.level is level]
    count = len(indexed) + (0 if boxes is None else len(boxes.keys))
    if not count:
        return []
    heading = level_words(level)
    if not (recorded and level in TO_DO_LEVELS):
        heading = f"{heading} ({count})"
    options = [Option(levels_marked(heading).stylize("bold"), id=f"level-{level.value}", disabled=True)]
    if boxes is not None:
        options.extend(unentered_options(boxes))
    options.extend(
        Option(_issue_prompt(line, expanded=False, technical=False), id=f"{_ISSUE_ID_PREFIX}{index}")
        for index, line in indexed
    )
    return options


def footer_keys_for_width(
    priority: tuple[str, ...],
    budget: int,
    enter_binding: Binding | None,
    bindings: Mapping[str, list[Binding]],
    key_display: Callable[[Binding], str],
    *,
    has_open_area: bool,
    has_confirm_target: bool,
    gap: int,
) -> set[str]:
    """Choose whole footer bindings in priority order, stopping before one would be clipped."""
    shown: set[str] = set()
    for key in priority:
        binding = _footer_binding(key, enter_binding, bindings)
        binding = _available_footer_binding(key, binding, has_open_area, has_confirm_target)
        if binding is None:
            continue
        cost = cell_len(f"{key_display(binding)} {binding.description}") + gap
        if cost > budget:
            break
        shown.add(key)
        budget -= cost
    return shown


def _footer_binding(key: str, enter_binding: Binding | None, bindings: Mapping[str, list[Binding]]) -> Binding | None:
    if key == "enter":
        return enter_binding
    entries = bindings.get(key)
    return entries[0] if entries else None


def _available_footer_binding(
    key: str, binding: Binding | None, has_open_area: bool, has_confirm_target: bool
) -> Binding | None:
    if binding is None or not binding.description:
        return None
    if (key == "a" and not has_open_area) or (key == "b" and not has_confirm_target):
        return None
    return binding


__all__ = (
    "_BOXES_SUFFIX",
    "_INTRO_SUFFIX",
    "_ISSUE_ID_PREFIX",
    "_SECTION_INFIX",
    "_IssueList",
    "options_for_screen",
)
