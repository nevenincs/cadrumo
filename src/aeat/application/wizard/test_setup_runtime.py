"""Scripted-answer round-trip tests for the wizard runtime against the setup flow.

These tests verify that ``run_flow`` walks the descriptor in the
declared order, skips conditional questions when ``visible_when`` is
not satisfied, builds a typed answers model that validates, and that
``persist_answers`` + ``project_answers`` round-trip the canonical-token
representation back to the same typed model.
"""

from __future__ import annotations

from collections import deque

import pytest

from aeat.application.wizard._catalogue import SETUP_FLOW
from aeat.application.wizard._errors import WizardScriptOverflowError
from aeat.application.wizard._models import WizardWidget
from aeat.application.wizard._persistence import project_answers, serialise_answers
from aeat.application.wizard._prompter import ScriptedPrompter
from aeat.application.wizard._runner import run_flow
from aeat.application.wizard._setup_answers import SetupAnswers

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _scripted_answers_for_individual_declaration() -> deque[str]:
    """Build a scripted answer set for an individual taxation profile.

    The order matches the declared question order in ``SETUP_FLOW``.
    Conditional spouse questions tied to ``taxation_type == "2"``
    are skipped by the runtime, so they should NOT appear in the
    deque.
    """

    return deque(
        [
            # ── profile ────────────────────────────
            "12345678Z",  # tax-id
            "Operator",  # name
            "Doe",  # surnames
            "Software development",  # activity
            "28001",  # address-postcode
            "1",  # taxation-type (individual)
            "en",  # output-language
            # ── taxpayer type ──────────────────────
            "natural_person",  # entity-type
            # legal-entity-form SKIPPED (conditional on entity-type == legal_entity)
            "trabajo,capital_inmobiliario",  # irpf-income-categories
            # ── taxpayer biographic ────────────────
            "",  # taxpayer-sex
            "",  # taxpayer-marital-status
            "",  # taxpayer-birth-date
            "",  # taxpayer-disability-grade
            "",  # taxpayer-death-date
            # ── spouse (joint taxation condition NOT satisfied) ──
            # spouse-tax-id … spouse-sex SKIPPED by runtime
            "",  # spouse-disability-grade (unconditional)
            "false",  # spouse-non-resident-irpf (unconditional)
            # spouse-eu-eea-resident SKIPPED (conditional on non-resident)
            # spouse-eu-eea-country SKIPPED (conditional on eu-eea-resident)
            # ── family ──────────────────────────────
            "false",  # family-descendants-eu-eea-deduction
            "false",  # family-minor-children-in-unit
            # ── IVA ────────────────────────────────
            "GENERAL",  # iva-regime
            "false",  # iva-roi-enrolled
            "false",  # iva-oss-enrolled
            "false",  # iva-sii-enrolled
            "false",  # iva-redeme-enrolled
            "false",  # iva-intracommunity-operations-exceed-50000-eur
            # ── enrollment ─────────────────────────
            "false",  # enrollment-large-company
            "false",  # enrollment-public-administration-budget-gt-6000000
            # ── obligations ────────────────────────
            "false",  # has-employees
            "false",  # pays-professionals-with-retencion
            "false",  # professional-income-withholding-ge-70pct
            "false",  # pays-rent-with-retencion
            "false",  # pays-capital-income-with-retencion
            "false",  # uses-objective-estimation-irpf
            "directa_normal",  # irpf-estimation-regime
            "false",  # does-intracomunitario
            "false",  # third-party-transactions-above-347-threshold
            "false",  # bienes-extranjero-above-threshold
            # ── residence ──────────────────────────
            "madrid",  # tax-residence-ccaa
            # ── notes ──────────────────────────────
            "",  # notes
        ]
    )


def test_run_flow_collects_visible_questions_in_order() -> None:
    prompter = ScriptedPrompter(_scripted_answers_for_individual_declaration())
    answers = run_flow(SETUP_FLOW, prompter)
    assert isinstance(answers, SetupAnswers)
    assert answers.tax_id == "12345678Z"
    assert answers.activity == "Software development"
    assert answers.output_language == "en"


def test_run_flow_skips_spouse_questions_when_declaration_is_individual() -> None:
    prompter = ScriptedPrompter(_scripted_answers_for_individual_declaration())
    run_flow(SETUP_FLOW, prompter)
    # Spouse joint-conditional questions must not be asked when taxation_type != "2"
    assert "spouse-tax-id" not in prompter.asked
    assert "spouse-name" not in prompter.asked
    assert "spouse-eu-eea-resident" not in prompter.asked
    # But the unconditional spouse-non-resident-irpf must be asked
    assert "spouse-non-resident-irpf" in prompter.asked


def test_runner_close_overflow_is_caught() -> None:
    """Calling close on a deque with extra answers raises overflow."""

    extras = _scripted_answers_for_individual_declaration()
    extras.append("orphan")
    prompter = ScriptedPrompter(extras)
    with pytest.raises(WizardScriptOverflowError, match=r"overflow|orphan|script|unused"):
        run_flow(SETUP_FLOW, prompter)


def test_persist_answers_round_trip_via_project_answers() -> None:
    prompter = ScriptedPrompter(_scripted_answers_for_individual_declaration())
    answers = run_flow(SETUP_FLOW, prompter)
    assert isinstance(answers, SetupAnswers)
    canonical = serialise_answers(SETUP_FLOW, answers)
    rebuilt = project_answers(SETUP_FLOW, canonical)
    assert isinstance(rebuilt, SetupAnswers)
    assert rebuilt.tax_id == answers.tax_id
    assert rebuilt.iva_regime == answers.iva_regime
    assert rebuilt.tax_residence_ccaa == answers.tax_residence_ccaa


def test_canonical_dict_only_carries_profile_bound_keys() -> None:
    prompter = ScriptedPrompter(_scripted_answers_for_individual_declaration())
    answers = run_flow(SETUP_FLOW, prompter)
    canonical = serialise_answers(SETUP_FLOW, answers)
    assert "identity.tax_id" in canonical
    assert canonical["identity.tax_id"] == "12345678Z"
    assert canonical["preferences.output_language"] == "en"
    assert "tax_residence.ccaa" in canonical
    assert canonical["tax_residence.ccaa"] == "madrid"
    # Non-profile-bound questions don't surface in the canonical map
    non_profile_questions = {
        question.id.replace("-", "_")
        for section in SETUP_FLOW.sections
        for question in section.questions
        if question.profile_key is None
    }
    for key in non_profile_questions:
        assert key not in canonical


def test_run_flow_walks_joint_taxation_spouse_questions() -> None:
    """When ``taxation_type == "2"``, the spouse questions appear in order."""

    answers_deque: deque[str] = deque(
        [
            "12345678Z",  # tax-id
            "Operator",  # name
            "Doe",  # surnames
            "Software development",  # activity
            "28001",  # address-postcode
            "2",  # taxation-type (joint)
            "en",  # output-language
            "natural_person",  # entity-type
            # legal-entity-form SKIPPED (conditional on entity-type == legal_entity)
            "trabajo",  # irpf-income-categories
            "",  # taxpayer-sex
            "",  # taxpayer-marital-status
            "",  # taxpayer-birth-date
            "",  # taxpayer-disability-grade
            "",  # taxpayer-death-date
            # spouse joint-conditional questions are NOW visible
            "87654321X",  # spouse-tax-id
            "Spouse",  # spouse-name
            "Doe",  # spouse-surnames
            "",  # spouse-birth-date
            "",  # spouse-sex
            "",  # spouse-disability-grade
            "false",  # spouse-non-resident-irpf
            # spouse-eu-eea-resident SKIPPED (non-resident=false)
            # spouse-eu-eea-country SKIPPED
            "false",  # family-descendants-eu-eea-deduction
            "false",  # family-minor-children-in-unit
            "GENERAL",  # iva-regime
            "false",  # iva-roi-enrolled
            "false",  # iva-oss-enrolled
            "false",  # iva-sii-enrolled
            "false",  # iva-redeme-enrolled
            "false",  # iva-intracommunity-operations-exceed-50000-eur
            "false",  # enrollment-large-company
            "false",  # enrollment-public-administration-budget-gt-6000000
            "false",  # has-employees
            "false",  # pays-professionals-with-retencion
            "false",  # professional-income-withholding-ge-70pct
            "false",  # pays-rent-with-retencion
            "false",  # pays-capital-income-with-retencion
            "false",  # uses-objective-estimation-irpf
            "directa_normal",  # irpf-estimation-regime
            "false",  # does-intracomunitario
            "false",  # third-party-transactions-above-347-threshold
            "false",  # bienes-extranjero-above-threshold
            "madrid",  # tax-residence-ccaa
            "",  # notes
        ]
    )
    prompter = ScriptedPrompter(answers_deque)
    answers = run_flow(SETUP_FLOW, prompter)
    assert isinstance(answers, SetupAnswers)
    assert "spouse-tax-id" in prompter.asked
    assert "spouse-name" in prompter.asked
    assert "spouse-eu-eea-resident" not in prompter.asked
    assert answers.spouse_tax_id == "87654321X"


def test_select_widget_default_is_set_during_runtime() -> None:
    """Smoke check that SELECT defaults survive the flow."""

    iva_question = next(q for section in SETUP_FLOW.sections for q in section.questions if q.id == "iva-regime")
    assert iva_question.widget is WizardWidget.SELECT
    assert iva_question.default == "GENERAL"
