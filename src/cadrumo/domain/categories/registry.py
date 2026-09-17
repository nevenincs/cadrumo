"""Artifact-backed spending-category profile registry."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ...core.citation_grounding import CitationGrounding
from ...core.i18n.translatable import Translatable as tr
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
)
from ..calculations.registry.facts.schema import FactSelector
from ..calculations.registry.schema_base import DateAxis
from .errors import CategoryValidationError
from .iva_hint import require_iva_deductibility_hint
from .profile import CategoryProfile
from .proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityRule,
    StatutoryCapAmount,
    StatutoryCapVariant,
    parse_http_url,
)
from .proportionality_catalogue import require_proportionality_kind, require_statutory_cap_period
from .spending_category import SpendingCategory
from .spending_category_catalogue import require_spending_category, spending_category_tokens

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation
CATEGORY_PROFILE_FACT_ID = "categories.profile"
CATEGORY_STATUTORY_CAP_FACT_ID = "categories.statutory-cap"
_CAP_VARIANT_PREFIX = "statutory_cap_variant."
_CAP_VARIANT_FIELDS = {"label": "label", "eur_per_day": "statutory_cap_eur_per_day", "eur": "statutory_cap_eur"}


def load_category_profiles(
    *,
    operation: PinnedAuthorityOperation,
) -> Mapping[SpendingCategory, CategoryProfile]:
    """Return the latest profiles while retaining each declared dated cap schedule."""
    years = category_profile_years(operation=operation)
    if not years:
        raise CategoryValidationError("installed authority has no complete category profile coverage")
    return _resolve_profiles(max(years), materialise_schedule=False, operation=operation)


def category_profile_years(
    *,
    operation: PinnedAuthorityOperation,
) -> frozenset[int]:
    """Return the supported filing years every category profile resolves for.

    Profiles resolve through the registry's temporal projection, so coverage is
    the registry's enumerated support span rather than a reading of each
    variant's own window.
    """
    return frozenset[int](operation.supported_filing_years().years)


def resolve_category_profiles(
    year: int,
    *,
    operation: PinnedAuthorityOperation,
) -> Mapping[SpendingCategory, CategoryProfile]:
    """Resolve every category profile for one exact filing year."""
    return _resolve_profiles(year, materialise_schedule=True, operation=operation)


def _resolve_profiles(
    year: int,
    *,
    materialise_schedule: bool,
    operation: PinnedAuthorityOperation,
) -> Mapping[SpendingCategory, CategoryProfile]:
    profiles: dict[SpendingCategory, CategoryProfile] = {}
    for category in spending_category_tokens(
        effective_date=date(year, 12, 31),
        authority=operation,
    ):
        try:
            fact = operation.resolve_governed_fact(
                MappingFactQuery(
                    fact_id=CATEGORY_PROFILE_FACT_ID,
                    date_axis=DateAxis.FILING_PERIOD,
                    effective_date=date(year, 12, 31),
                    selectors=(FactSelector(name="category", value=category.value),),
                )
            )
        except RegistryValidationError as exc:
            raise CategoryValidationError(
                f"category authority has no profile for {category.value}/{year}; the year is unsupported"
            ) from exc
        if not isinstance(fact, ResolvedMappingFact):
            raise CategoryValidationError("category profile authority returned a non-mapping fact")
        profiles[category] = _profile_from_authority_fact(
            fact,
            operation=operation,
            year=year,
            materialise_schedule=materialise_schedule,
        )
    return MappingProxyType(profiles)


def _profile_from_authority_fact(
    resolved: ResolvedMappingFact,
    *,
    operation: PinnedAuthorityOperation,
    year: int,
    materialise_schedule: bool = True,
) -> CategoryProfile:
    values = {str(entry.key): entry.value for entry in resolved.payload.entries}
    citations: list[CategoryCitation] = []
    index = 0
    while f"citation.{index}.source" in values:
        prefix = f"citation.{index}"
        citations.append(
            CategoryCitation.model_validate(
                {
                    "source": CategoryCitationSource(str(values[f"{prefix}.source"])),
                    "reference": str(values[f"{prefix}.reference"]),
                    "locator": str(values[f"{prefix}.locator"]),
                    "url": parse_http_url(str(values[f"{prefix}.url"])),
                    "quote": str(values.get(f"{prefix}.quote", "")),
                    "grounding": CitationGrounding(str(values[f"{prefix}.grounding"])),
                    "grounding_reason": str(values.get(f"{prefix}.grounding_reason", "")),
                    "legal_ref": str(values[f"{prefix}.legal_ref"]) if f"{prefix}.legal_ref" in values else None,
                    "valid_from": values[f"{prefix}.valid_from"],
                    "valid_to": values[f"{prefix}.valid_to"],
                }
            )
        )
        index += 1
    category = str(resolved.matched_selectors[0].value)
    category_token = require_spending_category(
        category,
        effective_date=date(year, 12, 31),
        authority=operation,
    )
    projected_kind = require_proportionality_kind(
        values["proportionality_kind"],
        effective_date=date(year, 12, 31),
        authority=operation,
    )
    variants = _cap_variants_from_entries(values, category=category)
    cap = values.get("statutory_cap_eur")
    schedule: tuple[StatutoryCapAmount, ...] = ()
    if projected_kind.is_statutory_cap and not variants and cap is None and "statutory_cap_eur_per_day" not in values:
        # The profile carries no amount of its own, so the cap is year-referenced
        # and its amounts live only in the dated cap fact.
        cap = _resolve_statutory_cap(operation=operation, category=category, year=year).payload.value
        if not materialise_schedule:
            schedule = _declared_cap_schedule(operation=operation, category=category)
            cap = None
    cap_period = values.get("statutory_cap_period")
    rule = {
        "kind": projected_kind,
        "notes": tr(str(values["notes"])),
        "citations": tuple(citations),
        "fixed_pct": values.get("fixed_pct"),
        "default_ratio": values.get("default_ratio"),
        "statutory_multiplier": values.get("statutory_multiplier"),
        "statutory_cap_eur_per_day": values.get("statutory_cap_eur_per_day"),
        "statutory_cap_eur": cap,
        "statutory_cap_period": (
            None
            if cap_period is None
            else require_statutory_cap_period(
                cap_period,
                effective_date=date(year, 12, 31),
                authority=operation,
            )
        ),
        "statutory_cap_variants": variants,
        "statutory_cap_schedule": schedule,
    }
    try:
        proportionality = ProportionalityRule.model_validate(rule)
    except ValidationError as exc:
        raise CategoryValidationError(f"category authority carries an invalid rule for {category}: {exc}") from exc
    return CategoryProfile(
        category=category_token,
        display_label=tr(str(values["display_label"])),
        proportionality=proportionality,
        iva_hint=(
            require_iva_deductibility_hint(
                values["iva_hint"],
                authority=operation,
                effective_date=date(year, 12, 31),
            )
            if "iva_hint" in values
            else None
        ),
    )


def _declared_cap_schedule(
    *,
    operation: PinnedAuthorityOperation,
    category: str,
) -> tuple[StatutoryCapAmount, ...]:
    """Return the cap amount the registry resolves for each supported filing year."""
    schedule: list[StatutoryCapAmount] = []
    for year in operation.supported_filing_years().years:
        resolved = _resolve_statutory_cap(operation=operation, category=category, year=year)
        schedule.append(
            StatutoryCapAmount.model_validate(
                {"value": resolved.payload.value, "valid_from": date(year, 1, 1), "valid_to": date(year, 12, 31)}
            )
        )
    return tuple(schedule)


def _resolve_statutory_cap(
    *,
    operation: PinnedAuthorityOperation,
    category: str,
    year: int,
) -> ResolvedScalarFact:
    """Resolve one category's statutory cap amount for one filing year."""
    try:
        resolved = operation.resolve_governed_fact(
            ScalarFactQuery(
                fact_id=CATEGORY_STATUTORY_CAP_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(year, 12, 31),
                selectors=(FactSelector(name="category", value=category),),
            )
        )
    except RegistryValidationError as exc:
        raise CategoryValidationError(f"category authority has no dated statutory cap for {category}/{year}") from exc
    if not isinstance(resolved, ResolvedScalarFact):
        raise CategoryValidationError(f"category cap authority returned a non-scalar fact for {category}")
    return resolved


def _cap_variants_from_entries(values: Mapping[str, object], *, category: str) -> tuple[StatutoryCapVariant, ...]:
    """Rebuild the condition-selected cap variants the profile fact projects.

    Each variant arrives as ``statutory_cap_variant.<id>.<field>`` entries. An
    unrecognised field is refused rather than skipped, because dropping it
    could silently discard the amount the variant exists to carry.
    """
    fields: dict[str, dict[str, object]] = {}
    for key, value in values.items():
        if not key.startswith(_CAP_VARIANT_PREFIX):
            continue
        variant_id, _, field = key.removeprefix(_CAP_VARIANT_PREFIX).rpartition(".")
        if not variant_id or field not in _CAP_VARIANT_FIELDS:
            raise CategoryValidationError(f"category authority carries an unknown cap variant entry {key!r}")
        fields.setdefault(variant_id, {})[_CAP_VARIANT_FIELDS[field]] = value
    variants: list[StatutoryCapVariant] = []
    for variant_id, declared in fields.items():
        if "label" not in declared:
            raise CategoryValidationError(f"category authority cap variant {category}/{variant_id} has no label")
        try:
            variants.append(
                StatutoryCapVariant.model_validate({**declared, "id": variant_id, "label": tr(str(declared["label"]))})
            )
        except ValidationError as exc:
            raise CategoryValidationError(
                f"category authority carries an invalid cap variant {category}/{variant_id}: {exc}"
            ) from exc
    return tuple(variants)


__all__ = [
    "CATEGORY_PROFILE_FACT_ID",
    "CATEGORY_STATUTORY_CAP_FACT_ID",
    "category_profile_years",
    "load_category_profiles",
    "resolve_category_profiles",
]
