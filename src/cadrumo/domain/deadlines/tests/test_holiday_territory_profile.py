"""Holiday territory resolution in the deadline profile projection."""

import pytest

from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def _profile(**values: str):
    return taxpayer_profile_from_mapping(
        {"identity.tax_id": "12345678Z", "activities.description": "consultoria", **values},
        tax_id_default="12345678Z",
    )


def _resident(ccaa: str, **extra: str):
    return _profile(
        **{
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.fiscal_residency": "resident_irpf",
            "tax_residence.ccaa": ccaa,
            **extra,
        },
    )


def test_declared_common_regime_residence_sets_the_holiday_territory() -> None:
    assert str(_resident("cataluna").holiday_territory) == "ES-CT"


def test_residences_named_differently_by_the_calendar_still_resolve() -> None:
    assert str(_resident("baleares").holiday_territory) == "ES-IB"
    assert str(_resident("comunidad_valenciana").holiday_territory) == "ES-VC"


def test_missing_residence_is_not_replaced_by_the_catalogue_default() -> None:
    profile = _profile(
        **{"taxpayer_type.entity_type": "natural_person", "taxpayer_type.fiscal_residency": "resident_irpf"},
    )

    assert profile.holiday_territory is None


def test_non_resident_keeps_no_territory_even_with_a_declared_ccaa() -> None:
    profile = _profile(
        **{
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.fiscal_residency": "non_resident_irnr",
            "taxpayer_type.country_of_fiscal_residence": "FR",
            "tax_residence.ccaa": "madrid",
        },
    )

    assert profile.holiday_territory is None


def test_undeclared_fiscal_residency_keeps_no_territory() -> None:
    profile = _profile(**{"taxpayer_type.entity_type": "natural_person", "tax_residence.ccaa": "madrid"})

    assert profile.holiday_territory is None


def test_legal_entity_keeps_no_territory() -> None:
    profile = _profile(
        **{
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.fiscal_residency": "resident_irpf",
            "tax_residence.ccaa": "madrid",
        },
    )

    assert profile.holiday_territory is None


def test_foral_jurisdiction_scope_keeps_no_territory() -> None:
    assert _resident("madrid", **{"tax_residence.jurisdiction_scope": "foral_unsupported"}).holiday_territory is None


def test_common_regime_scope_keeps_the_declared_territory() -> None:
    profile = _resident("madrid", **{"tax_residence.jurisdiction_scope": "common_regime"})

    assert str(profile.holiday_territory) == "ES-MD"
