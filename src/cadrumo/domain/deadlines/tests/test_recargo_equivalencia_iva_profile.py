"""A retailer in the recargo de equivalencia states no Modelo 303 regime composition.

LIVA arts. 154-163: the supplier charges the recargo and the retailer files no
Modelo 303 for those activities, so the composition of general and simplified
regimes has nothing to describe. Every other regime must still state one.
"""

import pytest

from ..errors import ProfileError
from ..profiles import modelo_iva_profile_required_paths, taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_COMPOSITION = "iva.m303_regime_composition"


def _facts(regime: str, *, composition: str | None = None) -> dict[str, str]:
    facts = {
        "identity.tax_id": "12345678Z",
        "activities.description": "comercio al por menor",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.roi_enrolled": "false",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }
    facts["iva.regime"] = regime
    if composition is not None:
        facts[_COMPOSITION] = composition
    return facts


def test_a_recargo_retailer_builds_its_iva_block_without_a_composition() -> None:
    profile = taxpayer_profile_from_mapping(_facts("RECARGO_EQUIVALENCIA"), tax_id_default="12345678Z")

    assert profile.iva is not None
    assert profile.iva.regime_composition is None
    assert profile.iva.roi_enrolled is False


def test_the_regime_is_read_in_its_dashed_operator_spelling() -> None:
    profile = taxpayer_profile_from_mapping(_facts("recargo-equivalencia"), tax_id_default="12345678Z")

    assert profile.iva is not None
    assert profile.iva.regime_composition is None


def test_a_composition_stated_beside_the_recargo_regime_is_kept() -> None:
    profile = taxpayer_profile_from_mapping(
        _facts("RECARGO_EQUIVALENCIA", composition="mixed"),
        tax_id_default="12345678Z",
    )

    assert profile.iva is not None
    assert profile.iva.regime_composition is not None
    assert str(profile.iva.regime_composition) == "mixed"


def test_the_simplified_regime_without_a_composition_is_still_refused() -> None:
    with pytest.raises(ProfileError, match="m303_regime_composition"):
        taxpayer_profile_from_mapping(_facts("SIMPLIFICADO"), tax_id_default="12345678Z")


def test_an_unknown_composition_is_refused_even_under_the_recargo_regime() -> None:
    with pytest.raises(ProfileError, match=r"unsupported iva.m303_regime_composition"):
        taxpayer_profile_from_mapping(
            _facts("RECARGO_EQUIVALENCIA", composition="nonsense"),
            tax_id_default="12345678Z",
        )


def test_completeness_does_not_ask_a_recargo_retailer_for_a_composition() -> None:
    recargo = modelo_iva_profile_required_paths(_facts("RECARGO_EQUIVALENCIA"))
    simplified = modelo_iva_profile_required_paths(_facts("SIMPLIFICADO"))

    assert _COMPOSITION not in recargo
    assert _COMPOSITION in simplified
    assert set(simplified) - set(recargo) == {_COMPOSITION}


def test_completeness_asks_a_recargo_retailer_that_states_one_to_keep_it_valid() -> None:
    required = modelo_iva_profile_required_paths(_facts("RECARGO_EQUIVALENCIA", composition="general"))

    assert _COMPOSITION in required
