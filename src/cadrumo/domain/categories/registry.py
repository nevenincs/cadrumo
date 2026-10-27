"""Artifact-backed spending-category profile registry."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ...core.citation_grounding import CitationGrounding
from ...core.i18n.translatable import Translatable as tr
from ...core.text_fold import normalise_corpus_text
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
)
from ..calculations.registry.facts.variants import FactSelector
from ..calculations.registry.schema_base import DateAxis
from .errors import CategoryValidationError
from .iva_hint import require_iva_deductibility_hint
from .profile import CategoryProfile
from .proportionality import (
    ANNUAL_EDITION_CITATION_SOURCES,
    CategoryCitation,
    CategoryCitationSource,
    IvaMixedUseRule,
    IvaMixedUseShare,
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
    return MappingProxyType(
        {
            category: _resolve_profile(category, year, materialise_schedule=materialise_schedule, operation=operation)
            for category in spending_category_tokens(
                effective_date=date(year, 12, 31),
                authority=operation,
            )
        }
    )


def resolve_category_profile(
    category: SpendingCategory,
    year: int,
    *,
    operation: PinnedAuthorityOperation,
) -> CategoryProfile:
    """Resolve one category's profile for one exact filing year.

    For a per-row reader that needs a single category: resolving the whole
    catalogue for each ledger row would repeat every other category's work.
    """
    return _resolve_profile(category, year, materialise_schedule=True, operation=operation)


def _resolve_profile(
    category: SpendingCategory,
    year: int,
    *,
    materialise_schedule: bool,
    operation: PinnedAuthorityOperation,
) -> CategoryProfile:
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
    return _profile_from_authority_fact(
        fact,
        operation=operation,
        year=year,
        materialise_schedule=materialise_schedule,
    )


def _profile_from_authority_fact(
    resolved: ResolvedMappingFact,
    *,
    operation: PinnedAuthorityOperation,
    year: int,
    materialise_schedule: bool = True,
) -> CategoryProfile:
    values = {str(entry.key): entry.value for entry in resolved.payload.entries}
    category = str(resolved.matched_selectors[0].value)
    citations = _category_citations(values, resolved=resolved, root="citation")
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
        "citations": citations,
        "fixed_pct": values.get("fixed_pct"),
        "statutory_multiplier": values.get("statutory_multiplier"),
        "iva_mixed_use": _iva_mixed_use_rule(values, resolved=resolved, category=category),
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


def _iva_mixed_use_rule(
    values: Mapping[str, object],
    *,
    resolved: ResolvedMappingFact,
    category: str,
) -> IvaMixedUseRule | None:
    """Rebuild the category's IVA treatment of MIXED-use rows, when it declares one."""
    share = values.get("iva_mixed_use_share")
    citations = _category_citations(values, resolved=resolved, root="iva_citation")
    if share is None:
        if citations:
            raise CategoryValidationError(
                f"category authority for {category} cites an IVA treatment it does not declare",
            )
        return None
    try:
        return IvaMixedUseRule(share=IvaMixedUseShare(str(share)), citations=citations)
    except (ValueError, ValidationError) as exc:
        raise CategoryValidationError(
            f"category authority carries an invalid IVA treatment for {category}: {exc}"
        ) from exc


def _category_citations(
    values: Mapping[str, object],
    *,
    resolved: ResolvedMappingFact,
    root: str,
) -> tuple[CategoryCitation, ...]:
    citations: list[CategoryCitation] = []
    index = 0
    while f"{root}.{index}.source" in values:
        prefix = f"{root}.{index}"
        citation = CategoryCitation.model_validate(
            {
                "source": CategoryCitationSource(str(values[f"{prefix}.source"])),
                "reference": str(values[f"{prefix}.reference"]),
                "locator": str(values[f"{prefix}.locator"]),
                "url": parse_http_url(str(values[f"{prefix}.url"])),
                "quote": str(values.get(f"{prefix}.quote", "")),
                "grounding": CitationGrounding(str(values[f"{prefix}.grounding"])),
                "grounding_reason": str(values.get(f"{prefix}.grounding_reason", "")),
                "legal_ref": str(values[f"{prefix}.legal_ref"]) if f"{prefix}.legal_ref" in values else None,
                "source_ref": str(values[f"{prefix}.source_ref"]) if f"{prefix}.source_ref" in values else None,
                "valid_from": values[f"{prefix}.valid_from"],
                "valid_to": values[f"{prefix}.valid_to"],
            }
        )
        _require_edition_quotation_is_build_checked(citation, resolved=resolved)
        citations.append(citation)
        index += 1
    return tuple(citations)


def _require_edition_quotation_is_build_checked(
    citation: CategoryCitation,
    *,
    resolved: ResolvedMappingFact,
) -> None:
    """Refuse a verified edition quotation the registry build never checked.

    The build checks each variant's ``source_citations`` text against the
    bundled edition it names. A verified Manual quotation is evidence only if
    it lies inside one of those checked texts for its own edition; otherwise
    nothing has read it against the corpus.
    """
    if citation.source not in ANNUAL_EDITION_CITATION_SOURCES or citation.source_ref is None:
        return
    quotation = normalise_corpus_text(citation.quote)
    checked = any(
        quotation in normalise_corpus_text(required)
        for source_citation in resolved.source_citations
        if source_citation.source_ref == citation.source_ref
        for required in source_citation.required_text
    )
    if not checked:
        raise CategoryValidationError(
            f"verified citation {citation.reference!r}/{citation.locator!r} quotes {citation.source_ref!r}, but no "
            "source citation of its variant carries that text for the build to check",
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
    "resolve_category_profile",
    "resolve_category_profiles",
]
