"""AEAT spending-category taxonomy and proportionality substrate.

Owns the closed taxonomy of deductible autónomo spending categories
(:class:`SpendingCategory`, :class:`SpendingCategoryFamily`), their
explainable proportionality rules (:class:`ProportionalityRule`,
:class:`ProportionalityKind`, :class:`StatutoryCapPeriod`,
:class:`StatutoryCapVariant`), and their legal citations.

The :data:`CATEGORY_PROFILES_2025` registry is the curated
hand-checked source of truth; :func:`load_category_profiles_from_manual`
is the bridge to a future manual-derived loader and currently falls
back to the curated registry.

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
from ._registry import CATEGORY_PROFILES_2025
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
]
