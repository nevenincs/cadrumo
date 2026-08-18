"""M303 state attribution requires explicit canonical territory authority.

Guards the explicit-authority projection:
  1. ``_inject_derived_state_attribution_facts`` refuses absent territory,
     maps explicit común to Decimal("100"), and explicit foral to Decimal("0").
  2. ``resolve_profile_sourced_bindings`` resolves a profile binding that feeds a
     ``bound`` numeric casilla (casilla 65 is ``ratio``), even though the binding id
     never appears in a formula expression (casilla 66 reads casilla 65 by casilla
     reference).

The común-territory 100% attribution is grounded in the Concierto Económico
(Ley 12/2002, art. 29), but support population is not evidence: the persisted
territory fact must state it explicitly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileFactValue, UserProfileRecord
from .._profile_binding import (
    ProfileBindingResolutionError,
    _inject_derived_state_attribution_facts,
    resolve_profile_sourced_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RATIO_KEY = "tax_residence.state_attribution_ratio"
_SCOPE_KEY = "tax_residence.jurisdiction_scope"
_BINDING_ID = "modelo-303-profile-state-attribution-ratio"
_CLOCK = datetime(2026, 5, 27, 9, 0, 0, tzinfo=UTC)


def test_injector_refuses_absent_scope_instead_of_defaulting_common_regime() -> None:
    fact_index: dict[str, UserProfileFactValue] = {}
    with pytest.raises(ProfileBindingResolutionError, match="cannot default to common regime"):
        _inject_derived_state_attribution_facts(fact_index)


def test_injector_common_regime_resolves_to_one_hundred() -> None:
    fact_index: dict[str, UserProfileFactValue] = {_SCOPE_KEY: "common_regime"}
    _inject_derived_state_attribution_facts(fact_index)
    assert fact_index[_RATIO_KEY] == Decimal("100")


def test_injector_explicit_foral_resolves_to_zero() -> None:
    fact_index: dict[str, UserProfileFactValue] = {_SCOPE_KEY: "foral_unsupported"}
    _inject_derived_state_attribution_facts(fact_index)
    assert fact_index[_RATIO_KEY] == Decimal("0")


def test_injector_refuses_legacy_ratio_as_authority_without_scope() -> None:
    fact_index: dict[str, UserProfileFactValue] = {_RATIO_KEY: Decimal("50")}
    with pytest.raises(ProfileBindingResolutionError, match="cannot default to common regime"):
        _inject_derived_state_attribution_facts(fact_index)


def test_injector_overwrites_legacy_ratio_from_explicit_scope() -> None:
    fact_index: dict[str, UserProfileFactValue] = {
        _SCOPE_KEY: "common_regime",
        _RATIO_KEY: Decimal("50"),
    }
    _inject_derived_state_attribution_facts(fact_index)
    assert fact_index[_RATIO_KEY] == Decimal("100")


def _common_profile() -> UserProfileRecord:
    return UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
        profile_id="27272727-2727-4272-8272-272727272727",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path=_SCOPE_KEY, value="common_regime"),
            UserProfileFact(path="activities.description", value="consultoria"),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _profile_without_jurisdiction_scope() -> UserProfileRecord:
    return UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
        profile_id="27272727-2727-4272-8272-272727272727",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="activities.description", value="consultoria"),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def test_non_m303_profile_resolution_does_not_require_jurisdiction_scope() -> None:
    snapshot = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")

    result = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id="state-attribution-test",
        profile_record=_profile_without_jurisdiction_scope(),
    )

    assert result.resolver_id == "profile"
    assert _BINDING_ID not in result.binding_values


def test_m303_profile_resolution_refuses_missing_jurisdiction_scope() -> None:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")

    with pytest.raises(ProfileBindingResolutionError, match="jurisdiction_scope"):
        resolve_profile_sourced_bindings(
            snapshot,
            bucket_id="state-attribution-test",
            profile_record=_profile_without_jurisdiction_scope(),
        )


def test_303_state_attribution_binding_resolves_to_100_for_common_profile() -> None:
    """End-to-end at the resolver boundary: the bound-casilla profile binding resolves to 100."""
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")
    result = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id="state-attribution-test",
        profile_record=_common_profile(),
    )
    assert result.binding_values.get(_BINDING_ID) == Decimal("100"), (
        "M303 state-attribution ratio must resolve to 100 for a común-territory profile; "
        f"got {result.binding_values.get(_BINDING_ID)!r} (binding excluded or defaulted to 0 = the B2 bug)"
    )
