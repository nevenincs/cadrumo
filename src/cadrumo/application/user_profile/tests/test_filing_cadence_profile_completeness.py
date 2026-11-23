"""A profile that owes a periodic self-assessment is not complete until its filing cadence is stated.

The large-company condition (LIVA art. 121 volume, RIVA art. 71.3) decides
whether Modelos 303, 111, 115, 123 and 216 are filed monthly or quarterly.
Setup reported a general-regime autónomo ready while the calendar could date
none of its 303 quarters, because nothing demanded the answer.
"""

import pytest

from ..completeness import conditional_profile_missing_required

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LARGE_COMPANY = "censo.large_company"
_IVA_BLOCK = {
    "taxpayer_type.entity_type": "natural_person",
    "taxpayer_type.irpf_income_categories": "actividad_economica",
    "identity.tax_id": "12345678Z",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}
_PAYER_FACTS = (
    "withholding.has_employees",
    "withholding.pays_professionals_with_retencion",
    "withholding.pays_rent_with_retencion",
    "withholding.pays_capital_income_with_retencion",
    "withholding.pays_non_resident_income_with_retencion",
)


def test_a_claimed_iva_block_owes_the_cadence() -> None:
    assert conditional_profile_missing_required(_IVA_BLOCK) == (_LARGE_COMPANY,)


@pytest.mark.parametrize("answer", ["false", "true"])
def test_either_stated_answer_settles_it(answer: str) -> None:
    assert conditional_profile_missing_required({**_IVA_BLOCK, _LARGE_COMPANY: answer}) == ()


@pytest.mark.parametrize("payer_fact", _PAYER_FACTS)
def test_a_stated_withholding_payer_owes_the_cadence(payer_fact: str) -> None:
    values = {"identity.tax_id": "12345678Z", payer_fact: "true"}

    assert _LARGE_COMPANY in conditional_profile_missing_required(values)


@pytest.mark.parametrize("payer_fact", _PAYER_FACTS)
def test_a_declined_withholding_payer_does_not(payer_fact: str) -> None:
    values = {"identity.tax_id": "12345678Z", payer_fact: "false"}

    assert _LARGE_COMPANY not in conditional_profile_missing_required(values)


def test_a_profile_owing_no_periodic_self_assessment_is_never_asked() -> None:
    assert _LARGE_COMPANY not in conditional_profile_missing_required({"identity.tax_id": "12345678Z"})
