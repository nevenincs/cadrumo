"""The operator's persisted per-category usage-ratio overrides.

This subpackage owns the user-writable substrate for usage-ratio coefficients:
a frozen pydantic profile (:class:`UsageRatioProfile`), an atomic encrypted
round-trip via :func:`load_usage_ratios` / :func:`save_usage_ratios`, and the
pure resolver :func:`resolve_user_ratio` consumed by the deductibility compute
service in :mod:`aeat.domain.deductibility`.

Callers must import from this package root rather than reaching into the
private submodules; the public surface listed in :data:`__all__` is the only
supported API.
"""

from __future__ import annotations

from ._errors import UsageRatioError, UsageRatioPersistenceError, UsageRatioValidationError
from ._model import (
    ELIGIBLE_USAGE_RATIO_CATEGORIES,
    UsageRatioProfile,
    UsageRatioReference,
    resolve_user_ratio,
    validate_usage_ratio_reference,
)
from ._service import (
    derive_home_office_ratios_from_census,
    load_usage_ratios,
    save_usage_ratios,
    usage_ratios_object_key,
)

__all__ = [
    "ELIGIBLE_USAGE_RATIO_CATEGORIES",
    "UsageRatioError",
    "UsageRatioPersistenceError",
    "UsageRatioProfile",
    "UsageRatioReference",
    "UsageRatioValidationError",
    "derive_home_office_ratios_from_census",
    "load_usage_ratios",
    "resolve_user_ratio",
    "save_usage_ratios",
    "usage_ratios_object_key",
    "validate_usage_ratio_reference",
]
