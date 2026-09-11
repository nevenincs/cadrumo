"""Artifact-backed spending-category profile registry."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...core.citation_grounding import CitationGrounding
from ...core.i18n import Translatable as tr
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact, ScalarFactQuery
from ..calculations.registry.facts.schema import FactSelector
from ..calculations.registry.schema_base import DateAxis
from .errors import CategoryValidationError
from .profile import CategoryProfile, IvaDeductibilityHint
from .proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapPeriod,
    StatutoryCapVariant,
    parse_http_url,
)
from .spending_category import SpendingCategory

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority
CATEGORY_PROFILE_FACT_ID = "categories.profile"
CATEGORY_STATUTORY_CAP_FACT_ID = "categories.statutory-cap"
CATEGORY_FACT_PROVIDER_ID = "category-profiles"
CATEGORY_FACT_PROVIDER_DIRECTORY = "categories"
_CAP_VARIANT_PREFIX = "statutory_cap_variant."
_CAP_VARIANT_FIELDS = {"label": "label", "eur_per_day": "statutory_cap_eur_per_day", "eur": "statutory_cap_eur"}


def load_category_profiles() -> Mapping[SpendingCategory, CategoryProfile]:
    years = category_profile_years()
    if not years:
        raise CategoryValidationError("installed authority has no complete category profile coverage")
    return resolve_category_profiles(max(years))


def category_profile_years() -> frozenset[int]:
    from ..calculations.registry.authority import bundled_authority

    fact = bundled_authority().catalogues.facts.facts.get(CATEGORY_PROFILE_FACT_ID)
    if fact is None:
        return frozenset()
    grouped: dict[str, set[int]] = {}
    for variant in fact.variants:
        category = next((s.value for s in variant.selectors if s.name == "category"), None)
        if category is not None and variant.valid_to is not None:
            grouped.setdefault(category, set()).update(range(variant.valid_from.year, variant.valid_to.year + 1))
    return frozenset(set.intersection(*grouped.values())) if grouped else frozenset()


def resolve_category_profiles(year: int) -> Mapping[SpendingCategory, CategoryProfile]:
    from ..calculations.registry.authority import bundled_authority

    authority = bundled_authority()
    profiles: dict[SpendingCategory, CategoryProfile] = {}
    for category in SpendingCategory:
        fact = authority.resolve_governed_fact(
            MappingFactQuery(
                fact_id=CATEGORY_PROFILE_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(year, 12, 31),
                selectors=(FactSelector(name="category", value=category.value),),
            )
        )
        if not isinstance(fact, ResolvedMappingFact):
            raise CategoryValidationError("category profile authority returned a non-mapping fact")
        profiles[category] = _profile_from_authority_fact(fact, authority=authority, year=year)
    return MappingProxyType(profiles)


def _profile_from_authority_fact(
    resolved: ResolvedMappingFact, *, authority: ValidatedRegistryAuthority, year: int
) -> CategoryProfile:
    values = {str(entry.key): entry.value for entry in resolved.payload.entries}
    citations: list[CategoryCitation] = []
    index = 0
    while f"citation.{index}.source" in values:
        prefix = f"citation.{index}"
        citations.append(
            CategoryCitation(
                source=CategoryCitationSource(str(values[f"{prefix}.source"])),
                reference=str(values[f"{prefix}.reference"]),
                locator=str(values[f"{prefix}.locator"]),
                url=parse_http_url(str(values[f"{prefix}.url"])),
                quote=str(values.get(f"{prefix}.quote", "")),
                grounding=CitationGrounding(str(values[f"{prefix}.grounding"])),
                grounding_reason=str(values.get(f"{prefix}.grounding_reason", "")),
                legal_ref=str(values[f"{prefix}.legal_ref"]) if f"{prefix}.legal_ref" in values else None,
                valid_from=values[f"{prefix}.valid_from"],
                valid_to=values[f"{prefix}.valid_to"],
            )
        )
        index += 1
    category = resolved.matched_selectors[0].value
    variants = _cap_variants_from_entries(values, category=category)
    cap = values.get("statutory_cap_eur")
    if (
        values.get("proportionality_kind") == ProportionalityKind.STATUTORY_CAP.value
        and not variants
        and cap is None
        and "statutory_cap_eur_per_day" not in values
    ):
        # The profile carries no amount of its own, so the cap is year-referenced
        # and its amount for this year lives only in the dated cap fact.
        try:
            cap = authority.resolve_governed_fact(
                ScalarFactQuery(
                    fact_id=CATEGORY_STATUTORY_CAP_FACT_ID,
                    date_axis=DateAxis.FILING_PERIOD,
                    effective_date=date(year, 12, 31),
                    selectors=(FactSelector(name="category", value=category),),
                )
            ).payload.value
        except RegistryValidationError as exc:
            raise CategoryValidationError(
                f"category authority has no dated statutory cap for {category}/{year}"
            ) from exc
    cap_period = values.get("statutory_cap_period")
    rule = {
        "kind": ProportionalityKind(str(values["proportionality_kind"])),
        "notes": tr(str(values["notes"])),
        "citations": tuple(citations),
        "fixed_pct": values.get("fixed_pct"),
        "default_ratio": values.get("default_ratio"),
        "statutory_multiplier": values.get("statutory_multiplier"),
        "statutory_cap_eur_per_day": values.get("statutory_cap_eur_per_day"),
        "statutory_cap_eur": cap,
        "statutory_cap_period": None if cap_period is None else StatutoryCapPeriod(str(cap_period)),
        "statutory_cap_variants": variants,
    }
    return CategoryProfile(
        category=SpendingCategory(resolved.matched_selectors[0].value),
        display_label=tr(str(values["display_label"])),
        proportionality=ProportionalityRule.model_validate(rule),
        iva_hint=IvaDeductibilityHint(str(values["iva_hint"])) if "iva_hint" in values else None,
    )


def _cap_variants_from_entries(
    values: Mapping[str, object], *, category: str
) -> tuple[StatutoryCapVariant, ...]:
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
        variants.append(
            StatutoryCapVariant.model_validate(
                {**declared, "id": variant_id, "label": tr(str(declared["label"]))}
            )
        )
    return tuple(variants)


__all__ = [
    "CATEGORY_FACT_PROVIDER_DIRECTORY",
    "CATEGORY_FACT_PROVIDER_ID",
    "CATEGORY_PROFILE_FACT_ID",
    "CATEGORY_STATUTORY_CAP_FACT_ID",
    "category_profile_years",
    "load_category_profiles",
    "resolve_category_profiles",
]
