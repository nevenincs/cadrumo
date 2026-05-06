"""Pydantic model and resolver for the operator's per-category usage-ratio overrides.

Defines :class:`UsageRatioProfile` — the strict, frozen pydantic v2 record
that captures the operator's persisted business / personal split coefficients
— plus :func:`resolve_user_ratio`, the pure helper consumed by
:mod:`aeat.domain.deductibility` to look up an override before falling back to
the statutory :attr:`aeat.domain.categories.ProportionalityRule.default_ratio`.
The eligibility set :data:`ELIGIBLE_USAGE_RATIO_CATEGORIES` is derived once at
import time from :data:`aeat.domain.categories.CATEGORY_PROFILES_2025`.
"""

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
    """Return the categories whose proportionality kind accepts a user ratio."""
    return frozenset(
        category
        for category, profile in CATEGORY_PROFILES_2025.items()
        if profile.proportionality.kind in _USER_RATIO_KINDS
    )


ELIGIBLE_USAGE_RATIO_CATEGORIES: frozenset[SpendingCategory] = _eligible_categories()
"""Categories for which a :class:`UsageRatioProfile` may carry an override.

Derived from :data:`aeat.domain.categories.CATEGORY_PROFILES_2025` at import
time: a category is eligible iff its
:attr:`aeat.domain.categories.ProportionalityRule.kind` is
:attr:`aeat.domain.categories.ProportionalityKind.USAGE_RATIO_HOME_AREA` or
:attr:`aeat.domain.categories.ProportionalityKind.USAGE_RATIO_PERSONAL`.
"""


class UsageRatioProfile(BaseModel):
    """The operator's persisted per-category usage-ratio overrides.

    Only categories listed in :data:`ELIGIBLE_USAGE_RATIO_CATEGORIES` may be
    persisted; every other key is rejected by the cross-field validator. The
    bounds validator additionally rejects ``NaN`` / ``Infinity`` Decimal values
    and any ratio outside the inclusive ``[0, 1]`` range. Stored ratios are
    canonicalised by category-value sort order so two equal profiles serialise
    to identical bytes — a property relied on when the encrypted envelope is
    git-tracked.

    ``frozen=True`` prevents attribute reassignment but does not freeze the
    inner mapping. Callers must treat :attr:`ratios` as read-only and use
    :meth:`with_ratio` / :meth:`without_ratio` to derive new profiles.

    Attributes:
        ratios: Mapping from :class:`aeat.domain.categories.SpendingCategory`
            to a :class:`~decimal.Decimal` in ``[0, 1]``.
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
        # operator's ``var/financial/usage-ratios.json`` is a candidate for git-tracking;
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
        """Return a new :class:`UsageRatioProfile` with one ratio set or replaced.

        Args:
            category: The spending category whose ratio to set.
            ratio: The replacement ratio in ``[0, 1]``.

        Returns:
            A fresh frozen profile; the receiver is left unchanged.
        """
        new_ratios = dict(self.ratios)
        new_ratios[category] = ratio
        return UsageRatioProfile(ratios=new_ratios)

    def without_ratio(self, category: SpendingCategory) -> UsageRatioProfile:
        """Return a new :class:`UsageRatioProfile` with one ratio removed.

        A no-op when ``category`` has no current override.

        Args:
            category: The spending category whose override to remove.

        Returns:
            A fresh frozen profile; the receiver is left unchanged.
        """
        new_ratios = dict(self.ratios)
        new_ratios.pop(category, None)
        return UsageRatioProfile(ratios=new_ratios)


def resolve_user_ratio(profile: UsageRatioProfile, category: SpendingCategory) -> Decimal | None:
    """Return the operator's persisted ratio for ``category``, or ``None`` if unset.

    Pure helper consumed by :mod:`aeat.domain.deductibility`. When the return
    value is ``None`` the caller falls back to
    :attr:`aeat.domain.categories.ProportionalityRule.default_ratio` and
    records the resolution source in the transaction trace fields.

    Args:
        profile: The operator's currently persisted :class:`UsageRatioProfile`.
        category: The spending category whose ratio to resolve.

    Returns:
        The user-configured ratio, or ``None`` if the category has no override.
    """
    return profile.ratios.get(category)
