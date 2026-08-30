"""Scripted-answer round-trip tests for the setup flow on the flow substrate.

These tests verify that the scripted intent driver walks the projected
setup definition in the declared order, skips conditional questions when
``visible_when`` is not satisfied, builds a typed answers model that
validates, and that ``persist_answers`` + ``project_answers`` round-trip
the canonical-token representation back to the same typed model.
"""

from __future__ import annotations

from collections import deque

import pytest

from ....core.flows import FlowMode
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH, SetupAnswers
from ....domain.deadlines.models import LegalEntityForm
from ...flows.errors import FlowAnswerError
from ...flows.scripted import run_scripted_flow
from ..catalogue import SETUP_FLOW
from ..commands import (
    _answers_model_from_canonical,
    _force_pages_visible,
    _project_scripted_answers,
    setup_flow_definition,
)
from ..descendant_group import DESCENDANTS_COUNT_PAGE_ID
from ..models import WizardWidget
from ..persistence import project_answers, serialise_answers

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _default_tokens() -> dict[str, str]:
    """Every descriptor default, keyed by question id — the quiet-path seed."""

    return {
        question.id: question.default or ""
        for section in SETUP_FLOW.sections
        for question in section.questions
        if question.default is not None
    }


def _drive_scripted(
    canonical: dict[str, str],
    *,
    force_visible: frozenset[str] = frozenset(),
) -> tuple[SetupAnswers, dict[str, str]]:
    """Drive a non-interactive walk through the shared flow substrate.

    Mirrors the production non-interactive command path: project the
    catalogue onto the flow definition, force any explicitly-supplied
    gated questions visible, project the canonical dict into the
    driver's own visible-sequence token order, run the scripted intent
    driver, and coerce the committed answers through the one typed
    projection every frontend shares.

    Returns the typed answers plus the committed page-keyed answer map —
    a question the walk visited carries a key in the map, a gate-hidden
    question is absent.
    """
    definition = _force_pages_visible(setup_flow_definition(SETUP_FLOW), force_visible)
    tokens, _intended = _project_scripted_answers(definition, canonical, mode=FlowMode.CREATE)
    state, _projection = run_scripted_flow(
        definition,
        tokens,
        mode=FlowMode.CREATE,
        defaults=_default_tokens(),
    )
    committed = dict(state.answers)
    answers = _answers_model_from_canonical(SETUP_FLOW, committed)
    assert isinstance(answers, SetupAnswers)
    return answers, committed


def _scripted_answers_for_individual_declaration() -> deque[str]:
    """Build the ordered scripted token queue for an individual taxation profile.

    The order matches the scripted driver's visible-sequence walk over the
    projected setup definition: the identidad section is walked first, so
    ``entity-type`` fixes the natural-person path before every later
    section's gated questions. Conditional spouse questions tied to
    ``taxation_type == "2"`` are never visited, so they do NOT appear in
    the queue. Shared by sibling test modules that drive the substrate
    with a positional token queue.
    """

    canonical = _individual_declaration_canonical()
    definition = setup_flow_definition(SETUP_FLOW)
    _tokens, intended = _project_scripted_answers(definition, canonical, mode=FlowMode.CREATE)
    # The shared fixture carries no token for the descendant count page:
    # the sibling scripted-walk helper defaults that page in walk order, so
    # a positional token for it would misfeed the next visible page.
    return deque(token for key, token in intended.items() if key != DESCENDANTS_COUNT_PAGE_ID)


def _individual_declaration_canonical() -> dict[str, str]:
    """Build the canonical answer set for an individual taxation profile.

    Conditional spouse questions tied to ``taxation_type == "2"`` stay
    gate-hidden, so the driver never visits them. The ``activity``
    question is visible because the declared IRPF income categories
    include ``actividad_economica``.
    """

    return {
        # -- identidad --
        "output-language": "en",
        "entity-type": "natural_person",
        # legal-entity-form gate-hidden (conditional on entity-type == legal_entity)
        "tax-id": "12345678Z",
        "name": "Operator",
        "surnames": "Doe",
        # -- residence --
        "fiscal-residency": "resident_irpf",
        "tax-residence-jurisdiction-scope": "common_regime",
        "tax-residence-ccaa": "madrid",
        "address-postcode": "28001",
        # -- actividad --
        "irpf-income-categories": "actividad_economica,capital_inmobiliario",
        "activity": "Software development",
        "activity-start-date": "",
        "incn-prior-12-months": "",
        # -- IVA --
        "iva-regime": "GENERAL",
        "iva-m303-regime-composition": "general",
        "iva-roi-enrolled": "false",
        "iva-oss-enrolled": "false",
        "iva-group-member-enrolled": "false",
        "iva-group-dominant-entity-enrolled": "false",
        "iva-sii-enrolled": "false",
        "iva-redeme-enrolled": "false",
        "iva-intracommunity-operations-exceed-50000-eur": "false",
        "iva-cash-accounting-regime-enrolled": "false",
        "iva-voluntary-sii-enrolled": "false",
        "iva-hydrocarbon-deposit-advance-payment-deduction-entitled": "false",
        # -- enrollment --
        "enrollment-large-company": "false",
        "enrollment-public-administration-budget-gt-6000000": "false",
        # -- familia --
        "taxation-type": "1",
        "taxpayer-sex": "",
        "taxpayer-marital-status": "",
        "situacion-familiar": "soltero",
        "taxpayer-birth-date": "",
        "taxpayer-disability-grade": "",
        "taxpayer-death-date": "",
        "family-descendants-eu-eea-deduction": "false",
        "family-minor-children-in-unit": "false",
        # -- obligations --
        "has-employees": "false",
        "pays-professionals-with-retencion": "false",
        "art109-activity-income-withholding-ge-70pct": "false",
        "pays-rent-with-retencion": "false",
        "pays-capital-income-with-retencion": "false",
        "modelo-111-no-retenciones-periods": "",
        "irpf-estimation-regime": "directa_normal",
        "irpf-special-regime": "general",
        "does-intracomunitario": "false",
        "third-party-transactions-above-347-threshold": "false",
        "bienes-extranjero-above-threshold": "false",
        "monedas-virtuales-extranjero-above-threshold": "false",
        # -- preferencias --
        "cloud-evidence-upload": "false",
        "llm-vision": "true",
        "google-export": "true",
        "notes": "",
    }


def test_output_language_is_the_first_page_of_the_flow() -> None:
    """The operator chooses the output language before anything else renders.

    The language question must open the flow so the chosen locale can be
    activated for the remainder of the walk; it therefore heads the first
    section and appears nowhere else.
    """
    first_section = SETUP_FLOW.sections[0]
    first_question = first_section.questions[0]
    assert first_question.id == "output-language"
    assert first_question.profile_key == PROFILE_OUTPUT_LANGUAGE_PATH
    all_ids = [question.id for section in SETUP_FLOW.sections for question in section.questions]
    assert all_ids.count("output-language") == 1


def test_scripted_walk_collects_visible_questions_in_order() -> None:
    answers, _committed = _drive_scripted(_individual_declaration_canonical())
    assert answers.tax_id == "12345678Z"
    assert answers.activity == "Software development"
    assert answers.output_language == "en"


def test_scripted_walk_skips_spouse_questions_when_declaration_is_individual() -> None:
    _answers, committed = _drive_scripted(_individual_declaration_canonical())
    # Every spouse question is joint-gated; none is visited for an
    # individual declaration (taxation_type != "2").
    assert "spouse-tax-id" not in committed
    assert "spouse-name" not in committed
    assert "spouse-eu-eea-resident" not in committed
    assert "spouse-non-resident-irpf" not in committed
    assert "spouse-disability-grade" not in committed


def test_scripted_driver_rejects_unconsumed_tokens() -> None:
    """A queue longer than the visible walk raises overflow, counts only."""

    definition = setup_flow_definition(SETUP_FLOW)
    tokens, _intended = _project_scripted_answers(
        definition,
        _individual_declaration_canonical(),
        mode=FlowMode.CREATE,
    )
    with pytest.raises(FlowAnswerError) as excinfo:
        run_scripted_flow(
            definition,
            [*tokens, "orphan"],
            mode=FlowMode.CREATE,
            defaults=_default_tokens(),
        )
    assert excinfo.value.translated_message == "application.flows.errors.scripted_queue_overflow"
    assert excinfo.value.context == {
        "remaining_count": 1,
        "consumed_count": len(tokens),
    }
    assert "orphan" not in str(excinfo.value.context)


def test_persist_answers_round_trip_via_project_answers() -> None:
    answers, _committed = _drive_scripted(_individual_declaration_canonical())
    canonical = serialise_answers(SETUP_FLOW, answers)
    rebuilt = project_answers(SETUP_FLOW, canonical)
    assert isinstance(rebuilt, SetupAnswers)
    assert rebuilt.tax_id == answers.tax_id
    assert rebuilt.iva_regime == answers.iva_regime
    assert rebuilt.tax_residence_ccaa == answers.tax_residence_ccaa


def test_canonical_dict_only_carries_profile_bound_keys() -> None:
    answers, _committed = _drive_scripted(_individual_declaration_canonical())
    canonical = serialise_answers(SETUP_FLOW, answers)
    assert "identity.tax_id" in canonical
    assert canonical["identity.tax_id"] == "12345678Z"
    assert canonical[PROFILE_OUTPUT_LANGUAGE_PATH] == "en"
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


def test_scripted_walk_visits_joint_taxation_spouse_questions() -> None:
    """When ``taxation_type == "2"``, the spouse questions become visible."""

    joint = _individual_declaration_canonical()
    joint.update(
        {
            "irpf-income-categories": "actividad_economica,trabajo",
            "taxation-type": "2",
            # spouse joint-conditional questions are NOW visible
            "spouse-tax-id": "87654321X",
            "spouse-name": "Spouse",
            "spouse-surnames": "Doe",
            "spouse-birth-date": "",
            "spouse-sex": "",
            "spouse-disability-grade": "",
            "spouse-non-resident-irpf": "false",
            # spouse-eu-eea-resident stays gate-hidden (non-resident=false)
        },
    )
    answers, committed = _drive_scripted(joint)
    assert "spouse-tax-id" in committed
    assert "spouse-name" in committed
    assert "spouse-eu-eea-resident" not in committed
    assert answers.spouse_tax_id == "87654321X"


def test_iva_regime_has_no_implicit_runtime_default() -> None:
    """A profile must declare its IVA regime explicitly."""

    iva_question = next(q for section in SETUP_FLOW.sections for q in section.questions if q.id == "iva-regime")
    assert iva_question.widget is WizardWidget.SELECT
    assert iva_question.default is None


def _non_interactive_canonical(explicit: dict[str, str]) -> dict[str, str]:
    """Seed descriptor defaults, then layer the operator's explicit flags.

    Mirrors the ``--accept-defaults`` create path: the canonical dict is
    every descriptor default plus the operator's explicit flag values.
    """

    seeded = _default_tokens()
    seeded.update(explicit)
    return seeded


_LEGAL_ENTITY_FLAGS: dict[str, str] = {
    "entity-type": "legal_entity",
    "legal-entity-form": "sl",
    "tax-id": "B66012345",
    "activity": "consultoria",
    "tax-residence-jurisdiction-scope": "common_regime",
}


def test_legal_entity_intra_section_gate_walks_legal_entity_form() -> None:
    """A legal entity reveals ``legal-entity-form`` even though its gate
    names ``entity-type`` in the *same* section.

    The driver re-evaluates visibility after every commit, so an
    intra-section gate sees the answer to an earlier question in the
    same section. A section-wide upfront evaluation hid this question.
    """

    canonical = _non_interactive_canonical(_LEGAL_ENTITY_FLAGS)
    explicit = frozenset(_LEGAL_ENTITY_FLAGS)
    answers, committed = _drive_scripted(canonical, force_visible=explicit)
    assert "legal-entity-form" in committed
    assert answers.legal_entity_form is LegalEntityForm.SL


def test_legal_entity_does_not_walk_spouse_or_irpf_personal_questions() -> None:
    """A legal entity is never asked the spouse / personal-IRPF or the
    IRPF income-category questions — they are gated to natural persons."""

    canonical = _non_interactive_canonical(_LEGAL_ENTITY_FLAGS)
    explicit = frozenset(_LEGAL_ENTITY_FLAGS)
    _answers, committed = _drive_scripted(canonical, force_visible=explicit)
    for hidden in (
        "irpf-income-categories",
        "taxation-type",
        "taxpayer-sex",
        "taxpayer-marital-status",
        "spouse-tax-id",
        "spouse-non-resident-irpf",
        "family-minor-children-in-unit",
    ):
        assert hidden not in committed, hidden


def test_explicit_flag_forces_a_gated_question_visible() -> None:
    """An explicitly-supplied flag is honoured even when its
    ``visible_when`` gate would hide the question.

    ``activity`` is gated behind the economic-activity declaration; a
    legal entity reaches it via the ``entity_type == legal_entity``
    clause, but a natural person with no actividad_economica only gets
    it asked because the operator named ``--activity`` on the command
    line (``force_visible``)."""

    flags = {
        "entity-type": "natural_person",
        "irpf-income-categories": "capital_inmobiliario",
        "tax-id": "12345678Z",
        "activity": "explicitly supplied",
        "tax-residence-jurisdiction-scope": "common_regime",
    }
    canonical = _non_interactive_canonical(flags)
    explicit = frozenset(flags)
    answers, committed = _drive_scripted(canonical, force_visible=explicit)
    assert "activity" in committed
    assert answers.activity == "explicitly supplied"


def test_landlord_without_activity_flag_is_not_asked_for_activity() -> None:
    """A pure landlord (only capital_inmobiliario, no --activity flag)
    is never asked for an economic activity — the gate stays closed."""

    flags = {
        "entity-type": "natural_person",
        "irpf-income-categories": "capital_inmobiliario",
        "tax-id": "12345678Z",
        "tax-residence-jurisdiction-scope": "common_regime",
    }
    canonical = _non_interactive_canonical(flags)
    explicit = frozenset(flags)
    answers, committed = _drive_scripted(canonical, force_visible=explicit)
    assert "activity" not in committed
    assert answers.activity == ""


def test_direct_estimation_profile_is_not_asked_for_modulos_annual_facts() -> None:
    """The módulos annual facts are gated to estimación objetiva only."""

    flags = {
        "entity-type": "natural_person",
        "irpf-income-categories": "actividad_economica",
        "tax-id": "12345678Z",
        "activity": "direct activity",
        "irpf-estimation-regime": "directa_normal",
        "tax-residence-jurisdiction-scope": "common_regime",
    }
    canonical = _non_interactive_canonical(flags)
    explicit = frozenset(flags)
    answers, committed = _drive_scripted(canonical, force_visible=explicit)
    assert "objective-estimation-modulos-iae-epigraph" not in committed
    assert "objective-estimation-modulos-module-1-units" not in committed
    assert answers.objective_estimation_modulos_iae_epigraph == ""
    assert answers.objective_estimation_modulos_module_1_units == ""


def test_objetiva_profile_collects_modulos_annual_facts() -> None:
    """Objective-estimation profiles collect stable annual módulo facts once."""

    flags = {
        "entity-type": "natural_person",
        "irpf-income-categories": "actividad_economica",
        "tax-id": "12345678Z",
        "activity": "barber shop",
        "irpf-estimation-regime": "objetiva",
        "objective-estimation-modulos-iae-epigraph": "972.1",
        "objective-estimation-modulos-module-1-units": "2.50",
        "objective-estimation-modulos-module-2-units": "85",
        "objective-estimation-modulos-module-3-units": "12000.75",
        "tax-residence-jurisdiction-scope": "common_regime",
    }
    canonical = _non_interactive_canonical(flags)
    explicit = frozenset(flags)
    answers, committed = _drive_scripted(canonical, force_visible=explicit)

    assert "objective-estimation-modulos-iae-epigraph" in committed
    assert "objective-estimation-modulos-module-1-units" in committed
    assert answers.objective_estimation_modulos_iae_epigraph == "972.1"
    assert answers.objective_estimation_modulos_module_1_units == "2.50"
    assert answers.objective_estimation_modulos_module_2_units == "85"
    assert answers.objective_estimation_modulos_module_3_units == "12000.75"

    canonical_profile = serialise_answers(SETUP_FLOW, answers)
    assert canonical_profile["irpf.objective_estimation_modulos_iae_epigraph"] == "972.1"
    assert canonical_profile["irpf.objective_estimation_modulos_module_1_units"] == "2.50"
