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


class InvoiceLegalMention(StrEnum):
    """RD 1619/2012 art. 6.1 fixed legal notices, closed by the reglamento's own wording.

    Each member is one of the LITERALLY QUOTED phrases (each printed between
    guillemets in the article text) the reglamento requires stated on the
    invoice when its triggering regime applies. This is evidence of what the
    issuer PRINTED, never something to derive from
    :attr:`~cadrumo.domain.invoices.Invoice.iva_category`: manufacturing a
    mención from our own classification would fabricate evidence of
    compliance nobody observed on the document. Use
    :func:`invoice_legal_mention_text` to read the exact wording a member
    represents.

    art. 6.1.j (the exemption reference) is deliberately absent from this
    enum: unlike the fixed phrases below, it is a REFERENCE the issuer
    composes -- to a Directiva 2006/112/CE provision, a LIVA article, or a
    bare statement that the operation is exempt -- not one closed literal
    string, so it is represented as free text
    (:attr:`~cadrumo.domain.invoices.Invoice.exemption_reference`), not a
    member here.

    Attributes:
        SELF_BILLED: art. 6.1.l, a destinatario-issued invoice
            (autofacturación, RD 1619/2012 art. 5).
        REVERSE_CHARGE: art. 6.1.m, the destinatario is the sujeto pasivo
            (inversión del sujeto pasivo, LIVA art. 84.Uno).
        TRAVEL_AGENCY_REGIME: art. 6.1.n, régimen especial de las agencias
            de viajes.
        USED_GOODS_REGIME: art. 6.1.o, régimen especial de los bienes
            usados (REBU).
        ART_OBJECTS_REGIME: art. 6.1.o, régimen especial de los objetos de
            arte (REBU).
        ANTIQUES_COLLECTORS_REGIME: art. 6.1.o, régimen especial de las
            antigüedades y objetos de colección (REBU).
        CASH_ACCOUNTING_REGIME: art. 6.1.p, régimen especial del criterio
            de caja.
    """

    SELF_BILLED = "SELF_BILLED"
    REVERSE_CHARGE = "REVERSE_CHARGE"
    TRAVEL_AGENCY_REGIME = "TRAVEL_AGENCY_REGIME"
    USED_GOODS_REGIME = "USED_GOODS_REGIME"
    ART_OBJECTS_REGIME = "ART_OBJECTS_REGIME"
    ANTIQUES_COLLECTORS_REGIME = "ANTIQUES_COLLECTORS_REGIME"
    CASH_ACCOUNTING_REGIME = "CASH_ACCOUNTING_REGIME"


_INVOICE_LEGAL_MENTION_TEXT: dict[InvoiceLegalMention, str] = {
    InvoiceLegalMention.SELF_BILLED: "facturación por el destinatario",
    InvoiceLegalMention.REVERSE_CHARGE: "inversión del sujeto pasivo",
    InvoiceLegalMention.TRAVEL_AGENCY_REGIME: "régimen especial de las agencias de viajes",
    InvoiceLegalMention.USED_GOODS_REGIME: "régimen especial de los bienes usados",
    InvoiceLegalMention.ART_OBJECTS_REGIME: "régimen especial de los objetos de arte",
    InvoiceLegalMention.ANTIQUES_COLLECTORS_REGIME: "régimen especial de las antigüedades y objetos de colección",
    InvoiceLegalMention.CASH_ACCOUNTING_REGIME: "régimen especial del criterio de caja",
}


def invoice_legal_mention_text(mention: InvoiceLegalMention) -> str:
    """Return the exact RD 1619/2012 art. 6.1 phrase ``mention`` represents.

    The reglamento quotes each of these phrases verbatim between guillemets,
    so this returns exactly that wording -- extracted from the bundled
    corpus, not retyped -- for a caller comparing against, or rendering,
    what the invoice document is required to state.
    """
    return _INVOICE_LEGAL_MENTION_TEXT[mention]


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


_NUMERIC_RATE_PREFIX = "RATE_"


def numeric_iva_rate_slots() -> dict[Decimal, IvaRate]:
    """Return the integer percentage to :class:`IvaRate` slot mapping.

    The one canonical percentage-to-slot resolution, and the only place the
    ``0 / 4 / 10 / 21`` correspondence is expressed. The derivation is
    structural — the ``RATE_`` prefix is stripped from each member name and the
    remainder parsed as an integer — so the mapping tracks :class:`IvaRate`
    membership rather than re-listing literals beside it.
    :attr:`IvaRate.EXEMPT` and :attr:`IvaRate.NOT_SUBJECT` carry no numeric
    percentage and are excluded.

    Deriving rather than listing is what keeps the accepted rate set consistent
    across surfaces as the taxonomy changes, and the trigger is already named in
    :class:`IvaRate`'s own docstring: ``RATE_5``, the transient 2022-2024 rate,
    is deliberately absent, and ingesting pre-2025 data would require adding it.
    An invoice-creation path holding a hand-written copy of this table would
    keep rejecting the new slot while a sibling that derived it accepted one —
    creation and editing disagreeing about what a valid rate is.

    Returns:
        A fresh mutable mapping, so a caller cannot mutate the shared taxonomy.
    """
    return {
        Decimal(member.value[len(_NUMERIC_RATE_PREFIX) :]): member
        for member in IvaRate
        if member.value.startswith(_NUMERIC_RATE_PREFIX)
    }


def numeric_iva_rate_percentages() -> frozenset[Decimal]:
    """Return the integer-percentage values for the numeric :class:`IvaRate` slots.

    The keys of :func:`numeric_iva_rate_slots`, and derived from it rather than
    by a second walk of the enum, so the accepted percentages and the slots they
    resolve to cannot drift apart.

    Returns:
        A :class:`frozenset` of :class:`Decimal` integer percentages; for
        the current taxonomy ``frozenset({Decimal("0"), Decimal("4"),
        Decimal("10"), Decimal("21")})``.
    """
    return frozenset(numeric_iva_rate_slots())


__all__ = [
    "InvoiceClass",
    "InvoiceLegalMention",
    "InvoiceOperationDateRole",
    "IvaRate",
    "IvaRateNotFoundError",
    "PaymentStatus",
    "invoice_legal_mention_text",
    "iva_rate_kind",
    "iva_rate_percentage",
    "numeric_iva_rate_percentages",
    "numeric_iva_rate_slots",
]
