"""Closed enumerations for invoice records."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType


class InvoiceKind(StrEnum):
    """Direction of an invoice relative to the autónomo."""

    ISSUED = "ISSUED"
    RECEIVED = "RECEIVED"


class IvaRate(StrEnum):
    """Supported Spanish VAT rates and their non-numeric states.

    `RATE_5` (a transient 2022-2024 rate) is intentionally omitted; if a
    future workflow ingests pre-2025 data this enum will need to be
    extended alongside the per-rate percentage table below.
    """

    RATE_0 = "RATE_0"
    RATE_4 = "RATE_4"
    RATE_10 = "RATE_10"
    RATE_21 = "RATE_21"
    EXEMPT = "EXEMPT"
    NOT_SUBJECT = "NOT_SUBJECT"


class PaymentStatus(StrEnum):
    """Lifecycle states for an invoice payment."""

    PAID = "PAID"
    PENDING = "PENDING"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


_IVA_RATE_PERCENTAGES: Mapping[IvaRate, Decimal | None] = MappingProxyType(
    {
        IvaRate.RATE_0: Decimal("0"),
        IvaRate.RATE_4: Decimal("0.04"),
        IvaRate.RATE_10: Decimal("0.10"),
        IvaRate.RATE_21: Decimal("0.21"),
        IvaRate.EXEMPT: None,
        IvaRate.NOT_SUBJECT: None,
    }
)


def iva_rate_percentage(rate: IvaRate) -> Decimal | None:
    """Return the numeric percentage for ``rate``, or ``None`` for non-numeric rates.

    Args:
        rate: VAT rate enum member.

    Returns:
        The Decimal percentage (e.g. ``Decimal("0.21")``) for numeric rates,
        or ``None`` for ``EXEMPT`` / ``NOT_SUBJECT``.
    """
    return _IVA_RATE_PERCENTAGES[rate]
