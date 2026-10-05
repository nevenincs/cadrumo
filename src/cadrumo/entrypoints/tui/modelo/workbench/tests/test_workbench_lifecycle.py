"""The workbench runs a declaration's lifecycle and never skips a question the step must ask.

Driven through the standalone host with a fake actions port that records what
it was asked: a Modelo 303 calculation first asks its filing answers and
cancelling them calculates nothing; staged changes are applied or discarded
before a recalculation; a registered refusal is shown in its own words; and an
export is offered only once verified, submitting every election, asked or
defaulted.
"""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, Select, Static

from ......core.config import override_settings
from ......core.i18n.render import tr
from ......core.payment_election import PaymentElection
from ......core.prior_domiciliation_election import PriorDomiciliationElection
from ......core.refund_election import RefundElection
from ....components.host import ScreenHostApp
from ...lifecycle import ModeloLifecycleActionUnavailableError
from ...m303_evidence import OrdinaryM303FilingEvidenceScreen
from ..export import WorkbenchExportScreen
from ..ports import WorkbenchCalculationEvidence
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeActions, FakeReader

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _notice(screen: ModeloWorkbenchScreen) -> str:
    return str(screen.query_one("#wb-notice", Static).render())


@pytest.mark.asyncio
async def test_a_303_calculation_asks_its_answers_and_cancelling_calculates_nothing() -> None:
    actions = FakeActions(evidence=WorkbenchCalculationEvidence(work_unit_id="a" * 64, asks_modelo_390=False))
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("c")
            await _settle(pilot)
            asked = isinstance(app.screen, OrdinaryM303FilingEvidenceScreen)
            await pilot.press("escape")
            await _settle(pilot)
            notice = _notice(screen)

    assert asked
    assert actions.requested == []
    assert notice == tr("tui.modelo.m303_evidence.cancelled", locale="es")


@pytest.mark.asyncio
async def test_staged_changes_are_applied_before_a_recalculation() -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"10", "enter")
            await _settle(pilot)
            await pilot.press("c")
            await _settle(pilot)
            notice = _notice(screen)

    assert actions.requested == []
    assert notice == "Apply or discard your changes before recalculating [R]."


@pytest.mark.asyncio
async def test_a_registered_refusal_is_shown_in_its_own_words() -> None:
    actions = FakeActions(
        refusal=ModeloLifecycleActionUnavailableError(translated_message="tui.modelo.m303_evidence.stale_context")
    )
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("c")
            await _settle(pilot, 6)
            notice = _notice(screen)

    assert actions.requested == ["calculate"]
    assert notice == tr("tui.modelo.m303_evidence.stale_context", locale="en")


@pytest.mark.asyncio
async def test_an_export_waits_for_verification() -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(verified=False), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("e")
            await _settle(pilot)
            still_workbench = app.screen is screen
            notice = _notice(screen)

    assert still_workbench
    assert notice == tr("tui.modelo.workbench.export.verify_first", locale="en")
    assert actions.exports == []


@pytest.mark.asyncio
async def test_an_export_submits_the_elections_it_asked_and_defaults_the_rest() -> None:
    asking = FakeActions(asks_elections=True)
    silent = FakeActions()
    with override_settings(cadrumo_output_language="es"):
        for actions in (asking, silent):
            screen = ModeloWorkbenchScreen(FakeReader(verified=True), actions=actions)
            app = ScreenHostApp(screen)
            async with app.run_test(size=(140, 48)) as pilot:
                await _settle(pilot)
                await pilot.press("e")
                await _settle(pilot)
                dialog = app.screen
                assert isinstance(dialog, WorkbenchExportScreen)
                elections = len(dialog.query(Select)) - 1
                if actions is asking:
                    dialog.query_one("#export-payment-election", Select).value = PaymentElection.DOMICILIACION.value
                await pilot.press(*"salida.txt")
                dialog.query_one("#export-path", Input).focus()
                await pilot.press("enter")
                await _settle(pilot, 6)
                assert (elections == 3) is (actions is asking)

    (asked,) = asking.exports
    (defaulted,) = silent.exports
    assert asked.output_path == "salida.txt"
    assert asked.payment_election is PaymentElection.DOMICILIACION
    assert asked.refund_election is RefundElection.COMPENSAR
    assert defaulted.payment_election is PaymentElection.INGRESO
    assert defaulted.prior_domiciliation_election is PriorDomiciliationElection.KEEP
    assert not defaulted.replace_existing
