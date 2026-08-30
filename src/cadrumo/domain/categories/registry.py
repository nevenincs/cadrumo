"""Read-only spending-category profile registry.

The corpus is ONE undated file. The proportionality rules do not vary by filing
year; the evidence does, so each citation declares the closed span it is asserted
over and the resolvable years are derived from those spans rather than from a
filename.

:func:`load_category_profiles` reads the committed TOML into an immutable mapping
from :class:`SpendingCategory` to :class:`CategoryProfile` carrying every
citation. :func:`resolve_category_profiles` projects that corpus onto one filing
year, keeping only the citations asserted over it, and refuses a year the corpus
cannot ground. The refusal is deliberate and unchanged from the year-named shape
this replaced: there is no adjacent-year fallback and no widening, because a
profile answered from another year's evidence is a rule the operator cannot
trace.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import cast

from pydantic import ValidationError

from ...core import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER, read_toml
from ...core.citation_grounding import CitationGrounding
from ...core.decimal import coerce_decimal
from ...core.i18n import Translatable as tr
from ...core.paths import path_stat_fingerprint
from ...core.resources import bundled_path
from ...core.validity_window import ValidityWindow, years_covered_by_any, years_covered_by_every_group
from .errors import CategoryValidationError
from .profile import CategoryProfile, IvaDeductibilityHint
from .proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapAmount,
    StatutoryCapPeriod,
    StatutoryCapVariant,
    parse_http_url,
)
from .spending_category import SpendingCategory


def load_category_profiles(path: Path | None = None) -> Mapping[SpendingCategory, CategoryProfile]:
    """Load the committed spending-category profile corpus.

    Args:
        path: The corpus file. Defaults to the bundled one, resolved through the
            ``bundled_path`` boundary that is the single resolution surface.

    Returns:
        Mapping from :class:`SpendingCategory` to :class:`CategoryProfile`,
        carrying every citation regardless of the span it is asserted over.

    Raises:
        CategoryValidationError: When the file is unreadable, malformed, carries
            a duplicate category, or omits a declared spending category.
    """
    target = path if path is not None else bundled_path("registry", "aeat", "categories", "profiles.toml")
    resolved = target.resolve()
    try:
        fingerprint = path_stat_fingerprint(resolved)
    except OSError as exc:
        raise CategoryValidationError(f"{resolved}: cannot stat category profile registry: {exc}") from exc
    return _load_category_profiles_cached(*fingerprint)


@lru_cache(maxsize=8)
def _load_category_profiles_cached(
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


def category_profile_years(path: Path | None = None) -> frozenset[int]:
    """Return every filing year the corpus can be resolved for.

    A year counts only when EVERY profile can be grounded for it: at least one
    citation asserted over the year AND, where the rule's cap is one the law
    re-fixes each ejercicio, a scheduled amount for that year. One profile whose
    evidence stops earlier stops the corpus, because the loader refuses a partial
    registry anyway -- reporting the year as covered and then failing to assemble
    it would be the same lie in two places.

    Returns:
        The derived set of resolvable filing years.
    """
    profiles = load_category_profiles(path)
    return years_covered_by_every_group(_grounding_windows(profile) for profile in profiles.values())


def _grounding_windows(profile: CategoryProfile) -> tuple[ValidityWindow, ...]:
    """Return the spans over which ``profile`` is grounded end to end.

    A citation window says the evidence covers a year. For a cap the law
    re-fixes each ejercicio, the evidence is not enough on its own: without an
    amount for that year the rule cannot be applied at all. Intersecting the two
    keeps the corpus from claiming a year it can cite but cannot compute.
    """
    rule = profile.proportionality
    citation_years = years_covered_by_any(citation.window for citation in rule.citations)
    if not rule.statutory_cap_schedule:
        return tuple(citation.window for citation in rule.citations)
    scheduled_years = years_covered_by_any(amount.window for amount in rule.statutory_cap_schedule)
    both = sorted(citation_years & scheduled_years)
    return tuple(ValidityWindow(valid_from=date(year, 1, 1), valid_to=date(year, 12, 31)) for year in both)


def resolve_category_profiles(year: int) -> Mapping[SpendingCategory, CategoryProfile]:
    """Return the category profile registry as grounded for ``year``.

    Every profile is projected onto ``year``: citations asserted over another
    span are dropped, so what the caller receives cites only evidence that
    actually speaks to the year asked for.

    Returns:
        Mapping from :class:`SpendingCategory` to :class:`CategoryProfile` for
        ``year``.

    Raises:
        CategoryValidationError: When the corpus grounds no such year. There is
            no fallback to an adjacent year.
    """
    return _resolve_category_profiles_cached(year, tuple(sorted(category_profile_years())))


@lru_cache(maxsize=16)
def _resolve_category_profiles_cached(
    year: int,
    covered: tuple[int, ...],
) -> Mapping[SpendingCategory, CategoryProfile]:
    if year not in covered:
        raise CategoryValidationError(
            f"no category profile registry grounded for year={year}; "
            f"the corpus grounds {list(covered)}. Ground the year against BOE or AEAT and add its "
            "citations -- never widen an existing citation's window to admit it.",
        )
    projected: dict[SpendingCategory, CategoryProfile] = {}
    for category, profile in load_category_profiles().items():
        rule = profile.proportionality
        update: dict[str, object] = {
            "citations": tuple(citation for citation in rule.citations if citation.window.covers_year(year)),
        }
        if rule.statutory_cap_schedule:
            # The year's amount is materialised onto the flat field and the
            # schedule dropped, so every consumer keeps reading one cap and
            # cannot pick the wrong year's by reaching past the resolver.
            update["statutory_cap_eur"] = rule.cap_amount_for_year(year)
            update["statutory_cap_schedule"] = ()
        projected[category] = profile.model_copy(
            update={"proportionality": rule.model_copy(update=update)},
        )
    return MappingProxyType(projected)


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
    raw_schedule = data.get("statutory_cap_schedule", ())
    if not isinstance(raw_schedule, list | tuple):
        raise CategoryValidationError("statutory_cap_schedule must be a list")
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
            "statutory_cap_schedule": tuple(
                _parse_cap_amount(raw_amount) for raw_amount in OBJECT_TUPLE_ADAPTER.validate_python(raw_schedule)
            ),
            "citations": tuple(
                _parse_citation(raw_citation) for raw_citation in OBJECT_TUPLE_ADAPTER.validate_python(raw_citations)
            ),
            "notes": tr(str(data.get("notes"))),
        },
    )


def _parse_cap_amount(raw_amount: object) -> StatutoryCapAmount:
    """Hydrate one dated statutory-cap row."""
    if not isinstance(raw_amount, dict):
        raise CategoryValidationError("statutory_cap_schedule entries must be tables")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_amount)
    return StatutoryCapAmount.model_validate(
        {
            "value": _decimal_or_none(data.get("value")),
            "valid_from": data.get("valid_from"),
            "valid_to": data.get("valid_to"),
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
            "statutory_cap_eur": _decimal_or_none(data.get("statutory_cap_eur")),
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
            # Read as plain text, never through ``tr``. Resolving it here is how
            # the defect survived: the loader turned every locale key into the
            # fallback word "Quote" before the validator saw it, so a check for
            # non-empty text passed for all eighty-three ungrounded citations.
            "quote": str(data.get("quote") or ""),
            "grounding": CitationGrounding(str(data.get("grounding") or "verified")),
            "grounding_reason": str(data.get("grounding_reason") or ""),
            "legal_ref": data.get("legal_ref"),
            "valid_from": data.get("valid_from"),
            "valid_to": data.get("valid_to"),
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
    "category_profile_years",
    "load_category_profiles",
    "resolve_category_profiles",
]
