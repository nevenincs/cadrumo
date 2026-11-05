"""Schedule registry dotted profile-path contracts."""

from dataclasses import dataclass

import pytest

from .. import schedules

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_schedules_final_path_constants() -> None:
    assert schedules.IVA_REGIME_PATH == "iva.regime"
    assert schedules.TAXPAYER_ENTITY_TYPE_PATH == "taxpayer.entity_type"


def test_schedules_resolver_accepts_registry_dotted_profile_paths() -> None:
    @dataclass(frozen=True)
    class _Regime:
        value: str

    @dataclass(frozen=True)
    class _Profile:
        iva_regime: _Regime
        entity_type: str

    profile = _Profile(iva_regime=_Regime("monthly"), entity_type="legal_entity")
    assert schedules.resolve_profile_fact(profile, schedules.IVA_REGIME_PATH) == "monthly"
    assert schedules.resolve_profile_fact(profile, schedules.TAXPAYER_ENTITY_TYPE_PATH) == "legal_entity"
