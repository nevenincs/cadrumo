"""Regression: M303 casilla 65 (state-attribution ratio) resolves to 100 for común profiles.

Guards the two-layer B2 fix:
  1. ``_inject_derived_state_attribution_facts`` defaults común / absent
     ``jurisdiction_scope`` to Decimal("100") and explicit foral to Decimal("0").
  2. ``resolve_profile_sourced_bindings`` resolves a profile binding that feeds a
     ``bound`` numeric casilla (casilla 65 is ``ratio``), even though the binding id
     never appears in a formula expression (casilla 66 reads casilla 65 by casilla
     reference).

Before the fix, casilla 65 silently resolved to 0 for every real profile (nothing
sets ``jurisdiction_scope`` in production), zeroing the headline result casilla 71 on
a real liability — a silent under-declaration. The común-territory 100% attribution
is grounded in the Concierto Económico (Ley 12/2002, art. 29); the ``CCAA`` enum is
común-only and foral residences are refused at profile creation, so 100 is correct for
every supported profile.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.user_profile import UserProfileFact, UserProfileFactValue, UserProfileRecord
from .._profile_binding import (
    _inject_derived_state_attribution_facts,
    resolve_profile_sourced_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RATIO_KEY = "tax_residence.state_attribution_ratio"
_SCOPE_KEY = "tax_residence.jurisdiction_scope"
_BINDING_ID = "modelo-303-profile-state-attribution-ratio"
_CLOCK = datetime(2026, 5, 27, 9, 0, 0, tzinfo=UTC)


def test_injector_defaults_absent_scope_to_one_hundred() -> None:
    fact_index: dict[str, UserProfileFactValue] = {}
    _inject_derived_state_attribution_facts(fact_index)
    assert fact_index[_RATIO_KEY] == Decimal("100")


def test_injector_common_regime_resolves_to_one_hundred() -> None:
    fact_index: dict[str, UserProfileFactValue] = {_SCOPE_KEY: "common_regime"}
    _inject_derived_state_attribution_facts(fact_index)
    assert fact_index[_RATIO_KEY] == Decimal("100")


def test_injector_explicit_foral_resolves_to_zero() -> None:
    fact_index: dict[str, UserProfileFactValue] = {_SCOPE_KEY: "foral_unsupported"}
    _inject_derived_state_attribution_facts(fact_index)
    assert fact_index[_RATIO_KEY] == Decimal("0")


def test_injector_is_idempotent_when_ratio_already_present() -> None:
    fact_index: dict[str, UserProfileFactValue] = {_RATIO_KEY: Decimal("50")}
    _inject_derived_state_attribution_facts(fact_index)
    assert fact_index[_RATIO_KEY] == Decimal("50")


def _common_profile() -> UserProfileRecord:
    """A común-territory profile with NO jurisdiction_scope fact (the real-world case)."""
    return UserProfileRecord(
        profile_id="27272727-2727-4272-8272-272727272727",
        display_name="State attribution test taxpayer",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="activities.description", value="consultoria"),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
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
