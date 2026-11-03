"""The setup flow asks a single parent whether they live with the child's other parent.

Art. 84.2.4º LIRPF denies the joint-taxation reduction of the single-parent
family unit while the taxpayer lives with the father or mother of a child in the
unit. The question is asked only of that modality, carries no default, and an
unanswered question leaves the profile fact absent rather than false.
"""

from __future__ import annotations

import pytest

from cadrumo.application.wizard.models import (
    WizardCondition,
    WizardFlow,
    WizardQuestion,
    WizardVisibility,
    WizardWidget,
)
from cadrumo.application.wizard.tests.registry_setup_flow_support import registry_setup_flow as registry_setup_flow
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.deadlines.setup_answer_projection import project_setup_answers
from cadrumo.domain.user_profile.setup_answers import SetupAnswers

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.flows import FlowMode
from ....core.i18n.render import tr
from ...flows.engine import start_flow, visible_sequence
from ..commands import setup_flow_definition
from ..errors import WizardValidationError
from ..patch_edit import cleared_profile_paths
from ..persistence import profile_values_from_patch, serialise_answers
from ..widgets import validate_widget_answer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_QUESTION_ID = "family-convive-con-otro-progenitor"
_PATH = "renta_family.convive_con_otro_progenitor"
_SITUATION_ID = "situacion-familiar"
#: The Art. 82.1.2ª single-parent modalities, as the family-situation vocabulary of the facts registry declares them.
_SINGLE_PARENT = frozenset({"soltero", "separado_divorciado", "pareja_hecho_registrada", "pareja_hecho_no_registrada"})


def _question(flow: WizardFlow, question_id: str) -> WizardQuestion:
    return next(q for section in flow.sections for q in section.questions if q.id == question_id)


def _asked(flow: WizardFlow, operation: PinnedAuthorityOperation, answers: dict[str, str]) -> bool:
    """Whether the live flow walk reaches the question under ``answers``."""
    definition = setup_flow_definition(flow, operation=operation)
    state = start_flow(definition, mode=FlowMode.CREATE).model_copy(update={"answers": answers})
    return _QUESTION_ID in {entry.key for entry in visible_sequence(definition, state)}


def test_the_question_is_a_confirm_with_no_default_stored_under_the_family_fact(
    registry_setup_flow: WizardFlow,
) -> None:
    question = _question(registry_setup_flow, _QUESTION_ID)
    assert question.profile_key == _PATH
    assert question.widget is WizardWidget.CONFIRM
    assert question.default is None
    assert not question.required
    assert question.answer_type is bool
    assert question.help is not None
    # It follows the other two answers of the unit it qualifies.
    ids = [q.id for section in registry_setup_flow.sections for q in section.questions]
    assert ids.index(_QUESTION_ID) > ids.index("family-minor-children-in-unit") > ids.index(_SITUATION_ID)


def test_the_question_is_gated_on_exactly_the_single_parent_situations(registry_setup_flow: WizardFlow) -> None:
    gate = _question(registry_setup_flow, _QUESTION_ID).visible_when
    assert isinstance(gate, WizardVisibility)
    assert all(isinstance(clause, WizardCondition) for clause in gate.any_of)
    assert {clause.question_id for clause in gate.any_of} == {_SITUATION_ID}
    assert {clause.equals for clause in gate.any_of} == _SINGLE_PARENT
    declared = {choice.value for choice in _question(registry_setup_flow, _SITUATION_ID).choices}
    # The married unit and every other declared situation never reach the question.
    assert "casado" in declared
    assert declared - _SINGLE_PARENT == {"casado"}


@pytest.mark.parametrize("situation", sorted(_SINGLE_PARENT))
def test_a_single_parent_is_asked(
    registry_setup_flow: WizardFlow, operation: PinnedAuthorityOperation, situation: str
) -> None:
    assert _asked(registry_setup_flow, operation, {_SITUATION_ID: situation})


def test_a_married_filer_and_a_filer_who_has_not_said_are_not_asked(
    registry_setup_flow: WizardFlow, operation: PinnedAuthorityOperation
) -> None:
    assert not _asked(registry_setup_flow, operation, {_SITUATION_ID: "casado"})
    assert not _asked(registry_setup_flow, operation, {})


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("part", ["prompt", "help"])
def test_the_question_is_worded_in_every_language(language: str, part: str) -> None:
    key = f"wizard.setup.family.{_QUESTION_ID}.{part}"
    text = tr(key, locale=language)
    assert text and text != key
    flag = tr(f"wizard.setup.flags.{_QUESTION_ID}.help", locale=language)
    assert flag and not flag.startswith("wizard.setup.")


def test_the_prompts_address_the_filer_informally_in_the_singular() -> None:
    assert tr("wizard.setup.family.family-convive-con-otro-progenitor.prompt", locale="es").startswith("¿Convives")
    assert tr("wizard.setup.family.family-convive-con-otro-progenitor.prompt", locale="ca").startswith("Convius")
    assert tr("wizard.setup.family.family-convive-con-otro-progenitor.prompt", locale="hu").startswith("Együtt élsz")


@pytest.mark.parametrize(("raw", "stored"), [("true", "true"), ("false", "false")])
def test_a_supplied_answer_becomes_the_fact(registry_setup_flow: WizardFlow, raw: str, stored: str) -> None:
    assert profile_values_from_patch(registry_setup_flow, {_QUESTION_ID: raw}) == {_PATH: stored}


def test_an_omitted_answer_is_not_a_patch_and_a_blank_one_clears_the_fact(registry_setup_flow: WizardFlow) -> None:
    assert profile_values_from_patch(registry_setup_flow, {_SITUATION_ID: "soltero"}) == {
        "renta_family.situacion_familiar": "soltero"
    }
    assert cleared_profile_paths(registry_setup_flow, {_SITUATION_ID: "soltero"}) == ()
    assert cleared_profile_paths(registry_setup_flow, {_QUESTION_ID: ""}) == (_PATH,)


def test_an_answer_that_is_neither_yes_nor_no_is_refused(registry_setup_flow: WizardFlow) -> None:
    with pytest.raises(WizardValidationError):
        validate_widget_answer(_question(registry_setup_flow, _QUESTION_ID), "maybe")


def test_unanswered_stays_unstated_and_is_never_false(registry_setup_flow: WizardFlow) -> None:
    answers = SetupAnswers.model_validate({"tax_id": "12345678Z"})
    assert answers.family_convive_con_otro_progenitor == ""
    # Blank, which no writer stores: never the "false" a default would have said.
    assert serialise_answers(registry_setup_flow, answers)[_PATH] == ""

    projected = project_setup_answers({"identity.tax_id": "12345678Z"})
    assert projected.family_convive_con_otro_progenitor == ""
    stated = project_setup_answers({"identity.tax_id": "12345678Z", _PATH: "false"})
    assert stated.family_convive_con_otro_progenitor is False
    stated = project_setup_answers({"identity.tax_id": "12345678Z", _PATH: "true"})
    assert stated.family_convive_con_otro_progenitor is True


@pytest.mark.parametrize(("given", "held"), [(True, True), (False, False), ("true", True), ("false", False), ("", "")])
def test_the_answers_model_holds_a_three_state_answer(given: object, held: object) -> None:
    answers = SetupAnswers.model_validate({"tax_id": "12345678Z", "family_convive_con_otro_progenitor": given})
    assert answers.family_convive_con_otro_progenitor == held
    assert type(answers.family_convive_con_otro_progenitor) is type(held)


def test_the_answers_model_refuses_an_answer_that_is_neither_yes_nor_no() -> None:
    with pytest.raises(ValueError, match="family_convive_con_otro_progenitor"):
        SetupAnswers.model_validate({"tax_id": "12345678Z", "family_convive_con_otro_progenitor": "maybe"})
