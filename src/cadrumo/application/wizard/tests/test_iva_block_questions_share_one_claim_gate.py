"""The wizard may not claim the IVA block behind a gate that skips its facts.

Declaring any IVA fact obliges the whole block. A question whose answer
claims the block must therefore sit behind the same gate as the questions
the block requires -- otherwise the wizard completes, the profile claims a
block, and the domain resolver refuses it for a fact the run never asked.
Six enrolment confirms sat on the entity-shaped gate while the facts they
oblige sat on the claim gate.
"""

from __future__ import annotations

import pytest

from ....domain.deadlines.profiles import MODELO_IVA_BLOCK_CLAIMING_PATHS, MODELO_IVA_BLOCK_REQUIRED_PATHS
from ..catalogue import _IVA_BLOCK_CLAIMED, SETUP_FLOW
from ..models import WizardQuestion

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _questions() -> tuple[WizardQuestion, ...]:
    return tuple(question for section in SETUP_FLOW.sections for question in section.questions)


def test_every_block_claiming_question_sits_behind_the_claim_gate() -> None:
    """A question that claims the block, gated more loosely, is the divergence."""
    offenders = {
        question.id: question.visible_when
        for question in _questions()
        if question.profile_key in MODELO_IVA_BLOCK_CLAIMING_PATHS
        and question.profile_key != "iva.regime"
        and question.visible_when != _IVA_BLOCK_CLAIMED
    }

    assert offenders == {}, f"these questions claim the IVA block behind a different gate: {offenders}"


def test_the_facts_a_claimed_block_requires_are_asked_and_required() -> None:
    """Every path the resolver refuses without is a required question on that gate.

    ``tax_residence.jurisdiction_scope`` is excluded: it is required of every
    profile by the schema, not conditionally by the IVA block, so it is
    collected outside this section.
    """
    by_key = {question.profile_key: question for question in _questions()}

    for path in MODELO_IVA_BLOCK_REQUIRED_PATHS:
        if path == "tax_residence.jurisdiction_scope":
            continue
        question = by_key.get(path)
        assert question is not None, f"the block requires {path} and no question collects it"
        assert question.required is True, f"{path} is required by the resolver but optional in the wizard"
        assert question.visible_when == _IVA_BLOCK_CLAIMED, f"{path} is not gated on the claim"
