"""AEAT spending-category taxonomy and registry-backed profiles.

Owns the closed taxonomy of deductible autónomo spending categories
(:class:`SpendingCategory`, :class:`SpendingCategoryFamily`), their
explainable proportionality rules (:class:`ProportionalityRule`,
:class:`ProportionalityKind`, :class:`StatutoryCapPeriod`,
:class:`StatutoryCapVariant`), and their legal citations.

Profile data is loaded from committed TOML under
`registry/aeat/categories/profiles`. Runtime Python owns validation and
resolution behaviour, not legal profile values.

Every profile must carry at least one
:class:`CategoryCitation` so the explainability chain back to
BOE / Manual práctico stays intact.
"""

from __future__ import annotations

from ._corpus import load_category_profiles_from_manual
from ._profile import CategoryProfile, VatCategory
from ._proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapPeriod,
    StatutoryCapVariant,
    parse_http_url,
)
from ._registry import (
    CATEGORY_PROFILE_REGISTRY_BY_YEAR,
    CATEGORY_PROFILES_2025,
    resolve_category_profiles,
)
from ._spending_category import (
    CATEGORY_FAMILY_MEMBERS,
    SpendingCategory,
    SpendingCategoryFamily,
    categories_for_family,
    family_for,
)

__all__ = [
    "CATEGORY_FAMILY_MEMBERS",
    "CATEGORY_PROFILES_2025",
    "CATEGORY_PROFILE_REGISTRY_BY_YEAR",
    "CategoryCitation",
    "CategoryCitationSource",
    "CategoryProfile",
    "ProportionalityKind",
    "ProportionalityRule",
    "SpendingCategory",
    "SpendingCategoryFamily",
    "StatutoryCapPeriod",
    "StatutoryCapVariant",
    "VatCategory",
    "categories_for_family",
    "family_for",
    "load_category_profiles_from_manual",
    "parse_http_url",
    "resolve_category_profiles",
]
