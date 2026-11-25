"""The wizard may not claim the IVA block behind a gate that skips its facts.

Declaring any IVA fact obliges the whole block. A question whose answer
claims the block must therefore sit behind the same gate as the questions
the block requires -- otherwise the wizard completes, the profile claims a
block, and the domain resolver refuses it for a fact the run never asked.
Six enrolment confirms sat on the entity-shaped gate while the facts they
oblige sat on the claim gate.

The Modelo 303 composition is the one narrower gate: it is asked only under a
regime that leaves it open, because the general regime settles it and a pure
recargo retailer files no Modelo 303 for those activities. Its gate is the
resolver's own answer, so it still asks exactly what completeness demands.
"""

from __future__ import annotations

import pytest

from cadrumo.application.wizard.models import WizardFlow
from cadrumo.application.wizard.tests.registry_setup_flow_support import registry_setup_flow as registry_setup_flow
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.deadlines.profiles import (
    MODELO_IVA_BLOCK_CLAIMING_PATHS,
    MODELO_IVA_BLOCK_REQUIRED_PATHS,
    iva_regime_owes_m303_regime_composition,
    modelo_iva_profile_required_paths,
)
from ..models import WizardCondition, WizardQuestion, WizardVisibility

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _questions(*, registry_setup_flow: WizardFlow) -> tuple[WizardQuestion, ...]:
    return tuple(question for section in registry_setup_flow.sections for question in section.questions)


def test_every_block_claiming_question_sits_behind_the_claim_gate(*, registry_setup_flow: WizardFlow) -> None:
    """A question that claims the block, gated more loosely, is the divergence."""
    offenders = {
        question.id: question.visible_when
        for question in _questions(registry_setup_flow=registry_setup_flow)
        if question.profile_key in MODELO_IVA_BLOCK_CLAIMING_PATHS
        and question.profile_key != "iva.regime"
        and question.visible_when != _expected_gate(registry_setup_flow, question.profile_key)
    }

    assert offenders == {}, f"these questions claim the IVA block behind a different gate: {offenders}"


def test_the_facts_a_claimed_block_requires_are_asked_and_required(*, registry_setup_flow: WizardFlow) -> None:
    """Every path the resolver refuses without is a required question on that gate.

    ``tax_residence.jurisdiction_scope`` is excluded: it is required of every
    profile by the schema, not conditionally by the IVA block, so it is
    collected outside this section.
    """
    by_key = {question.profile_key: question for question in _questions(registry_setup_flow=registry_setup_flow)}

    for path in MODELO_IVA_BLOCK_REQUIRED_PATHS:
        if path == "tax_residence.jurisdiction_scope":
            continue
        question = by_key.get(path)
        assert question is not None, f"the block requires {path} and no question collects it"
        assert question.required is True, f"{path} is required by the resolver but optional in the wizard"
        assert question.visible_when == _expected_gate(registry_setup_flow, path), f"{path} is not gated on the claim"


def test_the_composition_is_asked_under_exactly_the_regimes_whose_completeness_owes_it(
    *, registry_setup_flow: WizardFlow
) -> None:
    """DISCRIMINATING: the general regime hides it, the simplified regime asks it, and both agree with completeness."""
    gate = _expected_gate(registry_setup_flow, _COMPOSITION)
    asked = {condition.equals for condition in gate.any_of}

    assert "GENERAL" not in asked
    assert "SIMPLIFICADO" in asked
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        for choice in _regime_choices(registry_setup_flow):
            owed = _COMPOSITION in modelo_iva_profile_required_paths({"iva.regime": choice})
            assert (choice in asked) is owed, choice


_COMPOSITION = "iva.m303_regime_composition"


def _regime_choices(flow: WizardFlow) -> tuple[str, ...]:
    regime = next(
        question for section in flow.sections for question in section.questions if question.id == "iva-regime"
    )
    assert regime.choices, "the setup descriptor must offer IVA regimes"
    return tuple(choice.value for choice in regime.choices)


def _expected_gate(flow: WizardFlow, path: str | None) -> WizardVisibility:
    """Claim the block for every declared IVA-regime choice; the composition only where a regime leaves it open."""
    choices = _regime_choices(flow)
    if path == _COMPOSITION:
        with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
            choices = tuple(choice for choice in choices if iva_regime_owes_m303_regime_composition(choice))
    return WizardVisibility(
        any_of=tuple(WizardCondition(question_id="iva-regime", equals=choice) for choice in choices)
    )
