"""Kent's persisted per-category usage-ratio overrides (issue #259).

This subpackage owns the user-writable substrate for usage-ratio coefficients:
a frozen pydantic profile, an atomic JSON round-trip, a CLI-facing family-alias
map, and the pure resolver consumed by the deductibility compute service
(issue #257).

Callers import from the package root, not the private submodules.
"""

from __future__ import annotations

from ._errors import UsageRatioError, UsageRatioPersistenceError
from ._model import ELIGIBLE_USAGE_RATIO_CATEGORIES, UsageRatioProfile, resolve_user_ratio
from ._service import load_usage_ratios, save_usage_ratios

__all__ = [
    "ELIGIBLE_USAGE_RATIO_CATEGORIES",
    "UsageRatioError",
    "UsageRatioPersistenceError",
    "UsageRatioProfile",
    "load_usage_ratios",
    "resolve_user_ratio",
    "save_usage_ratios",
]
