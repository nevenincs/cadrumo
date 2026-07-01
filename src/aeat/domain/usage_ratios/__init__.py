"""Public facade for persisted per-category usage-ratio overrides.

This subpackage owns the user-writable substrate for proportional-deduction
coefficients: a frozen :class:`UsageRatioProfile`, the
:data:`ELIGIBLE_USAGE_RATIO_CATEGORIES` set derived from
:mod:`aeat.domain.categories`, the pure resolver :func:`resolve_user_ratio`,
and the ledger reference validator :func:`validate_usage_ratio_reference`.
Usage-ratio identifiers are concrete
:class:`~aeat.domain.categories.SpendingCategory` values, not aliases or
parallel ids.

Profile persistence is an encrypted ``FINANCIAL`` secure-object round trip via
:func:`load_usage_ratios` / :func:`save_usage_ratios`, keyed by
:func:`usage_ratios_object_key` and guarded during read-modify-write by
:func:`usage_ratio_bucket_lock`. HOME_OFFICE category values can also be derived
from the bound censo through :func:`derive_home_office_ratios_from_censo` and
refused on drift by :func:`load_usage_ratios_with_censo_guard`.

Usage ratios model business/personal proportional deduction for ledger and
Renta paths. They are explicitly separate from IVA prorrata and do not decide
modelo applicability or casilla routing.

Callers must import from this package root rather than reaching into the
private submodules; the public surface listed in :data:`__all__` is the only
supported API.
"""

from __future__ import annotations

from ._errors import (
    CensoRatioMismatchError,
    UsageRatioError,
    UsageRatioPersistenceError,
    UsageRatioValidationError,
)
from ._model import (
    ELIGIBLE_USAGE_RATIO_CATEGORIES,
    UsageRatioProfile,
    UsageRatioReference,
    resolve_user_ratio,
    validate_usage_ratio_reference,
)
from ._service import (
    derive_home_office_ratios_from_censo,
    load_usage_ratios,
    load_usage_ratios_with_censo_guard,
    save_usage_ratios,
    usage_ratio_bucket_lock,
    usage_ratios_object_key,
)

__all__ = [
    "ELIGIBLE_USAGE_RATIO_CATEGORIES",
    "CensoRatioMismatchError",
    "UsageRatioError",
    "UsageRatioPersistenceError",
    "UsageRatioProfile",
    "UsageRatioReference",
    "UsageRatioValidationError",
    "derive_home_office_ratios_from_censo",
    "load_usage_ratios",
    "load_usage_ratios_with_censo_guard",
    "resolve_user_ratio",
    "save_usage_ratios",
    "usage_ratio_bucket_lock",
    "usage_ratios_object_key",
    "validate_usage_ratio_reference",
]
