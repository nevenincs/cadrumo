"""A refusal that serves the IVA balance as its way out is offered as a door that opens the balance where it names.

Driven through the standalone host with the real workbench and dialog widgets. The
refusals are the ones the application raises and serves for the wallet gate, built
by the application's own refusal functions and detail builder: the opening-balance
refusal (``not_seeded``), the two that ask an express override
(``filed_history_requires_override``) and the one that leaves the decision to the
filer (``wallet_local_recurrence_divergence``). The door's words, the recording,
the period and the amount are what the refusal served; the dialog sends nothing
until the filer does. Data is synthetic.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final
from uuid import UUID

import pytest
from textual.widgets import Button, Input, OptionList, Static

from ......application.modelo.iva_wallet_balance_operation import ModeloIvaWalletBalanceProjection
from ......application.modelo.iva_wallet_binding import apply_iva_compensation_decision_binding
from ......application.modelo.iva_wallet_override_operation import ModeloIvaWalletOverrideProjection
from ......application.modelo.iva_wallet_refusal import (
    ModeloIvaWalletReconciliationBlocked,
    iva_wallet_door,
    raise_iva_wallet_precondition,
)
from ......application.modelo.work_form_models import ModeloWorkForm
from ......application.operations.error_detail import build_operation_error_detail
from ......application.operations.public_period import PublicPeriod
from ......core.casilla_id import CasillaId, validated_casilla_id
from ......core.config import override_settings
from ......core.i18n.render import tr
from ......core.period import Period
from ......domain.calculations.registry.authority import bundled_indexed_authority
from ......domain.calculations.registry.form_codes import form_for_role
from ......domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ....components.host import ScreenHostApp
from ....refusal.served import ServedRefusalV1, served_refusal
from ....tests.settling import settle
from ...wallet import IvaWalletActionKind, IvaWalletEntryV1, IvaWalletReceiptV1
from ...wallet_screen import ModeloIvaWalletScreen, mode_label_key
from ...wallet_workbench import WALLET_DOOR_ID
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WIDE: Final = (400, 60)
_PROFILE: Final = UUID("5aa00000-0000-4000-8000-0000000000aa")
_WORK_UNIT: Final = "b" * 64
_OTHER_WORK_UNIT: Final = "c" * 64
_LOCAL_AMOUNT: Final = Decimal("123.45")
_MODES: Final = list(IvaWalletActionKind)
_CASILLA: Final[CasillaId] = validated_casilla_id("iva.compensacion-pendiente-periodos-anteriores")
_BLOCKED_MESSAGES: Final = "application.iva_wallet.decision_reason"


@pytest.fixture(autouse=True)
def _english() -> Iterator[None]:
    with override_settings(cadrumo_output_language="en"):
        yield


def _supported_year() -> int:
    support = published_supported_filing_years()
    assert support is not None
    return tuple(support.years)[-1]


def _detail_refusal(error: BaseException) -> ServedRefusalV1:
    detail = build_operation_error_detail(error)
    refusal = served_refusal(detail)
    assert refusal is not None
    return refusal


def _not_seeded() -> ServedRefusalV1:
    """The refusal of a Modelo 303 carry no wallet authority backs, as the wallet gate raises and serves it."""
    year = _supported_year()
    period = Period.from_year_and_code(year, "2T")
    with bundled_indexed_authority().operation(), pytest.raises(ModeloIvaWalletReconciliationBlocked) as raised:
        apply_iva_compensation_decision_binding(
            form_for_role("iva.periodic"),
            year,
            period,
            bucket_id="34343434-3434-4343-8343-343434343434",
            revision=published_snapshot(form_for_role("iva.periodic"), filing_year=year, period="2T").revision,
            taxpayer_nif="taxpayeralpha",
            casilla_inputs={_CASILLA: Decimal(800)},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=None,
        )
    return _detail_refusal(raised.value)


def _blocked(reason: str, work_unit_id: str = _WORK_UNIT) -> ServedRefusalV1:
    """A blocked-decision refusal of the calculation, with the Saldo de IVA of ``work_unit_id`` as its door."""
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as raised, iva_wallet_door(work_unit_id):
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code=reason,
            translated_message=f"{_BLOCKED_MESSAGES}.{reason}",
            evidence_values={"reason": reason},
            carry_period=Period.from_year_and_code(_supported_year(), "2T"),
            local_amount=_LOCAL_AMOUNT,
        )
    return _detail_refusal(raised.value)


def _form(*, modelo: str = "303", work_unit_id: str = _WORK_UNIT, offers: bool = True) -> ModeloWorkForm:
    return synthetic_form().model_copy(
        update={"offers_iva_wallet": offers, "modelo": modelo, "work_unit_id": work_unit_id}
    )


@dataclass
class FakeDoor:
    read: list[int] = field(default_factory=list)
    recorded: list[IvaWalletEntryV1] = field(default_factory=list)
    answer: IvaWalletReceiptV1 | Exception | None = None

    def read_balance(self, as_of_year: int) -> ModeloIvaWalletBalanceProjection:
        self.read.append(as_of_year)
        return ModeloIvaWalletBalanceProjection(
            profile_id=_PROFILE,
            as_of_year=as_of_year,
            total_balance="0",
            active_balance="0",
            expired_balance="0",
            lot_count=0,
            next_expiry_year=None,
            unallocated_applied_amount="0",
        )

    def record(self, entry: IvaWalletEntryV1) -> IvaWalletReceiptV1:
        self.recorded.append(entry)
        if isinstance(self.answer, Exception):
            raise self.answer
        assert self.answer is not None
        return self.answer


def _workbench(
    door: FakeDoor | None, form: ModeloWorkForm
) -> tuple[ModeloWorkbenchScreen, ScreenHostApp[None], FakeReader]:
    reader = FakeReader(form=form)
    screen = ModeloWorkbenchScreen(reader, actions=FakeActions(), wallet=door)
    return screen, ScreenHostApp(screen), reader


def _doors(screen: ModeloWorkbenchScreen) -> list[Button]:
    return list(screen.query(f"#{WALLET_DOOR_ID}").results(Button))


def _highlighted(dialog: ModeloIvaWalletScreen) -> IvaWalletActionKind:
    index = dialog.query_one("#wallet-modes", OptionList).highlighted
    assert index is not None
    return _MODES[index]


def _typed(dialog: ModeloIvaWalletScreen, name: str) -> str:
    return dialog.query_one(f"#wallet-{name}", Input).value


@pytest.mark.asyncio
async def test_the_opening_balance_refusal_offers_its_served_door_and_the_dialog_opens_at_the_served_period() -> None:
    refusal = _not_seeded()
    step = refusal.next_step
    assert step is not None and step.kind == "open_iva_wallet_opening_balance"
    door = FakeDoor()
    screen, app, _reader = _workbench(door, _form(modelo=step.modelo))
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        assert _doors(screen) == []
        screen._show_operation_refusal(refusal)
        await settle(pilot)
        doors = _doors(screen)
        label = str(doors[0].label) if doors else ""
        await pilot.click(f"#{WALLET_DOOR_ID}")
        await settle(pilot)
        dialog = app.screen
        assert isinstance(dialog, ModeloIvaWalletScreen)
        kind, year, code, amount = (
            _highlighted(dialog),
            _typed(dialog, "period-year"),
            _typed(dialog, "period-code"),
            _typed(dialog, "amount"),
        )
        submit = str(dialog.query_one("#wallet-submit", Button).label)
        sent = list(door.recorded)

    assert len(doors) == 1 and label == step.words
    assert kind is IvaWalletActionKind.SEED
    assert (year, code) == (str(step.filing_year), step.period_code)
    assert amount == "" and submit == tr(mode_label_key(IvaWalletActionKind.SEED))
    assert sent == [], "opening the balance sends nothing"


@pytest.mark.asyncio
async def test_a_refusal_asking_an_override_offers_the_balance_opened_on_the_override_with_the_served_amount() -> None:
    refusal = _blocked("filed_history_requires_override")
    step = refusal.next_step
    assert step is not None and step.kind == "open_iva_wallet"
    served_year = _supported_year()
    answer = ModeloIvaWalletOverrideProjection(
        profile_id=_PROFILE,
        period=PublicPeriod(filing_year=served_year, code="2T"),
        taxpayer_nif="00000000T",
        amount=str(_LOCAL_AMOUNT),
        reason="records of the earlier returns",
        evidence_locator="folder/note-2",
        selected_authority="taxpayer_override",
        divergence="override",
    )
    door = FakeDoor(answer=answer)
    screen, app, _reader = _workbench(door, _form())
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        screen._show_operation_refusal(refusal)
        await settle(pilot)
        label = str(_doors(screen)[0].label)
        await pilot.click(f"#{WALLET_DOOR_ID}")
        await settle(pilot)
        dialog = app.screen
        assert isinstance(dialog, ModeloIvaWalletScreen)
        opened = (_highlighted(dialog), _typed(dialog, "period-year"), _typed(dialog, "period-code"))
        amount = _typed(dialog, "amount")
        blocked_without_reason = dialog.query_one("#wallet-submit", Button).disabled
        dialog.query_one("#wallet-reason", Input).value = "records of the earlier returns"
        dialog.query_one("#wallet-evidence", Input).value = "folder/note-2"
        await settle(pilot)
        dialog.query_one("#wallet-submit", Button).press()
        await settle(pilot)

    assert label == step.words
    assert opened == (IvaWalletActionKind.OVERRIDE, str(served_year), "2T")
    assert amount == str(_LOCAL_AMOUNT)
    assert blocked_without_reason
    assert door.recorded == [
        IvaWalletEntryV1(
            kind=IvaWalletActionKind.OVERRIDE,
            filing_year=served_year,
            period_code="2T",
            amount=str(_LOCAL_AMOUNT),
            reason="records of the earlier returns",
            evidence_locator="folder/note-2",
        )
    ]


@pytest.mark.asyncio
async def test_a_refusal_that_leaves_the_decision_to_the_filer_opens_the_balance_on_the_declarations_own_period() -> (
    None
):
    refusal = _blocked("wallet_local_recurrence_divergence")
    assert refusal.verdict is not None and refusal.verdict.action_id is None
    form = _form()
    door = FakeDoor()
    screen, app, _reader = _workbench(door, form)
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        screen._show_operation_refusal(refusal)
        await settle(pilot)
        label = str(_doors(screen)[0].label)
        await pilot.click(f"#{WALLET_DOOR_ID}")
        await settle(pilot)
        dialog = app.screen
        assert isinstance(dialog, ModeloIvaWalletScreen)
        opened = (_highlighted(dialog), _typed(dialog, "period-year"), _typed(dialog, "period-code"))
        amount = _typed(dialog, "amount")

    assert label == tr("application.modelo.iva_wallet.next_step.open")
    assert opened == (IvaWalletActionKind.SEED, str(form.filing_year), form.period.registry_token)
    assert amount == ""


@pytest.mark.asyncio
async def test_the_door_is_taken_away_when_a_later_operation_settles_and_when_a_refusal_serves_none() -> None:
    door = FakeDoor()
    screen, app, _reader = _workbench(door, _form())
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        screen._show_operation_refusal(_blocked("wallet_local_recurrence_divergence"))
        await settle(pilot)
        shown = len(_doors(screen))
        screen._show_operation_refusal(None)
        await settle(pilot)
        after_success = len(_doors(screen))
        screen._show_operation_refusal(_blocked("wallet_local_recurrence_divergence"))
        await settle(pilot)
        screen._show_operation_refusal(ServedRefusalV1())
        await settle(pilot)
        after_other_refusal = len(_doors(screen))

    assert (shown, after_success, after_other_refusal) == (1, 0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["other_declaration", "other_modelo", "no_balance", "no_door"])
async def test_a_door_that_does_not_belong_to_this_declaration_is_not_offered(case: str) -> None:
    refusal = _not_seeded() if case == "other_modelo" else _blocked("wallet_local_recurrence_divergence")
    step = refusal.next_step
    assert step is not None
    forms = {
        "other_declaration": _form(work_unit_id=_OTHER_WORK_UNIT),
        "other_modelo": _form(modelo="130"),
        "no_balance": _form(offers=False),
        "no_door": _form(modelo=getattr(step, "modelo", "303")),
    }
    screen, app, _reader = _workbench(None if case == "no_door" else FakeDoor(), forms[case])
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        screen._show_operation_refusal(refusal)
        await settle(pilot)
        offered = len(_doors(screen))
        words = str(screen.query_one("#wb-operation-refusal #refusal-words", Static).render())

    assert offered == 0
    assert words == refusal.sentence, "the refusal itself is still shown through the slot"


@pytest.mark.asyncio
async def test_a_recording_sent_from_the_door_whose_outcome_is_unknown_is_kept_unknown_and_not_sent_again() -> None:
    refusal = _blocked("filed_history_requires_override")
    door = FakeDoor(answer=RuntimeError("connection lost"))
    screen, app, reader = _workbench(door, _form())
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        screen._show_operation_refusal(refusal)
        await settle(pilot)
        await pilot.click(f"#{WALLET_DOOR_ID}")
        await settle(pilot)
        dialog = app.screen
        assert isinstance(dialog, ModeloIvaWalletScreen)
        dialog.query_one("#wallet-reason", Input).value = "records"
        dialog.query_one("#wallet-evidence", Input).value = "folder/note-3"
        await settle(pilot)
        dialog.query_one("#wallet-submit", Button).press()
        await settle(pilot)
        note = str(dialog.query_one("#wallet-note", Static).render())
        blocked = dialog.query_one("#wallet-submit", Button).disabled
        dialog.query_one("#wallet-submit", Button).press()
        await settle(pilot)
        dialog.action_close()
        await settle(pilot)
        notice = str(screen.query_one("#wb-notice", Static).render())

    assert note == tr("tui.modelo.wallet.outcome_unknown") and blocked
    assert len(door.recorded) == 1
    assert reader.loads == 2, "the declaration is read again"
    assert notice == tr("tui.modelo.wallet.outcome_unknown")


@pytest.mark.asyncio
async def test_a_year_that_is_no_number_is_named_as_typed_and_nothing_is_read() -> None:
    door = FakeDoor()
    _screen, app, _reader = _workbench(door, _form())
    async with app.run_test(size=_WIDE) as pilot:
        await settle(pilot)
        await pilot.press("w")
        await settle(pilot)
        dialog = app.screen
        assert isinstance(dialog, ModeloIvaWalletScreen)
        dialog.query_one("#wallet-as-of", Input).value = "20x6"
        await settle(pilot)
        dialog.query_one("#wallet-reload", Button).press()
        await settle(pilot)
        status = str(dialog.query_one("#wallet-status", Static).render())
        reads = list(door.read)

    assert status == tr("desktop.ledger.edit.refusal.year_not_a_number", raw="20x6")
    assert reads == [_form().filing_year]
