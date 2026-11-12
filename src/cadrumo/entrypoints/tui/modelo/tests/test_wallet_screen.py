"""The IVA balance dialog shows exactly what the application served and sends what the filer typed.

Driven through the standalone screen host with the real widgets. The door stands
at the runtime boundary: it records each call and whether an event loop was
running on the calling thread, and answers with the application's own
projections. Every figure is served; the cases check that the dialog draws them
as served, never as zero when nothing was served, and that a recording is sent
with exactly the coordinates typed. Data is synthetic. The dialog's own words
are catalogue keys under ``tui.modelo.wallet``; the cases compare against the
catalogue's rendering and so hold while those keys are not yet carried.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final, override
from uuid import UUID

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, OptionList, Static

from .....application.modelo.iva_wallet_balance_operation import ModeloIvaWalletBalanceProjection
from .....application.modelo.iva_wallet_correction_operation import ModeloIvaWalletCorrectionProjection
from .....application.modelo.iva_wallet_override_operation import ModeloIvaWalletOverrideProjection
from .....application.modelo.iva_wallet_seed_operation import ModeloIvaWalletSeedProjection
from .....application.operations.public_period import PublicPeriod
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...components.host import ScreenHostApp
from ...refusal.panel import RefusalSlot
from ...refusal.served import ServedRefusalV1, ServedWordsV1
from ...tests.settling import settle
from ..wallet import (
    IvaWalletActionKind,
    IvaWalletEntryV1,
    IvaWalletNotSentError,
    IvaWalletReceiptV1,
    IvaWalletRefusedError,
    offers_iva_wallet,
)
from ..wallet_screen import ModeloIvaWalletScreen, balance_lines, mode_label_key
from ..workbench.tests.workbench_fixture import synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _english() -> Iterator[None]:
    with override_settings(cadrumo_output_language="en"):
        yield


_PROFILE: Final = UUID("5aa00000-0000-4000-8000-0000000000aa")
_NIF: Final = "00000000T"
_FORM = synthetic_form()
_PERIOD = PublicPeriod.from_period(_FORM.period)
_REFUSAL_SENTENCE: Final = "Served sentence: the opening balance was not admitted."


def _balance(
    *, total: str = "300.00", active: str = "200.00", expired: str = "100.00", lots: int = 2, expiry: int | None = None
) -> ModeloIvaWalletBalanceProjection:
    return ModeloIvaWalletBalanceProjection(
        profile_id=_PROFILE,
        as_of_year=_FORM.filing_year,
        total_balance=total,
        active_balance=active,
        expired_balance=expired,
        lot_count=lots,
        next_expiry_year=expiry if expiry is not None else _FORM.filing_year + 3,
        unallocated_applied_amount="12.50",
    )


def _seed(amount: str) -> ModeloIvaWalletSeedProjection:
    return ModeloIvaWalletSeedProjection(
        profile_id=_PROFILE,
        period=_PERIOD,
        taxpayer_nif=_NIF,
        amount=amount,
        provenance=IvaCompensationStateProvenance.OPERATOR_SEED,
    )


def _correction(amount: str, previous: str, reason: str) -> ModeloIvaWalletCorrectionProjection:
    return ModeloIvaWalletCorrectionProjection(
        profile_id=_PROFILE,
        period=_PERIOD,
        taxpayer_nif=_NIF,
        previous_amount=previous,
        amount=amount,
        provenance=IvaCompensationStateProvenance.OPERATOR_CORRECTION,
        reason=reason,
    )


def _override(amount: str, reason: str, evidence: str) -> ModeloIvaWalletOverrideProjection:
    return ModeloIvaWalletOverrideProjection(
        profile_id=_PROFILE,
        period=_PERIOD,
        taxpayer_nif=_NIF,
        amount=amount,
        reason=reason,
        evidence_locator=evidence,
        selected_authority="taxpayer_override",
        divergence="override",
    )


def _served_refusal() -> ServedRefusalV1:
    return ServedRefusalV1(refusal_words=ServedWordsV1(words=_REFUSAL_SENTENCE, language=OutputLanguage.EN))


@dataclass
class FakeDoor:
    """Stands at the runtime boundary: records each call and whether it ran on an event loop."""

    balances: list[ModeloIvaWalletBalanceProjection | Exception] = field(default_factory=list)
    answer: IvaWalletReceiptV1 | Exception | None = None
    read: list[int] = field(default_factory=list)
    recorded: list[IvaWalletEntryV1] = field(default_factory=list)
    on_loop: list[str] = field(default_factory=list)

    def _enter(self, name: str) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self.on_loop.append(name)

    def read_balance(self, as_of_year: int) -> ModeloIvaWalletBalanceProjection:
        self._enter("read_balance")
        self.read.append(as_of_year)
        served = self.balances[min(len(self.read), len(self.balances)) - 1]
        if isinstance(served, Exception):
            raise served
        return served

    def record(self, entry: IvaWalletEntryV1) -> IvaWalletReceiptV1:
        self._enter("record")
        self.recorded.append(entry)
        if isinstance(self.answer, Exception):
            raise self.answer
        assert self.answer is not None
        return self.answer


def _screen(door: FakeDoor) -> ModeloIvaWalletScreen:
    return ModeloIvaWalletScreen(door, form=_FORM)


def _text(screen: ModeloIvaWalletScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


async def _fill[ResultT](pilot: Pilot[ResultT], screen: ModeloIvaWalletScreen, **values: str) -> None:
    for name, value in values.items():
        screen.query_one(f"#wallet-{name}", Input).value = value
    await settle(pilot)


async def _choose[ResultT](pilot: Pilot[ResultT], screen: ModeloIvaWalletScreen, kind: IvaWalletActionKind) -> None:
    screen.query_one("#wallet-modes", OptionList).highlighted = list(IvaWalletActionKind).index(kind)
    await settle(pilot)


async def _send[ResultT](pilot: Pilot[ResultT], screen: ModeloIvaWalletScreen) -> None:
    screen.query_one("#wallet-submit", Button).press()
    await settle(pilot)


@pytest.mark.asyncio
async def test_the_served_balance_is_drawn_figure_by_figure_off_the_event_loop() -> None:
    door = FakeDoor(balances=[_balance()])
    screen = _screen(door)
    async with ScreenHostApp(screen).run_test(size=(120, 50)) as pilot:
        await settle(pilot)
        shown = _text(screen, "#wallet-balance")
        status_shown = screen.query_one("#wallet-status").display
        phase = screen.phase
    expected = "\n".join(balance_lines(_balance(), OutputLanguage.EN))

    assert door.read == [_FORM.filing_year]
    assert door.on_loop == []
    assert phase == "ready" and not status_shown
    assert shown == expected, (shown, expected)
    assert "300" in shown and "200" in shown and "100" in shown and "12" in shown
    assert str(_FORM.filing_year + 3) in shown


@pytest.mark.asyncio
async def test_a_balance_without_lots_is_drawn_with_its_served_zeros_and_says_no_lot_is_recorded() -> None:
    door = FakeDoor(balances=[_balance(total="0", active="0", expired="0", lots=0)])
    screen = _screen(door)
    async with ScreenHostApp(screen).run_test(size=(120, 50)) as pilot:
        await settle(pilot)
        shown = _text(screen, "#wallet-balance")

    assert shown.splitlines()[:-1] == list(
        balance_lines(_balance(total="0", active="0", expired="0", lots=0), OutputLanguage.EN)
    )
    assert shown.splitlines()[-1] == tr("tui.modelo.wallet.no_lots")


@pytest.mark.asyncio
async def test_a_read_that_failed_is_not_drawn_as_a_balance_and_reading_again_works() -> None:
    door = FakeDoor(balances=[RuntimeError("transport"), _balance()])
    screen = _screen(door)
    async with ScreenHostApp(screen).run_test(size=(120, 50)) as pilot:
        await settle(pilot)
        failed_phase = screen.phase
        failed_status = _text(screen, "#wallet-status")
        failed_balance_shown = screen.query_one("#wallet-balance").display
        screen.query_one("#wallet-reload", Button).press()
        await settle(pilot)
        ready_phase = screen.phase
        ready_balance_shown = screen.query_one("#wallet-balance").display

    assert failed_phase == "failed" and failed_status == tr("workspace.modelo.iva_wallet.read_failed")
    assert not failed_balance_shown
    assert ready_phase == "ready" and ready_balance_shown
    assert door.read == [_FORM.filing_year, _FORM.filing_year]


@pytest.mark.asyncio
async def test_a_refused_read_shows_the_served_refusal_and_no_balance() -> None:
    door = FakeDoor(balances=[IvaWalletRefusedError(_served_refusal())])
    screen = _screen(door)
    async with ScreenHostApp(screen).run_test(size=(120, 50)) as pilot:
        await settle(pilot)
        phase = screen.phase
        refusal = screen.query_one("#wallet-read-refusal", RefusalSlot).refusal
        words = str(screen.query_one("#wallet-read-refusal #refusal-words", Static).render())
        balance_shown = screen.query_one("#wallet-balance").display

    assert phase == "refused" and refusal == _served_refusal()
    assert words == _REFUSAL_SENTENCE
    assert not balance_shown


@pytest.mark.asyncio
async def test_the_year_the_filer_types_is_the_year_read() -> None:
    door = FakeDoor(balances=[_balance()])
    screen = _screen(door)
    asked = _FORM.filing_year - 1
    async with ScreenHostApp(screen).run_test(size=(120, 50)) as pilot:
        await settle(pilot)
        screen.query_one("#wallet-as-of", Input).value = str(asked)
        await settle(pilot)
        screen.query_one("#wallet-reload", Button).press()
        await settle(pilot)

    assert door.read == [_FORM.filing_year, asked]


@pytest.mark.asyncio
async def test_an_opening_balance_is_sent_with_the_typed_period_and_amount_then_the_balance_is_read_again() -> None:
    door = FakeDoor(balances=[_balance(), _balance(total="450.00")], answer=_seed("450.00"))
    screen = _screen(door)
    async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
        await settle(pilot)
        blocked = screen.query_one("#wallet-submit", Button).disabled
        await _fill(pilot, screen, amount="450.00")
        await _send(pilot, screen)
        receipt = _text(screen, "#wallet-receipt")
        balance = _text(screen, "#wallet-balance")
        submit_after = screen.query_one("#wallet-submit", Button).disabled
        reading = [door.read[:]]

    assert blocked
    assert door.recorded == [
        IvaWalletEntryV1(
            kind=IvaWalletActionKind.SEED,
            filing_year=_PERIOD.filing_year,
            period_code=_PERIOD.code,
            amount="450.00",
        )
    ]
    assert door.on_loop == []
    assert receipt.splitlines()[0] == tr("workspace.modelo.iva_wallet.recorded")
    assert tr("workspace.modelo.iva_wallet.receipt.provenance.operator_seed") in receipt
    assert "450" in receipt
    assert reading == [[_FORM.filing_year, _FORM.filing_year]]
    assert "450" in balance
    assert submit_after


@pytest.mark.asyncio
async def test_a_correction_needs_a_reason_and_shows_the_previous_amount_it_came_back_with() -> None:
    door = FakeDoor(balances=[_balance()], answer=_correction("80.00", "60.00", "typo in the earlier return"))
    screen = _screen(door)
    async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
        await settle(pilot)
        await _choose(pilot, screen, IvaWalletActionKind.CORRECT)
        await _fill(pilot, screen, amount="80.00")
        without_reason = screen.query_one("#wallet-submit", Button).disabled
        label = str(screen.query_one("#wallet-submit", Button).label)
        await _fill(pilot, screen, reason="typo in the earlier return")
        await _send(pilot, screen)
        receipt = _text(screen, "#wallet-receipt")

    assert without_reason
    assert label == tr(mode_label_key(IvaWalletActionKind.CORRECT))
    assert door.recorded[0].kind is IvaWalletActionKind.CORRECT
    assert door.recorded[0].reason == "typo in the earlier return"
    assert door.recorded[0].evidence_locator == ""
    assert "60" in receipt and "80" in receipt and "typo in the earlier return" in receipt
    assert tr("workspace.modelo.iva_wallet.receipt.provenance.operator_correction") in receipt


@pytest.mark.asyncio
async def test_an_override_needs_a_reason_and_an_evidence_reference_and_shows_the_served_authority() -> None:
    door = FakeDoor(balances=[_balance()], answer=_override("95.00", "carry stated by hand", "folder/note-1"))
    screen = _screen(door)
    async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
        await settle(pilot)
        await _choose(pilot, screen, IvaWalletActionKind.OVERRIDE)
        await _fill(pilot, screen, amount="95.00", reason="carry stated by hand")
        without_evidence = screen.query_one("#wallet-submit", Button).disabled
        await _fill(pilot, screen, evidence="folder/note-1")
        await _send(pilot, screen)
        receipt = _text(screen, "#wallet-receipt")

    assert without_evidence
    assert door.recorded[0].evidence_locator == "folder/note-1"
    assert "folder/note-1" in receipt
    assert tr("workspace.modelo.iva_wallet.receipt.authority.taxpayer_override") in receipt
    assert tr("workspace.modelo.iva_wallet.receipt.divergence.override") in receipt


@pytest.mark.asyncio
async def test_a_refused_recording_shows_the_served_refusal_changes_nothing_and_can_be_sent_again() -> None:
    door = FakeDoor(balances=[_balance()], answer=IvaWalletRefusedError(_served_refusal()))
    screen = _screen(door)
    async with (app := ScreenHostApp(screen)).run_test(size=(120, 60)) as pilot:
        await settle(pilot)
        await _fill(pilot, screen, amount="10.00")
        await _send(pilot, screen)
        words = str(screen.query_one("#wallet-refusal #refusal-words", Static).render())
        receipt_shown = screen.query_one("#wallet-receipt").display
        may_retry = not screen.query_one("#wallet-submit", Button).disabled
        reads = len(door.read)
        screen.action_close()
        await settle(pilot)

    assert words == _REFUSAL_SENTENCE
    assert not receipt_shown and may_retry
    assert reads == 1
    assert app.return_value is None


@pytest.mark.asyncio
async def test_a_refusal_that_served_no_words_still_says_it_refused() -> None:
    door = FakeDoor(balances=[_balance()], answer=IvaWalletRefusedError(None))
    screen = _screen(door)
    async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
        await settle(pilot)
        await _fill(pilot, screen, amount="10.00")
        await _send(pilot, screen)
        note = _text(screen, "#wallet-note")

    assert note == tr("tui.modelo.wallet.refused")


@pytest.mark.asyncio
async def test_a_request_the_application_rejects_says_nothing_was_sent() -> None:
    door = FakeDoor(balances=[_balance()], answer=IvaWalletNotSentError())
    screen = _screen(door)
    async with (app := ScreenHostApp(screen)).run_test(size=(120, 60)) as pilot:
        await settle(pilot)
        await _fill(pilot, screen, amount="not a number")
        await _send(pilot, screen)
        note = _text(screen, "#wallet-note")
        screen.action_close()
        await settle(pilot)

    assert note == tr("tui.modelo.wallet.not_sent")
    assert app.return_value is None


@pytest.mark.asyncio
async def test_an_unknown_outcome_is_kept_unknown_never_sent_again_and_reported_on_closing() -> None:
    door = FakeDoor(balances=[_balance(), _balance()], answer=RuntimeError("connection lost"))
    screen = _screen(door)
    async with (app := ScreenHostApp(screen)).run_test(size=(120, 60)) as pilot:
        await settle(pilot)
        await _fill(pilot, screen, amount="10.00")
        await _send(pilot, screen)
        note = _text(screen, "#wallet-note")
        blocked = screen.query_one("#wallet-submit", Button).disabled
        receipt_shown = screen.query_one("#wallet-receipt").display
        screen.query_one("#wallet-submit", Button).press()
        await settle(pilot)
        screen.action_close()
        await settle(pilot)

    assert note == tr("tui.modelo.wallet.outcome_unknown")
    assert blocked and not receipt_shown
    assert len(door.recorded) == 1
    assert len(door.read) == 2
    assert app.return_value == tr("tui.modelo.wallet.outcome_unknown")


@pytest.mark.asyncio
async def test_closing_after_a_stored_recording_returns_the_sentence_for_it() -> None:
    door = FakeDoor(balances=[_balance(), _balance()], answer=_seed("10.00"))
    screen = _screen(door)
    async with (app := ScreenHostApp(screen)).run_test(size=(120, 60)) as pilot:
        await settle(pilot)
        await _fill(pilot, screen, amount="10.00")
        await _send(pilot, screen)
        screen.action_close()
        await settle(pilot)

    assert app.return_value == tr("workspace.modelo.iva_wallet.recorded")


@pytest.mark.asyncio
async def test_the_balance_read_before_a_recording_is_not_shown_while_it_is_read_again() -> None:
    release = threading.Event()

    class HeldSecondRead(FakeDoor):
        @override
        def read_balance(self, as_of_year: int) -> ModeloIvaWalletBalanceProjection:
            if self.read:
                release.wait(timeout=10)
            return super().read_balance(as_of_year)

    door = HeldSecondRead(balances=[_balance(), _balance(total="999.00")], answer=_seed("10.00"))
    screen = _screen(door)
    async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
        await settle(pilot)
        await _fill(pilot, screen, amount="10.00")
        screen.query_one("#wallet-submit", Button).press()
        await settle(pilot, workers=False)
        await asyncio.sleep(0.2)
        await settle(pilot, workers=False)
        during_phase = screen.phase
        during_shown = screen.query_one("#wallet-balance").display
        release.set()
        await settle(pilot)
        final = _text(screen, "#wallet-balance")

    assert during_phase == "reading" and not during_shown
    assert "999" in final


@pytest.mark.asyncio
async def test_the_dialog_is_reworded_in_another_language() -> None:
    door = FakeDoor(balances=[_balance()])
    with override_settings(cadrumo_output_language="es"):
        screen = _screen(door)
        async with ScreenHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            title = _text(screen, "#wallet-title")
            shown = _text(screen, "#wallet-balance")
        expected = "\n".join(balance_lines(_balance(), OutputLanguage.ES))
        expected_title = tr("workspace.modelo.iva_wallet.title")

    assert title == expected_title
    assert shown == expected


def test_the_balance_is_offered_only_where_the_form_serves_it() -> None:
    assert not offers_iva_wallet(None)
    assert not offers_iva_wallet(_FORM)
    assert offers_iva_wallet(_FORM.model_copy(update={"offers_iva_wallet": True}))
