"""The setup flow asks for the RIRPF art. 7 criterion one ejercicio at a time.

Structure, validation and the facts an answer becomes. The writers that persist
those facts are exercised against an encrypted profile in the persistence tests.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.aggregation.renta_imputation import ActivityImputationCriterion
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.user_profile.setup_answers import SetupAnswers

from ..errors import WizardMissingFlagError, WizardValidationError
from ..imputation_election import (
    ACCOUNTING_PROFILE_PATH,
    ACCOUNTING_QUESTION_ID,
    CRITERION_PROFILE_PATH,
    CRITERION_QUESTION_ID,
    ELECTION_QUESTION_IDS,
    YEAR_QUESTION_ID,
    election_answers,
    election_changes,
)
from ..models import WizardCondition, WizardFlow, WizardQuestion, WizardVisibility
from ..patch_edit import cleared_profile_paths
from ..persistence import profile_values_from_patch
from ..widgets import validate_widget_answer
from .registry_setup_flow_support import registry_setup_flow as registry_setup_flow

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_REGIME_QUESTION_ID = "irpf-estimation-regime"
_YEAR = filing_year_envelope().horizon


def _question(flow: WizardFlow, question_id: str) -> WizardQuestion:
    return next(q for section in flow.sections for q in section.questions if q.id == question_id)


def test_election_is_asked_after_the_regime_and_offers_the_schema_criteria_with_no_default(
    registry_setup_flow: WizardFlow, operation: PinnedAuthorityOperation
) -> None:
    ids = [q.id for section in registry_setup_flow.sections for q in section.questions]
    at = ids.index(_REGIME_QUESTION_ID)
    assert ids[at + 1 : at + 4] == [CRITERION_QUESTION_ID, YEAR_QUESTION_ID, ACCOUNTING_QUESTION_ID]

    criterion, year, accounting = (_question(registry_setup_flow, question_id) for question_id in ids[at + 1 : at + 4])
    declared = operation.profile_schema().field(CRITERION_PROFILE_PATH).enum_values
    assert [choice.value for choice in criterion.choices] == list(declared)
    assert declared[0] == ActivityImputationCriterion.DEVENGO.value
    assert set(declared) == {member.value for member in ActivityImputationCriterion}
    assert criterion.default is None
    assert not criterion.required
    assert criterion.profile_key == CRITERION_PROFILE_PATH
    assert accounting.default is None
    assert not accounting.required
    assert accounting.profile_key == ACCOUNTING_PROFILE_PATH
    assert year.profile_key is None
    assert not year.required

    year_gate = year.visible_when
    assert isinstance(year_gate, WizardVisibility)
    assert {clause.equals for clause in year_gate.any_of} == set(declared)
    assert {clause.question_id for clause in year_gate.any_of} == {CRITERION_QUESTION_ID}
    accounting_gate = accounting.visible_when
    assert isinstance(accounting_gate, WizardCondition)
    assert accounting_gate.question_id == CRITERION_QUESTION_ID
    assert accounting_gate.equals == ActivityImputationCriterion.COBROS_Y_PAGOS.value


@pytest.mark.parametrize("raw", ["25", "20250", "20x5", "٢٠٢٥", "0000", "-202", "2 25"])
def test_the_ejercicio_must_be_four_digits(registry_setup_flow: WizardFlow, raw: str) -> None:
    with pytest.raises(WizardValidationError):
        validate_widget_answer(_question(registry_setup_flow, YEAR_QUESTION_ID), raw)
    with pytest.raises(ValueError, match="four-digit"):
        SetupAnswers.model_validate({"tax_id": "x", "irpf_activity_income_imputation_year": raw})


def test_a_blank_or_four_digit_ejercicio_is_accepted(registry_setup_flow: WizardFlow) -> None:
    question = _question(registry_setup_flow, YEAR_QUESTION_ID)
    assert validate_widget_answer(question, " ") == ""
    assert validate_widget_answer(question, f" {_YEAR} ") == str(_YEAR)
    assert SetupAnswers.model_validate({"tax_id": "x", "irpf_activity_income_imputation_year": str(_YEAR)})


def test_election_answers_become_facts_dated_to_the_whole_ejercicio(registry_setup_flow: WizardFlow) -> None:
    changes = election_changes(
        registry_setup_flow,
        {CRITERION_QUESTION_ID: "devengo", YEAR_QUESTION_ID: str(_YEAR), ACCOUNTING_QUESTION_ID: "true"},
    )

    assert {(fact.path, fact.value, fact.valid_from, fact.valid_to) for fact in changes} == {
        (CRITERION_PROFILE_PATH, "devengo", date(_YEAR, 1, 1), date(_YEAR, 12, 31)),
        (ACCOUNTING_PROFILE_PATH, True, date(_YEAR, 1, 1), date(_YEAR, 12, 31)),
    }


def test_a_blank_answer_is_a_dated_clear_and_a_missing_answer_is_nothing(registry_setup_flow: WizardFlow) -> None:
    cleared = election_changes(registry_setup_flow, {CRITERION_QUESTION_ID: " ", YEAR_QUESTION_ID: str(_YEAR)})

    assert [(fact.path, fact.value, fact.valid_from) for fact in cleared] == [
        (CRITERION_PROFILE_PATH, None, date(_YEAR, 1, 1))
    ]
    assert election_changes(registry_setup_flow, {}) == ()
    assert election_changes(registry_setup_flow, {YEAR_QUESTION_ID: str(_YEAR)}) == ()


@pytest.mark.parametrize(
    "supplied",
    [{CRITERION_QUESTION_ID: "devengo"}, {ACCOUNTING_QUESTION_ID: "false"}, {CRITERION_QUESTION_ID: ""}],
)
def test_an_answer_without_its_ejercicio_is_refused(registry_setup_flow: WizardFlow, supplied: dict[str, str]) -> None:
    with pytest.raises(WizardMissingFlagError):
        election_changes(registry_setup_flow, supplied)


def test_an_unknown_criterion_and_a_malformed_accounting_answer_are_refused(registry_setup_flow: WizardFlow) -> None:
    with pytest.raises(WizardValidationError):
        election_changes(registry_setup_flow, {CRITERION_QUESTION_ID: "caja", YEAR_QUESTION_ID: str(_YEAR)})
    with pytest.raises(WizardValidationError):
        election_changes(registry_setup_flow, {ACCOUNTING_QUESTION_ID: "maybe", YEAR_QUESTION_ID: str(_YEAR)})


def test_the_undated_projections_never_carry_the_election(registry_setup_flow: WizardFlow) -> None:
    supplied = {question_id: "" for question_id in ELECTION_QUESTION_IDS}
    assert profile_values_from_patch(registry_setup_flow, {**supplied, CRITERION_QUESTION_ID: "devengo"}) == {}
    assert cleared_profile_paths(registry_setup_flow, supplied) == ()


def test_a_completed_answers_model_states_only_what_was_answered() -> None:
    blank = SetupAnswers.model_validate({"tax_id": "x"})
    assert election_answers(blank, stored={}) == {}

    stated = SetupAnswers.model_validate(
        {
            "tax_id": "x",
            "irpf_activity_income_imputation_criterion": "cobros_y_pagos",
            "irpf_activity_income_imputation_year": str(_YEAR),
            "irpf_codigo_comercio_accounting": False,
        }
    )
    assert election_answers(stated, stored={}) == {
        CRITERION_QUESTION_ID: "cobros_y_pagos",
        YEAR_QUESTION_ID: str(_YEAR),
        ACCOUNTING_QUESTION_ID: "false",
    }
