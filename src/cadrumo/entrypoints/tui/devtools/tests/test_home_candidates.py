"""Focused compositor contracts for the two Home prototype candidates."""

from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path

import pytest
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from ...components.host import ScreenHostApp
from ..home_candidates import DueDrivenHomeCandidateScreen, TaskLauncherHomeCandidateScreen
from ..home_fixtures import HomeFixtureScenario, build_home_projection_fixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", list(HomeFixtureScenario))
@pytest.mark.parametrize("screen_type", (DueDrivenHomeCandidateScreen, TaskLauncherHomeCandidateScreen))
async def test_every_state_renders_truthfully_without_internal_copy(
    screen_type: type, scenario: HomeFixtureScenario
) -> None:
    projection = build_home_projection_fixture(scenario)
    screen = screen_type(projection)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        rendered = app.export_screenshot().lower()

    assert screen.projection is projection
    if projection.actions_state.reason_code is not None:
        assert projection.actions_state.reason_code not in rendered
    assert "work unit" not in rendered and "work_unit" not in rendered
    if projection.ledger is None:
        assert "ledger: available — 0" not in rendered
    if projection.messages_requiring_attention is None:
        assert "messages: available — 0" not in rendered


@pytest.mark.asyncio
async def test_due_driven_is_three_lists_in_actions_declarations_agenda_order() -> None:
    screen = DueDrivenHomeCandidateScreen(build_home_projection_fixture(HomeFixtureScenario.READY))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        tables = list(app.screen.query(DataTable))
        assert [table.id for table in tables] == ["due-actions", "due-declarations", "due-agenda"]
        assert len(app.screen.query(VerticalScroll)) == 1
        assert screen.has_class("compact")
        await pilot.press("enter")
        await pilot.pause()

    assert screen.selected_target is not None
    assert screen.selected_target.kind == "action"
    assert screen.selected_target.identity.startswith("action:")


@pytest.mark.asyncio
async def test_task_launcher_is_one_chooser_with_arrow_updated_context() -> None:
    screen = TaskLauncherHomeCandidateScreen(build_home_projection_fixture(HomeFixtureScenario.READY))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert len(app.screen.query(DataTable)) == 1
        assert len(app.screen.query(VerticalScroll)) == 1
        assert screen.has_class("wide")
        detail = app.screen.query_one("#launcher-detail", Static)
        initial = str(detail.render())
        await pilot.press("down")
        await pilot.pause()
        assert str(detail.render()) != initial
        await pilot.press("enter")
        await pilot.pause()

    assert screen.selected_target is not None
    assert screen.selected_target.identity.startswith("action:")


@pytest.mark.asyncio
async def test_agenda_detail_names_local_and_aeat_evidence_separately() -> None:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    screen = TaskLauncherHomeCandidateScreen(projection)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        chooser = app.screen.query_one("#launcher-chooser", DataTable)
        chooser.move_cursor(row=len(projection.actions) + len(projection.declarations))
        await pilot.pause()
        detail = str(app.screen.query_one("#launcher-detail", Static).render())

    assert "Local:" in detail
    assert "AEAT:" in detail
    assert projection.agenda[0].local_filing_state.value not in detail
    assert projection.agenda[0].aeat_submission_state.value not in detail


@pytest.mark.asyncio
async def test_due_agenda_keeps_local_and_aeat_evidence_on_every_row() -> None:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    screen = DueDrivenHomeCandidateScreen(projection)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        agenda = app.screen.query_one("#due-agenda", DataTable)
        first_row = tuple(str(cell) for cell in agenda.get_row_at(0))

    assert first_row[-2:] == ("not ready locally", "submission observed at AEAT")
    assert projection.agenda[0].local_filing_state.value not in first_row
    assert projection.agenda[0].aeat_submission_state.value not in first_row


@pytest.mark.asyncio
@pytest.mark.parametrize("screen_type", (DueDrivenHomeCandidateScreen, TaskLauncherHomeCandidateScreen))
async def test_escape_returns_from_each_candidate(screen_type: type) -> None:
    screen = screen_type(build_home_projection_fixture(HomeFixtureScenario.READY))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    assert screen.was_closed


@pytest.mark.asyncio
async def test_semantic_row_keys_ignore_mutable_order_and_deadline_facts() -> None:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    changed_action = projection.actions[1].model_copy(
        update={
            "action": projection.actions[0].action,
            "modelo": projection.actions[0].modelo,
            "filing_year": projection.actions[0].filing_year,
            "period": projection.actions[0].period,
        }
    )
    changed_agenda = projection.agenda[0].model_copy(update={"due_on": projection.agenda[0].due_on + timedelta(days=1)})
    changed = projection.model_copy(
        update={
            "actions": (projection.actions[0], changed_action, projection.actions[2]),
            "agenda": (changed_agenda, *projection.agenda[1:]),
        }
    )
    original_screen = DueDrivenHomeCandidateScreen(projection)
    changed_screen = DueDrivenHomeCandidateScreen(changed)
    original_app = ScreenHostApp[None](original_screen)
    changed_app = ScreenHostApp[None](changed_screen)
    async with original_app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        original_agenda_key = original_app.screen.query_one("#due-agenda", DataTable).ordered_rows[0].key.value
    async with changed_app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        actions = changed_app.screen.query_one("#due-actions", DataTable)
        changed_agenda_key = changed_app.screen.query_one("#due-agenda", DataTable).ordered_rows[0].key.value
        action_keys = tuple(row.key.value for row in actions.ordered_rows)

    assert changed_agenda_key == original_agenda_key
    assert len(action_keys) == len(set(action_keys))


def test_candidate_module_has_no_io_or_application_action_imports() -> None:
    path = Path(__file__).parents[1] / "home_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for name in (
            *((alias.name for alias in node.names) if isinstance(node, ast.Import) else ()),
            *((node.module,) if isinstance(node, ast.ImportFrom) and node.module is not None else ()),
        )
    }
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }

    assert not {"open", "read", "write", "read_text", "write_text", "Path"} & calls
    assert not any("adapters" in name or "entrypoints.cli" in name for name in imports)
