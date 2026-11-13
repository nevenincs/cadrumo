"""A calculation note's served way out is offered beside the findings list through the refusal panel.

The note carries the verdict its reason and fact open. The list shows the note's
served sentence and the verdict's served words, routes the action by its served
target operations, and leaves the list for the destination the operator chooses.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import partial

import pytest
from textual.widgets import Button, Static

from ......application.modelo.work_form_declaration_facts import ModeloFormCalculationNote
from ......application.modelo.work_form_findings import ModeloFormAttention
from ......application.modelo.work_form_models import ModeloWorkForm
from ......application.modelo.work_form_notes import note_recovery
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ....components.host import ScreenHostApp
from ....navigation import TuiNavigationTargetV1
from ....refusal.intent import RefusalRouterV1
from ....refusal.panel import RefusalPanel
from ....refusal.routing import route_refusal_way
from ....refusal.served import ServedRefusalV1
from ....refusal.tests.refusal_fixtures import destinations, operations
from ....tests.settling import settle
from ..issue_scale import IssuesChoice
from ..issues import WorkbenchIssuesScreen
from .workbench_fixture import served_load, synthetic_form

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UNCLASSIFIED = "m349_operation_unclassified"
_INVOICE_ID = "ab" * 32
_WRITTEN = "Synthetic sentence: one invoice has no operation type."


@pytest.fixture(autouse=True)
def _english() -> Iterator[None]:
    with override_settings(cadrumo_output_language="en"):
        yield


def _fact() -> CalculationNoteFact:
    return CalculationNoteFact.of(
        CalculationNoteSentence.M349_OPERATION_UNCLASSIFIED,
        rows=(_INVOICE_ID,),
        invoice="DE-1",
        party="EU Counterparty GmbH (DE123456789)",
    )


def _form(*, door: bool) -> ModeloWorkForm:
    fact = _fact()
    note = ModeloFormCalculationNote(
        reason=_UNCLASSIFIED,
        attention=ModeloFormAttention.MISSING,
        box="12",
        fact=fact,
        message=_WRITTEN,
        recovery=note_recovery(_UNCLASSIFIED, fact, OutputLanguage.EN) if door else None,
    )
    return synthetic_form(needs_input=False).model_copy(update={"calculation_notes": (note,)})


class _Host(ScreenHostApp[IssuesChoice]):
    """A root that admits the destinations and records where a chosen way out leads."""

    def __init__(self, screen: WorkbenchIssuesScreen) -> None:
        super().__init__(screen)
        self.opened: list[TuiNavigationTargetV1] = []
        self.argument_values: dict[str, object] = {}

    async def refusal_router(self, refusal: ServedRefusalV1, /) -> RefusalRouterV1:
        del refusal
        return partial(route_refusal_way, destinations=destinations(), operations=operations())

    def on_refusal_panel_action_chosen(self, message: RefusalPanel.ActionChosen) -> None:
        message.stop()
        self.opened.append(message.intent.navigation_target())
        self.argument_values = {item.argument_name: item.value for item in message.intent.argument_bindings}


@pytest.mark.asyncio
async def test_a_note_with_a_way_out_offers_its_served_action_and_opens_the_destination() -> None:
    screen = WorkbenchIssuesScreen(served_load(_form(door=True)))
    app = _Host(screen)
    expected = note_recovery(_UNCLASSIFIED, _fact(), OutputLanguage.EN)
    assert expected is not None and expected.action_words is not None
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        sentence = str(screen.query_one(".issues-recovery-words", Static).render())
        (button,) = screen.query_one("#issues-recoveries").query(Button)
        assert sentence == f"[12] {_WRITTEN}"
        assert str(button.label) == f"{expected.action_words} …"
        assert not button.disabled
        await pilot.click(button)
        await settle(pilot)

    assert len(app.opened) == 1
    assert app.argument_values["invoice_id"] == _INVOICE_ID
    assert app.argument_values["operation_type"] is None


@pytest.mark.asyncio
async def test_a_host_that_admits_no_destination_shows_the_served_action_disabled() -> None:
    screen = WorkbenchIssuesScreen(served_load(_form(door=True)))
    app = ScreenHostApp(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        (button,) = screen.query_one("#issues-recoveries").query(Button)
        assert button.disabled
        assert screen.query_one("#refusal-unroutable", Static) is not None


@pytest.mark.asyncio
async def test_a_note_without_a_way_out_draws_no_recovery_area() -> None:
    screen = WorkbenchIssuesScreen(served_load(_form(door=False)))
    app = ScreenHostApp(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        assert not screen.query("#issues-recoveries")


def test_the_fixture_form_keeps_the_note_it_was_given() -> None:
    (note,) = _form(door=True).calculation_notes
    assert note.recovery is not None and note.message == _WRITTEN
