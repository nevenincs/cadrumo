"""Read-only spending-category profile registry."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from pydantic import ValidationError

from ...core.i18n import Translatable as tr  # noqa: N813
from ...core.paths import PROJECT_ROOT
from ._errors import CategoryValidationError
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
from ._spending_category import SpendingCategory

_DEFAULT_PROFILE_ROOT = PROJECT_ROOT / "registry" / "aeat" / "categories" / "profiles"


def load_category_profile_file(path: Path) -> Mapping[SpendingCategory, CategoryProfile]:
    """Load one year-keyed spending-category profile TOML file."""

    try:
        with path.open("rb") as fh:
            payload = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise CategoryValidationError(f"{path}: invalid category profile TOML: {exc}") from exc
    except OSError as exc:
        raise CategoryValidationError(f"{path}: cannot read category profile registry: {exc}") from exc

    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise CategoryValidationError(f"{path}: missing [[profiles]] entries")

    profiles: dict[SpendingCategory, CategoryProfile] = {}
    for index, raw_profile in enumerate(raw_profiles, start=1):
        if not isinstance(raw_profile, dict):
            raise CategoryValidationError(f"{path}: profiles[{index}] must be a table")
        try:
            profile = _parse_profile(cast("Mapping[str, Any]", raw_profile))
        except (ValidationError, ValueError) as exc:
            raise CategoryValidationError(f"{path}: invalid profiles[{index}]: {exc}") from exc
        if profile.category in profiles:
            raise CategoryValidationError(f"{path}: duplicate spending category {profile.category.value!r}")
        profiles[profile.category] = profile

    missing = sorted(category.value for category in set(SpendingCategory) - set(profiles))
    if missing:
        raise CategoryValidationError(f"{path}: category profile registry missing categories: {missing}")
    return MappingProxyType(profiles)


def load_category_profile_registry(
    root: Path = _DEFAULT_PROFILE_ROOT,
) -> Mapping[int, Mapping[SpendingCategory, CategoryProfile]]:
    """Load every committed year-keyed spending-category profile registry."""

    registries: dict[int, Mapping[SpendingCategory, CategoryProfile]] = {}
    for path in sorted(root.glob("*.toml")):
        try:
            year = int(path.stem)
        except ValueError as exc:
            raise CategoryValidationError(f"{path}: category profile filename must be a year") from exc
        registries[year] = load_category_profile_file(path)
    if not registries:
        raise CategoryValidationError(f"{root}: no category profile TOML files found")
    return MappingProxyType(registries)


def resolve_category_profiles(year: int) -> Mapping[SpendingCategory, CategoryProfile]:
    """Return the exact category profile registry for ``year``."""

    profiles = CATEGORY_PROFILE_REGISTRY_BY_YEAR.get(year)
    if profiles is None:
        raise CategoryValidationError(f"no category profile registry registered for year={year}")
    return profiles


def _parse_profile(raw_profile: Mapping[str, Any]) -> CategoryProfile:
    category = SpendingCategory(str(raw_profile.get("category")))
    raw_rule = raw_profile.get("proportionality")
    if not isinstance(raw_rule, dict):
        raise CategoryValidationError(f"profile {category.value!r} must declare [profiles.proportionality]")
    raw_vat_hint = raw_profile.get("vat_hint")
    return CategoryProfile.model_validate(
        {
            "category": category,
            "display_label": tr(str(raw_profile.get("display_label"))),
            "proportionality": _parse_rule(cast("Mapping[str, Any]", raw_rule)),
            "vat_hint": VatCategory(str(raw_vat_hint)) if raw_vat_hint is not None else None,
        }
    )


def _parse_rule(raw_rule: Mapping[str, Any]) -> ProportionalityRule:
    raw_variants = raw_rule.get("statutory_cap_variants", ())
    if not isinstance(raw_variants, list | tuple):
        raise CategoryValidationError("statutory_cap_variants must be a list")
    raw_citations = raw_rule.get("citations", ())
    if not isinstance(raw_citations, list | tuple):
        raise CategoryValidationError("citations must be a list")
    return ProportionalityRule.model_validate(
        {
            "kind": ProportionalityKind(str(raw_rule.get("kind"))),
            "fixed_pct": _decimal_or_none(raw_rule.get("fixed_pct")),
            "default_ratio": _decimal_or_none(raw_rule.get("default_ratio")),
            "statutory_cap_eur_per_day": _decimal_or_none(raw_rule.get("statutory_cap_eur_per_day")),
            "statutory_cap_eur": _decimal_or_none(raw_rule.get("statutory_cap_eur")),
            "statutory_cap_period": _cap_period_or_none(raw_rule.get("statutory_cap_period")),
            "statutory_cap_variants": tuple(
                _parse_cap_variant(cast("Mapping[str, Any]", raw_variant)) for raw_variant in raw_variants
            ),
            "citations": tuple(
                _parse_citation(cast("Mapping[str, Any]", raw_citation)) for raw_citation in raw_citations
            ),
            "notes": tr(str(raw_rule.get("notes"))),
        }
    )


def _parse_cap_variant(raw_variant: Mapping[str, Any]) -> StatutoryCapVariant:
    return StatutoryCapVariant.model_validate(
        {
            "id": raw_variant.get("id"),
            "label": tr(str(raw_variant.get("label"))),
            "statutory_cap_eur_per_day": _decimal_or_none(raw_variant.get("statutory_cap_eur_per_day")),
        }
    )


def _parse_citation(raw_citation: Mapping[str, Any]) -> CategoryCitation:
    url = raw_citation.get("url")
    if not isinstance(url, str):
        raise CategoryValidationError("citation url must be a string")
    return CategoryCitation.model_validate(
        {
            "source": CategoryCitationSource(str(raw_citation.get("source"))),
            "reference": raw_citation.get("reference"),
            "locator": raw_citation.get("locator"),
            "url": parse_http_url(url),
            "quote": tr(str(raw_citation.get("quote"))),
        }
    )


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool | float):
        raise CategoryValidationError("decimal profile values must not be booleans or floats")
    return Decimal(str(value))


def _cap_period_or_none(value: Any) -> StatutoryCapPeriod | None:
    if value is None:
        return None
    return StatutoryCapPeriod(str(value))


CATEGORY_PROFILE_REGISTRY_BY_YEAR: Mapping[int, Mapping[SpendingCategory, CategoryProfile]] = (
    load_category_profile_registry()
)
CATEGORY_PROFILES_2025: Mapping[SpendingCategory, CategoryProfile] = resolve_category_profiles(2025)

__all__ = [
    "CATEGORY_PROFILES_2025",
    "CATEGORY_PROFILE_REGISTRY_BY_YEAR",
    "load_category_profile_file",
    "load_category_profile_registry",
    "resolve_category_profiles",
]
