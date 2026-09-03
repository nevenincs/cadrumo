"""Focused compositor and authority-boundary proof for the production Home."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from ..components.host import ScreenHostApp
from ..components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..devtools.frame import geometry_band, screen_text
from ..devtools.home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from ..home import HomeScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
@pytest.mark.parametrize("size", ((80, 24), (120, 40)))
@pytest.mark.parametrize("theme", (CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME))
async def test_home_renders_the_selected_due_driven_projection_without_overflow(
    size: tuple[int, int], theme: str
) -> None:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    screen = HomeScreen(projection)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        app.theme = theme
        await pilot.pause()
        assert geometry_band(app, size[0]) == []
        assert not screen.show_vertical_scrollbar
        assert all(cast("DataTable[str]", table).max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(
            widget
            for widget in screen.walk_children(VerticalScroll)
            if widget.display and widget.show_vertical_scrollbar
        )
        assert all(isinstance(owner, VerticalScroll) and owner.id == "home-page" for owner in owners)
        assert len(owners) <= 1
        assert tuple(widget.id for widget in screen.focus_chain) == (
            "home-actions",
            "home-declarations",
            "home-agenda",
        )
        assert app.focused is not None and app.focused.id == "home-actions"
        rendered = screen_text(app, *size)
        assert "Status: Active local session" in rendered
        assert str(screen.query_one("#home-ledger", Static).render()).startswith("Available —")
        assert str(screen.query_one("#home-agenda-state", Static).render()).startswith("Available")
        assert len(projection.actions) <= 3
        action_table = screen.query_one("#home-actions", DataTable)
        assert tuple(
            cast("DataTable[str]", action_table).get_row_at(index)[0] for index in range(action_table.row_count)
        ) == (
            "Review declaration",
            "Classify Ledger entries",
            "Add missing evidence",
        )


@pytest.mark.asyncio
async def test_home_selection_and_escape_are_host_requests_not_business_calls() -> None:
    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.READY))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert screen.selected_target == screen.highlighted_target
        await pilot.press("escape")
        await pilot.pause()
    assert screen.back_requested


@pytest.mark.asyncio
async def test_home_keeps_unknown_ledger_and_messages_as_unknown_not_zero() -> None:
    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.LOCKED))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        text = "\n".join(str(widget.render()) for widget in screen.query(Static))
    assert "Ledger readiness\nLocked" in text
    assert "Messages\nLocked" in text
    assert "Available — 0" not in text


def test_home_is_projection_only_and_does_not_import_devtools_or_application_actions() -> None:
    path = Path(__file__).parents[1] / "home.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not any("devtools" in name or "adapters" in name or "entrypoints.cli" in name for name in imports)
    assert not {"open", "read", "write", "read_text", "write_text", "Path"} & calls
