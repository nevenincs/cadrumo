"""Modelo 322/353 IVA group overview applicability."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.applicability import ApplicabilityVerdict, derive_modelo_applicability
from ....domain.deadlines import (
    EntityType,
    IVARegime,
    LegalEntityForm,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _legal_entity_with_iva_group_role(
    *,
    group_member: bool = False,
    group_dominant: bool = False,
) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            redeme_enrolled=False,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            group_member_enrolled=group_member,
            group_dominant_entity_enrolled=group_dominant,
        ),
    )


def test_modelo_322_applies_to_iva_group_member_role() -> None:
    result = derive_modelo_applicability(
        _legal_entity_with_iva_group_role(group_member=True),
        "322",
    )

    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.legal_refs == (
        "orden-eha-3434-2007:art-1",
        "orden-eha-3434-2007:art-8",
        "rd-1624-1992:art-71",
    )


def test_modelo_353_applies_to_iva_group_dominant_entity_role() -> None:
    result = derive_modelo_applicability(
        _legal_entity_with_iva_group_role(group_dominant=True),
        "353",
    )

    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.legal_refs == (
        "orden-eha-3434-2007:art-2",
        "orden-eha-3434-2007:art-8",
        "rd-1624-1992:art-71",
    )


def test_iva_group_member_role_does_not_imply_dominant_entity_role() -> None:
    profile = _legal_entity_with_iva_group_role(group_member=True)

    assert derive_modelo_applicability(profile, "322").verdict is ApplicabilityVerdict.APPLICABLE
    assert derive_modelo_applicability(profile, "353").verdict is ApplicabilityVerdict.INCOMPLETE


def test_iva_group_roles_are_incomplete_when_no_role_fact_is_declared() -> None:
    profile = _legal_entity_with_iva_group_role()

    assert derive_modelo_applicability(profile, "322").verdict is ApplicabilityVerdict.INCOMPLETE
    assert derive_modelo_applicability(profile, "353").verdict is ApplicabilityVerdict.INCOMPLETE
