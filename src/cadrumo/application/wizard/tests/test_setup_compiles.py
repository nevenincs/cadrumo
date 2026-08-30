"""Structural assertions on the ``setup`` wizard flow descriptor.

The tests verify every wiring invariant the runtime depends on: unique
question ids inside the flow, every ``WizardCondition.question_id``
resolves to an earlier question, every profile-bound question shows
up in the compiled ``PROFILE_KEYS``, and every choice value passes
``validate_widget_answer`` so the descriptor is internally consistent
before the runtime ever runs.
"""

from __future__ import annotations

import pytest

from ....domain.contribuyente.keys import PROFILE_KEYS
from ..catalogue import SETUP_FLOW, WIZARD_FLOWS
from ..compiler import compile_profile_keys
from ..models import WizardQuestion, iter_conditions
from ..widgets import validate_widget_answer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _setup_questions() -> tuple[WizardQuestion, ...]:
    return tuple(question for section in SETUP_FLOW.sections for question in section.questions)


def test_every_question_id_is_unique_inside_the_setup_flow() -> None:
    ids = [question.id for question in _setup_questions()]
    assert len(ids) == len(set(ids))


def test_every_visible_when_resolves_to_an_earlier_question() -> None:
    seen: set[str] = set()
    for question in _setup_questions():
        for clause in iter_conditions(question.visible_when):
            assert clause.question_id in seen
        seen.add(question.id)


def test_every_profile_key_appears_in_profile_keys() -> None:
    registered = {entry.key for entry in PROFILE_KEYS}
    for question in _setup_questions():
        if question.profile_key is not None:
            assert question.profile_key in registered


def test_every_choice_value_passes_its_widget_validator() -> None:
    questions_with_choices = [q for q in _setup_questions() if q.choices]
    assert questions_with_choices, "setup must declare at least one question with choices"
    validated = 0
    for question in questions_with_choices:
        for choice in question.choices:
            validate_widget_answer(question, choice.value)
            validated += 1
    assert validated > 0, "validator must have processed at least one choice"


def test_compile_profile_keys_returns_one_entry_per_profile_bound_question() -> None:
    expected = {question.profile_key for question in _setup_questions() if question.profile_key is not None}
    compiled = {entry.key for entry in compile_profile_keys(WIZARD_FLOWS)}
    assert expected == compiled


def test_tax_residence_ccaa_is_a_descriptor_bound_profile_key() -> None:
    profile_keys = {question.profile_key for question in _setup_questions()}
    assert "tax_residence.ccaa" in profile_keys
    registered = {entry.key for entry in PROFILE_KEYS}
    assert "tax_residence.ccaa" in registered


def test_pays_capital_income_and_irpf_estimation_regime_are_descriptor_questions() -> None:
    profile_keys = {question.profile_key for question in _setup_questions()}
    assert "withholding.pays_capital_income_with_retencion" in profile_keys
    assert "irpf.estimation_regime" in profile_keys
    assert "irpf.uses_objective_estimation" not in profile_keys
