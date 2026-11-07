"""A payer question nobody answered must project as unanswered, not as a no.

The withholding and intracommunity payer facts gate Modelos 111, 115, 180,
190, 216, 296 and 349. They are three-state: a stored ``true`` is a yes, a
stored ``false`` is a declared no, and an absent path is unanswered. The
registry setup catalogue used to declare ``false`` as their projection
default, so a taxpayer who was never asked projected as a declared no and
those modelos were refused as not applicable.

The projection front door is asserted here, and the verdicts it produces
are asserted through the real applicability classifier, so the chain from a
stored value to a modelo verdict is covered end to end.
"""

from __future__ import annotations

import pytest

from ...calculations.registry.applicability import derive_modelo_applicability
from ...calculations.registry.applicability_models import ApplicabilityVerdict
from ..models import TaxpayerProfile
from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_PAYER_FACT_PATHS = (
    "withholding.has_employees",
    "withholding.pays_professionals_with_retencion",
    "withholding.pays_rent_with_retencion",
    "iva.does_intracomunitario",
)

_PAYER_FACT_FIELDS = (
    "has_employees",
    "pays_professionals_with_retencion",
    "pays_rent_with_retencion",
    "does_intracomunitario",
)

_AUTONOMO: dict[str, str] = {
    "identity.tax_id": "X0001500M",
    "tax_residence.jurisdiction_scope": "common_regime",
    "taxpayer_type.entity_type": "natural_person",
    "taxpayer_type.irpf_income_categories": "actividad_economica",
    "irpf.estimation_regime": "directa_simplificada",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def _profile(**answers: str) -> TaxpayerProfile:
    return taxpayer_profile_from_mapping({**_AUTONOMO, **answers}, tax_id_default="X0001500M")


def test_an_unanswered_payer_question_projects_as_unanswered() -> None:
    profile = _profile()

    for field in _PAYER_FACT_FIELDS:
        assert getattr(profile, field) is None, field


@pytest.mark.parametrize("answered", ("false", "true"))
def test_a_stated_payer_answer_projects_as_that_answer(answered: str) -> None:
    profile = _profile(**dict.fromkeys(_PAYER_FACT_PATHS, answered))

    for field in _PAYER_FACT_FIELDS:
        assert getattr(profile, field) is (answered == "true"), field


@pytest.mark.parametrize("modelo", ("111", "349"))
def test_an_unanswered_payer_question_leaves_its_modelo_incomplete(modelo: str) -> None:
    result = derive_modelo_applicability(_profile(), modelo)

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE


@pytest.mark.parametrize("modelo", ("111", "349"))
def test_a_stated_no_to_every_payer_question_makes_its_modelo_not_applicable(modelo: str) -> None:
    profile = _profile(**dict.fromkeys(_PAYER_FACT_PATHS, "false"))

    result = derive_modelo_applicability(profile, modelo)

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
