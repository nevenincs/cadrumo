"""Canonical euro-cent rounding for the fincas domain.

All LIRPF art. 23.1 calculations round to euro-cent precision using
half-up semantics per AEAT convention. This module is the single
authoritative definition; callers import from here rather than
duplicating the quantize call.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


def _round_to_cents(value: Decimal) -> Decimal:
    """Round *value* to euro-cent precision using ROUND_HALF_UP."""
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)
