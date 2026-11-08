"""An IRPF estimation regime or activity kind proves economic-activity income.

Estimación directa (normal or simplificada) and estimación objetiva are the
methods for determining rendimientos de actividades económicas (LIRPF arts. 28
and 31), and the profesional/sectorial axis classifies an economic activity
(RIRPF art. 95). A natural person who declares either has economic-activity
income, so leaving the income categories blank must not make the taxpayer model
undeclared: that blanked the whole calendar for a profile that already said
everything the calendar needs.

An explicit category declaration is the operator's statement and is kept as
declared; only an undeclared one is completed.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ...calculations.registry.applicability import taxpayer_model_is_declared
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...calculations.registry.irpf_income_categories import irpf_income_category_actividad_economica_token
from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _authority_scope(operation: PinnedAuthorityOperation) -> Iterator[None]:
    with validating_governed_facts(operation):
        yield


_IVA_DECLARED = {
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.redeme_enrolled": "false",
    "iva.sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    "tax_residence.jurisdiction_scope": "common_regime",
    "tax_residence.autonomous_community": "madrid",
}
_NATURAL_PERSON = {"taxpayer_type.entity_type": "natural_person", **_IVA_DECLARED}


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("irpf.estimation_regime", "directa_simplificada"),
        ("irpf.estimation_regime", "directa_normal"),
        ("irpf.estimation_regime", "objetiva"),
        ("irpf.activity_kind", "profesional"),
        ("irpf.activity_kind", "sectorial"),
    ],
)
def test_an_activity_axis_without_categories_declares_economic_activity_income(path: str, value: str) -> None:
    profile = taxpayer_profile_from_mapping({**_NATURAL_PERSON, path: value}, tax_id_default="12345678Z")

    assert profile.irpf_income_categories == frozenset({irpf_income_category_actividad_economica_token()})
    assert taxpayer_model_is_declared(profile)


def test_explicit_categories_are_kept_as_declared() -> None:
    profile = taxpayer_profile_from_mapping(
        {
            **_NATURAL_PERSON,
            "taxpayer_type.irpf_income_categories": "trabajo",
            "irpf.estimation_regime": "directa_simplificada",
        },
        tax_id_default="12345678Z",
    )

    assert {str(category) for category in profile.irpf_income_categories} == {"trabajo"}


def test_without_an_activity_axis_the_categories_stay_undeclared() -> None:
    profile = taxpayer_profile_from_mapping(_NATURAL_PERSON, tax_id_default="12345678Z")

    assert profile.irpf_income_categories == frozenset()
    assert not taxpayer_model_is_declared(profile)


def test_a_legal_entity_gets_no_irpf_category() -> None:
    profile = taxpayer_profile_from_mapping(
        {"taxpayer_type.entity_type": "legal_entity", **_IVA_DECLARED, "irpf.activity_kind": "profesional"},
        tax_id_default="B12345674",
    )

    assert profile.irpf_income_categories == frozenset()
