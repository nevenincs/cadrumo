"""Closed enumerations for invoice records.

Defines :class:`IvaRate` and :class:`PaymentStatus` together with the two
percentage helpers backing each :class:`IvaRate` member:
:func:`iva_rate_slot_percentage` returns the number a slot names, and
:func:`iva_rate_percentage` returns that same number only once the
centralized IVA substrate at :mod:`cadrumo.domain.iva` confirms it was in
force on a given date.

The split exists because the two questions have different answers and
different homes. An invoice LINE has no date of its own and only needs the
number to check its own arithmetic; the INVOICE knows when the operation
happened and is where legality is decided. Both read one derivation, so the
number never differs between them -- only whether it is accepted.

:class:`IvaRate` keeps its closed-taxonomy role for invoice records, and
``registry/aeat/iva/rates.toml`` stays the dated legal-grade authority for
which rates existed when.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from ...core.time import today_madrid
from ..iva.errors import IvaRateNotFoundError
from ..iva.lookup import rate_kinds_for_declared_rate, rate_table_covers
from ..iva.schema import EUMemberState, IvaRateKind


class IvaRate(StrEnum):
    """Closed taxonomy of Spanish IVA rate slots used on invoice lines.

    The slot names map to substrate :class:`cadrumo.domain.iva.IvaRateKind`
    tiers, and each numeric slot NAMES its own percentage: the number is read
    off the member and then confirmed in force against the registry for Spain
    at the invoice's date. The registry stays the single source of truth for
    whether a rate was legal on a date -- it just is not asked what a tier
    means, because that is a different question from what a line was charged.

    The taxonomy carries the transitional food rates alongside the standing
    ones. ``RATE_2``, ``RATE_5`` and ``RATE_7_5`` back the RD-ley 4/2024
    phase-out of the RD-ley 20/2022 relief on basic foodstuffs and olive oil:
    the registry serves all three inside 2024, so an invoice dated in that
    window resolves to one of them and the slot must exist to record it.
    They are not dead members kept for history -- a 2024 filing is still
    amendable, and a rate the enum cannot name is a line that cannot be
    entered truthfully.

    Attributes:
        RATE_0: Zero-rated supply.
        RATE_2: Super-reduced transitional slot for basic foodstuffs
            (RD-ley 4/2024; served 2024-10-01 to 2024-12-31).
        RATE_4: Super-reduced rate slot (LIVA art. 91 Dos).
        RATE_5: Reduced transitional slot for olive oil and foodstuffs
            (RD-ley 20/2022 as continued; served 2024-07-01 to 2024-09-30).
        RATE_7_5: Reduced transitional slot on the way back to 10%
            (RD-ley 4/2024; served 2024-10-01 to 2024-12-31).
        RATE_10: Reduced rate slot (LIVA art. 91 Uno).
        RATE_21: General rate slot (LIVA art. 90 Uno).
        EXEMPT: Exempt operation; no numeric percentage.
        NOT_SUBJECT: Operation outside the scope of IVA; no numeric
            percentage.
    """

    RATE_0 = "RATE_0"
    RATE_2 = "RATE_2"
    RATE_4 = "RATE_4"
    # The VALUE carries a decimal point, not an underscore: the slot mapping
    # derives its percentage by stripping the prefix and parsing the rest, and
    # Decimal("7_5") parses as seventy-five rather than failing. The member NAME
    # keeps the underscore because an identifier cannot hold a dot.
    RATE_5 = "RATE_5"
    RATE_7_5 = "RATE_7.5"
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


_NUMERIC_RATE_PREFIX = "RATE_"


def _slot_declared_percentage(rate: IvaRate) -> Decimal | None:
    """Return the integer percentage a numeric slot names, or ``None`` for the non-numeric slots.

    The one derivation of a slot's own number, structural rather than listed:
    the ``RATE_`` prefix is stripped from the member VALUE and the remainder
    parsed. Both :func:`numeric_iva_rate_slots` and :func:`iva_rate_percentage`
    read it here, so the percentage a slot resolves to and the percentage the
    accepted-rate set advertises cannot disagree.
    """
    if not rate.value.startswith(_NUMERIC_RATE_PREFIX):
        return None
    return Decimal(rate.value[len(_NUMERIC_RATE_PREFIX) :])


_IVA_RATE_TO_IVA_KIND: dict[IvaRate, IvaRateKind] = {
    IvaRate.RATE_0: IvaRateKind.ZERO,
    IvaRate.RATE_2: IvaRateKind.SUPER_REDUCED,
    IvaRate.RATE_4: IvaRateKind.SUPER_REDUCED,
    IvaRate.RATE_5: IvaRateKind.REDUCED,
    IvaRate.RATE_7_5: IvaRateKind.REDUCED,
    IvaRate.RATE_10: IvaRateKind.REDUCED,
    IvaRate.RATE_21: IvaRateKind.GENERAL,
    IvaRate.EXEMPT: IvaRateKind.EXEMPT,
}


def iva_rate_slot_percentage(rate: IvaRate) -> Decimal | None:
    """Return the fractional percentage ``rate`` names, without asking whether it was in force.

    The undated half of the pair. A line's arithmetic -- does ``iva_amount``
    equal ``subtotal * rate`` -- needs the NUMBER the operator applied and
    nothing else, and an :class:`~cadrumo.domain.invoices.InvoiceLine` carries
    no date of its own to check legality against. Asking the dated
    :func:`iva_rate_percentage` there would resolve a 2024 line against today
    and refuse to build it at all.

    Whether the rate was legally available is a separate question, asked where
    a date actually exists: :func:`iva_rate_percentage` at the invoice's
    operation date, and the invoice-level validator that applies it to every
    line. Both read this same derivation, so the number never differs between
    the two -- only whether it is accepted.

    Returns:
        The slot's own percentage as a fraction (``Decimal("0.02")`` for
        :attr:`IvaRate.RATE_2`); ``None`` for :attr:`IvaRate.EXEMPT` and
        :attr:`IvaRate.NOT_SUBJECT`.
    """
    declared_percentage = _slot_declared_percentage(rate)
    if declared_percentage is None:
        return None
    return declared_percentage / Decimal("100")


def iva_rate_percentage(rate: IvaRate, on_date: date | None = None) -> Decimal | None:
    """Return the fractional percentage ``rate`` names, confirmed in force at ``on_date``.

    A numeric slot carries its own percentage in its name, and that number --
    not its tier's ordinary rate -- is what the line was charged. The registry
    is consulted to confirm the rate was legally in force for Spain on
    ``on_date`` and belonged to the slot's tier; it is not asked to supply the
    number. When ``on_date`` is omitted the check uses the current
    Europe/Madrid civil date (:func:`cadrumo.core.time.today_madrid`), the date
    the IVA devengo rate binds to (LIVA art. 90.Dos with art. 75).

    Resolving through :func:`cadrumo.domain.iva.lookup_rate` instead would
    answer a different question and silently return a different number. That
    function deliberately skips ``supersedes_tier_default`` records, because a
    rate applying to only part of a tier's supplies cannot say what the tier
    means -- so it answers ``RATE_2`` with the ordinary super-reducido 4 %, and
    a 2 % foodstuffs line would compute twice the IVA it carried.
    :func:`cadrumo.domain.iva.rate_kinds_for_declared_rate` is the inverse
    authority built for this direction and does see those records.

    Args:
        rate: IVA rate slot.
        on_date: Date at which the slot's rate must have been in force.
            Defaults to the Europe/Madrid civil date (``today_madrid()``).

    Returns:
        The slot's own percentage as a fractional Decimal (``Decimal("0.02")``
        for :attr:`IvaRate.RATE_2`, ``Decimal("0")`` for
        :attr:`IvaRate.RATE_0`); ``None`` for :attr:`IvaRate.EXEMPT` and
        :attr:`IvaRate.NOT_SUBJECT`, which carry no percentage.

    Raises:
        IvaRateNotFoundError: If the slot's rate was not in force for its tier
            on ``on_date`` -- a transitional slot used outside its statutory
            window, or a standing slot the registry no longer serves. Refusing
            is the point: substituting whatever the tier happens to mean that
            day would record a number the invoice never carried. When the rate
            table does not reach ``on_date`` FOR THAT TIER the refusal says so
            instead, because "not in force" would be a false claim about the law
            rather than a true one about our coverage. The reach differs between
            tiers, so the question is never whether the table reaches a date at
            all: it carries the general and reducido records well before the
            super-reducido ones.
            :attr:`IvaRate.RATE_0` is never refused, because
            :func:`~cadrumo.domain.iva.rate_kinds_for_declared_rate` answers
            ZERO on every date -- Spain zero-rates on three permanent grounds
            the rate table cannot express, so its silence there is incomplete
            coverage rather than a statement that zero-rating was unlawful.
    """
    fraction = iva_rate_slot_percentage(rate)
    if fraction is None:
        return None
    kind = _IVA_RATE_TO_IVA_KIND[rate]
    effective_date = on_date or today_madrid()
    if kind not in rate_kinds_for_declared_rate(EUMemberState.ES, fraction, effective_date):
        # Coverage and legality are different facts and must not share a
        # message. The registry's reach differs PER TIER -- the general and
        # reducido records run from 2012, the super-reducido ones only from
        # 2024 -- so a line can fail on OUR reach while the table carries other
        # tiers that same day. Saying "not in force" there sends a filer to
        # correct a figure that was right, and invites widening the table with
        # a guessed value rather than an authored, corpus-backed one.
        if not rate_table_covers(EUMemberState.ES, effective_date, kind):
            raise IvaRateNotFoundError(
                translated_message="errors.iva.rate_registry_coverage_gap",
                context={
                    "iva_rate_slot": rate.name,
                    "rate_pct": str(fraction * Decimal("100")),
                    "rate_kind": kind.value,
                    "member_state": EUMemberState.ES.value,
                    "on_date": effective_date.isoformat(),
                    "rate_registry_covers_date": False,
                },
            )
        raise IvaRateNotFoundError(
            translated_message="errors.iva.rate_slot_not_in_force",
            context={
                "iva_rate_slot": rate.name,
                "rate_pct": str(fraction * Decimal("100")),
                "rate_kind": kind.value,
                "member_state": EUMemberState.ES.value,
                "on_date": effective_date.isoformat(),
                "rate_registry_covers_date": True,
                "rate_in_force": False,
            },
        )
    return fraction


def iva_rate_kind(rate: IvaRate) -> IvaRateKind | None:
    """Return the substrate rate tier for an invoice line rate slot.

    ``NOT_SUBJECT`` has no OSS/IOSS rate tier because it is outside the
    taxable-supply universe; callers that need a Modelo 369 candidate should
    skip or reject it explicitly. Numeric and exempt slots return their
    corresponding :class:`IvaRateKind`.
    """
    return _IVA_RATE_TO_IVA_KIND.get(rate)


def numeric_iva_rate_slots() -> dict[Decimal, IvaRate]:
    """Return the integer percentage to :class:`IvaRate` slot mapping.

    The one canonical percentage-to-slot resolution, inverting the same
    :func:`_slot_declared_percentage` derivation :func:`iva_rate_percentage`
    reads, so the rates this advertises as acceptable are exactly the rates a
    slot resolves to. :attr:`IvaRate.EXEMPT` and :attr:`IvaRate.NOT_SUBJECT`
    carry no numeric percentage and are excluded.

    Deriving rather than listing is what keeps the accepted rate set consistent
    across surfaces as the taxonomy changes: the RD-ley 4/2024 food rates were
    added to :class:`IvaRate` and appeared here without this function being
    touched. An invoice-creation path holding a hand-written copy of this table
    would keep rejecting a new slot while a sibling that derived it accepted
    one — creation and editing disagreeing about what a valid rate is.

    Membership is not the same as availability: a slot appears here whenever it
    exists, while :func:`iva_rate_percentage` refuses it on a date its rate was
    not in force. This answers "which rates can a line name", not "which rates
    may this invoice charge today".

    Returns:
        A fresh mutable mapping, so a caller cannot mutate the shared taxonomy.
    """
    return {percentage: member for member in IvaRate if (percentage := _slot_declared_percentage(member)) is not None}


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
    "iva_rate_slot_percentage",
    "numeric_iva_rate_percentages",
    "numeric_iva_rate_slots",
]
