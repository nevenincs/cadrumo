"""Development-only compilation of authored spending-category profiles."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import cast

from pydantic import ValidationError

from cadrumo.core.citation_grounding import CitationGrounding
from cadrumo.core.decimal.coercion import coerce_decimal
from cadrumo.core.i18n import Translatable as tr
from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.core.toml import read_toml
from cadrumo.core.type_adapters import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER
from cadrumo.core.validity_window import ValidityWindow, years_covered_by_any, years_covered_by_every_group
from cadrumo.domain.calculations.registry.facts.schema import (
    FactOwnership,
    FactSelector,
    GovernedFact,
    GovernedFactFamily,
    GovernedFactVariant,
    MappingFactEntry,
    MappingFactPayload,
    ScalarFactPayload,
)
from cadrumo.domain.calculations.registry.loader_cache import toml_file_fingerprint
from cadrumo.domain.calculations.registry.loader_fingerprints import RegistryPathFingerprints
from cadrumo.domain.calculations.registry.schema_base import DateAxis, SourceCitation
from cadrumo.domain.categories.errors import CategoryValidationError
from cadrumo.domain.categories.profile import CategoryProfile, IvaDeductibilityHint
from cadrumo.domain.categories.proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapAmount,
    StatutoryCapPeriod,
    StatutoryCapVariant,
    parse_http_url,
)
from cadrumo.domain.categories.registry import (
    CATEGORY_FACT_PROVIDER_DIRECTORY,
    CATEGORY_PROFILE_FACT_ID,
    CATEGORY_STATUTORY_CAP_FACT_ID,
)
from cadrumo.domain.categories.spending_category import SpendingCategory

_CATEGORY_CITATION_SOURCE_REFS = {
    CategoryCitationSource.LEY_IRPF: "lirpf-cuota-chain-authority",
    CategoryCitationSource.REGLAMENTO_IRPF: "boe-rirpf-category-profile-authority",
}


@lru_cache(maxsize=8)
def _load_category_profiles_cached(
    path: str, byte_count: int, modified_ns: int
) -> Mapping[SpendingCategory, CategoryProfile]:
    del byte_count, modified_ns
    target = Path(path)
    payload = read_toml(target, error_factory=CategoryValidationError)
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise CategoryValidationError(f"{target}: missing [[profiles]] entries")
    profiles: dict[SpendingCategory, CategoryProfile] = {}
    for index, raw_profile in enumerate(OBJECT_TUPLE_ADAPTER.validate_python(raw_profiles), start=1):
        if not isinstance(raw_profile, Mapping):
            raise CategoryValidationError(f"{target}: profiles[{index}] must be a table")
        try:
            profile = _parse_profile(STR_KEYED_MAPPING_ADAPTER.validate_python(raw_profile))
        except (ValidationError, ValueError) as exc:
            raise CategoryValidationError(f"{target}: invalid profiles[{index}]: {exc}") from exc
        if profile.category in profiles:
            raise CategoryValidationError(f"{target}: duplicate spending category {profile.category.value!r}")
        profiles[profile.category] = profile
    missing = sorted(category.value for category in set(SpendingCategory) - set(profiles))
    if missing:
        raise CategoryValidationError(f"{target}: category profile registry missing categories: {missing}")
    return MappingProxyType(profiles)


def load_category_profiles(path: Path) -> Mapping[SpendingCategory, CategoryProfile]:
    """Parse one authored profile corpus for development publication."""
    resolved = path.resolve()
    try:
        stat = resolved.stat()
    except OSError as exc:
        raise CategoryValidationError(f"{resolved}: cannot stat category profile registry: {exc}") from exc
    return _load_category_profiles_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


def _grounding_windows(profile: CategoryProfile) -> tuple[ValidityWindow, ...]:
    rule = profile.proportionality
    if not rule.statutory_cap_schedule:
        return tuple(citation.window for citation in rule.citations)
    both = sorted(
        years_covered_by_any(citation.window for citation in rule.citations)
        & years_covered_by_any(amount.window for amount in rule.statutory_cap_schedule)
    )
    return tuple(ValidityWindow(valid_from=date(year, 1, 1), valid_to=date(year, 12, 31)) for year in both)


def compile_category_profile_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    """Project the retained category corpus into typed governed facts."""
    profiles = load_category_profiles(registry_root.resolve() / CATEGORY_FACT_PROVIDER_DIRECTORY / "profiles.toml")
    years = sorted(years_covered_by_every_group(_grounding_windows(profile) for profile in profiles.values()))
    profile_variants = tuple(
        _category_profile_fact_variant(profile, year) for profile in profiles.values() for year in years
    )
    cap_variants = tuple(
        _category_cap_fact_variant(profile, amount)
        for profile in profiles.values()
        for amount in profile.proportionality.statutory_cap_schedule
    )
    facts = [
        GovernedFact(fact_id=CATEGORY_PROFILE_FACT_ID, family=GovernedFactFamily.MAPPING, variants=profile_variants)
    ]
    if cap_variants:
        facts.append(
            GovernedFact(
                fact_id=CATEGORY_STATUTORY_CAP_FACT_ID, family=GovernedFactFamily.SCALAR, variants=cap_variants
            )
        )
    return tuple(facts)


def collect_category_profile_fact_fingerprints(registry_root: Path) -> RegistryPathFingerprints:
    target = registry_root.resolve() / CATEGORY_FACT_PROVIDER_DIRECTORY / "profiles.toml"
    return (toml_file_fingerprint(target),) if target.is_file() else ()


def reset_category_profile_fact_provider() -> None:
    _load_category_profiles_cached.cache_clear()


def _category_profile_fact_variant(profile: CategoryProfile, year: int) -> GovernedFactVariant:
    citations = tuple(citation for citation in profile.proportionality.citations if citation.window.covers_year(year))
    authoritative = tuple(c for c in citations if c.source in _CATEGORY_CITATION_SOURCE_REFS and c.quote)
    return GovernedFactVariant(
        variant_id=f"{CATEGORY_PROFILE_FACT_ID}:{profile.category.value}:{year}",
        selectors=(FactSelector(name="category", value=profile.category.value),),
        date_axis=DateAxis.FILING_PERIOD,
        valid_from=date(year, 1, 1),
        valid_to=date(year, 12, 31),
        payload=MappingFactPayload(entries=_profile_fact_entries(profile, citations)),
        legal_refs=_citation_legal_refs(authoritative),
        source_refs=tuple(dict.fromkeys(_citation_source_ref(c) for c in authoritative)),
        source_citations=_source_citations(authoritative),
        review_status=RevisionReviewStatus.AGENT_REVIEWED,
        ownership=FactOwnership.GENERATED,
    )


def _category_cap_fact_variant(profile: CategoryProfile, amount: StatutoryCapAmount) -> GovernedFactVariant:
    citations = tuple(
        c
        for c in profile.proportionality.citations
        if c.window.valid_from <= amount.window.valid_from and c.window.valid_to >= amount.window.valid_to
    )
    authoritative = tuple(c for c in citations if c.source in _CATEGORY_CITATION_SOURCE_REFS and c.quote)
    return GovernedFactVariant(
        variant_id=f"{CATEGORY_STATUTORY_CAP_FACT_ID}:{profile.category.value}:{amount.window.valid_from.year}",
        selectors=(FactSelector(name="category", value=profile.category.value),),
        date_axis=DateAxis.FILING_PERIOD,
        valid_from=amount.window.valid_from,
        valid_to=amount.window.valid_to,
        payload=ScalarFactPayload(value=amount.value, unit="eur"),
        legal_refs=_citation_legal_refs(authoritative),
        source_refs=tuple(dict.fromkeys(_citation_source_ref(c) for c in authoritative)),
        source_citations=_source_citations(authoritative),
        review_status=RevisionReviewStatus.AGENT_REVIEWED,
        ownership=FactOwnership.GENERATED,
    )


def _profile_fact_entries(
    profile: CategoryProfile, citations: tuple[CategoryCitation, ...]
) -> tuple[MappingFactEntry, ...]:
    rule = profile.proportionality
    values: list[tuple[str, str | Decimal | date]] = [
        ("display_label", str(profile.display_label)),
        ("proportionality_kind", rule.kind.value),
        ("notes", str(rule.notes)),
    ]
    if profile.iva_hint is not None:
        values.append(("iva_hint", profile.iva_hint.value))
    for name in (
        "fixed_pct",
        "default_ratio",
        "statutory_multiplier",
        "statutory_cap_eur_per_day",
        "statutory_cap_eur",
    ):
        if (value := getattr(rule, name)) is not None:
            values.append((name, value))
    if rule.statutory_cap_period is not None:
        values.append(("statutory_cap_period", rule.statutory_cap_period.value))
    for variant in rule.statutory_cap_variants:
        values.append((f"statutory_cap_variant.{variant.id}.label", str(variant.label)))
        if variant.statutory_cap_eur_per_day is not None:
            values.append((f"statutory_cap_variant.{variant.id}.eur_per_day", variant.statutory_cap_eur_per_day))
        if variant.statutory_cap_eur is not None:
            values.append((f"statutory_cap_variant.{variant.id}.eur", variant.statutory_cap_eur))
    for index, citation in enumerate(citations):
        prefix = f"citation.{index}"
        values.extend(
            (
                (f"{prefix}.source", citation.source.value),
                (f"{prefix}.reference", citation.reference),
                (f"{prefix}.locator", citation.locator),
                (f"{prefix}.url", str(citation.url)),
                (f"{prefix}.grounding", citation.grounding.value),
                (f"{prefix}.valid_from", citation.valid_from),
                (f"{prefix}.valid_to", citation.valid_to),
            )
        )
        if citation.quote:
            values.append((f"{prefix}.quote", citation.quote))
        if citation.grounding_reason:
            values.append((f"{prefix}.grounding_reason", citation.grounding_reason))
        if citation.legal_ref is not None:
            values.append((f"{prefix}.legal_ref", citation.legal_ref))
    return tuple(MappingFactEntry(key=key, value=value) for key, value in values)


def _citation_source_ref(citation: CategoryCitation) -> str:
    return _CATEGORY_CITATION_SOURCE_REFS[citation.source]


def _source_citations(citations: tuple[CategoryCitation, ...]) -> tuple[SourceCitation, ...]:
    grouped: dict[str, list[str]] = {}
    for citation in citations:
        grouped.setdefault(_citation_source_ref(citation), []).append(citation.quote)
    return tuple(
        SourceCitation(source_ref=ref, required_text=tuple(dict.fromkeys(text))) for ref, text in grouped.items()
    )


def _citation_legal_refs(citations: tuple[CategoryCitation, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(c.legal_ref for c in citations if c.legal_ref is not None))


def _parse_profile(raw_profile: object) -> CategoryProfile:
    if not isinstance(raw_profile, dict):
        raise CategoryValidationError("profile entry must be a table")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_profile)
    category = SpendingCategory(str(data.get("category")))
    raw_rule = cast("dict[str, object] | None", data.get("proportionality"))
    if not isinstance(raw_rule, dict):
        raise CategoryValidationError(f"profile {category.value!r} must declare [profiles.proportionality]")
    raw_iva_hint = data.get("iva_hint")
    return CategoryProfile.model_validate(
        {
            "category": category,
            "display_label": tr(str(data.get("display_label"))),
            "proportionality": _parse_rule(raw_rule),
            "iva_hint": IvaDeductibilityHint(str(raw_iva_hint)) if raw_iva_hint is not None else None,
        }
    )


def _parse_rule(raw_rule: object) -> ProportionalityRule:
    if not isinstance(raw_rule, dict):
        raise CategoryValidationError("proportionality rule must be a table")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_rule)
    raw_variants, raw_citations, raw_schedule = (
        data.get("statutory_cap_variants", ()),
        data.get("citations", ()),
        data.get("statutory_cap_schedule", ()),
    )
    if not all(isinstance(rows, list | tuple) for rows in (raw_variants, raw_citations, raw_schedule)):
        raise CategoryValidationError("profile rule collections must be lists")
    return ProportionalityRule.model_validate(
        {
            "kind": ProportionalityKind(str(data.get("kind"))),
            "fixed_pct": _decimal_or_none(data.get("fixed_pct")),
            "default_ratio": _decimal_or_none(data.get("default_ratio")),
            "statutory_multiplier": _decimal_or_none(data.get("statutory_multiplier")),
            "statutory_cap_eur_per_day": _decimal_or_none(data.get("statutory_cap_eur_per_day")),
            "statutory_cap_eur": _decimal_or_none(data.get("statutory_cap_eur")),
            "statutory_cap_period": _cap_period_or_none(data.get("statutory_cap_period")),
            "statutory_cap_variants": tuple(
                _parse_cap_variant(row) for row in OBJECT_TUPLE_ADAPTER.validate_python(raw_variants)
            ),
            "statutory_cap_schedule": tuple(
                _parse_cap_amount(row) for row in OBJECT_TUPLE_ADAPTER.validate_python(raw_schedule)
            ),
            "citations": tuple(_parse_citation(row) for row in OBJECT_TUPLE_ADAPTER.validate_python(raw_citations)),
            "notes": tr(str(data.get("notes"))),
        }
    )


def _parse_cap_amount(raw: object) -> StatutoryCapAmount:
    if not isinstance(raw, dict):
        raise CategoryValidationError("statutory_cap_schedule entries must be tables")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw)
    return StatutoryCapAmount.model_validate(
        {
            "value": _decimal_or_none(data.get("value")),
            "valid_from": data.get("valid_from"),
            "valid_to": data.get("valid_to"),
        }
    )


def _parse_cap_variant(raw: object) -> StatutoryCapVariant:
    if not isinstance(raw, dict):
        raise CategoryValidationError("statutory_cap_variants entries must be tables")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw)
    return StatutoryCapVariant.model_validate(
        {
            "id": data.get("id"),
            "label": tr(str(data.get("label"))),
            "statutory_cap_eur_per_day": _decimal_or_none(data.get("statutory_cap_eur_per_day")),
            "statutory_cap_eur": _decimal_or_none(data.get("statutory_cap_eur")),
        }
    )


def _parse_citation(raw: object) -> CategoryCitation:
    if not isinstance(raw, dict):
        raise CategoryValidationError("citations entries must be tables")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw)
    url = data.get("url")
    if not isinstance(url, str):
        raise CategoryValidationError("citation url must be a string")
    return CategoryCitation.model_validate(
        {
            "source": CategoryCitationSource(str(data.get("source"))),
            "reference": data.get("reference"),
            "locator": data.get("locator"),
            "url": parse_http_url(url),
            "quote": str(data.get("quote") or ""),
            "grounding": CitationGrounding(str(data.get("grounding") or "verified")),
            "grounding_reason": str(data.get("grounding_reason") or ""),
            "legal_ref": data.get("legal_ref"),
            "valid_from": data.get("valid_from"),
            "valid_to": data.get("valid_to"),
        }
    )


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool | float):
        raise CategoryValidationError("decimal profile values must not be booleans or floats")
    result = coerce_decimal(value)
    if result is None:
        raise CategoryValidationError(f"decimal profile value {value!r} could not be parsed")
    return result


def _cap_period_or_none(value: object) -> StatutoryCapPeriod | None:
    return None if value is None else StatutoryCapPeriod(str(value))
