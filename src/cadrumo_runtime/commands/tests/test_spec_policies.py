"""Runtime authentication mutations retain exact-profile custody policy."""

from __future__ import annotations

import pytest

from .. import spec_policies

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("name", ["GOOGLE_DESTRUCTIVE", "AEAT_SESSION_WRITE"])
def test_profile_bound_policies_explicitly_carry_custody_authority(name: str) -> None:
    policy = getattr(spec_policies, name)

    assert policy.write_route == "profile-bound"
    assert "profile-custody" in policy.capabilities
    assert "local-state" in policy.side_effects
