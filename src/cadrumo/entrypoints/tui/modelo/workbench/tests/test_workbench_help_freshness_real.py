"""Formula help follows the current calculation, including a fetch interrupted by a fresh read."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ......application.modelo.casilla_help import ModeloCasillaHelpCardV1
from ......application.modelo.edit_models import (
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ......application.modelo.work_form_models import ModeloFormCasillaAddressV1
from ......core.casilla_id import CasillaId
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from .....tests.modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work
from ....components.host import ScreenHostApp
from ....tests.modelo_workbench_session import application_workbench
from ..casilla_list_models import CasillaListEntry
from ..editor import CasillaEditorPanel
from ..installed import InstalledModeloWorkbench
from ..page_items import page_items
from ..screen import ModeloWorkbenchScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture
def calculated(tmp_path: Path) -> Iterator[tuple[SeededOperatorWork, InstalledModeloWorkbench]]:
    with seeded_operator_work(tmp_path) as work:
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, casilla_inputs={"06": Decimal("100")}, clock=SEEDED_AT
        )

        yield (
            work,
            application_workbench(work.work_unit, operation=work.operation),
        )


async def _set_retention(work: SeededOperatorWork, value: str) -> None:
    outcome = await asyncio.to_thread(
        work.apply,
        scalar=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id="06"),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value=Decimal(value),
            ),
        ),
    )
    assert outcome.refusal is None


async def _explanation(app: ScreenHostApp[None], pilot: Pilot[None]) -> str:
    screen = app.hosted_screen
    assert isinstance(screen, ModeloWorkbenchScreen)
    for _ in range(100):
        await pilot.pause()
        if screen.form is not None:
            break
    await pilot.press("g", "0", "7", "enter")
    await pilot.pause()
    await pilot.press("enter")
    for _ in range(100):
        await pilot.pause()
        panels = list(app.screen.query(CasillaEditorPanel))
        if panels and panels[0].query("#editor-calculation-text"):
            return str(panels[0].query_one("#editor-calculation-text", Static).render())
    raise AssertionError("the calculated box's explanation did not open")


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(80, 24), (120, 40)], ids=["dialog", "docked"])
async def test_reopening_help_uses_the_values_saved_by_apply_and_recalculation(
    calculated: tuple[SeededOperatorWork, InstalledModeloWorkbench], size: tuple[int, int]
) -> None:
    work, installed = calculated
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(installed, actions=installed)
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            before = await _explanation(app, pilot)
            assert "100.00" in before
            await pilot.press("escape")
            await pilot.pause()
            assert screen.form is not None
            before_head = screen.form.calculation_revision_id
            await _set_retention(work, "300")
            await screen._read()
            after_apply = await _explanation(app, pilot)
            assert screen.form.calculation_revision_id != before_head
            assert "300.00" in after_apply and "100.00" not in after_apply
            await pilot.press("escape")
            await pilot.pause()
            await _set_retention(work, "500")
            recalculated = await asyncio.to_thread(work.recalculate)
            assert recalculated.calculation_revision_id != screen.form.calculation_revision_id
            await screen._read()
            after_calculation = await _explanation(app, pilot)
            assert "500.00" in after_calculation and "300.00" not in after_calculation


@pytest.mark.asyncio
async def test_a_help_fetch_from_the_previous_head_cannot_repopulate_the_fresh_cache(
    calculated: tuple[SeededOperatorWork, InstalledModeloWorkbench], monkeypatch: pytest.MonkeyPatch
) -> None:
    work, installed = calculated
    started = threading.Event()
    release = threading.Event()
    original = installed.help_card

    def delayed(casilla_id: CasillaId, language: OutputLanguage) -> ModeloCasillaHelpCardV1:
        card = original(casilla_id, language)
        if casilla_id == "07" and not started.is_set():
            started.set()
            assert release.wait(timeout=20), "the test did not release the old help read"
        return card

    monkeypatch.setattr(installed, "help_card", delayed)
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(installed, actions=installed)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(100):
                await pilot.pause()
                if screen.form is not None:
                    break
            assert screen.form is not None
            entry = next(
                item
                for page in screen._pages
                for item in page_items(page, staged={})
                if isinstance(item, CasillaListEntry)
                and item.field.address == ModeloFormCasillaAddressV1(casilla_id="07")
            )
            pending = asyncio.create_task(screen._open_editor_once_explained(entry))
            try:
                assert await asyncio.to_thread(started.wait, 20)
                await _set_retention(work, "300")
                await screen._read()
            finally:
                release.set()
            await pending
            await pilot.pause()
            assert not app.screen.query(CasillaEditorPanel), "an old editor must not reopen after a fresh read"
            shown = await _explanation(app, pilot)
            assert "300.00" in shown and "100.00" not in shown
