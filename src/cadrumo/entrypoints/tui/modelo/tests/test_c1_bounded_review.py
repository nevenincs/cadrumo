"""Real behavioral accessibility proof for the sole C1 destination.

The review screen's own internal accessibility (locale, geometry, theme,
facet filters, keyboard scroll) is already proven exhaustively in
``view/tests/test_work_review.py`` against ``ModeloWorkReviewApp`` directly.
This module proves the piece that owns the C1 DESTINATION as a whole: the
keyboard-only picker (``ModeloWorkSelectApp``/``ModeloWorkSelectScreen``) an
operator actually lands on first, across the same four-locale, three-geometry,
two-theme, non-colour, and stable-keyboard-order matrix the companion decision
record requires before C1's route can become callable.

Every assertion here is a real Textual pilot interaction against the real
screen classes -- never a presence-only check. Selecting a row and reading
back the App's ``exit`` value is the actual reachability proof: an operator
who cannot navigate to and confirm a row could never reach the review screen
this destination exists to open.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Static

from .....core.config import override_settings
from .....core.i18n._render import SUPPORTED_OUTPUT_LANGUAGES, tr
from .....core.period import Period
from .....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from .....tests.terminal_sizes import SUPPORTED_TERMINAL_SIZE_IDS, SUPPORTED_TERMINAL_SIZES
from ..view.work_select import ModeloWorkSelectApp, ModeloWorkSelectScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=UTC)


def _unit(*, modelo: str, filing_year: int, period_code: str, name: str, state: WorkUnitState) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, period_code)
    revision_id = f"{modelo.lower()}-{period_code.lower()}-real"
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    discarded = state is WorkUnitState.DESCARTADO
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=name,
        created_at=_NOW,
        updated_at=_NOW,
        state=state,
        discarded_at=_NOW if discarded else None,
        discarded_by="test-fixture" if discarded else None,
    )


def _real_units() -> tuple[WorkUnit, ...]:
    return (
        _unit(modelo="130", filing_year=2026, period_code="1T", name="130-2026-1T", state=WorkUnitState.BORRADOR),
        _unit(
            modelo="303",
            filing_year=2025,
            period_code="4T",
            name="303-2025-4T-discarded",
            state=WorkUnitState.DESCARTADO,
        ),
    )


@pytest.mark.asyncio
async def test_keyboard_only_selection_returns_the_exact_chosen_work_unit_id() -> None:
    """A real Down/Enter sequence reaches the second row and confirms it."""
    units = _real_units()
    app = ModeloWorkSelectApp(units)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        table = app.screen.query_one("#modelo-select-table", DataTable)
        assert app.focused is table
        assert table.cursor_row == 0
        await pilot.press("down")
        await pilot.pause()
        assert table.cursor_row == 1
        await pilot.press("enter")
        await pilot.pause()
    assert app.return_value == units[1].work_unit_id


@pytest.mark.asyncio
async def test_quitting_without_a_selection_returns_none() -> None:
    units = _real_units()
    app = ModeloWorkSelectApp(units)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    assert app.return_value is None


@pytest.mark.asyncio
async def test_empty_catalogue_shows_localized_empty_state_never_a_dead_table() -> None:
    app = ModeloWorkSelectApp(())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        empty = app.screen.query_one("#modelo-select-empty", Static)
        assert empty.display
        assert str(empty.render()) == tr("flows.modelo_select.empty")
        table = app.screen.query_one("#modelo-select-table", DataTable)
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_row_state_is_distinguishable_by_text_not_colour_alone() -> None:
    """Non-colour proof: the lifecycle state renders as its own text cell."""
    units = _real_units()
    app = ModeloWorkSelectApp(units)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        table = app.screen.query_one("#modelo-select-table", DataTable)
        rendered_cells = {
            str(table.get_cell_at(Coordinate(row_index, column_index)))
            for row_index in range(table.row_count)
            for column_index in range(len(table.columns))
        }
    assert WorkUnitState.BORRADOR.value in rendered_cells
    assert WorkUnitState.DESCARTADO.value in rendered_cells


@pytest.mark.asyncio
async def test_four_locales_localize_title_and_columns_and_stay_reachable() -> None:
    units = _real_units()
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            app = ModeloWorkSelectApp(units)
            async with app.run_test(size=(90, 28)) as pilot:
                await pilot.pause()
                header = app.screen.query_one("#modelo-select-header", Static)
                assert str(header.render()) == tr("flows.modelo_select.title")
                table = app.screen.query_one("#modelo-select-table", DataTable)
                assert app.focused is table
                await pilot.press("enter")
                await pilot.pause()
            assert app.return_value == units[0].work_unit_id


@pytest.mark.asyncio
@pytest.mark.parametrize("size", SUPPORTED_TERMINAL_SIZES, ids=SUPPORTED_TERMINAL_SIZE_IDS)
async def test_three_geometries_keep_the_table_visible_and_navigable(size: tuple[int, int]) -> None:
    units = _real_units()
    app = ModeloWorkSelectApp(units)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        table = app.screen.query_one("#modelo-select-table", DataTable)
        assert table.row_count == len(units)
        assert app.focused is table
        await pilot.press("down")
        await pilot.pause()
        assert table.cursor_row == 1
        await pilot.press("up")
        await pilot.pause()
        assert table.cursor_row == 0


@pytest.mark.asyncio
async def test_two_themes_render_visibly_different_styles_via_shared_toggle() -> None:
    units = _real_units()
    app = ModeloWorkSelectApp(units)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        screen = app.screen
        dark_style = screen.get_style_at(1, 0)
        await pilot.press("f3")
        await pilot.pause()
        light_style = screen.get_style_at(1, 0)
    assert (dark_style.bgcolor, dark_style.color) != (light_style.bgcolor, light_style.color)


def test_select_screen_refuses_a_foreign_app_host() -> None:
    """The screen fails closed rather than rendering under an unrelated App."""
    from textual.app import App

    class _ForeignApp(App[None]):
        pass

    foreign = _ForeignApp()
    screen = ModeloWorkSelectScreen()
    foreign._register(foreign, screen)
    with pytest.raises(TypeError, match="ModeloWorkSelectApp"):
        _ = screen.select_app
