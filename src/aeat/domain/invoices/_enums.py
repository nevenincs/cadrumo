"""Closed enumerations for invoice records.

Defines :class:`InvoiceKind`, :class:`IvaRate`, and
:class:`PaymentStatus` together with the
:func:`iva_rate_percentage` helper that resolves the numeric Decimal
percentage backing each :class:`IvaRate` member.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType


class InvoiceKind(StrEnum):
    """Direction of an invoice relative to the autónomo.

    Attributes:
        ISSUED: Invoice emitted by the autónomo to a customer.
        RECEIVED: Invoice received by the autónomo from a supplier.
    """

    ISSUED = "ISSUED"
    RECEIVED = "RECEIVED"


class IvaRate(StrEnum):
    """Supported Spanish VAT rates and their non-numeric states.

    ``RATE_5`` (a transient 2022-2024 rate) is intentionally omitted; if
    a future workflow ingests pre-2025 data this enum will need to be
    extended alongside :data:`_IVA_RATE_PERCENTAGES`.

    Attributes:
        RATE_0: Zero-rated supply.
        RATE_4: Super-reduced 4 % rate (LIVA art. 91).
        RATE_10: Reduced 10 % rate (LIVA art. 91).
        RATE_21: General 21 % rate (LIVA art. 90).
        EXEMPT: Exempt operation; no numeric percentage.
        NOT_SUBJECT: Operation outside the scope of IVA; no numeric
            percentage.
    """

    RATE_0 = "RATE_0"
    RATE_4 = "RATE_4"
    RATE_10 = "RATE_10"
    RATE_21 = "RATE_21"
    EXEMPT = "EXEMPT"
    NOT_SUBJECT = "NOT_SUBJECT"


class PaymentStatus(StrEnum):
    """Lifecycle states for an invoice payment.

    Attributes:
        PAID: Settled in full.
        PENDING: Awaiting payment within agreed terms.
        PARTIALLY_PAID: Partially settled; remainder outstanding.
        OVERDUE: Past the due date and still outstanding.
        CANCELLED: Cancelled, regardless of whether previously paid.
    """

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
