"""The workbench offers the joint and individual comparison only where the form serves it.

Driven through the standalone host with the synthetic form and fake ports:

* a form that does not say it compares taxation offers no key, and the key does nothing;
* a form that says so, with actions that cannot ask, offers none either;
* where it is offered the footer names the key, the key opens the comparison, and the
  served results are shown from the actions' own read;
* a refusal that names boxes returns the workbench to the box the filer chooses.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

import pytest
from textual.widgets import Button, Static

from ......application.modelo.taxation_comparison import (
    TaxationComparisonRefusal,
    TaxationRecommendation,
    TaxationRecommendationReason,
    taxation_comparison_refusal,
)
from ......application.modelo.taxation_comparison_operation import ModeloTaxationComparisonProjection
from ......application.modelo.taxation_comparison_words import (
    individual_branch_caveat_words,
    recommendation_reason_words,
)
from ......application.modelo.work_form_models import ModeloWorkForm
from ......core.config import override_settings
from ......core.errors.hierarchy import CadrumoError
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....components.host import ScreenHostApp
from ....tests.settling import settle
from ...taxation_comparison import ModeloTaxationComparisonScreen
from ..casilla_list import CasillaList
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SIZE = (160, 48)
_WIDE = (400, 48)
"""Wide enough for the footer to show every key it can: the comparison key is the last of its priority list."""
_WORK_UNIT = "b" * 64


@pytest.fixture
def english() -> Iterator[None]:
    with override_settings(cadrumo_output_language="en"):
        yield


def _comparing_form() -> ModeloWorkForm:
    return synthetic_form().model_copy(update={"compares_taxation": True})


def _served() -> ModeloTaxationComparisonProjection:
    joint, individual, delta = Decimal("800.00"), Decimal("950.00"), Decimal("150.00")
    reason = TaxationRecommendationReason.CONJUNTA_LOWER_RESULT
    return ModeloTaxationComparisonProjection(
        profile_id=UUID("5aa00000-0000-4000-8000-0000000000aa"),
        work_unit_id=_WORK_UNIT,
        filing_year=newest_authored_edition("100"),
        modelo="100",
        revision="synthetic-revision",
        conjunta_cuota_resultante="1800.00",
        individual_cuota_resultante="1900.00",
        conjunta_resultado=str(joint),
        individual_resultado=str(individual),
        delta_resultado=str(delta),
        recommendation=TaxationRecommendation.CONJUNTA,
        recommendation_reason=reason,
        recommendation_reason_words=recommendation_reason_words(
            reason,
            conjunta_resultado=joint,
            individual_resultado=individual,
            delta_resultado=delta,
            language=OutputLanguage.EN,
        ),
        words_language=OutputLanguage.EN,
        individual_branch_single_earner_only=True,
        individual_branch_caveat=individual_branch_caveat_words(OutputLanguage.EN),
    )


@dataclass
class _ComparingActions(FakeActions):
    """The workbench's fake actions, able to read the comparison as the test sets it."""

    answer: ModeloTaxationComparisonProjection | CadrumoError = field(default_factory=_served)
    asked: int = 0

    async def compare_taxation(self) -> ModeloTaxationComparisonProjection:
        self.asked += 1
        if isinstance(self.answer, CadrumoError):
            raise self.answer
        return self.answer


def _footer_keys(screen: ModeloWorkbenchScreen) -> dict[str, str]:
    return {key: active.binding.description for key, active in screen.active_bindings.items() if active.binding.show}


@pytest.mark.asyncio
async def test_a_form_that_does_not_compare_taxation_offers_no_key_and_the_key_opens_nothing(english: None) -> None:
    actions = _ComparingActions()
    screen = ModeloWorkbenchScreen(FakeReader(), actions=actions)
    async with ScreenHostApp(screen).run_test(size=_WIDE) as pilot:
        await settle(pilot)
        footer = _footer_keys(screen)
        await pilot.press("t")
        await settle(pilot)
        stack = [type(item) for item in pilot.app.screen_stack]

    assert "t" not in footer
    assert ModeloTaxationComparisonScreen not in stack
    assert actions.asked == 0


@pytest.mark.asyncio
async def test_actions_that_cannot_ask_offer_no_comparison_even_where_the_form_serves_it(english: None) -> None:
    screen = ModeloWorkbenchScreen(FakeReader(form=_comparing_form()), actions=FakeActions())
    async with ScreenHostApp(screen).run_test(size=_WIDE) as pilot:
        await settle(pilot)
        footer = _footer_keys(screen)
        await pilot.press("t")
        await settle(pilot)
        stack = [type(item) for item in pilot.app.screen_stack]

    assert "t" not in footer
    assert ModeloTaxationComparisonScreen not in stack


@pytest.mark.asyncio
async def test_where_the_form_serves_the_comparison_the_footer_names_the_key_and_it_shows_the_served_results(
    english: None,
) -> None:
    served = _served()
    actions = _ComparingActions(answer=served)
    screen = ModeloWorkbenchScreen(FakeReader(form=_comparing_form()), actions=actions)
    async with ScreenHostApp(screen).run_test(size=_WIDE) as pilot:
        await settle(pilot)
        footer = _footer_keys(screen)
        await pilot.press("t")
        await settle(pilot)
        comparison = pilot.app.screen
        assert isinstance(comparison, ModeloTaxationComparisonScreen)
        comparison.query_one("#taxcmp-ask", Button).press()
        await settle(pilot)
        joint = str(comparison.query_one("#taxcmp-joint", Static).render())
        marked = comparison.query_one("#taxcmp-joint").has_class("-recommended")
        reason = str(comparison.query_one("#taxcmp-reason", Static).render())
        await pilot.press("escape")
        await settle(pilot)
        back_on_workbench = pilot.app.screen is screen

    assert footer["t"] == tr("tui.modelo.taxation.key")
    assert actions.asked == 1
    assert marked and "800.00" in joint
    assert reason == served.recommendation_reason_words
    assert back_on_workbench


@pytest.mark.asyncio
async def test_a_refusal_naming_a_box_returns_the_workbench_to_that_box(english: None) -> None:
    refusal = taxation_comparison_refusal(
        TaxationComparisonRefusal.UNRESOLVED_BOXES, casilla_ids=("07",), work_unit_id=_WORK_UNIT
    )
    screen = ModeloWorkbenchScreen(FakeReader(form=_comparing_form()), actions=_ComparingActions(answer=refusal))
    async with ScreenHostApp(screen).run_test(size=_SIZE) as pilot:
        await settle(pilot)
        await pilot.press("t")
        await settle(pilot)
        comparison = pilot.app.screen
        assert isinstance(comparison, ModeloTaxationComparisonScreen)
        comparison.query_one("#taxcmp-ask", Button).press()
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        on_workbench = pilot.app.screen is screen
        highlighted = screen.query_one(CasillaList).highlighted

    assert on_workbench
    assert highlighted is not None and highlighted.key == ("casilla", "07")
