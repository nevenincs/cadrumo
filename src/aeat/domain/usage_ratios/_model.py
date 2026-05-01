"""Pydantic model and resolver for Kent's per-category usage-ratio overrides (#259)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..categories import (
    CATEGORY_PROFILES_2025,
    ProportionalityKind,
    SpendingCategory,
)

__all__ = [
    "ELIGIBLE_USAGE_RATIO_CATEGORIES",
    "UsageRatioProfile",
    "resolve_user_ratio",
]


_USER_RATIO_KINDS: frozenset[ProportionalityKind] = frozenset(
    {ProportionalityKind.USAGE_RATIO_HOME_AREA, ProportionalityKind.USAGE_RATIO_PERSONAL}
)


def _eligible_categories() -> frozenset[SpendingCategory]:
    return frozenset(
        category
        for category, profile in CATEGORY_PROFILES_2025.items()
        if profile.proportionality.kind in _USER_RATIO_KINDS
    )


ELIGIBLE_USAGE_RATIO_CATEGORIES: frozenset[SpendingCategory] = _eligible_categories()


class UsageRatioProfile(BaseModel):
    """Kent's persisted per-category usage-ratio overrides.

    The ``ratios`` field holds a mapping from :class:`SpendingCategory` to a
    :class:`~decimal.Decimal` in the inclusive ``[0, 1]`` range. Only categories
    whose :class:`~aeat.domain.categories.ProportionalityRule` kind is
    ``USAGE_RATIO_HOME_AREA`` or ``USAGE_RATIO_PERSONAL`` may be persisted;
    every other kind is rejected by the cross-field validator.

    ``frozen=True`` prevents attribute reassignment but does not freeze the
    inner mapping. Callers must treat ``profile.ratios`` as read-only and use
    :meth:`with_ratio` / :meth:`without_ratio` to produce new profiles.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ratios: dict[SpendingCategory, Decimal] = Field(default_factory=dict)

    @field_validator("ratios", mode="after")
    @classmethod
    def _validate_bounds(cls, value: dict[SpendingCategory, Decimal]) -> dict[SpendingCategory, Decimal]:
        # Pydantic strict-mode Decimal handling rejects NaN / Infinity before this
        # validator runs (both via JSON parse and via Python constructor); the
        # bound check here covers the remaining domain.
        for category, ratio in value.items():
            if not (Decimal("0") <= ratio <= Decimal("1")):
                raise ValueError(f"usage ratio for {category.value!r} must be in [0, 1] (got {ratio})")
        # Canonicalise key order so two equal profiles serialise to identical bytes.
        # Kent's ``var/financial/usage-ratios.json`` is a candidate for git-tracking;
        # stable ordering prevents spurious diffs when ratios are toggled.
        return {category: value[category] for category in sorted(value, key=lambda c: c.value)}

    @model_validator(mode="after")
    def _validate_eligibility(self) -> UsageRatioProfile:
        invalid = tuple(category for category in self.ratios if category not in ELIGIBLE_USAGE_RATIO_CATEGORIES)
        if invalid:
            names = ", ".join(sorted(c.value for c in invalid))
            raise ValueError(f"usage ratios may only target USAGE_RATIO_* categories; rejected: {names}")
        return self

    def with_ratio(self, category: SpendingCategory, ratio: Decimal) -> UsageRatioProfile:
        """Return a new profile with one ratio set or replaced."""
        new_ratios = dict(self.ratios)
        new_ratios[category] = ratio
        return UsageRatioProfile(ratios=new_ratios)

    def without_ratio(self, category: SpendingCategory) -> UsageRatioProfile:
        """Return a new profile with one ratio removed (no-op if absent)."""
        new_ratios = dict(self.ratios)
        new_ratios.pop(category, None)
        return UsageRatioProfile(ratios=new_ratios)


def resolve_user_ratio(profile: UsageRatioProfile, category: SpendingCategory) -> Decimal | None:
    """Return Kent's persisted ratio for a category, or ``None`` if unset.

    Pure helper consumed by :mod:`aeat.domain.deductibility` (issue #257).
    When the return value is ``None`` the caller falls back to
    ``ProportionalityRule.default_ratio`` and records the resolution source in
    the transaction trace fields.

    Args:
        profile: Kent's currently persisted :class:`UsageRatioProfile`.
        category: The spending category whose ratio to resolve.

    Returns:
        The user-configured ratio, or ``None`` if the category has no override.
    """
    return profile.ratios.get(category)
