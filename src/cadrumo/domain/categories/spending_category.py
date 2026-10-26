"""Opaque spending-category tokens and mechanical family buckets.

The governed deductible-category vocabulary and its family membership live in
the dated ``categories.profile`` facts registry.  This module retains only the
opaque token shape and the coarse family buckets used by presentation and
aggregation mechanics.  Callers obtain category tokens through the typed
projection in :mod:`spending_category_catalogue`.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ...core.errors.hierarchy import CoreValidationError, pydantic_validation_boundary

if TYPE_CHECKING:
    from ..calculations.registry.governed_fact_scope import GovernedFactSource


class SpendingCategory(str):
    """Registry-projected deductible-spending token.

    Category membership is governing-body data, not a Python enum catalogue.
    Direct construction is therefore refused; :meth:`from_registry` is used
    only by the typed facts projection, while Pydantic input is resolved
    through that same projection.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct a token only when the facts projection has validated it."""
        if not _registry_validated:
            raise TypeError("SpendingCategory tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("SpendingCategory token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Materialise one token after a registry catalogue has declared it."""
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        """Coerce Pydantic/string input through the facts authority."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            from .spending_category_catalogue import require_spending_category

            token = require_spending_category(value)
            return cls.from_registry(token.value)
        raise CoreValidationError("SpendingCategory must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Register fail-closed facts-backed validation for Pydantic models."""
        return core_schema.no_info_plain_validator_function(
            pydantic_validation_boundary(cls._require_registry_token),
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the persisted registry token."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the token for diagnostics where an enum name was expected."""
        return str(self)


class SpendingCategoryFamily(StrEnum):
    """Mechanical coarse buckets used by CLI listings and classifiers.

    These values are presentation/aggregation grouping tokens, not the legal
    category catalogue.  Their retained membership is resolved from the facts
    projection by :func:`categories_for_family`.
    """

    SOCIAL_SECURITY = "social_security"
    PREMISES = "premises"
    HOME_OFFICE_SUMINISTROS = "home_office_suministros"
    HOME_OFFICE_OWNERSHIP = "home_office_ownership"
    TELECOMS = "telecoms"
    OFFICE = "office"
    VEHICLE = "vehicle"
    MEALS = "meals"
    PROFESSIONAL_SERVICES = "professional_services"
    TRAVEL = "travel"
    INSURANCE = "insurance"
    FINANCIAL = "financial"
    DIRECT_COSTS = "direct_costs"
    TAXES = "taxes"


# The family pair is a mechanical grouping used for dwelling-ratio routing.
# Category membership itself is projected from the facts registry.
HOME_OFFICE_FAMILIES: frozenset[SpendingCategoryFamily] = frozenset(
    {
        SpendingCategoryFamily(SpendingCategoryFamily.HOME_OFFICE_SUMINISTROS),
        SpendingCategoryFamily(SpendingCategoryFamily.HOME_OFFICE_OWNERSHIP),
    },
)


def family_for(
    category: SpendingCategory,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SpendingCategoryFamily:
    """Return the registry-declared coarse family for one category."""
    from .spending_category_catalogue import resolve_spending_category_catalogue

    return resolve_spending_category_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).family_for(category)


def categories_for_family(
    family: SpendingCategoryFamily,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[SpendingCategory, ...]:
    """Return registry-declared category tokens for one mechanical family."""
    from .spending_category_catalogue import resolve_spending_category_catalogue

    return resolve_spending_category_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).categories_for_family(family)


def home_office_categories(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> frozenset[SpendingCategory]:
    """Return registry categories in the retained home-office buckets."""
    return frozenset(
        category
        for family in HOME_OFFICE_FAMILIES
        for category in categories_for_family(family, effective_date=effective_date, authority=authority)
    )


__all__ = [
    "HOME_OFFICE_FAMILIES",
    "SpendingCategory",
    "SpendingCategoryFamily",
    "categories_for_family",
    "family_for",
    "home_office_categories",
]
