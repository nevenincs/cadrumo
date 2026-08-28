"""Public facade for AEAT spending-category taxonomy and profiles.

This package owns the closed autónomo expense vocabulary,
:class:`SpendingCategory`, its grouping surface
:class:`SpendingCategoryFamily`, and the
:data:`CATEGORY_FAMILY_MEMBERS` membership table. Category identifiers are the
stable values used by ledger rows, invoice rows, usage-ratio overrides, Renta
deductibility, and LLM classification hints; renaming an enum member is a
breaking storage and calculation change.

Profile data is loaded from one undated committed TOML file at
``registry/aeat/categories/profiles.toml`` through
:func:`load_category_profiles`; :func:`category_profile_years` derives the
resolvable filing years from the citation windows, and
:func:`resolve_category_profiles` and :func:`load_category_profiles_from_manual`
project the corpus onto one of them. Runtime Python owns validation and
resolution behaviour, not legal profile values.

Each :class:`CategoryProfile` binds a category to
:class:`ProportionalityRule`, :class:`ProportionalityKind`,
:class:`StatutoryCapPeriod`, :class:`StatutoryCapVariant`,
:class:`IvaDeductibilityHint`, and at least one :class:`CategoryCitation` /
:class:`CategoryCitationSource`, preserving the explainability chain back to
BOE, AEAT help, or Manual práctico evidence. :func:`effective_usage_ratio`
applies only the factual proportionality multiplier; modelo applicability,
casilla routing, and filing-grade legal treatment remain in
:mod:`domain.calculations.registry` and the application source mesh.

See Also:
    :mod:`domain.usage_ratios`
        Stores operator overrides keyed by concrete
        :class:`SpendingCategory` values whose proportionality kind permits a
        user ratio.
    :mod:`domain.renta`
        Evaluates category profiles and citations into Renta deductible-expense
        observations.
    :mod:`application.ledger`
        Validates ledger ``category_id`` / ``usage_ratio_id`` facts before the
        application source mesh feeds modelo calculation.
    :mod:`domain.invoices`
        Declares a per-line ``spending_category_id`` slot shaped for these
        identifiers. It is NOT typed to this taxonomy and no aggregation
        consumer reads it today -- an earlier form of this entry claimed both,
        and a reader who trusted it would look for a coupling that does not
        exist.
    :mod:`domain.calculations.registry`
        Owns modelo applicability, binding declarations, formulas, and casilla
        routing outside this taxonomy surface.
"""

from __future__ import annotations

from ._corpus import load_category_profiles_from_manual
from ._profile import CategoryProfile, IvaDeductibilityHint
from ._proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapPeriod,
    StatutoryCapVariant,
    effective_usage_ratio,
    parse_http_url,
)
from ._registry import (
    category_profile_years,
    load_category_profiles,
    resolve_category_profiles,
)
from ._spending_category import (
    CATEGORY_FAMILY_MEMBERS,
    HOME_OFFICE_FAMILIES,
    SpendingCategory,
    SpendingCategoryFamily,
    categories_for_family,
    family_for,
    home_office_categories,
)

__all__ = [
    "CATEGORY_FAMILY_MEMBERS",
    "HOME_OFFICE_FAMILIES",
    "CategoryCitation",
    "CategoryCitationSource",
    "CategoryProfile",
    "IvaDeductibilityHint",
    "ProportionalityKind",
    "ProportionalityRule",
    "SpendingCategory",
    "SpendingCategoryFamily",
    "StatutoryCapPeriod",
    "StatutoryCapVariant",
    "categories_for_family",
    "category_profile_years",
    "effective_usage_ratio",
    "family_for",
    "home_office_categories",
    "load_category_profiles",
    "load_category_profiles_from_manual",
    "parse_http_url",
    "resolve_category_profiles",
]
