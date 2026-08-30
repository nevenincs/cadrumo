"""Strict profile authority for Modelo 303 tax-territory production."""

import pytest

from ...user_profile.errors import UserProfileNotFoundError
from ...user_profile.loader import load_user_profile_schema
from ..errors import ProfileError
from ..models import M303TaxTerritory
from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _profile(scope: str):
    return taxpayer_profile_from_mapping(
        {
            "identity.tax_id": "12345678Z",
            "activities.description": "consultoria",
            "tax_residence.jurisdiction_scope": scope,
            "iva.regime": "GENERAL",
            "iva.redeme_enrolled": "false",
            "iva.m303_regime_composition": "general",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
        tax_id_default="12345678Z",
    )


@pytest.mark.parametrize(
    ("scope", "expected"),
    (
        ("common_regime", M303TaxTerritory.COMMON_REGIME),
        ("foral_unsupported", M303TaxTerritory.FORAL),
    ),
)
def test_profile_hydration_preserves_explicit_tax_territory(
    scope: str,
    expected: M303TaxTerritory,
) -> None:
    iva = _profile(scope).iva
    assert iva is not None
    assert iva.tax_territory is expected


def test_wholly_absent_iva_block_stays_none() -> None:
    profile = taxpayer_profile_from_mapping({}, tax_id_default="12345678Z")
    assert profile.iva is None


def test_blank_wizard_iva_answers_do_not_claim_an_iva_block() -> None:
    profile = taxpayer_profile_from_mapping(
        {
            "iva.regime": "",
            "iva.roi_enrolled": "",
            "iva.redeme_enrolled": "",
            "iva.m303_regime_composition": "",
            "iva.cash_accounting_regime_enrolled": "",
            "iva.voluntary_sii_enrolled": "",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "",
        },
        tax_id_default="12345678Z",
    )
    assert profile.iva is None


def test_tax_territory_alone_does_not_manufacture_an_iva_block() -> None:
    profile = taxpayer_profile_from_mapping(
        {"tax_residence.jurisdiction_scope": "common_regime"},
        tax_id_default="12345678Z",
    )
    assert profile.iva is None


def test_any_claimed_iva_fact_refuses_a_partial_block() -> None:
    with pytest.raises(ProfileError, match="m303_regime_composition"):
        taxpayer_profile_from_mapping(
            {"iva.redeme_enrolled": "true"},
            tax_id_default="12345678Z",
        )


@pytest.mark.parametrize("scope", ("", "unknown"))
def test_profile_hydration_refuses_missing_or_unreadable_tax_territory(scope: str) -> None:
    with pytest.raises(ProfileError, match="jurisdiction_scope"):
        _profile(scope)


def test_profile_schema_requires_territory_and_removes_authorable_ratio() -> None:
    schema = load_user_profile_schema()
    territory = schema.field("tax_residence.jurisdiction_scope")

    assert territory.required is True
    assert all(
        field.key != "state_attribution_ratio"
        for section in schema.sections
        if section.key == "tax_residence"
        for field in section.fields
    )
    with pytest.raises(UserProfileNotFoundError, match="state_attribution_ratio"):
        schema.field("tax_residence.state_attribution_ratio")
