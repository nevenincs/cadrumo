"""Shared BUSINESS / MIXED business-proportion dispatch.

Centralises business proportion dispatch: four aggregation sites
(:mod:`~._iva_ledger`, :mod:`~._renta_ledger`, :mod:`~._renta_income_ledger`,
and :mod:`~._renta_gasto_ledger`) each carry the
same dispatch shape::

    if classification is BusinessClassification.BUSINESS:
        return Decimal("1")  # or the unit-scaled amount
    if classification is BusinessClassification.MIXED:
        assert business_pct is not None
        return business_pct  # or amount * business_pct
    return None

This module centralises the proportion lookup so every call site uses
one canonical mapping; the per-site multiplication into an amount stays
local because the unit semantics differ (IVA ledger returns a bare
proportion; renta sites return amount * proportion).
"""

from __future__ import annotations

from decimal import Decimal

from ...domain.transactions.enums import BusinessClassification


def business_proportion(
    classification: BusinessClassification,
    business_pct: Decimal | None,
) -> Decimal | None:
    """Return the BUSINESS / MIXED dispatch proportion, or ``None``.

    * ``BUSINESS`` → ``Decimal("1")`` (the whole row is deductible /
      business-attributable).
    * ``MIXED`` with a ``business_pct`` set → ``business_pct``.
    * ``MIXED`` with ``business_pct=None`` → ``None`` (caller treats
      as not-yet-classified; ``preflight`` surfaces the gap separately
      via ``MISSING_PROPORTIONALITY_REFERENCE``).
    * Any other classification (e.g. ``PERSONAL``, ``NOT_YET_PROCESSED``)
      → ``None``.
    """
    if classification is BusinessClassification.BUSINESS:
        return Decimal("1")
    if classification is BusinessClassification.MIXED and business_pct is not None:
        return business_pct
    return None


__all__ = ["business_proportion"]
