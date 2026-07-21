"""Domain exceptions for :mod:`domain.usage_ratios`.

The hierarchy roots at :class:`core.errors.CadrumoError` so callers may catch
the project-wide base class when treating the substrate as opaque, or the
specific subclass when they need to distinguish persistence faults from
upcoming domain-level failure modes.
"""

from __future__ import annotations

from ...core.errors import CadrumoError

__all__ = [
    "CensoRatioMismatchError",
    "UsageRatioError",
    "UsageRatioPersistenceError",
    "UsageRatioValidationError",
]


class UsageRatioError(CadrumoError):
    """Base error for every :mod:`domain.usage_ratios` failure mode.

    Subclassed by every concrete error raised by the package so callers can
    catch the broad family with a single ``except`` clause.
    """


class UsageRatioPersistenceError(UsageRatioError):
    """Raised when the usage-ratio profile cannot be read or written.

    Surfaced by :func:`adapters.persistence.profile.usage_ratios.load_usage_ratios` and
    :func:`adapters.persistence.profile.usage_ratios.save_usage_ratios` for OS-level I/O
    failures and for envelope payloads that fail strict validation.
    """


class UsageRatioValidationError(UsageRatioError, ValueError):
    """Raised when usage-ratio profiles violate domain invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """


class CensoRatioMismatchError(UsageRatioError):
    """Raised when a persisted HOME_OFFICE ratio disagrees with the censo.

    Surfaced by
    :func:`adapters.persistence.profile.usage_ratios.load_usage_ratios_with_censo_guard`
    when a pre-existing per-category override for a HOME_OFFICE category
    deviates from the legally-binding censo-derived value, or when the
    operator has not yet captured a censo snapshot at all. The
    AEAT is the binding legal source of truth for censo-derived values:
    a profile in conflict with the censo must be refused at the load
    boundary so the calculation surface never silently consumes a stale
    ratio.

    The fix is operator-driven: either update the censo vivienda_office
    data via ``aeat config profile edit``, or unset the
    diverging override via ``aeat app ledger ratios unset``. No
    automatic migration; no shim.
    """
