"""The descendant group is live on the real setup definition.

These pin the splice: the count page and repeating group are present on
the shared ``_setup_flow_definition`` output, a scripted walk over that
real definition collects descendants and submits, the projected facts
land, and the adoption cross-field validator is genuinely wired into the
live definition's submit gate (a bad adoption date refuses). Expected
fact values are the specification, never a copy of the projection output.
"""

from __future__ import annotations

import pytest

from ....core.flows import FlowMode
from ...flows import FlowSubmitError, answer, run_scripted_flow, start_flow, visible_sequence
from .. import descendant_facts_from_answers
from .._catalogue import SETUP_FLOW
from .._commands import _project_scripted_answers, _setup_flow_definition
from .._descendant_group import DESCENDANT_ADOPTION_VALIDATOR_ID
from .test_scripted_parity import _INDIVIDUAL_CANONICAL

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DESCENDANTS_CANONICAL: dict[str, str] = {
    **_INDIVIDUAL_CANONICAL,
    "descendientes-count": "2",
    "descendientes#0.birth-date": "2023-05-10",
    "descendientes#0.convivencia": "true",
    "descendientes#0.gastos-guarderia": "900",
    "descendientes#1.birth-date": "2015-03-01",
    "descendientes#1.adoption-date": "2016-06-01",
    "descendientes#1.convivencia": "true",
    "descendientes#1.nif": "00000000T",
}


def test_descendant_pages_are_live_on_the_setup_definition() -> None:
    definition = _setup_flow_definition(SETUP_FLOW)
    familia = next(section for section in definition.sections if section.id == "familia")
    item_ids = {item.id for item in familia.items}

    assert "descendientes-count" in item_ids
    assert "descendientes" in item_ids
    assert DESCENDANT_ADOPTION_VALIDATOR_ID in definition.flow_validator_ids


def test_natural_person_walk_reveals_the_instance_pages_when_count_positive() -> None:
    definition = _setup_flow_definition(SETUP_FLOW)
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "entity-type", "natural_person")
    state = answer(definition, state, "descendientes-count", "2")

    keys = {entry.key for entry in visible_sequence(definition, state)}
    assert "descendientes#0.birth-date" in keys
    assert "descendientes#1.birth-date" in keys


def test_scripted_walk_over_the_live_definition_collects_descendants_and_submits() -> None:
    definition = _setup_flow_definition(SETUP_FLOW)
    tokens, _intended = _project_scripted_answers(definition, _DESCENDANTS_CANONICAL, mode=FlowMode.CREATE)

    state, projection = run_scripted_flow(definition, tokens, mode=FlowMode.CREATE)

    # The walk demanded the instance pages …
    assert "descendientes#0.birth-date" in state.answers
    assert "descendientes#1.nif" in state.answers
    # … the projected facts land in the documented shape …
    facts = dict(descendant_facts_from_answers(state.answers))
    assert facts["renta_family.descendiente.0.birth_date"] == "2023-05-10"
    assert facts["renta_family.descendiente.0.gastos_guarderia"] == "900"
    assert facts["renta_family.descendiente.1.adoption_date"] == "2016-06-01"
    assert facts["renta_family.descendiente.1.nif"] == "00000000T"
    assert facts["renta_family.descendientes_count"] == "2"
    assert facts["renta_family.gastos_guarderia_reales_2024"] == "900"
    # … and submission holds (run_scripted_flow refuses a non-submittable walk).
    assert projection.submit_eligible


def test_scripted_walk_with_a_bad_adoption_date_refuses_at_submit() -> None:
    # A birth-before-adoption pair proves the adoption cross-field validator
    # is LIVE on the real _setup_flow_definition's flow-scope submit gate.
    definition = _setup_flow_definition(SETUP_FLOW)
    canonical = {**_DESCENDANTS_CANONICAL, "descendientes#1.adoption-date": "2000-01-01"}
    tokens, _intended = _project_scripted_answers(definition, canonical, mode=FlowMode.CREATE)

    with pytest.raises(FlowSubmitError):
        run_scripted_flow(definition, tokens, mode=FlowMode.CREATE)
