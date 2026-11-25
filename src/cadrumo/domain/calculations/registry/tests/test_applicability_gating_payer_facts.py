"""The rule's gating payer facts cover what only an exclusion reads.

A payer fact an exclusion reads decides ``NOT_APPLICABLE`` or keeps the modelo
``INCOMPLETE``, so the operator's answer settles the verdict exactly as the
required fact's answer does. Callers that report unanswered gating facts read
:attr:`ModeloApplicabilityRule.gating_payer_facts` for that reason, and this
pins the accessor's contract: both sources, authored order, no duplicate when
one fact is read twice.
"""

from __future__ import annotations

import pytest

from cadrumo.core.modelo import Modelo
from cadrumo.domain.contribuyente.entity_type import EntityType

from ..applicability import iter_modelo_applicability_rules
from ..applicability_models import (
    ApplicabilityVerdict,
    ModeloApplicabilityExclusion,
    ModeloApplicabilityRule,
)
from ..applicability_payer_facts import PayerFactProjection, payer_fact_profile_keys
from ..authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REQUIRED_FACT = PayerFactProjection(
    "exceeds_third_party_threshold",
    profile_keys=("third_party_transactions_above_347_threshold",),
    label="supera el umbral de operaciones con terceros",
    legal_refs=("rd-1065-2007:art-31",),
    three_state=True,
)
_EXCLUDING_FACT = PayerFactProjection(
    "iva_books_kept_through_sii",
    profile_keys=("iva.sii_enrolled", "iva.voluntary_sii_enrolled"),
    label="lleva los libros registro del IVA a través del SII",
    legal_refs=("rd-1065-2007:art-32",),
    three_state=True,
)


def _exclusion(fact: PayerFactProjection, *, identifier: str) -> ModeloApplicabilityExclusion:
    return ModeloApplicabilityExclusion(
        id=identifier,
        outcome=ApplicabilityVerdict.NOT_APPLICABLE,
        payer_fact=fact,
        reason="excluded",
        legal_refs=("rd-1065-2007:art-32",),
    )


def _rule(
    *exclusions: ModeloApplicabilityExclusion,
    required: PayerFactProjection | None = None,
) -> ModeloApplicabilityRule:
    return ModeloApplicabilityRule(
        modelo="347",
        applicable_entity_types=frozenset({EntityType.from_registry("legal_entity")}),
        required_payer_fact=required,
        applicable_reason="applies",
        not_applicable_reason="does not apply",
        exclusions=exclusions,
        legal_refs=("rd-1065-2007:art-31",),
    )


def test_a_rule_with_no_payer_fact_gates_on_none() -> None:
    assert _rule().gating_payer_facts == ()


def test_an_exclusion_only_fact_is_a_gating_fact() -> None:
    rule = _rule(_exclusion(_EXCLUDING_FACT, identifier="sii"))

    assert rule.required_payer_fact is None
    assert rule.gating_payer_facts == (_EXCLUDING_FACT,)


def test_the_required_fact_comes_first_and_is_not_repeated_by_an_exclusion() -> None:
    """An exclusion qualifying the required fact must not name it twice."""
    rule = _rule(
        _exclusion(_REQUIRED_FACT, identifier="qualifies-required"),
        _exclusion(_EXCLUDING_FACT, identifier="sii"),
        required=_REQUIRED_FACT,
    )

    assert rule.gating_payer_facts == (_REQUIRED_FACT, _EXCLUDING_FACT)


def test_the_production_pago_fraccionado_rule_gates_on_its_art109_exclusion(
    operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 130's Art. 109 coverage fact is authored only as an exclusion."""
    rule = next(
        candidate
        for candidate in iter_modelo_applicability_rules(operation=operation)
        if candidate.modelo == Modelo("130")
    )

    keys = {key for fact in rule.gating_payer_facts for key in payer_fact_profile_keys(fact)}

    assert rule.required_payer_fact is None
    assert "art109_activity_income_withholding_ge_70pct" in keys
