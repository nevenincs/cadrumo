"""The workbench offers the IVA balance only where the form serves it, and re-reads the declaration after a recording.

Driven through the standalone host with the real workbench and dialog widgets.
The door stands at the runtime boundary and answers with the application's own
projections. The key is offered when the form says the declaration offers the
balance and a host bound a door; otherwise the footer names no key and the key
opens nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

import pytest
from textual.widgets import Button, Input, Static

from ......application.modelo.iva_wallet_balance_operation import ModeloIvaWalletBalanceProjection
from ......application.modelo.iva_wallet_seed_operation import ModeloIvaWalletSeedProjection
from ......application.modelo.work_form_models import ModeloWorkForm
from ......application.operations.public_period import PublicPeriod
from ......core.config import override_settings
from ......core.i18n.render import tr
from ......core.iva_compensation_provenance import IvaCompensationStateProvenance
from ....components.host import ScreenHostApp
from ....tests.settling import settle
from ...wallet import IvaWalletEntryV1, IvaWalletReceiptV1
from ...wallet_screen import ModeloIvaWalletScreen
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WIDE: Final = (400, 48)
_PROFILE: Final = UUID("5aa00000-0000-4000-8000-0000000000aa")


@pytest.fixture(autouse=True)
def _english() -> Iterator[None]:
    with override_settings(cadrumo_output_language="en"):
        yield


def _form(*, offers: bool) -> ModeloWorkForm:
    return synthetic_form().model_copy(update={"offers_iva_wallet": offers})


@dataclass
class FakeDoor:
    read: list[int] = field(default_factory=list)
    recorded: list[IvaWalletEntryV1] = field(default_factory=list)

    def read_balance(self, as_of_year: int) -> ModeloIvaWalletBalanceProjection:
        self.read.append(as_of_year)
        return ModeloIvaWalletBalanceProjection(
            profile_id=_PROFILE,
            as_of_year=as_of_year,
            total_balance="10.00",
            active_balance="10.00",
            expired_balance="0",
            lot_count=1,
            next_expiry_year=as_of_year + 1,
            unallocated_applied_amount="0",
        )

    def record(self, entry: IvaWalletEntryV1) -> IvaWalletReceiptV1:
        self.recorded.append(entry)
        return ModeloIvaWalletSeedProjection(
            profile_id=_PROFILE,
            period=PublicPeriod(filing_year=entry.filing_year, code=entry.period_code),
            taxpayer_nif="00000000T",
            amount=entry.amount,
            provenance=IvaCompensationStateProvenance.OPERATOR_SEED,
        )


def _footer_keys(screen: ModeloWorkbenchScreen) -> dict[str, str]:
    return {key: active.binding.description for key, active in screen.active_bindings.items() if active.binding.show}


def _workbench(
    door: FakeDoor | None, form: ModeloWorkForm
) -> tuple[ModeloWorkbenchScreen, ScreenHostApp[None], FakeReader]:
    reader = FakeReader(form=form)
    screen = ModeloWorkbenchScreen(reader, actions=FakeActions(), wallet=door)
    return screen, ScreenHostApp(screen), reader


@pytest.mark.asyncio
async def test_a_form_that_does_not_offer_the_balance_names_no_key_and_the_key_opens_nothing() -> None:
    door = FakeDoor()
    _screen, app, _reader = _workbench(door, _form(offers=False))
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        footer = _footer_keys(_screen)
        await pilot.press("w")
        await settle(pilot)
        stack = [type(item) for item in pilot.app.screen_stack]

    assert "w" not in footer
    assert ModeloIvaWalletScreen not in stack
    assert door.read == []


@pytest.mark.asyncio
async def test_a_host_that_bound_no_door_offers_no_key_even_where_the_form_serves_the_balance() -> None:
    screen, app, _reader = _workbench(None, _form(offers=True))
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        footer = _footer_keys(screen)
        await pilot.press("w")
        await settle(pilot)
        stack = [type(item) for item in pilot.app.screen_stack]

    assert "w" not in footer
    assert ModeloIvaWalletScreen not in stack


@pytest.mark.asyncio
async def test_where_the_form_serves_the_balance_the_footer_names_the_key_and_it_opens_the_balance() -> None:
    door = FakeDoor()
    screen, app, _reader = _workbench(door, _form(offers=True))
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        footer = _footer_keys(screen)
        await pilot.press("w")
        await settle(pilot)
        dialog = app.screen
        assert isinstance(dialog, ModeloIvaWalletScreen)
        figures = str(dialog.query_one("#wallet-balance", Static).render())

    assert footer["w"] == tr("tui.modelo.wallet.key")
    assert door.read == [synthetic_form().filing_year]
    assert "10" in figures


@pytest.mark.asyncio
async def test_a_recording_reads_the_declaration_again_and_says_it_was_recorded() -> None:
    door = FakeDoor()
    screen, app, reader = _workbench(door, _form(offers=True))
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        await pilot.press("w")
        await settle(pilot)
        dialog = app.screen
        assert isinstance(dialog, ModeloIvaWalletScreen)
        dialog.query_one("#wallet-amount", Input).value = "25.00"
        await settle(pilot)
        dialog.query_one("#wallet-submit", Button).press()
        await settle(pilot)
        dialog.action_close()
        await settle(pilot)
        back_on_workbench = app.screen is screen
        notice = str(screen.query_one("#wb-notice", Static).render())

    assert [entry.amount for entry in door.recorded] == ["25.00"]
    assert back_on_workbench
    assert reader.loads == 2
    assert notice == tr("workspace.modelo.iva_wallet.recorded")


@pytest.mark.asyncio
async def test_closing_without_recording_leaves_the_declaration_unread_again() -> None:
    door = FakeDoor()
    screen, app, reader = _workbench(door, _form(offers=True))
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        await pilot.press("w")
        await settle(pilot)
        app.screen.dismiss(None)
        await settle(pilot)
        back = app.screen is screen

    assert back
    assert reader.loads == 1
    assert door.recorded == []
