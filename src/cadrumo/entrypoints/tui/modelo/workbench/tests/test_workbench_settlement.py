"""The export dialog asks the settlement questions the read served, in the words it served, and sends the answers.

Driven through the real dialog widgets with questions built by the application's own models. Every
sentence on a question, its help, its figures and the reason it cannot be answered is the served one;
the cases check each state of a question: answerable with its default, stating figures one of which is
advisory, applicable but unavailable, and made meaningless by the result (not asked at all). A question
not asked is sent at its neutral default.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Final

import pytest
from textual.widgets import Button, Input, Select, Static

from ......application.modelo.work_form_export_offer import (
    ModeloFormElection,
    ModeloFormElectionChoice,
    ModeloFormElectionFigure,
    ModeloFormElectionQuestion,
    ModeloFormElectionReason,
    ModeloFormElectionState,
    ModeloFormInstalment,
)
from ......core.config import override_settings
from ......core.i18n.render import tr
from ......core.modelo_export_artefact import ModeloExportArtefact
from ......core.payment_election import PaymentElection
from ......core.payment_instalment_election import PaymentInstalmentElection
from ......core.prior_domiciliation_election import PriorDomiciliationElection
from ......core.refund_election import RefundElection
from ....components.host import ScreenHostApp
from ....tests.settling import settle
from ..export import ADVISORY_LOCALE_KEY, SETTLEMENT_TITLE_LOCALE_KEY, WorkbenchExportScreen
from ..ports import WorkbenchExportOffer, WorkbenchExportRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SIZE: Final = (140, 70)
_HELP: Final = "Synthetic help: the conditions of this answer."
_FIRST: Final = "Synthetic first instalment"
_SECOND: Final = "Synthetic second instalment"
_WHY: Final = "Synthetic reason this amount is Cadrumo's own working"


@pytest.fixture(autouse=True)
def _english() -> Iterator[None]:
    with override_settings(cadrumo_output_language="en"):
        yield


def _answerable(
    election: ModeloFormElection, field: str, words: str, default: str | None, *values: str, **extra: object
) -> ModeloFormElectionQuestion:
    return ModeloFormElectionQuestion.model_validate(
        {
            "election": election,
            "request_field": field,
            "words": words,
            "default": default,
            "choices": tuple(ModeloFormElectionChoice(value=value, words=f"Synthetic {value}") for value in values),
            **extra,
        }
    )


def _refund(**extra: object) -> ModeloFormElectionQuestion:
    return _answerable(
        ModeloFormElection.REFUND,
        "refund_election",
        "Synthetic: what to do with a negative result",
        "compensar",
        "compensar",
        "devolver",
        **extra,
    )


def _payment() -> ModeloFormElectionQuestion:
    return _answerable(
        ModeloFormElection.PAYMENT, "payment_election", "Synthetic: how to pay", "ingreso", "ingreso", "domiciliacion"
    )


def _prior() -> ModeloFormElectionQuestion:
    return _answerable(
        ModeloFormElection.PRIOR_DOMICILIATION,
        "prior_domiciliation_election",
        "Synthetic: the earlier direct debit",
        "keep",
        "keep",
        "cancel_or_modify",
    )


def _instalment(*, advisory: bool) -> ModeloFormElectionQuestion:
    return _answerable(
        ModeloFormElection.INSTALMENT,
        "instalment_election",
        "Synthetic: pay at once or in two",
        "single",
        "single",
        "two_instalments_second_debited",
        help=_HELP,
        figures=(
            ModeloFormElectionFigure(
                instalment=ModeloFormInstalment.FIRST, amount="600.00", words=_FIRST, advisory=False
            ),
            ModeloFormElectionFigure(
                instalment=ModeloFormInstalment.SECOND,
                amount="400.00",
                words=_SECOND,
                advisory=advisory,
                advisory_words=_WHY if advisory else None,
            ),
        ),
    )


def _withheld(
    election: ModeloFormElection, field: str, reason: ModeloFormElectionReason, state: ModeloFormElectionState
) -> ModeloFormElectionQuestion:
    return ModeloFormElectionQuestion.model_validate(
        {
            "election": election,
            "request_field": field,
            "words": f"Synthetic question {election.value}",
            "state": state,
            "reason": reason,
            "state_words": f"Synthetic why {reason.value}",
        }
    )


async def _export(
    elections: tuple[ModeloFormElectionQuestion, ...],
    act: Callable[[WorkbenchExportScreen], None] | None = None,
) -> tuple[WorkbenchExportRequest | None, list[str], dict[str, object]]:
    """Open the dialog on ``elections``, let ``act`` answer, and return the request, the words drawn and the controls."""
    offer = WorkbenchExportOffer(
        artefacts=(ModeloExportArtefact.FICHERO_BOE,), asks_elections=True, modelo="303", elections=elections
    )
    screen = WorkbenchExportScreen(offer)
    app = ScreenHostApp(screen)
    shown: list[str] = []
    controls: dict[str, object] = {}
    async with app.run_test(size=_SIZE) as pilot:
        await settle(pilot)
        shown.extend(str(node.render()) for node in screen.query(Static))
        controls.update({select.id or "": select.value for select in screen.query(Select)})
        if act is not None:
            act(screen)
            await settle(pilot)
        screen.query_one("#export-path", Input).value = "salida.txt"
        screen.query_one("#export-submit", Button).press()
        await settle(pilot)
    request = app.return_value
    assert request is None or isinstance(request, WorkbenchExportRequest)
    return request, shown, controls


@pytest.mark.asyncio
async def test_an_answerable_question_is_drawn_in_its_served_words_at_its_served_default_and_its_answer_is_sent() -> (
    None
):
    def choose(screen: WorkbenchExportScreen) -> None:
        screen.query_one("#export-refund-election", Select).value = "devolver"

    request, shown, controls = await _export(
        (_refund(help="Synthetic help for the refund"), _payment(), _prior()), choose
    )

    assert "Synthetic: what to do with a negative result" in shown
    assert "Synthetic help for the refund" in shown
    assert tr(SETTLEMENT_TITLE_LOCALE_KEY) in shown
    assert controls["export-payment-election"] == "ingreso"
    assert controls["export-refund-election"] == "compensar", "read at the served default before the filer chose"
    assert request is not None
    assert request.refund_election is RefundElection.DEVOLVER
    assert request.payment_election is PaymentElection.INGRESO
    assert request.prior_domiciliation_election is PriorDomiciliationElection.KEEP
    assert request.instalment_election is PaymentInstalmentElection.SINGLE


@pytest.mark.asyncio
async def test_a_question_that_states_figures_draws_each_with_its_advisory_mark_and_reason_and_sends_its_answer() -> (
    None
):
    def choose(screen: WorkbenchExportScreen) -> None:
        screen.query_one("#export-instalment-election", Select).value = "two_instalments_second_debited"

    request, shown, _controls = await _export((_instalment(advisory=True),), choose)

    assert _HELP in shown
    assert _FIRST in shown
    assert f"{_SECOND} [{tr(ADVISORY_LOCALE_KEY)}]" in shown
    assert _WHY in shown
    assert request is not None
    assert request.instalment_election is PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_DEBITED


@pytest.mark.asyncio
async def test_a_figure_that_is_not_advisory_carries_no_mark_and_no_reason() -> None:
    _request, shown, _controls = await _export((_instalment(advisory=False),))

    assert _SECOND in shown
    assert all(tr(ADVISORY_LOCALE_KEY) not in line and _WHY not in line for line in shown)


@pytest.mark.asyncio
async def test_an_unavailable_question_says_why_offers_no_answer_and_is_sent_at_its_neutral_default() -> None:
    redeme = _withheld(
        ModeloFormElection.REFUND,
        "refund_election",
        ModeloFormElectionReason.REDEME_UNSTATED,
        ModeloFormElectionState.UNAVAILABLE,
    )
    window = _withheld(
        ModeloFormElection.INSTALMENT,
        "instalment_election",
        ModeloFormElectionReason.PAST_FILING_WINDOW,
        ModeloFormElectionState.UNAVAILABLE,
    )
    request, shown, controls = await _export((redeme, _payment(), window))

    assert "Synthetic question refund" in shown and "Synthetic why redeme_unstated" in shown
    assert "Synthetic why past_filing_window" in shown
    assert "export-refund-election" not in controls and "export-instalment-election" not in controls
    assert request is not None
    assert request.refund_election is RefundElection.COMPENSAR
    assert request.instalment_election is PaymentInstalmentElection.SINGLE


@pytest.mark.asyncio
async def test_a_question_the_result_makes_meaningless_is_not_asked_and_not_explained() -> None:
    carry_only = _withheld(
        ModeloFormElection.REFUND,
        "refund_election",
        ModeloFormElectionReason.CARRY_FORWARD_ONLY,
        ModeloFormElectionState.NOT_APPLICABLE,
    )
    request, shown, controls = await _export((carry_only, _prior()))

    assert all("Synthetic question refund" not in line and "carry_forward_only" not in line for line in shown)
    assert "export-refund-election" not in controls
    assert "export-prior-domiciliation-election" in controls
    assert request is not None and request.refund_election is RefundElection.COMPENSAR


@pytest.mark.asyncio
async def test_a_declaration_that_asks_nothing_draws_no_settlement_and_sends_every_default() -> None:
    offer = WorkbenchExportOffer(artefacts=(ModeloExportArtefact.FICHERO_BOE,), asks_elections=False, modelo="130")
    screen = WorkbenchExportScreen(offer)
    app = ScreenHostApp(screen)
    async with app.run_test(size=_SIZE) as pilot:
        await settle(pilot)
        titled = bool(screen.query("#export-settlement-title"))
        screen.query_one("#export-path", Input).value = "salida.txt"
        screen.query_one("#export-submit", Button).press()
        await settle(pilot)
    request = app.return_value

    assert not titled
    assert isinstance(request, WorkbenchExportRequest)
    assert request.payment_election is PaymentElection.INGRESO
    assert request.instalment_election is PaymentInstalmentElection.SINGLE
