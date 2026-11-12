"""The refusal panel shows served words and served ways out only, in served order, and never submits."""

from __future__ import annotations

from typing import override

import pytest
from pydantic import ValidationError
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from .....core.i18n.render import tr
from .....core.operator_action_enums import NoRecoveryOutcome
from ...tests.settling import settle
from ..intent import RefusalIntentV1, RefusalRouterV1
from ..panel import RefusalPanel
from ..routing import route_refusal_way
from ..served import RefusalWayV1, ServedRefusalV1
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
async def test_primary_only_is_one_enabled_primary_control_that_posts_its_intent() -> None:
    refusal = ServedRefusalV1(
        refusal_words=words(_REFUSED),
        verdict=primary_verdict(CREATE_WORK),
        primary_action_words=words("Start the declaration"),
    )
    app = _Host(refusal)
    async with app.run_test() as pilot:
        await settle(pilot)
        (button,) = _buttons(app)
        assert str(button.label) == "Start the declaration"
        assert button.variant == "primary"
        assert not button.disabled
        await pilot.click("#refusal-action-0")
        await settle(pilot)
        assert [intent.target_command_key for intent in app.chosen] == ["modelo.work.create"]
        assert app.chosen[0].kind == "follow"


@pytest.mark.asyncio
async def test_primary_then_two_alternatives_keep_the_served_order() -> None:
    refusal = ServedRefusalV1(
        refusal_words=words(_REFUSED),
        verdict=primary_verdict(CREATE_WORK, attest_alternative(), review_alternative()),
        primary_action_words=words("Start the declaration"),
        alternative_action_words=(words("State last year's figure"), words("Review the ledger")),
    )
    app = _Host(refusal)
    async with app.run_test() as pilot:
        await settle(pilot)
        buttons = _buttons(app)
        assert [str(button.label) for button in buttons] == [
            "Start the declaration",
            "State last year's figure …",
            "Review the ledger",
        ]
        assert [button.variant for button in buttons] == ["primary", "default", "default"]


@pytest.mark.asyncio
async def test_a_conditional_action_is_marked_and_opens_the_form_for_its_missing_arguments() -> None:
    refusal = ServedRefusalV1(
        verdict=primary_verdict(CREATE_WORK, missing_year=True),
        primary_action_words=words("Start the declaration"),
    )
    app = _Host(refusal)
    async with app.run_test() as pilot:
        await settle(pilot)
        (button,) = _buttons(app)
        assert str(button.label) == "Start the declaration …"
        assert _text(app, "#refusal-needs-details") == tr("tui.refusal.action_needs_details")
        await pilot.click("#refusal-action-0")
        await settle(pilot)
        (intent,) = app.chosen
        assert intent.kind == "form"
        assert intent.missing_argument_names == ("year",)


@pytest.mark.asyncio
async def test_an_unroutable_action_is_shown_disabled_with_the_reason_and_posts_nothing() -> None:
    refusal = ServedRefusalV1(
        verdict=primary_verdict(ATTEST_PRIOR_VALUE), primary_action_words=words("State last year's figure")
    )
    app = _Host(refusal)
    async with app.run_test() as pilot:
        await settle(pilot)
        (button,) = _buttons(app)
        assert str(button.label) == "State last year's figure"
        assert button.disabled
        assert _text(app, "#refusal-unroutable") == tr("tui.refusal.action_unroutable")
        await pilot.click("#refusal-action-0")
        await settle(pilot)
        assert app.chosen == []


@pytest.mark.parametrize(
    "outcome", [NoRecoveryOutcome.TERMINAL, NoRecoveryOutcome.OPERATOR_DECISION, NoRecoveryOutcome.SAFETY]
)
@pytest.mark.asyncio
async def test_no_way_out_is_its_served_words_and_no_control(outcome: NoRecoveryOutcome) -> None:
    refusal = ServedRefusalV1(
        refusal_words=words(_REFUSED),
        verdict=closed_verdict(outcome),
        no_recovery_words=words("Only you can decide this."),
    )
    app = _Host(refusal)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert _text(app, "#refusal-no-recovery") == "Only you can decide this."
        assert _buttons(app) == []


@pytest.mark.asyncio
async def test_before_the_backend_serves_action_words_no_control_is_drawn() -> None:
    routed: list[RefusalWayV1] = []

    def watching(way: RefusalWayV1) -> RefusalIntentV1 | None:
        routed.append(way)
        return _route(way)

    refusal = ServedRefusalV1(
        refusal_words=words(_REFUSED),
        verdict=primary_verdict(CREATE_WORK, attest_alternative(), review_alternative()),
    )
    app = _Host(refusal, watching)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert _text(app, "#refusal-words") == _REFUSED
        assert _buttons(app) == []
        assert not app.query("#refusal-unroutable")
        assert not app.query("#refusal-needs-details")
    assert routed == []


def test_words_that_do_not_belong_to_the_verdict_are_refused() -> None:
    with pytest.raises(ValidationError):
        ServedRefusalV1(primary_action_words=words("Start the declaration"))
    with pytest.raises(ValidationError):
        ServedRefusalV1(
            verdict=primary_verdict(CREATE_WORK, attest_alternative(), review_alternative()),
            alternative_action_words=(words("Review the ledger"),),
        )
    with pytest.raises(ValidationError):
        ServedRefusalV1(verdict=primary_verdict(CREATE_WORK), no_recovery_words=words("Nothing to do."))
