"""Modelos 322, 353 and 369 read their IVA enrolment fact in three states.

The projection under test is the production one: a real
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord` goes through
:func:`projection_for_taxpayer` and the registry's own applicability
classifier. Each of these three modelos exists only for an enrolment the
taxpayer opted into: the régimen especial del grupo de entidades for the
member (Modelo 322) and the dominant entity (Modelo 353), under LIVA arts.
163 quinquies and following with RIVA art. 71, and the one-stop-shop for
Modelo 369 under LIVA art. 163 octiesdecies and following.

While the projection collapsed those enrolments with ``is True`` the facts
were two-state: a taxpayer who had stated they are not enrolled got the same
INCOMPLETE verdict as one who had never been asked, so an enrolment answered
no could never rule its modelo out.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.applicability import derive_modelo_applicability
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.applicability_payer_facts import (
    PayerFactDeclaration,
    payer_fact_declaration,
    resolve_payer_fact,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..projections import projection_for_taxpayer
from .payer_fact_record_support import IVA_ENROLMENT_GATED_MODELOS, iva_enrolment_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELOS = tuple(sorted(IVA_ENROLMENT_GATED_MODELOS))


def _verdicts(operation: PinnedAuthorityOperation, *, answer: bool | None) -> dict[str, ApplicabilityVerdict]:
    record = iva_enrolment_record(operation, answer=answer)
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    return {modelo: derive_modelo_applicability(profile, modelo, operation=operation).verdict for modelo in _MODELOS}


def test_an_unanswered_enrolment_leaves_every_gated_modelo_incomplete(
    operation: PinnedAuthorityOperation,
) -> None:
    assert _verdicts(operation, answer=None) == dict.fromkeys(_MODELOS, ApplicabilityVerdict.INCOMPLETE)


def test_a_stated_no_rules_every_gated_modelo_out(operation: PinnedAuthorityOperation) -> None:
    """The defect this closes: a stated no used to read as unanswered and kept all three incomplete."""
    assert _verdicts(operation, answer=False) == dict.fromkeys(_MODELOS, ApplicabilityVerdict.NOT_APPLICABLE)


def test_a_stated_yes_makes_every_gated_modelo_applicable(operation: PinnedAuthorityOperation) -> None:
    assert _verdicts(operation, answer=True) == dict.fromkeys(_MODELOS, ApplicabilityVerdict.APPLICABLE)


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (None, PayerFactDeclaration.UNDECLARED),
        (False, PayerFactDeclaration.DECLARED_NO),
        (True, PayerFactDeclaration.DECLARED_YES),
    ],
)
def test_each_coded_enrolment_fact_answers_all_three_declaration_states(
    operation: PinnedAuthorityOperation,
    answer: bool | None,
    expected: PayerFactDeclaration,
) -> None:
    """The verdicts above come from the fact's declaration, so pin that reading directly."""
    record = iva_enrolment_record(operation, answer=answer)
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())

    declarations = {
        modelo: payer_fact_declaration(profile, resolve_payer_fact(_required_fact(operation, modelo)))
        for modelo in _MODELOS
    }
    assert declarations == dict.fromkeys(_MODELOS, expected)


def test_a_profile_with_no_iva_block_leaves_the_enrolment_unanswered(
    operation: PinnedAuthorityOperation,
) -> None:
    """An absent optional section is the same unanswered state as an unstated enrolment."""
    record = iva_enrolment_record(operation, answer=None)
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    assert profile.iva is not None
    assert profile.iva.group_member_enrolled is None
    assert profile.iva.group_dominant_entity_enrolled is None
    assert profile.iva.oss_enrolled is None

    without_block = profile.model_copy(update={"iva": None})

    assert {
        payer_fact_declaration(without_block, resolve_payer_fact(_required_fact(operation, modelo)))
        for modelo in _MODELOS
    } == {PayerFactDeclaration.UNDECLARED}


def _required_fact(operation: PinnedAuthorityOperation, modelo: str) -> str:
    """Return the payer fact the modelo's own rule requires, from the registry."""
    from ....domain.calculations.registry.applicability import iter_modelo_applicability_rules

    for rule in iter_modelo_applicability_rules(operation=operation):
        if rule.modelo == modelo and rule.required_payer_fact is not None:
            return str(rule.required_payer_fact)
    raise AssertionError(f"Modelo {modelo} declares no required payer fact")
