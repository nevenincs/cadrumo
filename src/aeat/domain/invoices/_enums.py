"""Closed enumerations for invoice records.

Defines :class:`InvoiceKind`, :class:`IvaRate`, and
:class:`PaymentStatus` together with the
:func:`iva_rate_percentage` helper that resolves the numeric Decimal
percentage backing each :class:`IvaRate` member.

The percentage helper queries the centralized VAT substrate at
:mod:`aeat.domain.iva` rather than carrying its own rate literals.
:class:`IvaRate` keeps its closed-taxonomy role for invoice records;
the legal-grade percentage value lives in
``registry/aeat/vat/rates.toml`` and is dated.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from ..iva import EUMemberState, InvoiceKind, IvaRateKind, lookup_rate
from ..iva.errors import IvaRateNotFoundError


class IvaRate(StrEnum):
    """Closed taxonomy of Spanish VAT rate slots used on invoice lines.

    The slot names map to substrate :class:`aeat.domain.iva.IvaRateKind`
    tiers and the percentage backing each slot is resolved against
    :func:`aeat.domain.iva.lookup_rate` for Spain at a given date. This
    module no longer stores rate percentages as Python literals; if the
    legal rate changes, the substrate's TOML registry is the single
    source of truth.

    ``RATE_5`` (a transient 2022-2024 rate) is intentionally absent
    from this slot taxonomy. If a future workflow ingests pre-2025
    data this enum and the slot mapping below must be extended in
    sync with a corresponding registry rate entry.

    Attributes:
        RATE_0: Zero-rated supply.
        RATE_4: Super-reduced rate slot (LIVA art. 91 Dos).
        RATE_10: Reduced rate slot (LIVA art. 91 Uno).
        RATE_21: General rate slot (LIVA art. 90 Uno).
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


_IVA_RATE_TO_VAT_KIND: dict[IvaRate, IvaRateKind] = {
    IvaRate.RATE_4: IvaRateKind.SUPER_REDUCED,
    IvaRate.RATE_10: IvaRateKind.REDUCED,
    IvaRate.RATE_21: IvaRateKind.GENERAL,
}


def iva_rate_percentage(rate: IvaRate, on_date: date | None = None) -> Decimal | None:
    """Return the fractional percentage backing ``rate`` at ``on_date``.

    Slot membership in :class:`IvaRate` is structural; the actual
    percentage is resolved against
    :func:`aeat.domain.iva.lookup_rate` for Spain at ``on_date``. When
    ``on_date`` is omitted the lookup uses today's date.

    Args:
        rate: VAT rate slot.
        on_date: Date at which to resolve the rate percentage.
            Defaults to ``date.today()``.

    Returns:
        ``Decimal("0")`` for :attr:`IvaRate.RATE_0`; the substrate's
        rate as a fractional Decimal (``pct/100``) for the
        ``RATE_4`` / ``RATE_10`` / ``RATE_21`` slots; ``None`` for
        :attr:`IvaRate.EXEMPT` and :attr:`IvaRate.NOT_SUBJECT`.

    Raises:
        IvaRateNotFoundError: If the substrate has no rate for the
            requested slot at ``on_date``. This indicates registry
            drift (e.g. asking for a rate before its
            ``effective_from`` window) and must be fixed by updating
            the registry rather than by hardcoding a fallback here.
    """
    if rate is IvaRate.RATE_0:
        return Decimal("0")
    if rate in {IvaRate.EXEMPT, IvaRate.NOT_SUBJECT}:
        return None

    kind = _IVA_RATE_TO_VAT_KIND[rate]
    effective_date = on_date or date.today()
    rate_record = lookup_rate(EUMemberState.ES, kind, effective_date)
    return rate_record.pct / Decimal("100")


__all__ = [
    "InvoiceKind",
    "IvaRate",
    "PaymentStatus",
    "IvaRateNotFoundError",
    "iva_rate_percentage",
]
