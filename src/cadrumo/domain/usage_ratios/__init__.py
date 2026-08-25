"""Public facade for persisted per-category usage-ratio overrides.

This subpackage owns the user-writable substrate for proportional-deduction
coefficients: a frozen :class:`UsageRatioProfile`, the
:data:`ELIGIBLE_USAGE_RATIO_CATEGORIES` set derived from
:mod:`domain.categories`, the pure resolver :func:`resolve_user_ratio`,
and the ledger reference validator :func:`validate_usage_ratio_reference`.
Usage-ratio identifiers are concrete
:class:`domain.categories.SpendingCategory` values, not aliases or
parallel ids.

Profile persistence is an encrypted ``FINANCIAL`` secure-object round trip via
:func:`adapters.persistence.profile.usage_ratios.load_usage_ratios` /
:func:`~adapters.persistence.profile.usage_ratios.save_usage_ratios`, keyed
by :func:`usage_ratios_object_key` and guarded during read-modify-write by
:func:`usage_ratio_bucket_lock`. HOME_OFFICE category values are derived from the
bound censo through :func:`derive_home_office_ratios_from_censo` and refused on
drift by
:func:`~adapters.persistence.profile.usage_ratios.load_usage_ratios_with_censo_guard`.

Usage ratios model business/personal proportional deduction for ledger and
Renta paths. Ledger commands validate ``usage_ratio_id`` against this profile
and require any stored ``business_pct`` to match the referenced category ratio;
Renta aggregation then consumes the resolved mapping as business-use
proportions. They are explicitly separate from legal IVA prorrata and do not
decide modelo applicability or casilla routing.

See Also:
    :mod:`application.ledger`
        Validates ledger ratio references, reports missing proportionality, and
        surfaces HOME_OFFICE censo drift before modelo calculation.
    :mod:`application.aggregation`
        Consumes resolved ratios when building Renta deductible-expense binding
        values from active ledger rows.
    :mod:`domain.iva`
        Owns the separate legal IVA prorrata substrate used by IVA aggregation.
    :mod:`application.user_profile`
        Supplies the bound censo facts used to derive and guard HOME_OFFICE
        usage-ratio values.

Callers must import from this package root rather than reaching into the
private submodules; the public surface listed in :data:`__all__` is the only
supported API.
"""

from __future__ import annotations

from .errors import (
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
    validate_usage_ratio_bound,
    validate_usage_ratio_reference,
)
from ._service import (
    derive_home_office_ratios_from_censo,
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
    "resolve_user_ratio",
    "usage_ratio_bucket_lock",
    "usage_ratios_object_key",
    "validate_usage_ratio_bound",
    "validate_usage_ratio_reference",
]
