"""Modelo 193 overview applicability for capital-income withholding payers."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.applicability import ApplicabilityVerdict, derive_modelo_applicability
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.contribuyente.entity_type import EntityType, LegalEntityForm

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_modelo_193_tracks_modelo_123_capital_income_payer_fact() -> None:
    profile = TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        pays_capital_income_with_retencion=True,
    )

    quarterly = derive_modelo_applicability(profile, "123")
    annual = derive_modelo_applicability(profile, "193")

    assert quarterly.verdict is ApplicabilityVerdict.APPLICABLE
    assert annual.verdict is ApplicabilityVerdict.APPLICABLE
    assert annual.legal_refs == (
        "ley-35-2006:art-25",
        "ley-35-2006:art-99",
        "orden-eha-3377-2011:art-1",
        "rd-439-2007:art-108",
        "rd-439-2007:art-90",
        "ley-35-2006:art-101",
        "ley-58-2003:art-93",
    )


def test_modelo_193_is_incomplete_when_capital_income_payer_fact_is_undeclared() -> None:
    profile = TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
    )

    result = derive_modelo_applicability(profile, "193")

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
