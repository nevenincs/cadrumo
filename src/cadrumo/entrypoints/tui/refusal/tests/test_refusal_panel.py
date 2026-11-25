"""The refusal panel shows the words the verdict served, in served order, routes by served operations, and never submits."""

from __future__ import annotations

from collections.abc import Iterator
from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from .....core.config import override_settings
from .....core.i18n.render import tr
from .....core.operator_action_enums import NoRecoveryOutcome
from ...operations.destination import OPERATIONS_DESTINATION
from ...tests.settling import settle
from ..intent import RefusalIntentV1, RefusalRouterV1
from ..panel import RefusalPanel
from ..routing import route_refusal_way
from ..served import RefusalWayV1, ServedRefusalV1, refusal_ways
from .refusal_fixtures import (
    ATTEST_PRIOR_VALUE,
    CREATE_WORK,
    attest_alternative,
    closed_verdict,
    destinations,
    operations,
    primary_verdict,
    review_alternative,
    words,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REFUSED = "The work cannot be checked until last year's return is in."
_START = "Start this declaration"
_ATTEST = "State the earlier return's figure"
_REVIEW = "Review the ledger"


@pytest.fixture(autouse=True)
def _english() -> Iterator[None]:
    """Serve every verdict's words in English, whatever the machine's language."""
    with override_settings(cadrumo_output_language="en"):
        yield


def _route(way: RefusalWayV1) -> RefusalIntentV1 | None:
    return route_refusal_way(way, destinations=destinations(), operations=operations())


class _Host(App[None]):
    def __init__(self, refusal: ServedRefusalV1, route: RefusalRouterV1 = _route) -> None:
        super().__init__()
        self._refusal = refusal
        self._route = route
        self.chosen: list[RefusalIntentV1] = []

    @override
    def compose(self) -> ComposeResult:
        yield RefusalPanel(self._refusal, route=self._route, id="panel")

    def on_refusal_panel_action_chosen(self, message: RefusalPanel.ActionChosen) -> None:
        self.chosen.append(message.intent)


def _text(app: App[None], selector: str) -> str:
    return str(app.query_one(selector, Static).render())


def _buttons(app: App[None]) -> list[Button]:
    return list(app.query(Button))


@pytest.mark.asyncio
async def test_words_only_show_the_refusal_and_no_control() -> None:
    app = _Host(ServedRefusalV1(refusal_words=words(_REFUSED)))
    async with app.run_test() as pilot:
        await settle(pilot)
        assert _text(app, "#refusal-words") == _REFUSED
        assert _buttons(app) == []
        assert not app.query("#refusal-unroutable")


@pytest.mark.asyncio
async def test_primary_door_is_the_served_words_and_posts_the_intent_of_the_served_operation() -> None:
    refusal = ServedRefusalV1(refusal_words=words(_REFUSED), verdict=primary_verdict(CREATE_WORK))
    app = _Host(refusal)
    async with app.run_test() as pilot:
        await settle(pilot)
        (button,) = _buttons(app)
        assert str(button.label) == _START
        assert button.variant == "primary"
        assert not button.disabled
        await pilot.click("#refusal-action-0")
        await settle(pilot)
        (intent,) = app.chosen
        assert intent.target_command_key == "modelo.work.create"
        assert intent.kind == "follow"
        assert intent.target.destination == OPERATIONS_DESTINATION


@pytest.mark.asyncio
async def test_alternatives_follow_the_primary_in_served_order_with_their_served_words() -> None:
    refusal = ServedRefusalV1(
        refusal_words=words(_REFUSED),
        verdict=primary_verdict(CREATE_WORK, attest_alternative(), review_alternative()),
    )
    app = _Host(refusal)
    async with app.run_test() as pilot:
        await settle(pilot)
        buttons = _buttons(app)
        assert [str(button.label) for button in buttons] == [_START, f"{_ATTEST} …", _REVIEW]
        assert [button.variant for button in buttons] == ["primary", "default", "default"]
        assert [way.words.words for way in refusal_ways(refusal) if way.words is not None] == [
            _START,
            _ATTEST,
            _REVIEW,
        ]


@pytest.mark.asyncio
async def test_a_conditional_action_is_marked_and_opens_the_form_for_its_missing_arguments() -> None:
    refusal = ServedRefusalV1(verdict=primary_verdict(CREATE_WORK, missing_year=True))
    app = _Host(refusal)
    async with app.run_test() as pilot:
        await settle(pilot)
        (button,) = _buttons(app)
        assert str(button.label) == f"{_START} …"
        assert _text(app, "#refusal-needs-details") == tr("tui.refusal.action_needs_details")
        await pilot.click("#refusal-action-0")
        await settle(pilot)
        (intent,) = app.chosen
        assert intent.kind == "form"
        assert intent.missing_argument_names == ("year",)


@pytest.mark.asyncio
async def test_an_action_whose_served_operations_are_not_registered_is_shown_disabled_with_the_reason_and_posts_nothing() -> (
    None
):
    verdict = primary_verdict(ATTEST_PRIOR_VALUE).model_copy(
        update={"target_operation_ids": ("unregistered.operation",)}
    )
    refusal = ServedRefusalV1(verdict=verdict)
    app = _Host(refusal)
    async with app.run_test() as pilot:
        await settle(pilot)
        (button,) = _buttons(app)
        assert str(button.label) == _ATTEST
        assert button.disabled
        assert _text(app, "#refusal-unroutable") == tr("tui.refusal.action_unroutable")
        await pilot.click("#refusal-action-0")
        await settle(pilot)
        assert app.chosen == []


@pytest.mark.asyncio
async def test_a_served_operation_the_operations_destination_does_not_admit_is_disabled() -> None:
    closed = destinations(unavailable=frozenset({OPERATIONS_DESTINATION}))

    def closed_route(way: RefusalWayV1) -> RefusalIntentV1 | None:
        return route_refusal_way(way, destinations=closed, operations=operations())

    refusal = ServedRefusalV1(verdict=primary_verdict(CREATE_WORK))
    assert refusal.verdict is not None
    assert refusal.verdict.target_operation_ids == ("modelo.work.create",)
    app = _Host(refusal, closed_route)
    async with app.run_test() as pilot:
        await settle(pilot)
        (button,) = _buttons(app)
        assert button.disabled
        assert _text(app, "#refusal-unroutable") == tr("tui.refusal.action_unroutable")


@pytest.mark.parametrize(
    ("outcome", "sentence"),
    [
        (NoRecoveryOutcome.TERMINAL, "This refusal is final: no action can clear it."),
        (NoRecoveryOutcome.OPERATOR_DECISION, "This needs your own decision; no action can take it for you."),
        (NoRecoveryOutcome.SAFETY, "This was stopped to protect your data, so no action is offered."),
    ],
)
@pytest.mark.asyncio
async def test_no_way_out_is_its_served_sentence_and_no_control(outcome: NoRecoveryOutcome, sentence: str) -> None:
    refusal = ServedRefusalV1(refusal_words=words(_REFUSED), verdict=closed_verdict(outcome))
    app = _Host(refusal)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert _text(app, "#refusal-no-recovery") == sentence
        assert _buttons(app) == []


@pytest.mark.asyncio
async def test_a_way_the_backend_served_no_words_for_gets_no_control_and_is_never_routed() -> None:
    routed: list[RefusalWayV1] = []

    def watching(way: RefusalWayV1) -> RefusalIntentV1 | None:
        routed.append(way)
        return _route(way)

    served = primary_verdict(CREATE_WORK, attest_alternative(), review_alternative())
    unworded = served.model_copy(
        update={
            "action_words": None,
            "action_words_language": None,
            "alternative_actions": tuple(
                alternative.model_copy(update={"action_words": None, "action_words_language": None})
                for alternative in served.alternative_actions
            ),
        }
    )
    app = _Host(ServedRefusalV1(refusal_words=words(_REFUSED), verdict=unworded), watching)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert _text(app, "#refusal-words") == _REFUSED
        assert _buttons(app) == []
        assert not app.query("#refusal-unroutable")
        assert not app.query("#refusal-needs-details")
    assert routed == []
