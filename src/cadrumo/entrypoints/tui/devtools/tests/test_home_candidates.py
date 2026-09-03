"""Measured compositor contracts for the two Home interaction candidates."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import pytest
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import DataTable, Static

from .....core.external_constants import OutputLanguage
from ...components.host import ScreenHostApp
from ...components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..frame import geometry_band, screen_text
from ..home_candidates import (
    DueDrivenHomeCandidateScreen,
    TaskLauncherHomeCandidateScreen,
)
from ..home_fixtures import HomeFixtureScenario, build_home_projection_fixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

type CandidateScreen = DueDrivenHomeCandidateScreen | TaskLauncherHomeCandidateScreen
type CandidateType = type[DueDrivenHomeCandidateScreen] | type[TaskLauncherHomeCandidateScreen]

_CANDIDATES: Final[tuple[CandidateType, ...]] = (
    DueDrivenHomeCandidateScreen,
    TaskLauncherHomeCandidateScreen,
)
_SIZES: Final[tuple[tuple[int, int], ...]] = ((80, 24), (100, 30), (120, 40), (200, 50))
_THEMES: Final[tuple[str, ...]] = (CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME)
_LOCALES: Final[tuple[OutputLanguage, ...]] = tuple(OutputLanguage)
_DENSE_CASES: Final = tuple(
    (candidate, size, theme, locale)
    for candidate in _CANDIDATES
    for size in _SIZES
    for theme in _THEMES
    for locale in _LOCALES
)
_LOCALE_MARKERS: Final[dict[OutputLanguage, str]] = {
    OutputLanguage.ES: "Inicio",
    OutputLanguage.EN: "Home",
    OutputLanguage.CA: "Inici",
    OutputLanguage.HU: "Kezdőlap",
}
_STATE_MARKERS: Final[dict[HomeFixtureScenario, str]] = {
    HomeFixtureScenario.READY: "Revisar declaración",
    HomeFixtureScenario.LOCKED: "Bloqueado",
    HomeFixtureScenario.STALE: "Desactualizado",
    HomeFixtureScenario.NEVER_CAPTURED: "Aún no capturado",
    HomeFixtureScenario.UNAVAILABLE: "No disponible",
    HomeFixtureScenario.EMPTY: "No hay tareas rápidas",
    HomeFixtureScenario.BLOCKED: "Resolver bloqueo",
}


@dataclass(frozen=True, slots=True)
class FrameReading:
    """One measured candidate frame retained for comparison tooling."""

    candidate: str
    size: tuple[int, int]
    theme: str
    locale: str
    focus_chain: tuple[str, ...]
    semantic_targets: tuple[str, ...]
    vertical_owners: tuple[str, ...]


CANDIDATE_FRAME_READINGS: list[FrameReading] = []


def _tables(screen: CandidateScreen) -> tuple[DataTable[str], ...]:
    return tuple(cast("DataTable[str]", table) for table in screen.query(DataTable))


def _semantic_targets(screen: CandidateScreen) -> tuple[str, ...]:
    return tuple(str(row.key.value) for table in _tables(screen) for row in table.ordered_rows)


def _cursor_target(table: DataTable[object]) -> str:
    return str(table.ordered_rows[table.cursor_row].key.value)


def _all_rendered_copy(screen: CandidateScreen) -> str:
    static_copy = [str(widget.render()) for widget in screen.query(Static)]
    table_copy = [
        str(cell) for table in _tables(screen) for row in range(table.row_count) for cell in table.get_row_at(row)
    ]
    return "\n".join((*static_copy, *table_copy))


def _vertical_owners(screen: CandidateScreen) -> tuple[Widget, ...]:
    return tuple(widget for widget in screen.walk_children(Widget) if widget.display and widget.show_vertical_scrollbar)


def _assert_geometry(app: ScreenHostApp[None], screen: CandidateScreen, width: int) -> None:
    assert geometry_band(app, width) == []
    assert all(table.max_scroll_x == 0 for table in _tables(screen))
    owners = _vertical_owners(screen)
    assert len(owners) <= 1
    assert all(isinstance(owner, VerticalScroll) and owner.id in {"due-page", "launcher-page"} for owner in owners)
    assert not screen.show_vertical_scrollbar


def _case_id(case: tuple[CandidateType, tuple[int, int], str, OutputLanguage]) -> str:
    candidate, size, theme, locale = case
    return f"{candidate.__name__}-{size[0]}x{size[1]}-{theme}-{locale.value}"


@pytest.mark.asyncio
@pytest.mark.parametrize(("screen_type", "size", "theme", "locale"), _DENSE_CASES, ids=map(_case_id, _DENSE_CASES))
async def test_dense_compositor_matrix_has_no_clipping_scroll_or_focus_regression(
    screen_type: CandidateType,
    size: tuple[int, int],
    theme: str,
    locale: OutputLanguage,
) -> None:
    """Measure 64 candidate/size/theme/locale frames through Textual itself."""
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    screen = screen_type(projection, locale=locale)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        app.theme = theme
        await pilot.pause()
        text = screen_text(app, *size)
        _assert_geometry(app, screen, size[0])
        focus_chain = tuple(widget.id or type(widget).__name__ for widget in screen.focus_chain)
        expected_focus = (
            ("due-actions", "due-declarations", "due-agenda")
            if screen_type is DueDrivenHomeCandidateScreen
            else ("launcher-chooser",)
        )
        assert focus_chain == expected_focus
        assert (app.focused.id if app.focused is not None else None) == expected_focus[0]
        assert _LOCALE_MARKERS[locale] in text
        targets = _semantic_targets(screen)
        assert len(targets) == len(set(targets))
        if screen_type is TaskLauncherHomeCandidateScreen:
            assert len(targets) <= 5
        CANDIDATE_FRAME_READINGS.append(
            FrameReading(
                candidate=screen_type.__name__,
                size=size,
                theme=theme,
                locale=locale.value,
                focus_chain=focus_chain,
                semantic_targets=targets,
                vertical_owners=tuple(owner.id or type(owner).__name__ for owner in _vertical_owners(screen)),
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", list(HomeFixtureScenario))
@pytest.mark.parametrize("screen_type", _CANDIDATES)
async def test_all_seven_states_are_legible_at_the_terminal_floor(
    screen_type: CandidateType,
    scenario: HomeFixtureScenario,
) -> None:
    """Measure the 14 candidate/state floor frames without false empty claims."""
    projection = build_home_projection_fixture(scenario)
    screen = screen_type(projection, locale=OutputLanguage.ES)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        text = screen_text(app, 80, 24)
        _assert_geometry(app, screen, 80)
    marker = (
        "sin acciones sugeridas"
        if scenario is HomeFixtureScenario.EMPTY and screen_type is DueDrivenHomeCandidateScreen
        else _STATE_MARKERS[scenario]
    )
    assert marker in text
    assert "work unit" not in text.lower() and "work_unit" not in text.lower()
    if projection.ledger is None:
        assert "Libros registro: Disponible — 0" not in text
    if projection.messages_requiring_attention is None:
        assert "Mensajes: Disponible — 0" not in text


@pytest.mark.asyncio
async def test_locales_change_copy_without_changing_semantic_targets() -> None:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    forbidden_english = (
        "Home ·",
        "Next actions",
        "Declarations",
        "Filing agenda",
        "Quick tasks",
        "Available",
        "Review declaration",
        "Local declaration status",
        " entries",
        "unclassified",
        "missing evidence",
    )
    for screen_type in _CANDIDATES:
        readings: list[tuple[str, tuple[str, ...]]] = []
        for locale in _LOCALES:
            screen = screen_type(projection, locale=locale)
            app = ScreenHostApp[None](screen)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                readings.append((_all_rendered_copy(screen), _semantic_targets(screen)))
        assert len({text for text, _targets in readings}) == len(_LOCALES)
        assert len({targets for _text, targets in readings}) == 1
        assert all(marker in text for marker, (text, _targets) in zip(_LOCALE_MARKERS.values(), readings, strict=True))
        for text, _targets in readings:
            if "Home ·" not in text:
                assert not any(phrase in text for phrase in forbidden_english)


@pytest.mark.asyncio
async def test_compact_launcher_reaches_every_preview_and_keeps_detail_visible() -> None:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    screen = TaskLauncherHomeCandidateScreen(projection, locale=OutputLanguage.EN)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        chooser = app.screen.query_one("#launcher-chooser", DataTable)
        detail = app.screen.query_one("#launcher-detail", Static)
        assert 1 <= chooser.row_count <= 5
        expected_targets = tuple(str(row.key.value) for row in chooser.ordered_rows)
        observed_details: list[str] = []
        for row_index, expected_target in enumerate(expected_targets):
            table = cast("DataTable[object]", chooser)
            assert _cursor_target(table) == expected_target
            assert screen.highlighted_target is not None
            assert screen.highlighted_target.identity == expected_target
            detail_copy = str(detail.render())
            assert detail_copy
            observed_details.append(detail_copy)
            assert detail.region.y >= 0 and detail.region.bottom <= 24
            assert detail.region.overlaps(app.screen.region)
            if row_index + 1 < len(expected_targets):
                await pilot.press("down")
                await pilot.pause()
        assert len(set(observed_details)) == len(expected_targets)
        assert len(expected_targets) <= 5  # At most four Down presses and Enter.
        await pilot.press("enter")
        await pilot.pause()
    assert screen.selected_target == screen.highlighted_target


@pytest.mark.asyncio
@pytest.mark.parametrize("screen_type", _CANDIDATES)
async def test_focus_chain_and_semantic_target_survive_resize_and_reordering(screen_type: CandidateType) -> None:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    screen = screen_type(projection, locale=OutputLanguage.EN)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        before = screen.highlighted_target
        assert before is not None
        focused_before = cast("DataTable[object]", app.focused)
        assert _cursor_target(focused_before) == before.identity
        await pilot.resize_terminal(200, 50)
        await pilot.pause()
        focused_after_resize = cast("DataTable[object]", app.focused)
        assert focused_after_resize.id in {"due-actions", "launcher-chooser"}
        assert _cursor_target(focused_after_resize) == before.identity
        assert focused_after_resize.region.overlaps(app.screen.region)
    reordered = projection.model_copy(update={"actions": tuple(reversed(projection.actions))})
    restored = screen_type(reordered, locale=OutputLanguage.EN, restore_target=before)
    restored_app = ScreenHostApp[None](restored)
    async with restored_app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        focused_restored = cast("DataTable[object]", restored_app.focused)
        assert focused_restored.id in {"due-actions", "launcher-chooser"}
        assert _cursor_target(focused_restored) == before.identity
        assert focused_restored.region.overlaps(restored_app.screen.region)
        assert focused_restored.region.y >= 0 and focused_restored.region.bottom <= 30


@pytest.mark.asyncio
async def test_due_focus_order_is_visual_order_and_launcher_is_one_tab_stop() -> None:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    due = DueDrivenHomeCandidateScreen(projection)
    due_app = ScreenHostApp[None](due)
    async with due_app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        reached = [due_app.focused.id if due_app.focused is not None else None]
        for _ in range(2):
            await pilot.press("tab")
            await pilot.pause()
            reached.append(due_app.focused.id if due_app.focused is not None else None)
    assert reached == ["due-actions", "due-declarations", "due-agenda"]
    launcher = TaskLauncherHomeCandidateScreen(projection)
    launcher_app = ScreenHostApp[None](launcher)
    async with launcher_app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert tuple(widget.id for widget in launcher.focus_chain) == ("launcher-chooser",)


def test_candidate_module_has_no_io_or_application_action_imports() -> None:
    path = Path(__file__).parents[1] / "home_candidates.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not {"open", "read", "write", "read_text", "write_text", "Path"} & calls
    assert not any("adapters" in name or "entrypoints.cli" in name for name in imports)


def iter_frame_readings() -> Iterator[FrameReading]:
    """Expose completed in-process readings without filesystem serialization."""
    return iter(tuple(CANDIDATE_FRAME_READINGS))
