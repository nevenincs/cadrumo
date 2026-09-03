"""Focused compositor contracts for the two Home prototype candidates."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from .....core.external_constants import OutputLanguage
from ...components.host import ScreenHostApp
from ...components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..home_candidates import DueDrivenHomeCandidateScreen, TaskLauncherHomeCandidateScreen
from ..home_fixtures import HomeFixtureScenario, build_home_projection_fixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_MEASUREMENT_SIZES: Final[tuple[tuple[int, int], ...]] = (
    (80, 24),
    (100, 30),
    (120, 40),
    (200, 50),
)
_MEASUREMENT_THEMES: Final[tuple[tuple[str, str], ...]] = (
    ("light", CADRUMO_LIGHT_THEME_NAME),
    ("dark", CADRUMO_DARK_THEME_NAME),
)
_MEASUREMENT_LOCALES: Final[tuple[OutputLanguage, ...]] = tuple(OutputLanguage)
_MEASUREMENT_SCENARIOS: Final[tuple[HomeFixtureScenario, ...]] = (
    HomeFixtureScenario.READY,
    HomeFixtureScenario.LOCKED,
    HomeFixtureScenario.STALE,
    HomeFixtureScenario.NEVER_CAPTURED,
    HomeFixtureScenario.EMPTY,
    HomeFixtureScenario.BLOCKED,
)


@dataclass(frozen=True, slots=True)
class CandidateFrameMetric:
    """Machine-readable compositor reading retained for the next comparison wave."""

    candidate: str
    scenario: str
    width: int
    height: int
    theme: str
    locale: str
    rendered_line_count: int
    maximum_rendered_line_width: int
    horizontal_overflow: bool
    unscrollable_overflow: bool
    geometry_findings: tuple[str, ...]
    visible_vertical_scroll_owner_ids: tuple[str, ...]
    page_scroll_owner_id: str | None
    nested_scroll_owner_ids: tuple[str, ...]
    screen_scrolls: bool
    focus_chain: tuple[str | None, ...]
    focused_id: str | None
    semantic_target_ids: tuple[str, ...]
    nearest_deadline_visible: bool


@dataclass(frozen=True, slots=True)
class CandidateKeyboardMetric:
    """Machine-readable pilot readings for the named operator keystrokes."""

    candidate: str
    scenario: str
    width: int
    height: int
    theme: str
    locale: str
    top_action_target: str | None
    second_declaration_target: str | None
    ledger_or_destination_target: str | None
    nearest_deadline_visible_before_navigation: bool
    nearest_deadline_visible_after_navigation: bool
    ctrl_p_effect: str
    f3_effect: str
    escape_closed: bool
    focus_chain: tuple[str | None, ...]
    tab_reached_ids: tuple[str | None, ...]
    offered_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateRestorationMetric:
    """Machine-readable semantic-selection reading across resize and reorder."""

    candidate: str
    selected_before_resize: str | None
    selected_after_resize: str | None
    selected_after_reorder: str | None
    original_focus_chain: tuple[str | None, ...]
    reordered_focus_chain: tuple[str | None, ...]


# These are deliberately module-level test records.  S374 can import this
# module after the measurement lane and serialise them without scraping a
# terminal screenshot or depending on pytest's human output.
CANDIDATE_FRAME_METRICS: list[CandidateFrameMetric] = []
CANDIDATE_KEYBOARD_METRICS: list[CandidateKeyboardMetric] = []
CANDIDATE_RESTORATION_METRICS: list[CandidateRestorationMetric] = []


def candidate_metrics_payload() -> dict[str, tuple[dict[str, object], ...]]:
    """Return the captured readings in a JSON-compatible, stable shape."""
    return {
        "frames": tuple(asdict(metric) for metric in CANDIDATE_FRAME_METRICS),
        "keyboard": tuple(asdict(metric) for metric in CANDIDATE_KEYBOARD_METRICS),
        "restoration": tuple(asdict(metric) for metric in CANDIDATE_RESTORATION_METRICS),
    }


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
