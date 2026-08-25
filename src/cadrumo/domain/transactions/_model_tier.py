"""Model capability tiers for the LLM classifier.

Decouples consumer code from the shifting sands of model IDs at each
provider. The operator picks a *capability tier* (``LOW`` /
``MEDIUM`` / ``HIGH``) and a *provider* (``claude`` / ``antigravity`` /
``codex``); :func:`resolve_profile` returns the current
:class:`ModelProfile` whose ``model_id`` meets the tier floor for
that provider.

Rationale:

- Model IDs change every few months (``sonnet-4.5``, ``gemini-3-pro``,
  ``o3`` -> ``o4``). Hard-coding IDs in CLI flags forces consumers to
  chase them. A stable tier + alias table is a better interface.
- Thinking models (multi-step reasoning, chain-of-thought) classify
  ambiguous transactions more accurately than single-shot models but
  cost more tokens. Surfacing the :class:`ModelCapability` axis lets
  the operator pick a trade-off.
- Classification accuracy on realistic autónomo data is acceptable at
  :attr:`ModelTier.MEDIUM` and above; :attr:`ModelTier.LOW` models are
  prone to ignoring the strict JSON schema or picking the wrong
  classification on ambiguous inputs.
  :data:`MINIMUM_CLASSIFICATION_TIER` enforces this floor.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from .errors import TransactionError


class ModelTier(IntEnum):
    """Ordered capability tier. Comparison operators work as expected.

    Attributes:
        LOW: Cheap / fast models prone to schema drift on ambiguous
            inputs.
        MEDIUM: Solid single-shot reasoning; the floor for the
            classification pipeline.
        HIGH: Top-tier models with strong multi-step reasoning.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class ModelCapability(StrEnum):
    """Whether the model natively does multi-step reasoning before answering.

    Attributes:
        NON_THINKING: Single-shot models that emit one response without
            internal chain-of-thought passes.
        THINKING: Models that perform explicit multi-step reasoning
            before producing the final answer.
    """

    NON_THINKING = "non_thinking"
    THINKING = "thinking"


@dataclass(frozen=True)
class ModelProfile:
    """One concrete model at one provider, tagged with its capability tier.

    Attributes:
        provider: Lower-case provider name (``claude`` / ``antigravity`` /
            ``codex``).
        alias: Stable human-friendly identifier, e.g. ``claude-sonnet``.
            The operator uses this on the CLI; the tool maps it to ``model_id``.
        model_id: Current provider-specific model argument. MAY be
            empty when the provider CLI defaults to the right model
            (e.g. ``codex`` picks its own default).
        tier: Capability tier.
        capability: Thinking vs non-thinking.
    """

    provider: str
    alias: str
    model_id: str
    tier: ModelTier
    capability: ModelCapability


# Minimum capability tier permitted for the classification pipeline. The
# observable failure mode at ``LOW`` is schema drift (the model returns
# prose instead of JSON, or picks a classification outside the allow-list)
# on more than a handful of transactions per batch, which defeats the
# confidence filter operator relies on downstream.
MINIMUM_CLASSIFICATION_TIER: ModelTier = ModelTier.MEDIUM
"""Minimum :class:`ModelTier` permitted for the classification pipeline.

The observable failure mode at :attr:`ModelTier.LOW` is schema drift
(the model returns prose instead of JSON, or picks a classification
outside the allow-list) on more than a handful of transactions per
batch, which defeats the confidence filter downstream consumers rely
on."""


# Per-provider catalogue of known models. Keep the list tight and prefer
# the current default over exhaustive historical IDs — this is a floor
# for operator's choices, not an archive.
#
# Tier placement rationale:
# - claude-haiku, gpt-4o-mini: fast/cheap, ~LOW.
# - claude-sonnet, antigravity default, gpt-4o, codex default: solid single-shot, MEDIUM.
# - claude-opus, o3/o4, codex-high: top-tier reasoning, HIGH.
_CATALOGUE: tuple[ModelProfile, ...] = (
    # Claude
    ModelProfile(
        provider="claude",
        alias="claude-haiku",
        model_id="claude-haiku-4-5",
        tier=ModelTier.LOW,
        capability=ModelCapability.NON_THINKING,
    ),
    ModelProfile(
        provider="claude",
        alias="claude-sonnet",
        model_id="claude-sonnet-4-6",
        tier=ModelTier.MEDIUM,
        capability=ModelCapability.NON_THINKING,
    ),
    ModelProfile(
        provider="claude",
        alias="claude-opus",
        model_id="claude-opus-4-7",
        tier=ModelTier.HIGH,
        capability=ModelCapability.THINKING,
    ),
    # Antigravity (Google's agentic CLI ``agy``, the supported successor to the
    # retired standalone ``gemini`` CLI). The CLI selects its own current
    # default model; an empty ``model_id`` omits ``--model`` and lets ``agy``
    # choose, mirroring the ``codex-default`` profile. Explicit model pinning is
    # a follow-up once ``agy models`` is queryable in CI.
    ModelProfile(
        provider="antigravity",
        alias="antigravity-default",
        model_id="",
        tier=ModelTier.MEDIUM,
        capability=ModelCapability.THINKING,
    ),
    # Codex — default is the agent's current top model; it does not accept
    # -m for most deployments. alias "codex-default" maps to empty model_id.
    ModelProfile(
        provider="codex",
        alias="codex-default",
        model_id="",
        tier=ModelTier.MEDIUM,
        capability=ModelCapability.THINKING,
    ),
    ModelProfile(
        provider="codex",
        alias="codex-o3",
        model_id="o3",
        tier=ModelTier.HIGH,
        capability=ModelCapability.THINKING,
    ),
)


def catalogue() -> tuple[ModelProfile, ...]:
    """Return the full known-model catalogue.

    Returns:
        A tuple of every registered :class:`ModelProfile`, in the
        catalogue's declared order.
    """
    return _CATALOGUE


def profiles_for_provider(provider: str) -> tuple[ModelProfile, ...]:
    """Return every profile registered for ``provider``.

    Args:
        provider: Provider name; matched case-insensitively against
            :attr:`ModelProfile.provider`.

    Returns:
        A tuple of every :class:`ModelProfile` registered for the
        normalised provider name. Empty tuple when no profile matches.
    """
    normalised = provider.lower().strip()
    return tuple(p for p in _CATALOGUE if p.provider == normalised)


def resolve_profile(
    provider: str,
    *,
    alias: str | None = None,
    minimum_tier: ModelTier = MINIMUM_CLASSIFICATION_TIER,
) -> ModelProfile:
    """Resolve an optional alias to a :class:`ModelProfile` for ``provider``.

    When ``alias`` is None, the default is the LOWEST-tier profile at or
    above ``minimum_tier`` for the provider (cheap but capable).

    Args:
        provider: Provider name (matched case-insensitively).
        alias: Optional capability-tier alias; when ``None`` the
            cheapest-meets-minimum profile is chosen.
        minimum_tier: Refuses aliases (and default selections) below
            this tier. Defaults to :data:`MINIMUM_CLASSIFICATION_TIER`.

    Returns:
        The resolved :class:`ModelProfile`.

    Raises:
        TransactionError: If the provider is unknown, if the alias is unknown
            for that provider, or if the resolved profile's tier is
            below ``minimum_tier``.
    """
    normalised_provider = provider.lower().strip()
    candidates = profiles_for_provider(normalised_provider)
    if not candidates:
        known = sorted({p.provider for p in _CATALOGUE})
        raise TransactionError(f"unknown provider {provider!r}; known: {known}")

    if alias is None:
        eligible = sorted(
            (p for p in candidates if p.tier >= minimum_tier),
            key=lambda p: p.tier,
        )
        if not eligible:
            available_tiers = sorted({p.tier.name for p in candidates})
            raise TransactionError(
                f"no {normalised_provider} model meets minimum tier {minimum_tier.name}; available: {available_tiers}",
            )
        return eligible[0]

    normalised_alias = alias.lower().strip()
    for profile in candidates:
        if profile.alias == normalised_alias:
            if profile.tier < minimum_tier:
                raise TransactionError(
                    f"model {profile.alias!r} is tier {profile.tier.name} "
                    f"but classification requires at least {minimum_tier.name}",
                )
            return profile
    known_aliases = sorted(p.alias for p in candidates)
    raise TransactionError(f"unknown alias {alias!r} for provider {normalised_provider}; known: {known_aliases}")


__all__ = [
    "MINIMUM_CLASSIFICATION_TIER",
    "ModelCapability",
    "ModelProfile",
    "ModelTier",
    "catalogue",
    "profiles_for_provider",
    "resolve_profile",
]
