"""Unit tests for the model-capability tier system.

Exercises :func:`cadrumo.domain.transactions._model_tier.resolve_profile`
against the per-provider catalogue, the :data:`MINIMUM_CLASSIFICATION_TIER`
floor, and frozen-dataclass invariants on
:class:`cadrumo.domain.transactions._model_tier.ModelProfile`.
"""

from __future__ import annotations

import pytest

from .._model_tier import (
    MINIMUM_CLASSIFICATION_TIER,
    ModelCapability,
    ModelTier,
    catalogue,
    profiles_for_provider,
    resolve_profile,
)
from ..errors import TransactionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORTED_PROVIDERS = ("claude", "antigravity", "codex")


def test_model_tier_is_ordered() -> None:
    """ModelTier members compare by capability strength."""
    assert ModelTier.LOW < ModelTier.MEDIUM < ModelTier.HIGH


def test_minimum_classification_tier_is_medium_or_above() -> None:
    """Classification requires at least MEDIUM capability."""
    assert MINIMUM_CLASSIFICATION_TIER >= ModelTier.MEDIUM


def test_catalogue_covers_supported_providers_with_minimum_tier_profiles() -> None:
    """Each supported provider has a registered MEDIUM+ profile."""
    providers = {profile.provider for profile in catalogue()}
    assert set(_SUPPORTED_PROVIDERS) <= providers
    for provider in _SUPPORTED_PROVIDERS:
        profiles = profiles_for_provider(provider)
        assert profiles, f"no profiles registered for provider {provider!r}"
        assert any(p.tier >= MINIMUM_CLASSIFICATION_TIER for p in profiles), (
            f"provider {provider!r} has no MEDIUM+ profile"
        )


def test_resolve_profile_without_alias_returns_lowest_tier_at_or_above_minimum() -> None:
    """Default resolution picks the cheapest capable model, not the flashiest."""
    profile = resolve_profile("claude")
    assert profile.tier >= MINIMUM_CLASSIFICATION_TIER
    # Verify it's the LOWEST tier meeting the floor, not the highest.
    all_eligible = [p for p in profiles_for_provider("claude") if p.tier >= MINIMUM_CLASSIFICATION_TIER]
    assert profile.tier == min(p.tier for p in all_eligible)


def test_resolve_profile_rejects_low_tier_alias() -> None:
    """An alias below the minimum tier must be refused."""
    # claude-haiku is LOW in the catalogue.
    with pytest.raises(TransactionError, match="tier LOW but classification requires at least MEDIUM"):
        resolve_profile("claude", alias="claude-haiku")


def test_resolve_profile_accepts_low_tier_alias_when_minimum_lowered() -> None:
    """An explicit minimum_tier=LOW lets low-tier models through (caller accepts the risk)."""
    profile = resolve_profile("claude", alias="claude-haiku", minimum_tier=ModelTier.LOW)
    assert profile.tier is ModelTier.LOW
    assert profile.capability is ModelCapability.NON_THINKING


def test_resolve_profile_rejects_unknown_provider() -> None:
    with pytest.raises(TransactionError, match="unknown provider"):
        resolve_profile("not-a-provider")


def test_resolve_profile_rejects_unknown_alias() -> None:
    with pytest.raises(TransactionError, match="unknown alias"):
        resolve_profile("claude", alias="claude-from-the-future")


def test_profile_is_frozen_dataclass() -> None:
    """ModelProfile is immutable at runtime."""
    from dataclasses import FrozenInstanceError

    profile = resolve_profile("claude")
    with pytest.raises(FrozenInstanceError, match=r"model_id"):
        # Negative test: verify frozen constraint raises FrozenInstanceError
        profile.__setattr__("model_id", "changed")


def test_every_profile_has_non_empty_alias_and_known_capability() -> None:
    """Profile aliases and capabilities stay inside the operator-facing contract."""
    valid_capabilities = {ModelCapability.THINKING, ModelCapability.NON_THINKING}
    for profile in catalogue():
        assert profile.alias, f"empty alias on profile {profile!r}"
        assert profile.alias == profile.alias.strip().lower()
        assert profile.capability in valid_capabilities
