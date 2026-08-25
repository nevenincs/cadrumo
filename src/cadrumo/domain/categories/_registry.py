"""Read-only spending-category profile registry.

:func:`load_category_profile_registry` reads committed TOML profile files into
immutable mappings from :class:`SpendingCategory` to :class:`CategoryProfile`;
:func:`resolve_category_profiles` selects the exact year registry used by
classification and filing review surfaces.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import cast

from pydantic import ValidationError

from ...core import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER, read_toml, scan_directory
from ...core.decimal import coerce_decimal
from ...core.i18n import Translatable as tr
from ...core.paths import file_stat_fingerprint, path_stat_fingerprint
from ...core.resources import bundled_path
from .errors import CategoryValidationError
from ._profile import CategoryProfile, IvaDeductibilityHint
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


def load_category_profile_file(path: Path) -> Mapping[SpendingCategory, CategoryProfile]:
    """Load one year-keyed spending-category profile TOML file.

    Returns:
        Mapping from :class:`SpendingCategory` to :class:`CategoryProfile` for the file's year.
    """
    resolved = path.resolve()
    try:
        fingerprint = path_stat_fingerprint(resolved)
    except OSError as exc:
        raise CategoryValidationError(f"{resolved}: cannot stat category profile registry: {exc}") from exc
    return _load_category_profile_file_cached(*fingerprint)


@lru_cache(maxsize=32)
def _load_category_profile_file_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
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


def load_category_profile_registry(
    root: Path | None = None,
) -> Mapping[int, Mapping[SpendingCategory, CategoryProfile]]:
    """Load every committed year-keyed spending-category profile registry.

    Resolves the bundled categories root on every call when no
    override is supplied; the ``bundled_path`` boundary is the
    single resolution surface.

    Returns:
        Mapping from year to a per-year mapping from :class:`SpendingCategory` to :class:`CategoryProfile`.
    """
    target = root if root is not None else bundled_path("registry", "aeat", "categories", "profiles")
    resolved = target.resolve()
    paths = scan_directory(resolved, pattern="*.toml")
    fingerprint = tuple(file_stat_fingerprint(path) for path in paths)
    return _load_category_profile_registry_cached(str(resolved), fingerprint)


@lru_cache(maxsize=8)
def _load_category_profile_registry_cached(
    root: str,
    fingerprint: tuple[tuple[str, int, int], ...],
) -> Mapping[int, Mapping[SpendingCategory, CategoryProfile]]:
    root_path = Path(root)
    registries: dict[int, Mapping[SpendingCategory, CategoryProfile]] = {}
    for filename, _byte_count, _modified_ns in fingerprint:
        path = root_path / filename
        try:
            year = int(path.stem)
        except ValueError as exc:
            raise CategoryValidationError(f"{path}: category profile filename must be a year") from exc
        registries[year] = load_category_profile_file(path)
    if not registries:
        raise CategoryValidationError(f"{root_path}: no category profile TOML files found")
    return MappingProxyType(registries)


def resolve_category_profiles(year: int) -> Mapping[SpendingCategory, CategoryProfile]:
    """Return the exact category profile registry for ``year``.

    Returns:
        Mapping from :class:`SpendingCategory` to :class:`CategoryProfile` for ``year``.
    """
    profiles = load_category_profile_registry().get(year)
    if profiles is None:
        raise CategoryValidationError(f"no category profile registry registered for year={year}")
    return profiles


def _parse_profile(raw_profile: object) -> CategoryProfile:
    if not isinstance(raw_profile, dict):
        raise CategoryValidationError("profile entry must be a table")
    # CAST-RATIONALE-TOML-INVARIANT-DICT:
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_profile)
    category = SpendingCategory(str(data.get("category")))
    # CAST-RATIONALE-CATEGORY-PROPORTIONALITY-RAW: data.get() is loosely typed
    # by the mapping adapter; the isinstance check immediately below is the
    # real runtime validation of this value's shape.
    # nosemgrep: no-cast-in-domain-application
    raw_rule = cast("dict[str, object] | None", data.get("proportionality"))
    if not isinstance(raw_rule, dict):
        raise CategoryValidationError(f"profile {category.value!r} must declare [profiles.proportionality]")
    raw_iva_hint = data.get("iva_hint")
    return CategoryProfile.model_validate(
        {
            "category": category,
            "display_label": tr(str(data.get("display_label"))),
            "proportionality": _parse_rule(raw_rule),
            "iva_hint": (IvaDeductibilityHint(str(raw_iva_hint)) if raw_iva_hint is not None else None),
        },
    )


def _parse_rule(raw_rule: object) -> ProportionalityRule:
    if not isinstance(raw_rule, dict):
        raise CategoryValidationError("proportionality rule must be a table")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_rule)
    raw_variants = data.get("statutory_cap_variants", ())
    if not isinstance(raw_variants, list | tuple):
        raise CategoryValidationError("statutory_cap_variants must be a list")
    raw_citations = data.get("citations", ())
    if not isinstance(raw_citations, list | tuple):
        raise CategoryValidationError("citations must be a list")
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
                _parse_cap_variant(raw_variant) for raw_variant in OBJECT_TUPLE_ADAPTER.validate_python(raw_variants)
            ),
            "citations": tuple(
                _parse_citation(raw_citation) for raw_citation in OBJECT_TUPLE_ADAPTER.validate_python(raw_citations)
            ),
            "notes": tr(str(data.get("notes"))),
        },
    )


def _parse_cap_variant(raw_variant: object) -> StatutoryCapVariant:
    if not isinstance(raw_variant, dict):
        raise CategoryValidationError("statutory_cap_variants entries must be tables")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_variant)
    return StatutoryCapVariant.model_validate(
        {
            "id": data.get("id"),
            "label": tr(str(data.get("label"))),
            "statutory_cap_eur_per_day": _decimal_or_none(data.get("statutory_cap_eur_per_day")),
        },
    )


def _parse_citation(raw_citation: object) -> CategoryCitation:
    if not isinstance(raw_citation, dict):
        raise CategoryValidationError("citations entries must be tables")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_citation)
    url = data.get("url")
    if not isinstance(url, str):
        raise CategoryValidationError("citation url must be a string")
    return CategoryCitation.model_validate(
        {
            "source": CategoryCitationSource(str(data.get("source"))),
            "reference": data.get("reference"),
            "locator": data.get("locator"),
            "url": parse_http_url(url),
            "quote": tr(str(data.get("quote"))),
        },
    )


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool | float):
        raise CategoryValidationError("decimal profile values must not be booleans or floats")
    coerced = coerce_decimal(value)
    if coerced is None:
        raise CategoryValidationError(f"decimal profile value {value!r} could not be parsed")
    return coerced


def _cap_period_or_none(value: object) -> StatutoryCapPeriod | None:
    if value is None:
        return None
    return StatutoryCapPeriod(str(value))


__all__ = [
    "load_category_profile_file",
    "load_category_profile_registry",
    "resolve_category_profiles",
]
