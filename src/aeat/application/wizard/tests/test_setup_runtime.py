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

from ....core.setup_answers import SetupAnswers
from ....domain.deadlines._models import LegalEntityForm
from .._catalogue import SETUP_FLOW
from .._errors import WizardScriptOverflowError
from .._models import WizardWidget
from .._persistence import project_answers, serialise_answers
from .._prompter import ScriptedPrompter
from .._runner import run_flow

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _scripted_answers_for_individual_declaration() -> deque[str]:
    """Build a scripted answer set for an individual taxation profile.

    The order matches the declared question order in ``SETUP_FLOW``:
    the taxpayer-type section is walked first, so ``entity-type``
    fixes the natural-person path before the IRPF-personal sections.
    Conditional spouse questions tied to ``taxation_type == "2"`` are
    skipped by the runtime, so they do NOT appear in the deque. The
    ``activity`` question is visible here because the declared IRPF
    income categories include ``actividad_economica``.
    """

    return deque(
        [
            # ── taxpayer type ──────────────────────
            "natural_person",  # entity-type
            # legal-entity-form SKIPPED (conditional on entity-type == legal_entity)
            "actividad_economica,capital_inmobiliario",  # irpf-income-categories
            "",  # incn-prior-12-months (optional, blank — natural person doesn't gate Modelo 202)
            # new-entity-first-two-profit-periods SKIPPED (conditional on entity-type == legal_entity)
            # ── profile ────────────────────────────
            "12345678Z",  # tax-id
            "Operator",  # name
            "Doe",  # surnames
            "Software development",  # activity (visible: has actividad_economica)
            "28001",  # address-postcode
            "",  # activity-start-date (optional, left blank)
            "1",  # taxation-type (individual, visible: natural person)
            "en",  # output-language
            # ── taxpayer biographic (visible: natural person) ──
            "",  # taxpayer-sex
            "",  # taxpayer-marital-status
            "soltero",  # situacion-familiar (Art. 82 LIRPF axis, contract)
            # taxpayer-marriage-date SKIPPED (conditional on marital-status == CASADO)
            "",  # taxpayer-birth-date
            "",  # taxpayer-disability-grade
            "",  # taxpayer-death-date
            # ── spouse (joint taxation condition NOT satisfied) ──
            # every spouse question is joint-gated; none is asked here
            # ── family (visible: natural person) ────
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
            "",  # modelo-111-no-retenciones-periods
            "directa_normal",  # irpf-estimation-regime
            "general",  # irpf-special-regime (visible: natural person; no special regime)
            # irpf-special-regime-start-date SKIPPED (conditional on irpf-special-regime == IMPATRIADO)
            "false",  # does-intracomunitario
            "false",  # third-party-transactions-above-347-threshold
            "false",  # bienes-extranjero-above-threshold
            "false",  # monedas-virtuales-extranjero-above-threshold
            # ── residence (non-resident axis #197) ────────────
            "resident_irpf",  # fiscal-residency
            # country-of-fiscal-residence + representante-fiscal-* SKIPPED
            # (conditional on fiscal-residency == non_resident_irnr).
            "madrid",  # tax-residence-ccaa (visible: resident)
            # ── capabilities ───────────────────────
            "false",  # cloud-evidence-upload
            "true",  # llm-vision
            "true",  # google-export
            # ── notes ──────────────────────────────
            "",  # notes
        ],
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
    # Every spouse question is joint-gated; none is asked for an
    # individual declaration (taxation_type != "2").
    assert "spouse-tax-id" not in prompter.asked
    assert "spouse-name" not in prompter.asked
    assert "spouse-eu-eea-resident" not in prompter.asked
    assert "spouse-non-resident-irpf" not in prompter.asked
    assert "spouse-disability-grade" not in prompter.asked


def test_runner_close_overflow_is_caught() -> None:
    """Calling close on a deque with extra answers raises overflow."""

    extras = _scripted_answers_for_individual_declaration()
    extras.append("orphan")
    prompter = ScriptedPrompter(extras)
    with pytest.raises(WizardScriptOverflowError) as excinfo:
        run_flow(SETUP_FLOW, prompter)
    assert excinfo.value.translated_message == "errors.internal.internal_wizard_script_overflow"
    assert excinfo.value.context == {
        "remaining_count": 1,
        "asked_count": len(_scripted_answers_for_individual_declaration()),
    }
    assert "orphan" not in str(excinfo.value.context)


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
            # ── taxpayer type ──────────────────────
            "natural_person",  # entity-type
            # legal-entity-form SKIPPED (conditional on entity-type == legal_entity)
            "actividad_economica,trabajo",  # irpf-income-categories
            "",  # incn-prior-12-months (optional)
            # new-entity-first-two-profit-periods SKIPPED (conditional on entity-type == legal_entity)
            # ── profile ────────────────────────────
            "12345678Z",  # tax-id
            "Operator",  # name
            "Doe",  # surnames
            "Software development",  # activity (visible: has actividad_economica)
            "28001",  # address-postcode
            "",  # activity-start-date (optional, left blank)
            "2",  # taxation-type (joint, visible: natural person)
            "en",  # output-language
            # ── taxpayer biographic (visible: natural person) ──
            "",  # taxpayer-sex
            "",  # taxpayer-marital-status
            "soltero",  # situacion-familiar (Art. 82 LIRPF axis, contract)
            # taxpayer-marriage-date SKIPPED (conditional on marital-status == CASADO)
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
            "",  # modelo-111-no-retenciones-periods
            "directa_normal",  # irpf-estimation-regime
            "general",  # irpf-special-regime (visible: natural person)
            # irpf-special-regime-start-date SKIPPED (conditional on impatriado)
            "false",  # does-intracomunitario
            "false",  # third-party-transactions-above-347-threshold
            "false",  # bienes-extranjero-above-threshold
            "false",  # monedas-virtuales-extranjero-above-threshold
            "resident_irpf",  # fiscal-residency (#197 non-resident axis)
            # country-of-fiscal-residence + representante-fiscal-* SKIPPED (resident)
            "madrid",  # tax-residence-ccaa
            "false",  # cloud-evidence-upload
            "true",  # llm-vision
            "true",  # google-export
            "",  # notes
        ],
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


def _non_interactive_canonical(explicit: dict[str, str]) -> dict[str, str]:
    """Seed descriptor defaults, then layer the operator's explicit flags.

    Mirrors the ``--accept-defaults`` create path: the canonical dict is
    every descriptor default plus the operator's explicit flag values.
    """

    seeded = {
        question.id: question.default or ""
        for section in SETUP_FLOW.sections
        for question in section.questions
        if question.default is not None
    }
    seeded.update(explicit)
    return seeded


_LEGAL_ENTITY_FLAGS: dict[str, str] = {
    "entity-type": "legal_entity",
    "legal-entity-form": "sl",
    "tax-id": "B66012345",
    "activity": "consultoria",
}


def test_legal_entity_intra_section_gate_walks_legal_entity_form() -> None:
    """A legal entity reveals ``legal-entity-form`` even though its gate
    names ``entity-type`` in the *same* section.

    The runner evaluates ``visible_when`` incrementally, so an
    intra-section gate sees the answer to an earlier question in the
    same section. A section-wide upfront evaluation hid this question.
    """

    from .._commands import _scripted_from_canonical

    canonical = _non_interactive_canonical(_LEGAL_ENTITY_FLAGS)
    explicit = frozenset(_LEGAL_ENTITY_FLAGS)
    prompter = _scripted_from_canonical(SETUP_FLOW, canonical, force_visible=explicit)
    answers = run_flow(SETUP_FLOW, prompter, force_visible=explicit)
    assert isinstance(answers, SetupAnswers)
    assert prompter.asked.count("legal-entity-form") == 1
    assert answers.legal_entity_form is LegalEntityForm.SL


def test_legal_entity_does_not_walk_spouse_or_irpf_personal_questions() -> None:
    """A legal entity is never asked the spouse / personal-IRPF or the
    IRPF income-category questions — they are gated to natural persons."""

    from .._commands import _scripted_from_canonical

    canonical = _non_interactive_canonical(_LEGAL_ENTITY_FLAGS)
    explicit = frozenset(_LEGAL_ENTITY_FLAGS)
    prompter = _scripted_from_canonical(SETUP_FLOW, canonical, force_visible=explicit)
    run_flow(SETUP_FLOW, prompter, force_visible=explicit)
    for hidden in (
        "irpf-income-categories",
        "taxation-type",
        "taxpayer-sex",
        "taxpayer-marital-status",
        "spouse-tax-id",
        "spouse-non-resident-irpf",
        "family-minor-children-in-unit",
    ):
        assert hidden not in prompter.asked, hidden


def test_explicit_flag_forces_a_gated_question_visible() -> None:
    """An explicitly-supplied flag is honoured even when its
    ``visible_when`` gate would hide the question.

    ``activity`` is gated behind the economic-activity declaration; a
    legal entity reaches it via the ``entity_type == legal_entity``
    clause, but a natural person with no actividad_economica only gets
    it asked because the operator named ``--activity`` on the command
    line (``force_visible``)."""

    from .._commands import _scripted_from_canonical

    flags = {
        "entity-type": "natural_person",
        "irpf-income-categories": "capital_inmobiliario",
        "tax-id": "12345678Z",
        "activity": "explicitly supplied",
    }
    canonical = _non_interactive_canonical(flags)
    explicit = frozenset(flags)
    prompter = _scripted_from_canonical(SETUP_FLOW, canonical, force_visible=explicit)
    answers = run_flow(SETUP_FLOW, prompter, force_visible=explicit)
    assert isinstance(answers, SetupAnswers)
    assert "activity" in prompter.asked
    assert answers.activity == "explicitly supplied"


def test_landlord_without_activity_flag_is_not_asked_for_activity() -> None:
    """A pure landlord (only capital_inmobiliario, no --activity flag)
    is never asked for an economic activity — the gate stays closed."""

    from .._commands import _scripted_from_canonical

    flags = {
        "entity-type": "natural_person",
        "irpf-income-categories": "capital_inmobiliario",
        "tax-id": "12345678Z",
    }
    canonical = _non_interactive_canonical(flags)
    explicit = frozenset(flags)
    prompter = _scripted_from_canonical(SETUP_FLOW, canonical, force_visible=explicit)
    answers = run_flow(SETUP_FLOW, prompter, force_visible=explicit)
    assert isinstance(answers, SetupAnswers)
    assert "activity" not in prompter.asked
    assert answers.activity == ""
