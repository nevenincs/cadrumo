"""Worded portfolio authorities, table groups and admitted key guidance."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from rich.text import Text

from ....application.modelo.declarations_calendar import DeclarationsCalendarSource
from ....application.modelo.declarations_list import DeclarationListGroup, DeclarationListRow
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ..components.cell_text import wrap_words
from ..components.widgets import ContentDataTable
from .controller import (
    DeclarationsWorkspaceController,
)
from .row_words import is_unlinked_local_draft, row_lines

DECLARATION_GROUP_LOCALE_KEYS: Final[Mapping[DeclarationListGroup, str]] = MappingProxyType(
    {
        DeclarationListGroup.ATTENTION: "tui.declarations.list.group.attention",
        DeclarationListGroup.IN_PROGRESS: "tui.declarations.list.group.in_progress",
        DeclarationListGroup.READY: "tui.declarations.list.group.ready",
        DeclarationListGroup.NOT_STARTED: "tui.declarations.list.group.not_started",
        DeclarationListGroup.RECORDED: "tui.declarations.list.group.recorded",
        DeclarationListGroup.AEAT_UNLINKED: "tui.declarations.list.state.aeat_unlinked",
        DeclarationListGroup.MAYBE: "tui.declarations.list.group.maybe",
    }
)


def portfolio_source_lines(controller: DeclarationsWorkspaceController) -> list[str]:
    """Describe observed authorities and retained incomplete evidence."""
    lines = []
    projection = controller.calendar_projection
    if projection is not None:
        for source in projection.sources:
            if source.source is not DeclarationsCalendarSource.AEAT_EVIDENCE:
                continue
            from .controller import timestamp_label

            observed = (
                timestamp_label(source.observed_at)
                if source.observed_at is not None
                else tr("tui.declarations.calendar.never_observed")
            )
            lines.append(
                tr(
                    "tui.declarations.calendar.detail.source",
                    source=tr("tui.declarations.calendar.source." + source.source.value),
                    availability=tr("tui.declarations.availability." + source.availability.value),
                    observed=observed,
                )
            )
    if any(zone.availability.value == "stale" for zone in controller.projection.zones):
        lines.append(tr("tui.declarations.refusal.source"))
    return lines


def configure_portfolio_columns(table: ContentDataTable[Text | str], width: int) -> str | None:
    """Reset the wrapped columns while retaining the prior semantic selection."""
    # Both columns already wrap to the same declared cell budget.
    table.fill_column = None
    selected = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value if table.row_count else None
    table.clear(columns=True)
    table.add_column(tr("tui.declarations.list.column.declaration"), width=width)
    table.add_column(tr("tui.declarations.list.column.state"), width=width)
    return selected


def portfolio_key_guidance(
    table: ContentDataTable[Text | str],
    rows: tuple[DeclarationListRow, ...],
    controller: DeclarationsWorkspaceController,
) -> str:
    """Show Enter only while the table owns focus, followed by supported shortcuts."""
    enter = ""
    if table.has_focus and table.row_count:
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        enter = portfolio_enter_action(key, rows, controller)
    shortcuts = portfolio_shortcuts(controller)
    return (enter + "\n" if enter else "") + " · ".join(shortcuts)


def populate_portfolio_groups(
    table: ContentDataTable[Text | str],
    visible: list[DeclarationListRow],
    folded_groups: set[DeclarationListGroup],
    width: int,
    language: OutputLanguage,
    controller: DeclarationsWorkspaceController,
) -> None:
    """Wrap the same two columns while retaining semantic group and row keys."""
    for group in DeclarationListGroup:
        members = [row for row in visible if row.group is group]
        folded = not members or group in folded_groups
        mark = "▹" if folded else "▿"
        group_key = DECLARATION_GROUP_LOCALE_KEYS[group]
        title = "\n".join(wrap_words(f"{mark} {tr(group_key)} ({len(members)})", width))
        table.add_row(
            Text(title, style="bold"),
            "",
            key="group:" + group.value,
            height=title.count("\n") + 1,
        )
        if folded:
            continue
        for row in members:
            add_portfolio_row(table, row, width, language, controller)


def portfolio_shortcuts(controller: DeclarationsWorkspaceController) -> list[str]:
    """List only supported list actions."""
    shortcuts = []
    if controller.work_create_handoff is not None:
        shortcuts.append("+ " + tr("tui.declarations.list.key.new"))
    shortcuts.extend(
        (
            "/ " + tr("tui.modelo.workbench.key.search"),
            "f " + tr("tui.modelo.workbench.key.filter"),
            "s " + tr("tui.modelo.workbench.key.sort"),
            "t " + tr("tui.modelo.workbench.issues.technical"),
        )
    )
    return shortcuts


def portfolio_enter_action(
    key: str | None, rows: tuple[DeclarationListRow, ...], controller: DeclarationsWorkspaceController
) -> str:
    """Describe the Enter action for exactly the current semantic row."""
    if key is not None and key.startswith("group:"):
        return "Enter " + tr("tui.declarations.list.key.toggle_group")
    row = next((item for item in rows if item.key == key), None)
    if row is None:
        return ""
    return row_enter_action(row, controller)


def row_enter_action(row: DeclarationListRow, controller: DeclarationsWorkspaceController) -> str:
    """Reflect the row's route without implying unavailable local work."""
    if row.declaration is not None and row.state != "unreadable":
        if controller.modelo_workspace_factory is not None:
            return "Enter " + tr(
                "tui.declarations.list.next.open_local_draft"
                if is_unlinked_local_draft(row)
                else "tui.declarations.calendar.action.open"
            )
    elif row.state == "not_started" and row.period is not None and controller.work_create_handoff is not None:
        return "Enter " + tr("tui.declarations.list.next.start")
    elif row.state == "aeat_unlinked":
        return "Enter " + tr("tui.declarations.calendar.action.open")
    return ""


def add_portfolio_row(
    table: ContentDataTable[Text | str],
    row: DeclarationListRow,
    width: int,
    language: OutputLanguage,
    controller: DeclarationsWorkspaceController,
) -> None:
    """Render one row's own result and next action in the declared cell budget."""
    left, right = row_lines(
        row,
        language,
        can_open=controller.modelo_workspace_factory is not None,
        can_create=controller.work_create_handoff is not None,
    )
    left_text = "\n".join(line for part in left for line in wrap_words(part, width))
    right_text = "\n".join(line for part in right if part for line in wrap_words(part, width))
    table.add_row(
        Text(left_text),
        Text(right_text),
        height=max(left_text.count("\n"), right_text.count("\n")) + 1,
        key=row.key,
    )


def portfolio_row_refusal(row: DeclarationListRow) -> str:
    """Keep the exact state-specific refusal after row routing."""
    key = (
        "tui.declarations.list.aeat_unlinked.help.confirmed"
        if row.state == "aeat_unlinked"
        else "tui.declarations.list.unreadable.help"
        if row.state == "unreadable"
        else "tui.declarations.list.maybe.help"
        if row.state == "maybe"
        else "tui.declarations.list.aeat_needs_check.help"
    )
    return tr(key)
