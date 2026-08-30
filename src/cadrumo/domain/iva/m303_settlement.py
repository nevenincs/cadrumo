"""LIVA annual-settlement timing for Modelo 303 regularisation flows."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from ...core import Period

_M303_ANNUAL_SETTLEMENT_ORDER: Final[dict[str, int]] = {"4T": 0, "0A": 1}


def m303_annual_settlement_period_order(period: Period) -> int | None:
    """Return the legal annual-settlement order for one Modelo 303 period.

    LIVA arts. 105.Cuatro and 107.Siete settle annual regularisations at
    ``4T`` for quarterly filers or ``0A`` for annual-only filers. Midyear
    periods have no settlement order.
    """
    return _M303_ANNUAL_SETTLEMENT_ORDER.get(period.registry_token)


def is_m303_annual_settlement_period(period: Period) -> bool:
    """Return whether the typed period is a legal Modelo 303 annual settlement."""
    return m303_annual_settlement_period_order(period) is not None


def m303_annual_settlement_order_key(period: Period, captured_at: datetime) -> tuple[int, datetime] | None:
    """Return the legal settlement precedence key for an observed source period.

    The legal settlement form wins first (annual-only ``0A`` after quarterly
    ``4T``), then the later capture wins within the same form. Non-settlement
    periods have no key and must not participate in annual carry selection.
    """
    order = m303_annual_settlement_period_order(period)
    return None if order is None else (order, captured_at)


def m303_annual_settlement_period_tokens() -> tuple[str, ...]:
    """Return legal Modelo 303 settlement tokens in increasing settlement order."""
    return tuple(_M303_ANNUAL_SETTLEMENT_ORDER)


__all__ = [
    "is_m303_annual_settlement_period",
    "m303_annual_settlement_order_key",
    "m303_annual_settlement_period_order",
    "m303_annual_settlement_period_tokens",
]
