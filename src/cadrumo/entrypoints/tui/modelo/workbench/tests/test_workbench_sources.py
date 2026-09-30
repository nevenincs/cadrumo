"""The sources view groups each box under the sources that feed it and leads back to the box or its source.

The grouping runs over the synthetic form with the product's real source
policies: families in the filer's order, each source with what may be done
about it and whether it produced anything, each box listed once and noted under
any further source. Driven through the standalone host, the view opens on the
box under the cursor, returns to a chosen box on its own page, and opens the
owning product area only after the filer has decided about staged changes.
"""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.source_policy import SourceSurface
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ....navigation import TuiNavigationTargetV1, declared_destination_ids
from ..casilla_list import CasillaList
from ..screen import ModeloWorkbenchScreen
from ..sources import WorkbenchSourcesScreen, source_groups, sources_listing, surface_target
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _lines(widget: CasillaList) -> list[str]:
    return [widget.render_line(y).text.rstrip() for y in range(widget.size.height)]


def test_each_box_sits_under_its_family_and_source_with_the_source_policy_and_state() -> None:
    with override_settings(cadrumo_output_language="es"):
        listing = sources_listing(source_groups(synthetic_form()), staged={})
        texts = [getattr(item, "text", None) for item in listing.items]

    assert texts == [
        "Tu contabilidad",
        "Totales de ingresos · se corrige en su origen · con datos",
        None,
        "Totales de gastos en estimación directa · se corrige en su origen · con datos",
        None,
        "Registros que llevas",
        "Totales de retenciones · aún no se puede cambiar aquí · sin datos: 1 de 1",
        None,
        "Registro de retención · aún no se puede cambiar aquí · con datos",
        "[06] Retenciones e ingresos a cuenta · ya aparece arriba",
    ]
    assert listing.listed_under[("casilla", "06")].source_kind is BindingSourceKind.RETENCIONES_AGGREGATION
    assert listing.listed_under[("casilla", "01")].surface is SourceSurface.LEDGER
    assert ("casilla", "03") not in listing.listed_under


def test_every_owning_surface_opens_a_declared_destination_and_none_opens_nothing() -> None:
    for surface in SourceSurface:
        target = surface_target(surface)
        if surface is SourceSurface.NONE:
            assert target is None
        else:
            assert target is not None
            assert target.destination in declared_destination_ids()


@pytest.mark.asyncio
async def test_sources_open_on_the_box_under_the_cursor_and_lead_back_to_a_chosen_box() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("s")
            await _settle(pilot)
            sources = app.screen
            assert isinstance(sources, WorkbenchSourcesScreen)
            opened_on = sources.query_one(CasillaList).highlighted
            await pilot.press("home", "enter")
            await _settle(pilot)
            back = app.screen is screen
            landed_on = screen.query_one(CasillaList).highlighted
            page = str(screen.query_one("#wb-page", Static).render())

    assert opened_on is not None
    assert opened_on.field.box == "06"
    assert back
    assert landed_on is not None
    assert landed_on.field.box == "01"
    assert page.startswith("Liquidación")


@pytest.mark.asyncio
async def test_opening_a_source_shows_staged_changes_and_asks_before_leaving_them() -> None:
    navigated: list[TuiNavigationTargetV1] = []
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions(), navigate=navigated.append)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"10", "enter")
            await _settle(pilot)
            await pilot.press("s")
            await _settle(pilot)
            staged_line = next(
                line for line in _lines(app.screen.query_one(CasillaList)) if "Retenciones e ingresos" in line
            )
            await pilot.press("o")
            await _settle(pilot)
            asked = isinstance(app.screen, ConfirmScreen)
            navigated_before_answer = list(navigated)
            await pilot.press("y")
            await _settle(pilot)

    assert "Δ" in staged_line
    assert asked
    assert navigated_before_answer == []
    assert [target.destination for target in navigated] == ["workbench.withholding"]


@pytest.mark.asyncio
async def test_without_a_way_to_open_other_areas_the_workbench_says_where_to_find_the_source() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("s")
            await _settle(pilot)
            await pilot.press("o")
            await _settle(pilot)
            back = app.screen is screen
            notice = str(screen.query_one("#wb-notice", Static).render())

    assert back
    assert notice == "That area cannot be opened from here; open it from the main menu."
