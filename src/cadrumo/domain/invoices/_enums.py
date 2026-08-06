"""Closed enumerations for invoice records.

Defines :class:`IvaRate` and :class:`PaymentStatus` together with the
:func:`iva_rate_percentage` helper that resolves the numeric Decimal
percentage backing each :class:`IvaRate` member.

The percentage helper queries the centralized IVA substrate at
:mod:`cadrumo.domain.iva` rather than carrying its own rate literals.
:class:`IvaRate` keeps its closed-taxonomy role for invoice records;
the legal-grade percentage value lives in
``registry/aeat/iva/rates.toml`` and is dated.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from ...core.time import today_madrid
from ..iva import EUMemberState, IvaRateKind, IvaRateNotFoundError, lookup_rate


class IvaRate(StrEnum):
    """Closed taxonomy of Spanish IVA rate slots used on invoice lines.

    The slot names map to substrate :class:`cadrumo.domain.iva.IvaRateKind`
    tiers and the percentage backing each slot is resolved against
    :func:`cadrumo.domain.iva.lookup_rate` for Spain at a given date. This
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


class InvoiceClass(StrEnum):
    """RD 1619/2012 art. 6.1.a invoice class, closed by the reglamento's own taxonomy.

    ``ORDINARIA`` is the factura completa the reglamento describes by default.
    ``RECTIFICATIVA`` is the class art. 6.1.a.2.º forces into a specific series
    and LIVA art. 89 requires to name what it corrects. ``SIMPLIFICADA`` is the
    class art. 7 (not yet bundled) relieves of most art. 6.1 content, including
    -- outside the three art. 6.1.d cases -- the counterparty's tax id.

    Attributes:
        ORDINARIA: The default factura completa.
        SIMPLIFICADA: A ticket-style invoice under the simplified regime.
        RECTIFICATIVA: An invoice correcting a previously issued one.
    """

    ORDINARIA = "ORDINARIA"
    SIMPLIFICADA = "SIMPLIFICADA"
    RECTIFICATIVA = "RECTIFICATIVA"


class InvoiceOperationDateRole(StrEnum):
    """Why :attr:`~cadrumo.domain.invoices.Invoice.operation_date` was recorded.

    RD 1619/2012 art. 6.1.i treats both cases as ONE datum in one clause: "la
    fecha en que se hayan efectuado las operaciones ... o en la que, en su
    caso, se haya recibido el pago anticipado, siempre que se trate de una
    fecha distinta a la de expedición de la factura." The role does not change
    how the date is READ for devengo purposes -- both cases are the LIVA
    art. 75 devengo date -- it records which of the two clauses the operator
    is stating, which is otherwise lost the moment the date is read back.

    Attributes:
        OPERATION_PERFORMED: The date the operation (entrega/prestación) took
            place, art. 75.Uno.
        ADVANCE_PAYMENT_RECEIVED: The date a pago anticipado was collected
            before the operation, art. 75.Dos.
    """

    OPERATION_PERFORMED = "OPERATION_PERFORMED"
    ADVANCE_PAYMENT_RECEIVED = "ADVANCE_PAYMENT_RECEIVED"


_IVA_RATE_TO_IVA_KIND: dict[IvaRate, IvaRateKind] = {
    IvaRate.RATE_0: IvaRateKind.ZERO,
    IvaRate.RATE_4: IvaRateKind.SUPER_REDUCED,
    IvaRate.RATE_10: IvaRateKind.REDUCED,
    IvaRate.RATE_21: IvaRateKind.GENERAL,
    IvaRate.EXEMPT: IvaRateKind.EXEMPT,
}


def iva_rate_percentage(rate: IvaRate, on_date: date | None = None) -> Decimal | None:
    """Return the fractional percentage backing ``rate`` at ``on_date``.

    Slot membership in :class:`IvaRate` is structural; the actual
    percentage is resolved against
    :func:`cadrumo.domain.iva.lookup_rate` for Spain at ``on_date``. When
    ``on_date`` is omitted the lookup uses the current Europe/Madrid civil date
    (:func:`cadrumo.core.time.today_madrid`), the date the IVA devengo rate binds
    to (LIVA art. 90.Dos with art. 75).

    Args:
        rate: IVA rate slot.
        on_date: Date at which to resolve the rate percentage.
            Defaults to the Europe/Madrid civil date (``today_madrid()``).

    Returns:
        ``Decimal("0")`` for :attr:`IvaRate.RATE_0`; the substrate's
        rate as a fractional Decimal (``pct/100``) for the
        ``RATE_4`` / ``RATE_10`` / ``RATE_21`` slots; ``None`` for
        :attr:`IvaRate.EXEMPT` and :attr:`IvaRate.NOT_SUBJECT`.

    """
    if rate is IvaRate.RATE_0:
        return Decimal("0")
    if rate in {IvaRate.EXEMPT, IvaRate.NOT_SUBJECT}:
        return None

    kind = _IVA_RATE_TO_IVA_KIND[rate]
    effective_date = on_date or today_madrid()
    rate_record = lookup_rate(EUMemberState.ES, kind, effective_date)
    return rate_record.pct / Decimal("100")


def iva_rate_kind(rate: IvaRate) -> IvaRateKind | None:
    """Return the substrate rate tier for an invoice line rate slot.

    ``NOT_SUBJECT`` has no OSS/IOSS rate tier because it is outside the
    taxable-supply universe; callers that need a Modelo 369 candidate should
    skip or reject it explicitly. Numeric and exempt slots return their
    corresponding :class:`IvaRateKind`.
    """
    return _IVA_RATE_TO_IVA_KIND.get(rate)


def numeric_iva_rate_percentages() -> frozenset[Decimal]:
    """Return the integer-percentage values for the numeric :class:`IvaRate` slots.

    Parses the ``RATE_<n>`` member names of :class:`IvaRate` to derive the
    closed set of integer percentages the CLI boundary accepts on
    ``--set iva.rate``.  :attr:`IvaRate.EXEMPT` and
    :attr:`IvaRate.NOT_SUBJECT` carry no numeric percentage and are
    excluded.

    The derivation is structural — the ``RATE_`` prefix is stripped and the
    remainder is parsed as an integer — so the returned set tracks
    :class:`IvaRate` membership without re-listing ``0 / 4 / 10 / 21`` as
    literals.

    Returns:
        A :class:`frozenset` of :class:`Decimal` integer percentages; for
        the current taxonomy ``frozenset({Decimal("0"), Decimal("4"),
        Decimal("10"), Decimal("21")})``.
    """
    _prefix = "RATE_"
    return frozenset(Decimal(member.value[len(_prefix) :]) for member in IvaRate if member.value.startswith(_prefix))


__all__ = [
    "InvoiceClass",
    "InvoiceOperationDateRole",
    "IvaRate",
    "IvaRateNotFoundError",
    "PaymentStatus",
    "iva_rate_kind",
    "iva_rate_percentage",
    "numeric_iva_rate_percentages",
]
