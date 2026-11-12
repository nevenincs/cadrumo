"""The comparison of joint and individual filing shows exactly what the application served.

Driven through the standalone screen host with the real widgets. Each
projection is the application's own model carrying the application's own
reason words; each refusal is the application's own error with its verdict, so
the screen meets the shapes it meets in production. Figures are synthetic. The
screen compares no amount: which mode is recommended, or that neither is, is the
served recommendation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from decimal import Decimal
from uuid import UUID

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, OptionList, Static

from .....application.modelo.taxation_comparison import (
    TaxationComparisonRefusal,
    TaxationRecommendation,
    TaxationRecommendationReason,
    taxation_comparison_refusal,
)
from .....application.modelo.taxation_comparison_operation import ModeloTaxationComparisonProjection
from .....application.modelo.taxation_comparison_words import (
    individual_branch_caveat_words,
    recommendation_reason_words,
)
from .....core.config import override_settings
from .....core.errors.hierarchy import CadrumoError
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ...components.host import ScreenHostApp
from ...refusal.panel import RefusalSlot
from ...tests.settling import settle
from ..taxation_comparison import ComparisonPhase, ModeloTaxationComparisonScreen
from ..workbench.tests.workbench_fixture import synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.fixture
def english() -> Iterator[None]:
    with override_settings(cadrumo_output_language="en"):
        yield


@pytest.fixture
def spanish() -> Iterator[None]:
    with override_settings(cadrumo_output_language="es"):
        yield


_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_WORK_UNIT = "a" * 64
_YEAR = newest_authored_edition("100")
_REASON: dict[TaxationRecommendation, TaxationRecommendationReason] = {
    TaxationRecommendation.CONJUNTA: TaxationRecommendationReason.CONJUNTA_LOWER_RESULT,
    TaxationRecommendation.INDIVIDUAL: TaxationRecommendationReason.INDIVIDUAL_LOWER_RESULT,
    TaxationRecommendation.INDIFFERENT: TaxationRecommendationReason.BELOW_MATERIALITY,
}


def _projection(
    *,
    joint: str,
    individual: str,
    recommendation: TaxationRecommendation,
    delta: str,
    joint_tax: str = "2000.00",
    individual_tax: str = "2100.00",
    language: OutputLanguage = OutputLanguage.EN,
) -> ModeloTaxationComparisonProjection:
    reason = _REASON[recommendation]
    return ModeloTaxationComparisonProjection(
        profile_id=_PROFILE,
        work_unit_id=_WORK_UNIT,
        filing_year=_YEAR,
        modelo="100",
        revision="synthetic-revision",
        conjunta_cuota_resultante=joint_tax,
        individual_cuota_resultante=individual_tax,
        conjunta_resultado=joint,
        individual_resultado=individual,
        delta_resultado=delta,
        recommendation=recommendation,
        recommendation_reason=reason,
        recommendation_reason_words=recommendation_reason_words(
            reason,
            conjunta_resultado=Decimal(joint),
            individual_resultado=Decimal(individual),
            delta_resultado=Decimal(delta),
            language=language,
        ),
        words_language=language,
        individual_branch_single_earner_only=True,
        individual_branch_caveat=individual_branch_caveat_words(language),
    )


def _serving(
    projection: ModeloTaxationComparisonProjection,
) -> Callable[[], Awaitable[ModeloTaxationComparisonProjection]]:
    async def door() -> ModeloTaxationComparisonProjection:
        return projection

    return door


def _refusing(error: CadrumoError) -> Callable[[], Awaitable[ModeloTaxationComparisonProjection]]:
    async def door() -> ModeloTaxationComparisonProjection:
        raise error

    return door


def _text(screen: ModeloTaxationComparisonScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _shown(screen: ModeloTaxationComparisonScreen, selector: str) -> bool:
    return screen.query_one(selector).display


async def _ask[ResultT](pilot: Pilot[ResultT], screen: ModeloTaxationComparisonScreen) -> None:
    screen.query_one("#taxcmp-ask", Button).press()
    await settle(pilot)


@pytest.mark.asyncio
async def test_before_it_is_asked_only_the_lead_and_the_ask_control_show(english: None) -> None:
    screen = ModeloTaxationComparisonScreen(
        _serving(_projection(joint="1", individual="2", delta="1", recommendation=TaxationRecommendation.CONJUNTA)),
        form=synthetic_form(),
    )
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        phase = screen.phase
        lead = _text(screen, "#taxcmp-lead")
        ask = str(screen.query_one("#taxcmp-ask", Button).label)
        modes_shown = _shown(screen, "#taxcmp-modes")
        reading_shown = _shown(screen, "#taxcmp-reading")
        failed_shown = _shown(screen, "#taxcmp-failed")

    assert phase is ComparisonPhase.IDLE
    assert lead == tr("desktop.modelo.compare.taxation.lead")
    assert ask == tr("desktop.modelo.compare.taxation.ask")
    assert not (modes_shown or reading_shown or failed_shown)


@pytest.mark.asyncio
async def test_the_mode_the_application_recommends_is_the_one_marked_with_both_served_results(english: None) -> None:
    served = _projection(
        joint="1250.00",
        individual="1400.00",
        delta="150.00",
        joint_tax="3000.00",
        individual_tax="3100.00",
        recommendation=TaxationRecommendation.CONJUNTA,
    )
    screen = ModeloTaxationComparisonScreen(_serving(served), form=synthetic_form())
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await _ask(pilot, screen)
        joint = _text(screen, "#taxcmp-joint")
        individual = _text(screen, "#taxcmp-individual")
        joint_marked = screen.query_one("#taxcmp-joint").has_class("-recommended")
        individual_marked = screen.query_one("#taxcmp-individual").has_class("-recommended")
        reason = _text(screen, "#taxcmp-reason")
        caveat = _text(screen, "#taxcmp-caveat")
        ask = str(screen.query_one("#taxcmp-ask", Button).label)
        language_note_shown = _shown(screen, "#taxcmp-language")

    recommended = tr("desktop.modelo.compare.taxation.recommended")
    assert joint_marked and not individual_marked
    assert joint.splitlines()[0] == f"{tr('desktop.modelo.compare.taxation.joint')} · {recommended}"
    assert individual.splitlines()[0] == tr("desktop.modelo.compare.taxation.individual")
    assert "1,250.00" in joint and "3,000.00" in joint
    assert "1,400.00" in individual and "3,100.00" in individual
    assert recommended not in individual
    assert reason == served.recommendation_reason_words
    assert caveat == served.individual_branch_caveat
    assert ask == tr("desktop.modelo.compare.again")
    assert not language_note_shown


@pytest.mark.asyncio
async def test_a_lower_individual_result_marks_the_individual_mode_instead(english: None) -> None:
    served = _projection(
        joint="1900.00", individual="1500.00", delta="-400.00", recommendation=TaxationRecommendation.INDIVIDUAL
    )
    screen = ModeloTaxationComparisonScreen(_serving(served), form=synthetic_form())
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await _ask(pilot, screen)
        joint_marked = screen.query_one("#taxcmp-joint").has_class("-recommended")
        individual_marked = screen.query_one("#taxcmp-individual").has_class("-recommended")
        reason = _text(screen, "#taxcmp-reason")

    assert individual_marked and not joint_marked
    assert reason == served.recommendation_reason_words


@pytest.mark.asyncio
async def test_an_indifferent_comparison_marks_neither_mode_and_says_so_in_the_served_words(english: None) -> None:
    served = _projection(
        joint="1000.00", individual="1000.50", delta="0.50", recommendation=TaxationRecommendation.INDIFFERENT
    )
    screen = ModeloTaxationComparisonScreen(_serving(served), form=synthetic_form())
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await _ask(pilot, screen)
        marked = [widget.id for widget in screen.query(".taxcmp-mode") if widget.has_class("-recommended")]
        texts = _text(screen, "#taxcmp-joint") + _text(screen, "#taxcmp-individual")
        reason = _text(screen, "#taxcmp-reason")
        phase = screen.phase

    assert phase is ComparisonPhase.READY
    assert marked == []
    assert tr("desktop.modelo.compare.taxation.recommended") not in texts
    assert reason == served.recommendation_reason_words


@pytest.mark.asyncio
async def test_a_refund_keeps_the_sign_it_was_served_with_next_to_an_amount_to_pay(spanish: None) -> None:
    served = _projection(
        joint="-300.00",
        individual="1250.00",
        delta="1550.00",
        joint_tax="-300.00",
        individual_tax="1250.00",
        recommendation=TaxationRecommendation.CONJUNTA,
        language=OutputLanguage.ES,
    )
    screen = ModeloTaxationComparisonScreen(_serving(served), form=synthetic_form())
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await _ask(pilot, screen)
        joint = _text(screen, "#taxcmp-joint")
        individual = _text(screen, "#taxcmp-individual")

    joint_result = next(
        line for line in joint.splitlines() if line.startswith(tr("desktop.modelo.compare.taxation.result"))
    )
    individual_result = next(
        line for line in individual.splitlines() if line.startswith(tr("desktop.modelo.compare.taxation.result"))
    )
    # The product writes a negative amount with the true minus sign.
    assert "−300,00" in joint_result
    assert "1.250,00" in individual_result
    assert not {"-", "−"} & set(individual_result.split(":", 1)[1])


@pytest.mark.asyncio
async def test_words_served_in_another_language_are_shown_as_served_and_the_language_is_named(english: None) -> None:
    served = _projection(
        joint="100.00",
        individual="200.00",
        delta="100.00",
        recommendation=TaxationRecommendation.CONJUNTA,
        language=OutputLanguage.HU,
    )
    screen = ModeloTaxationComparisonScreen(_serving(served), form=synthetic_form())
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await _ask(pilot, screen)
        reason = _text(screen, "#taxcmp-reason")
        note = _text(screen, "#taxcmp-language")
        note_shown = _shown(screen, "#taxcmp-language")

    assert reason == served.recommendation_reason_words
    assert note_shown
    assert note == tr(
        "desktop.modelo.compare.words_language",
        language=tr("wizard.setup.profile.output-language.choices.hu.label", locale="hu"),
    )


@pytest.mark.asyncio
async def test_while_the_comparison_is_read_the_screen_says_so_and_asks_nothing_more(english: None) -> None:
    release = asyncio.Event()
    served = _projection(joint="1.00", individual="2.00", delta="1.00", recommendation=TaxationRecommendation.CONJUNTA)
    calls = 0

    async def door() -> ModeloTaxationComparisonProjection:
        nonlocal calls
        calls += 1
        await release.wait()
        return served

    screen = ModeloTaxationComparisonScreen(door, form=synthetic_form())
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        screen.query_one("#taxcmp-ask", Button).press()
        await pilot.pause()
        await pilot.pause()
        reading_phase = screen.phase
        reading_text = _text(screen, "#taxcmp-reading")
        ask_disabled = screen.query_one("#taxcmp-ask", Button).disabled
        screen.ask()
        release.set()
        await settle(pilot)
        answered_phase = screen.phase
        ask_disabled_after = screen.query_one("#taxcmp-ask", Button).disabled

    assert reading_phase is ComparisonPhase.READING
    assert reading_text == tr("tui.modelo.taxation.reading")
    assert ask_disabled
    assert calls == 1
    assert answered_phase is ComparisonPhase.READY
    assert not ask_disabled_after


@pytest.mark.asyncio
async def test_a_refusal_is_shown_in_its_served_words_through_the_refusal_panel_with_its_verdict(english: None) -> None:
    error = taxation_comparison_refusal(TaxationComparisonRefusal.SPOUSE_UNSTATED, work_unit_id=_WORK_UNIT)
    screen = ModeloTaxationComparisonScreen(_refusing(error), form=synthetic_form())
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await _ask(pilot, screen)
        phase = screen.phase
        refusal = screen.query_one("#taxcmp-refusal", RefusalSlot).refusal
        words = _text(screen, "#refusal-words")
        fallback_shown = _shown(screen, "#taxcmp-refused")
        boxes_shown = _shown(screen, "#taxcmp-boxes")
        modes_shown = _shown(screen, "#taxcmp-modes")
        ask = str(screen.query_one("#taxcmp-ask", Button).label)

    assert phase is ComparisonPhase.REFUSED
    assert refusal is not None and refusal.verdict is not None and refusal.verdict.action_id is not None
    assert words == tr("application.modelo.taxation_comparison_words.refusal.spouse_unstated")
    assert not (fallback_shown or boxes_shown or modes_shown)
    assert ask == tr("desktop.modelo.compare.again")


@pytest.mark.asyncio
async def test_a_refusal_naming_boxes_lists_them_with_the_forms_labels_and_choosing_one_returns_its_id(
    english: None,
) -> None:
    error = taxation_comparison_refusal(
        TaxationComparisonRefusal.UNRESOLVED_BOXES, casilla_ids=("07", "09"), work_unit_id=_WORK_UNIT
    )
    screen = ModeloTaxationComparisonScreen(_refusing(error), form=synthetic_form())
    app = ScreenHostApp(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await _ask(pilot, screen)
        listing = screen.query_one("#taxcmp-boxes", OptionList)
        prompts = [str(listing.get_option_at_index(index).prompt) for index in range(listing.option_count)]
        heading = _text(screen, "#taxcmp-boxes-title")
        await pilot.press("down", "enter")
        await settle(pilot)
    chosen = app.return_value

    assert prompts == ["[07] Base imponible", "[09] Cuota"]
    assert heading == tr("desktop.modelo.compare.taxation.boxes")
    assert chosen == "09"


@pytest.mark.asyncio
async def test_a_box_the_form_does_not_place_is_still_named(english: None) -> None:
    error = taxation_comparison_refusal(
        TaxationComparisonRefusal.UNRESOLVED_BOXES, casilla_ids=("9999",), work_unit_id=_WORK_UNIT
    )
    screen = ModeloTaxationComparisonScreen(_refusing(error), form=synthetic_form())
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await _ask(pilot, screen)
        listing = screen.query_one("#taxcmp-boxes", OptionList)
        prompts = [str(listing.get_option_at_index(index).prompt) for index in range(listing.option_count)]

    assert prompts == ["[9999]"]


@pytest.mark.asyncio
async def test_a_failure_that_served_no_refusal_says_the_comparison_could_not_be_read_and_asking_again_works(
    english: None,
) -> None:
    served = _projection(joint="1.00", individual="2.00", delta="1.00", recommendation=TaxationRecommendation.CONJUNTA)
    answers: list[ModeloTaxationComparisonProjection | Exception] = [RuntimeError("no service"), served]

    async def door() -> ModeloTaxationComparisonProjection:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    screen = ModeloTaxationComparisonScreen(door, form=synthetic_form())
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await _ask(pilot, screen)
        failed_phase = screen.phase
        failed_text = _text(screen, "#taxcmp-failed")
        await _ask(pilot, screen)
        ready_phase = screen.phase
        failed_shown = _shown(screen, "#taxcmp-failed")

    assert failed_phase is ComparisonPhase.FAILED
    assert failed_text == tr("desktop.modelo.compare.failed")
    assert ready_phase is ComparisonPhase.READY and not failed_shown


@pytest.mark.asyncio
async def test_escape_closes_the_comparison_without_choosing_a_box() -> None:
    served = _projection(joint="1.00", individual="2.00", delta="1.00", recommendation=TaxationRecommendation.CONJUNTA)
    screen = ModeloTaxationComparisonScreen(_serving(served), form=synthetic_form())
    app = ScreenHostApp(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await pilot.press("escape")
        await settle(pilot)

    assert app.return_value is None
