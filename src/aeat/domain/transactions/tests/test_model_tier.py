"""Unit tests for the model-capability tier system.

Exercises :func:`aeat.domain.transactions._model_tier.resolve_profile`
against the per-provider catalogue, the :data:`MINIMUM_CLASSIFICATION_TIER`
floor, and frozen-dataclass invariants on
:class:`aeat.domain.transactions._model_tier.ModelProfile`.
"""

from __future__ import annotations

import pytest

from .._errors import TransactionError
from .._model_tier import (
    MINIMUM_CLASSIFICATION_TIER,
    ModelCapability,
    ModelTier,
    catalogue,
    profiles_for_provider,
    resolve_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_model_tier_is_ordered() -> None:
    """ModelTier members compare by capability strength."""
    assert ModelTier.LOW < ModelTier.MEDIUM < ModelTier.HIGH


def test_minimum_classification_tier_is_medium_or_above() -> None:
    """Classification requires at least MEDIUM capability."""
    assert MINIMUM_CLASSIFICATION_TIER >= ModelTier.MEDIUM


def test_catalogue_covers_every_supported_provider() -> None:
    """claude, antigravity, and codex each have at least one registered profile."""
    providers = {profile.provider for profile in catalogue()}
    assert {"claude", "antigravity", "codex"} <= providers


def test_each_provider_has_a_profile_meeting_the_minimum_tier() -> None:
    """Every supported provider must offer at least one MEDIUM+ profile.

    Otherwise the default classifier for that provider would always
    fail tier enforcement, defeating the whole capability abstraction.
    """
    for provider in ("claude", "antigravity", "codex"):
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
        profile.model_id = "changed"  # type: ignore


def test_every_profile_has_a_non_empty_alias() -> None:
    """Aliases are the human-facing surface — they must not be blank."""
    for profile in catalogue():
        assert profile.alias, f"empty alias on profile {profile!r}"
        assert profile.alias == profile.alias.strip().lower()


def test_every_profile_has_a_known_capability() -> None:
    """Profiles must declare their thinking/non-thinking capability."""
    valid = {ModelCapability.THINKING, ModelCapability.NON_THINKING}
    for profile in catalogue():
        assert profile.capability in valid
