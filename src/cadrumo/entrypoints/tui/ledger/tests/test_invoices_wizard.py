"""Mounted step-by-step invoice wizard over the registered wizard request and outcome."""

from __future__ import annotations

from typing import cast, override

import pytest
from textual.containers import Vertical, VerticalScroll
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static
from textual.worker import NoActiveWorker, get_current_worker

from .....application.invoices.catalogue_intake_contracts import InvoiceWizardOutcome, InvoiceWizardRequest
from .....application.ledger.workspace import LedgerWorkspaceArea
from .....core.aggregation import IntracomOperationType
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.invoices.errors import InvoiceValidationError
from .....domain.iva.schema import InvoiceKind
from ...components.host import ScreenHostApp
from ...tests.frame import geometry_band
from ..controller import LedgerWorkspaceController
from ..invoices_wizard import LedgerInvoiceWizardScreen
from ..models import LedgerFlowState
from ..workspace_injection import LedgerWorkspaceInjection
from ..workspace_presentation import door_refusal_text
from .invoices_fixtures import INVOICES_PROFILE_ID, MemoryInvoiceWizardDoor, ReplacingHostApp
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_TYPED = {
    "counterparty_name": "Synthetic customer",
    "counterparty_nif": "B00000000",
    "country_code": "ES",
    "invoice_number": "W-0001",
    "invoice_date": "2026-03-15",
    "taxable_base": "100.00",
    "iva_rate": "21",
    "notes": "typed in the wizard",
}


def _screen(door: MemoryInvoiceWizardDoor) -> LedgerInvoiceWizardScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    return LedgerInvoiceWizardScreen(controller, door)


def _text(screen: LedgerInvoiceWizardScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _visible_step(screen: LedgerInvoiceWizardScreen) -> list[str]:
    return [str(step.id) for step in screen.query(".ledger-invoices-step").results(Vertical) if step.display]


async def _settle(pilot: Pilot[None]) -> None:
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _press(pilot: Pilot[None], screen: LedgerInvoiceWizardScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await _settle(pilot)


async def _fill_and_review(pilot: Pilot[None], screen: LedgerInvoiceWizardScreen) -> None:
    cast("Select[str]", screen.query_one("#ledger-invoices-wizard-kind", Select)).value = InvoiceKind.ISSUED.value
    for name, value in _TYPED.items():
        screen.query_one(f"#ledger-invoices-wizard-{name.replace('_', '-')}", Input).value = value
    cast("Select[str]", screen.query_one("#ledger-invoices-wizard-operation-type", Select)).value = "E"
    for _ in range(3):
        await _press(pilot, screen, "ledger-invoices-wizard-next")
    await _press(pilot, screen, "ledger-invoices-wizard-review")


@pytest.mark.asyncio
async def test_the_wizard_moves_step_by_step_and_records_exactly_the_reviewed_request() -> None:
    door = MemoryInvoiceWizardDoor()
    screen = _screen(door)
    async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        assert _visible_step(screen) == ["ledger-invoices-wizard-step-counterparty"]
        assert screen.query_one("#ledger-invoices-wizard-previous", Button).disabled
        assert not screen.query_one("#ledger-invoices-wizard-review", Button).display
        await _press(pilot, screen, "ledger-invoices-wizard-next")
        assert _visible_step(screen) == ["ledger-invoices-wizard-step-invoice"]
        await _press(pilot, screen, "ledger-invoices-wizard-previous")
        assert _visible_step(screen) == ["ledger-invoices-wizard-step-counterparty"]

        await _fill_and_review(pilot, screen)
        assert screen.flow_state is LedgerFlowState.CONFIRMING
        assert door.requests == []
        assert _visible_step(screen) == []
        summary = _text(screen, "#ledger-invoices-wizard-summary")
        assert f"{tr('tui.ledger.invoice.field.invoice_number')}: W-0001" in summary
        assert f"{tr('tui.ledger.invoice.field.operation_type')}: E" in summary
        await _press(pilot, screen, "ledger-invoices-wizard-confirm")
        assert screen.flow_state is LedgerFlowState.SUCCEEDED
        assert _text(screen, "#ledger-flow-status") == tr(
            "tui.ledger.invoices.wizard.recorded", number="W-0001", total="121.00 EUR"
        )
    assert door.requests == [
        InvoiceWizardRequest(
            profile_id=INVOICES_PROFILE_ID,
            kind=InvoiceKind.ISSUED,
            counterparty_nif="B00000000",
            counterparty_name="Synthetic customer",
            invoice_number="W-0001",
            invoice_date="2026-03-15",
            taxable_base="100.00",
            iva_rate="21",
            currency="EUR",
            country_code="ES",
            notes="typed in the wizard",
            operation_type=IntracomOperationType("E"),
        )
    ]


@pytest.mark.asyncio
async def test_field_refusals_are_listed_and_correcting_reopens_at_the_first_refused_step() -> None:
    door = MemoryInvoiceWizardDoor()
    door.refused_fields = (("taxable_base", "must be a number"), ("invoice_date", "must be a date"))
    screen = _screen(door)
    screen.back_area = LedgerWorkspaceArea.OVERVIEW
    async with ReplacingHostApp(screen).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        await _fill_and_review(pilot, screen)
        await _press(pilot, screen, "ledger-invoices-wizard-confirm")
        assert screen.flow_state is LedgerFlowState.FAILED
        assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.invoices.wizard.refused")
        refusal = _text(screen, "#ledger-refusal")
        assert f"{tr('tui.ledger.invoice.field.taxable_base')}: must be a number" in refusal
        assert f"{tr('tui.ledger.invoice.field.invoice_date')}: must be a date" in refusal
        await _press(pilot, screen, "ledger-invoices-wizard-again")
        await _settle(pilot)
        fresh = pilot.app.screen
        assert isinstance(fresh, LedgerInvoiceWizardScreen)
        assert fresh is not screen
        assert fresh.back_area is LedgerWorkspaceArea.OVERVIEW
        assert _visible_step(fresh) == ["ledger-invoices-wizard-step-invoice"]
        assert fresh.query_one("#ledger-invoices-wizard-invoice-number", Input).value == "W-0001"
        assert str(cast("Select[str]", fresh.query_one("#ledger-invoices-wizard-operation-type", Select)).value) == "E"


@pytest.mark.asyncio
async def test_a_typed_door_refusal_is_shown_and_cancelling_writes_nothing() -> None:
    door = MemoryInvoiceWizardDoor()
    refusal = InvoiceValidationError("IVA category is not declared by the active registry")
    door.refusal = refusal
    screen = _screen(door)
    async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        await _fill_and_review(pilot, screen)
        await _press(pilot, screen, "ledger-invoices-wizard-confirm")
        assert screen.flow_state is LedgerFlowState.FAILED
        assert _text(screen, "#ledger-refusal") == door_refusal_text(refusal)

    cancelled_door = MemoryInvoiceWizardDoor()
    cancelled = _screen(cancelled_door)
    async with ScreenHostApp[None](cancelled).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        await _fill_and_review(pilot, cancelled)
        await _press(pilot, cancelled, "ledger-invoices-wizard-cancel")
        assert cancelled.flow_state is LedgerFlowState.CANCELLED
        assert _text(cancelled, "#ledger-flow-status") == tr("tui.ledger.invoices.wizard.cancelled")
    assert cancelled_door.requests == []


class _WorkerOnlyWizardDoor(MemoryInvoiceWizardDoor):
    def __init__(self) -> None:
        super().__init__()
        self.in_worker: list[bool] = []

    @override
    async def __call__(self, request: InvoiceWizardRequest) -> InvoiceWizardOutcome:
        try:
            get_current_worker()
        except NoActiveWorker:
            self.in_worker.append(False)
        else:
            self.in_worker.append(True)
        return await super().__call__(request)


@pytest.mark.asyncio
async def test_the_wizard_door_runs_only_in_a_worker() -> None:
    door = _WorkerOnlyWizardDoor()
    screen = _screen(door)
    async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
        await _settle(pilot)
        await _fill_and_review(pilot, screen)
        await _press(pilot, screen, "ledger-invoices-wizard-confirm")
    assert door.in_worker == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", ("cadrumo-dark", "cadrumo-light"))
@pytest.mark.parametrize("size", ((80, 24), (100, 30), (120, 40), (200, 50)))
async def test_every_wizard_step_fits_every_supported_terminal(theme: str, size: tuple[int, int]) -> None:
    door = MemoryInvoiceWizardDoor()
    screen = _screen(door)
    app = ScreenHostApp[None](screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            await _settle(pilot)
            for step in range(4):
                if step:
                    await _press(pilot, screen, "ledger-invoices-wizard-next")
                assert geometry_band(app, size[0]) == []
                assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
                owners = [w for w in screen.query(VerticalScroll) if w.display and w.show_vertical_scrollbar]
                assert all(owner.id == "ledger-page" for owner in owners)
