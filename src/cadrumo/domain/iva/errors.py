"""Canonical domain errors for the :mod:`cadrumo.domain.iva` subpackage.

Every failure mode raised by the IVA substrate inherits from
:class:`IvaError`, which in turn inherits from
:class:`cadrumo.core.errors.CadrumoError`. Downstream callers catch the base class
when they want to treat the substrate as an opaque unit, or the specific
subclass when they need to distinguish missing-rate from missing-category or
corpus load failures.
"""

from __future__ import annotations

from ...core.errors import CadrumoError


class IvaError(CadrumoError):
    """Base error for every :mod:`cadrumo.domain.iva` failure mode."""


class IvaRateNotFoundError(IvaError):
    """Raised when :func:`cadrumo.domain.iva.lookup_rate` cannot resolve a rate.

    The lookup fails either because the requested member state is absent from
    :func:`cadrumo.domain.iva.load_iva_rate_table`, because no rate of the requested
    :class:`cadrumo.domain.iva.IvaRateKind` is registered for that member state,
    or because every registered rate's effective window excludes the
    requested date.
    """


class IvaCategoryNotFoundError(IvaError):
    """Raised when a lookup against a resolved IVA catalogue misses."""


class IvaCatalogueError(IvaError):
    """Raised when an IVA catalogue cannot be loaded, resolved, or validated."""


class IvaRateOverlapError(IvaError):
    """Raised when two :class:`cadrumo.domain.iva.IvaRateRecord` records share a window.

    The substrate enforces that for every ``(member_state, kind)`` partition
    of :func:`cadrumo.domain.iva.load_iva_rate_table` no two records have overlapping
    ``effective_from`` / ``effective_until`` ranges. Adding a new record that
    violates this invariant raises this error at module import time so the
    regression surfaces in CI rather than silently affecting
    :func:`cadrumo.domain.iva.lookup_rate` results.
    """


class IvaClassificationError(IvaError):
    """Raised when :func:`cadrumo.domain.iva.classify_iva` cannot return a deterministic match.

    The classifier exposes a closed first-match-wins table; the only
    structural failure is when the input criteria cannot be represented under
    the closed enum set, which is caught at construction time by pydantic.
    This error is reserved for future extensions such as ambiguous rule
    rankings.
    """


class IvaValidationError(IvaError, ValueError):
    """Raised on invalid IVA field values. Inherits from ValueError for Pydantic."""


class ProrrataError(IvaError):
    """Base error for IVA prorrata calculation failures (LIVA arts. 101-103)."""


class ProrrataInputError(ProrrataError, ValueError):
    """Raised when prorrata inputs violate domain invariants.

    Inherits from ``ValueError`` so pydantic surfaces it as a
    ``ValidationError`` when raised from a model validator.
    """


class ProrrataSectorError(ProrrataError):
    """Raised when sectoral-separation inputs are inconsistent.

    Examples: a sector references an unknown id, two sectors share an
    activity code, or the sector list is empty when sectoral separation
    is required (LIVA art. 9.1.c).
    """
