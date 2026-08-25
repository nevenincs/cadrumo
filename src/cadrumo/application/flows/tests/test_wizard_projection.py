"""The wizard-to-flow bridge over the real setup catalogue.

Every scenario projects the real one-shot wizard catalogue
(:data:`cadrumo.application.wizard.WIZARD_FLOWS`) into a substrate
:class:`FlowDefinition` through its defining modules, then asserts the mechanical mapping
holds one-to-one: id and section count, every question id becoming a page
with its ``profile_key`` as ``domain_key``, widget identity with the
TEXT-with-choices upgrade to SELECT, ``visible_when`` clause shapes, and
locale-key copy references carrying the original translation keys. The
bridged definition is then driven through the real engine's ``start_flow``
and ``visible_sequence`` to prove it is a live, drivable flow.

Assertions read structural identity (ids, enum members, clause fields) and
the preserved translation *keys*, never localized prose.
"""

from __future__ import annotations

import pytest

from ....core.flows import (
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
)

# The bridge reads the real wizard catalogue. The import is at module top so
# a genuine peer-WIP breakage would surface as a loud collection error rather
# than a silent skip; at HEAD it imports cleanly.
from ...wizard.catalogue import WIZARD_FLOWS
from ...wizard.models import WizardFlow, WizardQuestion, WizardVisibility
from ..definition import FlowCondition, FlowDefinition, FlowPage, FlowVisibility
from ..engine import start_flow, visible_sequence
from ..wizard_projection import flow_definition_from_wizard_flow

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CHECKPOINT: dict[FlowMode, CheckpointAvailability] = {
    FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
    FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
}


def _setup_flow() -> WizardFlow:
    return next(flow for flow in WIZARD_FLOWS if flow.id == "setup")


def _bridged() -> FlowDefinition:
    return flow_definition_from_wizard_flow(_setup_flow(), checkpoint=dict(_CHECKPOINT))


def _pages_by_id(definition: FlowDefinition) -> dict[str, FlowPage]:
    pages: dict[str, FlowPage] = {}
    for section in definition.sections:
        for item in section.items:
            # The setup flow declares no repeating groups; every item is a page.
            assert isinstance(item, FlowPage)
            pages[item.id] = item
    return pages


def _questions_by_id(flow: WizardFlow) -> dict[str, WizardQuestion]:
    questions: dict[str, WizardQuestion] = {}
    for section in flow.sections:
        for question in section.questions:
            questions[question.id] = question
    return questions


def test_bridge_preserves_id_and_section_count() -> None:
    flow = _setup_flow()
    definition = _bridged()

    assert definition.id == flow.id
    assert len(definition.sections) == len(flow.sections)
    assert definition.answers_model is flow.answers_model


def test_every_question_becomes_a_page_binding_its_profile_key() -> None:
    flow = _setup_flow()
    questions = _questions_by_id(flow)
    pages = _pages_by_id(_bridged())

    assert set(pages) == set(questions)
    for qid, question in questions.items():
        assert pages[qid].domain_key == question.profile_key


def test_widget_mapping_is_value_identical_except_text_with_choices_upgrades() -> None:
    flow = _setup_flow()
    questions = _questions_by_id(flow)
    pages = _pages_by_id(_bridged())

    for qid, question in questions.items():
        page_widget = pages[qid].widget
        if question.widget.value == FlowWidgetKind.TEXT.value and question.choices:
            assert page_widget is FlowWidgetKind.SELECT, qid
            # The upgrade narrows free text to set membership; the value
            # set must carry over exactly, or an operator could no longer
            # answer a value the wizard accepted. A count-only check would
            # miss a value-set drift, so assert the sets themselves.
            assert {choice.value for choice in pages[qid].choices} == {choice.value for choice in question.choices}, qid
        else:
            assert page_widget.value == question.widget.value, qid


def test_taxation_type_text_with_choices_upgrades_to_select() -> None:
    pages = _pages_by_id(_bridged())
    questions = _questions_by_id(_setup_flow())

    # taxation-type is authored as a TEXT question carrying a closed choice
    # set; the bridge renders it as a selectable list.
    assert questions["taxation-type"].widget.value == FlowWidgetKind.TEXT.value
    assert questions["taxation-type"].choices
    assert pages["taxation-type"].widget is FlowWidgetKind.SELECT
    # Value-set equality (not a mere count) so a future value-set drift on
    # this upgraded question is caught rather than silently accepted.
    assert {choice.value for choice in pages["taxation-type"].choices} == {
        choice.value for choice in questions["taxation-type"].choices
    }


def test_single_condition_visibility_carries_over_one_to_one() -> None:
    pages = _pages_by_id(_bridged())
    # legal-entity-form is gated on a single entity-type == 'legal_entity' clause.
    gate = pages["legal-entity-form"].visible_when

    assert isinstance(gate, FlowCondition)
    assert gate.page_id == "entity-type"
    assert gate.equals == "legal_entity"
    assert gate.contains is None


def test_disjunction_visibility_carries_every_clause() -> None:
    flow = _setup_flow()
    questions = _questions_by_id(flow)
    pages = _pages_by_id(_bridged())

    # 'activity' is gated on an any_of disjunction of two clauses.
    source = questions["activity"].visible_when
    bridged = pages["activity"].visible_when

    assert isinstance(source, WizardVisibility)
    assert isinstance(bridged, FlowVisibility)
    assert len(bridged.any_of) == len(source.any_of)
    for source_clause, bridged_clause in zip(source.any_of, bridged.any_of, strict=True):
        assert bridged_clause.page_id == source_clause.question_id
        assert bridged_clause.equals == source_clause.equals
        assert bridged_clause.contains == source_clause.contains


def test_prompts_and_helps_become_locale_key_refs_carrying_original_keys() -> None:
    flow = _setup_flow()
    questions = _questions_by_id(flow)
    pages = _pages_by_id(_bridged())

    for qid, question in questions.items():
        prompt_ref = pages[qid].prompt
        assert prompt_ref.kind is CopyRefKind.LOCALE_KEY, qid
        assert prompt_ref.ref == str(question.prompt), qid

        help_ref = pages[qid].help
        if question.help is None:
            assert help_ref is None, qid
        else:
            assert help_ref is not None, qid
            assert help_ref.kind is CopyRefKind.LOCALE_KEY, qid
            assert help_ref.ref == str(question.help), qid


def test_bridged_definition_drives_the_real_engine() -> None:
    definition = _bridged()
    state = start_flow(definition, mode=FlowMode.CREATE)

    sequence = visible_sequence(definition, state)
    assert sequence  # a non-empty visible page sequence
    # The cursor lands on the first visible page's key.
    assert state.cursor == sequence[0].key
    # entity-type is unconditionally visible and drives the first branch.
    assert "entity-type" in {entry.key for entry in sequence}
