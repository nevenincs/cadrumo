"""AEAT spending-category taxonomy and proportionality substrate."""

from __future__ import annotations

from ._casilla_mapping import CasillaMapping, CasillaMappingSign
from ._corpus import load_category_profiles_from_manual
from ._profile import CategoryProfile, VatCategory
from ._proportionality import Citation, CitationSource, ProportionalityKind, ProportionalityRule, parse_http_url
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
    "CasillaMapping",
    "CasillaMappingSign",
    "CategoryProfile",
    "Citation",
    "CitationSource",
    "ProportionalityKind",
    "ProportionalityRule",
    "SpendingCategory",
    "SpendingCategoryFamily",
    "VatCategory",
    "categories_for_family",
    "family_for",
    "load_category_profiles_from_manual",
    "parse_http_url",
]
