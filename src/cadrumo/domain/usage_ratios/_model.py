"""Pydantic model and resolver for the operator's per-category usage-ratio overrides.

Defines :class:`UsageRatioProfile` — the strict, frozen pydantic v2 record
that captures the operator's persisted business / personal split coefficients
— plus :func:`resolve_user_ratio`, the pure helper consumed by
``cadrumo.domain.deductibility`` to look up an override before falling back to
the statutory :attr:`domain.categories.ProportionalityRule.default_ratio`.
The eligibility set :data:`ELIGIBLE_USAGE_RATIO_CATEGORIES` is derived once at
import time from :func:`domain.categories.resolve_category_profiles`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ..categories import (
    ProportionalityKind,
    SpendingCategory,
    resolve_category_profiles,
)
from .errors import UsageRatioValidationError

__all__ = [
    "ELIGIBLE_USAGE_RATIO_CATEGORIES",
    "UsageRatioProfile",
    "UsageRatioReference",
    "resolve_user_ratio",
    "validate_usage_ratio_bound",
    "validate_usage_ratio_reference",
]


def validate_usage_ratio_bound(ratio: Decimal, *, label: str) -> Decimal:
    """Return ``ratio`` when it lies in the closed interval ``[0, 1]``, else raise.

    The single authority for the usage-ratio range. Both the persisted
    :class:`UsageRatioProfile` and every transport surface that carries a
    usage ratio route their bound check through this function, so the
    interval is declared once rather than re-stated per call site.

    Args:
        ratio: Candidate usage ratio.
        label: Human-readable subject named in the refusal (a category id
            for the persisted profile, a field name at a transport edge).

    Returns:
        The same ``ratio`` when it is within ``[0, 1]``.

    Raises:
        UsageRatioValidationError: When ``ratio`` falls outside ``[0, 1]``.
    """
    if not (Decimal("0") <= ratio <= Decimal("1")):
        raise UsageRatioValidationError(f"usage ratio for {label!r} must be in [0, 1] (got {ratio})")
    return ratio


_USER_RATIO_KINDS: frozenset[ProportionalityKind] = frozenset(
    {ProportionalityKind.USAGE_RATIO_HOME_AREA, ProportionalityKind.USAGE_RATIO_PERSONAL},
)


def _eligible_categories() -> frozenset[SpendingCategory]:
    """Return the categories whose proportionality kind accepts a user ratio."""
    return frozenset(
        category
        for category, profile in resolve_category_profiles(2025).items()
        if profile.proportionality.kind in _USER_RATIO_KINDS
    )


ELIGIBLE_USAGE_RATIO_CATEGORIES: frozenset[SpendingCategory] = _eligible_categories()
"""Categories for which a :class:`UsageRatioProfile` may carry an override.

Derived from :func:`domain.categories.resolve_category_profiles` at import
time: a category is eligible iff its
:attr:`domain.categories.ProportionalityRule.kind` is
:attr:`domain.categories.ProportionalityKind.USAGE_RATIO_HOME_AREA` or
:attr:`domain.categories.ProportionalityKind.USAGE_RATIO_PERSONAL`.
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

    The inner mapping is frozen after validation. Callers use
    :meth:`with_ratio` / :meth:`without_ratio` to derive new profiles.

    Attributes:
        ratios: Frozen mapping from :class:`domain.categories.SpendingCategory`
            to a :class:`~decimal.Decimal` in ``[0, 1]``.
    """

    model_config = STRICT_FROZEN_CONFIG

    ratios: Mapping[SpendingCategory, Decimal] = Field(
        default_factory=lambda: dict[SpendingCategory, Decimal](),
    )

    @field_validator("ratios", mode="after")
    @classmethod
    def _validate_bounds(cls, value: Mapping[SpendingCategory, Decimal]) -> Mapping[SpendingCategory, Decimal]:
        # Pydantic strict-mode Decimal handling rejects NaN / Infinity before this
        # validator runs (both via JSON parse and via Python constructor); the
        # bound check here covers the remaining domain.
        for category, ratio in value.items():
            validate_usage_ratio_bound(ratio, label=category.value)
        # Canonicalise key order so two equal profiles serialise to identical bytes.
        # operator's ``var/financial/usage-ratios.json`` is a candidate for git-tracking;
        # stable ordering prevents spurious diffs when ratios are toggled.
        return MappingProxyType({category: value[category] for category in sorted(value, key=lambda c: c.value)})

    @field_serializer("ratios")
    def _serialize_ratios(self, value: Mapping[SpendingCategory, Decimal]) -> dict[SpendingCategory, Decimal]:
        return dict(value)

    @model_validator(mode="after")
    def _validate_eligibility(self) -> UsageRatioProfile:
        invalid = tuple(category for category in self.ratios if category not in ELIGIBLE_USAGE_RATIO_CATEGORIES)
        if invalid:
            names = ", ".join(sorted(c.value for c in invalid))
            raise UsageRatioValidationError(f"usage ratios may only target USAGE_RATIO_* categories; rejected: {names}")
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

    Pure helper consumed by ``cadrumo.domain.deductibility``. When the return
    value is ``None`` the caller falls back to
    :attr:`domain.categories.ProportionalityRule.default_ratio` and
    records the resolution source in the transaction trace fields.

    Args:
        profile: The operator's currently persisted :class:`UsageRatioProfile`.
        category: The spending category whose ratio to resolve.

    Returns:
        The user-configured ratio, or ``None`` if the category has no override.
    """
    return profile.ratios.get(category)


class UsageRatioReference(BaseModel):
    """Validated reference from one ledger transaction to a usage-ratio profile entry."""

    model_config = STRICT_FROZEN_CONFIG

    usage_ratio_id: str = Field(min_length=1, max_length=128)
    category: SpendingCategory
    ratio: Decimal


def validate_usage_ratio_reference(
    profile: UsageRatioProfile,
    *,
    category_id: str | None,
    usage_ratio_id: str,
    business_pct: Decimal | None = None,
) -> UsageRatioReference:
    """Validate a ledger transaction's usage-ratio reference against ``profile``.

    Usage-ratio profiles are keyed by :class:`SpendingCategory`; therefore a
    persisted ledger reference must be the concrete category value, not a CLI
    alias or a parallel identifier. When a row also carries ``business_pct``,
    the percentage must match the referenced profile ratio so the stored
    transaction fact and its proportionality source cannot drift.

    Returns:
        The validated :class:`UsageRatioReference` anchored to the profile.
    """
    if category_id is None:
        raise UsageRatioValidationError("usage_ratio_id requires category_id on the ledger transaction")
    try:
        category = SpendingCategory(category_id)
    except ValueError as exc:
        raise UsageRatioValidationError(f"category_id {category_id!r} is not a spending category") from exc
    try:
        ratio_category = SpendingCategory(usage_ratio_id)
    except ValueError as exc:
        raise UsageRatioValidationError(
            f"usage_ratio_id {usage_ratio_id!r} must be a concrete eligible spending category",
        ) from exc
    if ratio_category is not category:
        raise UsageRatioValidationError(
            "usage_ratio_id must match the ledger transaction category_id because "
            "usage-ratio profiles are category-keyed",
        )
    if ratio_category not in ELIGIBLE_USAGE_RATIO_CATEGORIES:
        raise UsageRatioValidationError(f"usage_ratio_id {usage_ratio_id!r} is not eligible for usage ratios")
    ratio = resolve_user_ratio(profile, ratio_category)
    if ratio is None:
        raise UsageRatioValidationError(f"usage_ratio_id {usage_ratio_id!r} is not configured in the active bucket")
    if business_pct is not None and business_pct != ratio:
        raise UsageRatioValidationError(
            f"business_pct {business_pct} does not match usage_ratio_id {usage_ratio_id!r} ratio {ratio}",
        )
    return UsageRatioReference(usage_ratio_id=usage_ratio_id, category=ratio_category, ratio=ratio)
