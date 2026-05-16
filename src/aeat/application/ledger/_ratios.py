"""Operator-facing extensions for the ``aeat app ledger ratios`` verb-group.

The existing usage-ratio CRUD verbs (``list``/``set``/``unset``) live in
the application-layer ledger actions backed by the domain
``usage_ratios`` module. This module adds two read-only verbs that
close the discoverability and pre-calculate readiness gaps:

  ``eligible``  enumerate categories that may carry a user ratio,
                annotated with their statutory default ratio
  ``validate``  inspect the persisted profile against eligibility and
                bound rules; report missing categories per modelo
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ...domain.categories import ProportionalityRule, SpendingCategory, resolve_category_profiles
from ...domain.usage_ratios import (
    ELIGIBLE_USAGE_RATIO_CATEGORIES,
    UsageRatioProfile,
    load_usage_ratios,
)


class EligibleCategoryRow(BaseModel):
    """One row in the ``ratios eligible`` listing.

    ``default_ratio`` is None for eligible categories whose
    proportionality rule does not ship a statutory default; the
    operator must supply an override before the modelo pre-calculate
    readiness check passes.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    category: SpendingCategory
    proportionality_kind: str = Field(min_length=1)
    default_ratio: Decimal | None = Field(default=None)
    override_present: bool


class RatiosValidationFinding(BaseModel):
    """One issue raised by ``ratios validate`` for an eligible category."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    category: SpendingCategory
    kind: str = Field(min_length=1)
    detail: str = Field(default="", max_length=300)


class RatiosValidationReport(BaseModel):
    """Result of ``ratios validate``. Read-only, emits no bucket event."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: str = Field(min_length=1)
    profile_present: bool
    eligible_count: int = Field(ge=0)
    overrides_count: int = Field(ge=0)
    missing_overrides: tuple[SpendingCategory, ...] = Field(default_factory=tuple)
    findings: tuple[RatiosValidationFinding, ...] = Field(default_factory=tuple)


def eligible_ratio_categories(profile: UsageRatioProfile) -> tuple[EligibleCategoryRow, ...]:
    """Return all eligible categories with their default ratio + override flag.

    The output is sorted by canonical category value so callers can
    diff snapshots without ordering noise.
    """
    rows: list[EligibleCategoryRow] = []
    for category in sorted(ELIGIBLE_USAGE_RATIO_CATEGORIES, key=lambda c: c.value):
        category_profile = resolve_category_profiles(2025)[category]
        rule: ProportionalityRule = category_profile.proportionality
        rows.append(
            EligibleCategoryRow(
                category=category,
                proportionality_kind=rule.kind.value,
                default_ratio=rule.default_ratio,
                override_present=category in profile.ratios,
            ),
        )
    return tuple(rows)


def validate_ratios_profile(
    *,
    bucket_id: str,
    profile: UsageRatioProfile,
    require_overrides_for: tuple[SpendingCategory, ...] = (),
) -> RatiosValidationReport:
    """Inspect a profile against eligibility and any required overrides.

    ``require_overrides_for`` is the set of categories the caller needs
    explicitly populated (e.g. a modelo's pre-calculate readiness check).
    Categories absent from :data:`ELIGIBLE_USAGE_RATIO_CATEGORIES` raise a
    ``not_eligible`` finding rather than silently passing.
    """
    findings: list[RatiosValidationFinding] = []
    missing: list[SpendingCategory] = []

    for category in require_overrides_for:
        if category not in ELIGIBLE_USAGE_RATIO_CATEGORIES:
            findings.append(
                RatiosValidationFinding(
                    category=category,
                    kind="not_eligible",
                    detail=(
                        f"category {category.value!r} is not eligible for a user ratio override "
                        "(its proportionality rule does not consume USAGE_RATIO_*)"
                    ),
                ),
            )
            continue
        if category not in profile.ratios:
            missing.append(category)

    # The domain-layer profile already rejects out-of-bounds ratios at
    # construction time; surfacing those here is a defensive guard for
    # legacy on-disk records that bypass validation on read.
    for category, ratio in profile.ratios.items():
        if category not in ELIGIBLE_USAGE_RATIO_CATEGORIES:
            findings.append(
                RatiosValidationFinding(
                    category=category,
                    kind="not_eligible_override",
                    detail=f"persisted override on a non-eligible category {category.value!r}",
                ),
            )
            continue
        if not (Decimal("0") <= ratio <= Decimal("1")):
            findings.append(
                RatiosValidationFinding(
                    category=category,
                    kind="out_of_bounds",
                    detail=f"persisted ratio {ratio} for {category.value!r} is outside [0, 1]",
                ),
            )

    return RatiosValidationReport(
        bucket_id=bucket_id,
        profile_present=bool(profile.ratios),
        eligible_count=len(ELIGIBLE_USAGE_RATIO_CATEGORIES),
        overrides_count=len(profile.ratios),
        missing_overrides=tuple(missing),
        findings=tuple(findings),
    )


def list_eligible_ratios_for_bucket(*, bucket_id: str) -> tuple[EligibleCategoryRow, ...]:
    """Convenience: load the bucket's profile and project the eligibility report."""
    profile = load_usage_ratios(bucket_id=bucket_id)
    return eligible_ratio_categories(profile)


def validate_ratios_for_bucket(
    *,
    bucket_id: str,
    require_overrides_for: tuple[SpendingCategory, ...] = (),
) -> RatiosValidationReport:
    """Convenience: load the bucket's profile and run validation."""
    profile = load_usage_ratios(bucket_id=bucket_id)
    return validate_ratios_profile(
        bucket_id=bucket_id,
        profile=profile,
        require_overrides_for=require_overrides_for,
    )


__all__ = [
    "EligibleCategoryRow",
    "RatiosValidationFinding",
    "RatiosValidationReport",
    "eligible_ratio_categories",
    "list_eligible_ratios_for_bucket",
    "validate_ratios_for_bucket",
    "validate_ratios_profile",
]
