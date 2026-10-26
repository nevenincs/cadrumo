"""Schedule registry dotted profile-path contracts."""

from dataclasses import dataclass

import pytest

from .. import schedules as _schedules

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_schedules_final_path_constants() -> None:
    assert _schedules._IVA_REGIME_PATH == "iva.regime"
    assert _schedules._TAXPAYER_ENTITY_TYPE_PATH == "taxpayer.entity_type"


def test_schedules_resolver_accepts_registry_dotted_profile_paths() -> None:
    @dataclass(frozen=True)
    class _Regime:
        value: str

    @dataclass(frozen=True)
    class _Profile:
        iva_regime: _Regime
        entity_type: str

    profile = _Profile(iva_regime=_Regime("monthly"), entity_type="legal_entity")
    assert _schedules._resolve_profile_fact(profile, _schedules._IVA_REGIME_PATH) == "monthly"
    assert _schedules._resolve_profile_fact(profile, _schedules._TAXPAYER_ENTITY_TYPE_PATH) == "legal_entity"
