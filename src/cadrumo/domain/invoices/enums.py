"""Closed enumerations for invoice records.

Defines :class:`IvaRate` and :class:`PaymentStatus`.  ``IvaRate`` is a
persisted taxonomy only: the legal number behind a numeric slot is resolved
from the IVA governed-fact authority at the explicit devengo date held by the
composition boundary.

:class:`IvaRate` keeps its closed-taxonomy role for invoice records, and
The IVA facade is the sole legal-grade authority for which rates existed when.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from ..calculations.registry.errors import RegistryValidationError
from ..iva.errors import IvaRateNotFoundError
from ..iva.lookup import rate_kinds_for_declared_rate, rate_table_covers, resolve_iva_rate
from ..iva.rates import iva_rate_record_from_fact
from ..iva.schema import EUMemberState, IvaRateKind


class IvaRate(StrEnum):
    """Closed taxonomy of Spanish IVA rate slots used on invoice lines.

    The slot names map to substrate :class:`cadrumo.domain.iva.IvaRateKind`
    tiers. Their persisted tokens are stable identifiers, not a numeric source:
    the fact authority resolves the exact ordinary or coexisting variant for a
    stated devengo date.

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
    the localized catalogue to read the exact wording a member
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

_IVA_RATE_TO_RATE_ROLE: dict[IvaRate, str] = {
    IvaRate.RATE_2: "coexisting-2",
    IvaRate.RATE_4: "ordinary",
    IvaRate.RATE_5: "coexisting-5",
    IvaRate.RATE_7_5: "coexisting-7.5",
    IvaRate.RATE_10: "ordinary",
    IvaRate.RATE_21: "ordinary",
}

_NON_NUMERIC_IVA_RATES = frozenset((IvaRate.EXEMPT, IvaRate.NOT_SUBJECT))


def resolve_iva_rate_slot_fact(rate: IvaRate, on_date: date):
    """Resolve a numeric slot's exact authority fact with its provenance.

    Zero is a permanent semantic slot whose IVA facade accepts the fraction on
    every date but which no flat rate fact can fully model; it consequently has
    no single rate-fact variant to return.  EXEMPT and NOT_SUBJECT are likewise
    nonnumeric taxonomy members.
    """
    if rate in _NON_NUMERIC_IVA_RATES or rate is IvaRate.RATE_0:
        return None
    return resolve_iva_rate(
        EUMemberState.ES,
        _IVA_RATE_TO_IVA_KIND[rate],
        on_date,
        rate_role=_IVA_RATE_TO_RATE_ROLE[rate],
    )


def iva_rate_percentage(rate: IvaRate, on_date: date) -> Decimal | None:
    """Resolve ``rate`` to its fractional authority value at ``on_date``.

    The result is projected from the exact Spanish member-state, tier, role,
    and devengo-date fact. No rate is parsed from the persisted enum token.

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
        on_date: The explicit devengo date at which the slot is resolved.

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
    if rate in _NON_NUMERIC_IVA_RATES:
        return None
    kind = _IVA_RATE_TO_IVA_KIND[rate]
    if rate is IvaRate.RATE_0:
        if kind not in rate_kinds_for_declared_rate(EUMemberState.ES, Decimal("0"), on_date):
            raise IvaRateNotFoundError("zero IVA slot is not accepted by the IVA authority")
        return Decimal("0")
    try:
        resolved = resolve_iva_rate_slot_fact(rate, on_date)
        if resolved is None:
            raise RegistryValidationError("numeric IVA slot resolved without an authority fact")
        return iva_rate_record_from_fact(resolved).pct / Decimal("100")
    except RegistryValidationError as exc:
        # Coverage and legality are different facts and must not share a
        # message. The registry's reach differs PER TIER -- the general and
        # reducido records run from 2012, the super-reducido ones only from
        # 2024 -- so a line can fail on OUR reach while the table carries other
        # tiers that same day. Saying "not in force" there sends a filer to
        # correct a figure that was right, and invites widening the table with
        # a guessed value rather than an authored, corpus-backed one.
        if not rate_table_covers(EUMemberState.ES, on_date, kind):
            raise IvaRateNotFoundError(
                translated_message="errors.iva.rate_registry_coverage_gap",
                context={
                    "iva_rate_slot": rate.name,
                    "rate_kind": kind.value,
                    "member_state": EUMemberState.ES.value,
                    "on_date": on_date.isoformat(),
                    "rate_registry_covers_date": False,
                },
            ) from exc
        raise IvaRateNotFoundError(
            translated_message="errors.iva.rate_slot_not_in_force",
            context={
                "iva_rate_slot": rate.name,
                "rate_kind": kind.value,
                "member_state": EUMemberState.ES.value,
                "on_date": on_date.isoformat(),
                "rate_registry_covers_date": True,
                "rate_in_force": False,
            },
        ) from exc


def iva_rate_kind(rate: IvaRate) -> IvaRateKind | None:
    """Return the substrate rate tier for an invoice line rate slot.

    ``NOT_SUBJECT`` has no OSS/IOSS rate tier because it is outside the
    taxable-supply universe; callers that need a Modelo 369 candidate should
    skip or reject it explicitly. Numeric and exempt slots return their
    corresponding :class:`IvaRateKind`.
    """
    return _IVA_RATE_TO_IVA_KIND.get(rate)


def resolve_iva_rate_slot(percentage: Decimal | None, on_date: date) -> IvaRate:
    """Resolve a printed percentage to its persisted slot at an explicit date."""
    if percentage is None:
        return IvaRate.EXEMPT
    resolved_rates: list[tuple[Decimal, IvaRate]] = []
    for rate in IvaRate:
        try:
            resolved = iva_rate_percentage(rate, on_date)
        except IvaRateNotFoundError:
            continue
        if resolved is not None:
            resolved_rates.append((resolved, rate))
    matches = tuple(rate for resolved, rate in resolved_rates if resolved * Decimal("100") == percentage)
    if len(matches) == 1:
        return matches[0]
    accepted = ", ".join(
        format(resolved * Decimal("100"), "f")
        for resolved, _ in resolved_rates
    )
    raise IvaRateNotFoundError(
        "IVA percentage has no unique persisted rate slot at the supplied devengo date",
        context={"iva_rate": format(percentage, "f"), "on_date": on_date.isoformat(), "accepted": accepted},
    )


__all__ = [
    "InvoiceClass",
    "InvoiceLegalMention",
    "InvoiceOperationDateRole",
    "IvaRate",
    "IvaRateNotFoundError",
    "PaymentStatus",
    "iva_rate_kind",
    "iva_rate_percentage",
    "resolve_iva_rate_slot",
    "resolve_iva_rate_slot_fact",
]
