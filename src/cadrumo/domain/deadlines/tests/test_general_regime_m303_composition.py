"""A taxpayer in the general IVA regime files Modelo 303 under the general regime alone.

Every Modelo 303 record design in the supported span (2022 to 2026 and
following) asks whether the filer "tributa exclusivamente en régimen
simplificado" and answers a general-regime filer with "3" NO (sólo RG). A
declared general regime therefore settles the composition, and the profile
need not ask for it again. The simplified regime does not settle it, because
such a filer may also carry general-regime activities (LIVA art. 122.Dos.1.º)
and must say whether the composition is simplified only or mixed.
"""

import pytest

from ...calculations.registry.m303_schema_vocabulary import m303_regime_composition_export_code
from ..errors import ProfileError
from ..profiles import modelo_iva_profile_required_paths, taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_COMPOSITION = "iva.m303_regime_composition"


def _facts(regime: str, *, composition: str | None = None) -> dict[str, str]:
    facts = {
        "identity.tax_id": "12345678Z",
        "activities.description": "consultoría",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": regime,
        "iva.roi_enrolled": "false",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }
    if composition is not None:
        facts[_COMPOSITION] = composition
    return facts


@pytest.mark.parametrize("regime", ["GENERAL", "general"])
def test_a_general_regime_filer_resolves_the_general_only_composition(regime: str) -> None:
    profile = taxpayer_profile_from_mapping(_facts(regime), tax_id_default="12345678Z")

    assert profile.iva is not None
    assert profile.iva.regime_composition is not None
    assert str(profile.iva.regime_composition) == "general"
    # The design's "Tributa exclusivamente en régimen simplificado" field: "3" NO (sólo RG).
    assert m303_regime_composition_export_code(profile.iva.regime_composition) == "3"


def test_completeness_does_not_ask_a_general_regime_filer_for_a_composition() -> None:
    general = modelo_iva_profile_required_paths(_facts("GENERAL"))
    simplified = modelo_iva_profile_required_paths(_facts("SIMPLIFICADO"))

    assert _COMPOSITION not in general
    assert set(simplified) - set(general) == {_COMPOSITION}


def test_a_composition_stated_beside_the_general_regime_is_kept() -> None:
    profile = taxpayer_profile_from_mapping(_facts("GENERAL", composition="mixed"), tax_id_default="12345678Z")

    assert profile.iva is not None
    assert str(profile.iva.regime_composition) == "mixed"
    assert _COMPOSITION in modelo_iva_profile_required_paths(_facts("GENERAL", composition="mixed"))


def test_an_unknown_composition_beside_the_general_regime_is_refused() -> None:
    with pytest.raises(ProfileError, match=r"unsupported iva.m303_regime_composition"):
        taxpayer_profile_from_mapping(_facts("GENERAL", composition="nonsense"), tax_id_default="12345678Z")


@pytest.mark.parametrize("regime", ["SIMPLIFICADO", "REAGP", "EXENTO"])
def test_a_regime_that_does_not_settle_the_composition_still_requires_it(regime: str) -> None:
    assert _COMPOSITION in modelo_iva_profile_required_paths(_facts(regime))


def test_a_block_claimed_without_a_regime_still_requires_the_composition() -> None:
    facts = _facts("GENERAL")
    del facts["iva.regime"]

    assert _COMPOSITION in modelo_iva_profile_required_paths(facts)
    with pytest.raises(ProfileError, match="m303_regime_composition"):
        taxpayer_profile_from_mapping(facts, tax_id_default="12345678Z")
