"""A received invoice's stated retención, read as the per-perceptor observation it evidences.

A person who pays a professional or the rent of business premises and keeps the
supplier's invoice with its retención has recorded everything Modelo 111 and
Modelo 115 declare: the perceptor, the base, the retención and, through the
paying movement, when it was paid. This module reads those records at calculation
time into :class:`~.retenciones.RetencionObservation` rows of source kind
``payable_invoice``. It writes nothing, and an invoice already captured into the
per-perceptor store keeps its stored allocation instead.

Each fact comes from its owner, never from a guess:

- the retención is the taxpayer's liability only where the IVA component table
  says so for a received invoice (:func:`.invoice_retencion.invoice_retencion_liability_defects`);
- the income kind is the paying movement's IRPF category, rent or activity;
- the recipient's tax is read from the leading character of its NIF
  (fact ``withholding-recipient-regime-by-tax-id-leader``) and its country;
- whether that recipient's income of that kind bears retención at all, and the
  provisions saying so, come from fact ``withholding-subject-income-by-recipient-regime``;
- recognition follows RIRPF art. 78 for an IRPF recipient (each payment, in
  proportion) and RIS art. 65 for urban rent paid to an IS recipient
  (:func:`.withholding_recognition.derive_withholding_recognition`);
- the scheme is urban rent for rent, and for an activity the registry rate the
  stated retención conforms to: a professional rate or another activity rate.

What stops an invoice is reported as a :class:`ReceivedInvoiceWithholdingFinding`
rather than dropped, so a declaration is never completed without a retención the
person recorded. A finding belongs to the quarter of the invoice's first payment,
or of its date while it is unpaid. An unpaid invoice whose retención follows
payment is otherwise simply not yet due and raises nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final

from ...core.aggregation import BindingSourceKind, RetencionScheme
from ...core.money.rounding import round_to_cents
from ...core.period import Period
from ...domain.calculations.registry.form_codes import resolve_form_codes
from ...domain.calculations.registry.ids import LegalRefId
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.enums import TransactionDirection, TransactionLifecycleState
from ...domain.transactions.irpf_categories import has_activity_irpf_category, has_rent_irpf_category
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.retencion_facts import (
    professional_activity_retencion_rates,
    statutory_activity_retencion_rates,
)
from .invoice_iva_source import with_movement_side_links
from .invoice_retencion import InvoiceRetencionProjectionDefect, invoice_retencion_liability_defects
from .renta_income_evidence import row_settles_invoice, settlement_comparison
from .retencion_rate_advisory import conforms_to_fixed_rate
from .retenciones import RetencionObservation
from .withholding_modelo_routing import modelo_for_income_kind
from .withholding_recognition import (
    WithholdingDatedEvent,
    WithholdingIncomeKind,
    WithholdingOperationKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
    WithholdingRecognitionError,
    WithholdingRecognitionEvidence,
    derive_withholding_recognition,
)

_REGIME_FACT: Final = "withholding-recipient-regime-by-tax-id-leader"
_SUBJECT_FACT: Final = "withholding-subject-income-by-recipient-regime"
_SUBJECT: Final = "subject"
_NOT_SUBJECT: Final = "not_subject"
_SPANISH_COUNTRY_CODE: Final = "ES"


class ReceivedInvoiceWithholdingFindingKind(StrEnum):
    """Why a received invoice's stated retención reaches no declaration."""

    INCOME_KIND_UNDECLARED = "received_invoice_income_kind_undeclared"
    """No paying movement says whether the payment is rent or an activity's fee, or they disagree."""

    ENTITY_PROFESSIONAL_FEE = "received_invoice_entity_professional_fee"
    """The supplier pays Impuesto sobre Sociedades, whose professional fees bear no retención (RIS art. 60.1)."""

    RECIPIENT_UNKNOWN = "received_invoice_recipient_unknown"
    """The supplier's NIF, or the registry, does not settle whether its income of this kind bears retención."""

    NON_RESIDENT = "received_invoice_non_resident"
    """The supplier is not resident in Spain, so its retención is not an IRPF one."""

    RATE_UNRECOGNISED = "received_invoice_rate_unrecognised"
    """The stated retención matches no activity rate the registry declares for the date."""

    INVOICE_INCOMPLETE = "received_invoice_invoice_incomplete"
    """The invoice lacks a fact the declaration needs: the supplier's NIF, a euro value, or a liability role."""


@dataclass(frozen=True, slots=True)
class ReceivedInvoiceWithholdingFinding:
    """One received invoice whose stated retención reaches no declaration, and why."""

    invoice_id: str
    invoice_number: str
    counterparty_name: str
    retencion: Decimal
    kind: ReceivedInvoiceWithholdingFindingKind
    modelo: str | None
    """The modelo the retención would reach, or ``None`` where the income kind is not known."""
    legal_refs: tuple[LegalRefId, ...] = ()
    """The provisions the finding rests on, as the registry fact cites them; empty where none is cited."""
    blocking: bool = True
    """Whether the finding holds the declaration back until the invoice is corrected."""


@dataclass(frozen=True, slots=True)
class ReceivedInvoiceWithholding:
    """The observations and findings received invoices give one modelo and period."""

    observations: tuple[RetencionObservation, ...]
    findings: tuple[ReceivedInvoiceWithholdingFinding, ...]


def recipient_tax_regime(tax_id: str, *, country: str | None) -> WithholdingRecipientTaxRegime:
    """Return the income tax a Spanish supplier answers to, from its NIF's leading character.

    A supplier outside Spain answers to the non-residents' tax. A leader the fact
    does not declare, or declares unknown, stays unknown.
    """
    if country not in (None, _SPANISH_COUNTRY_CODE):
        return WithholdingRecipientTaxRegime.IRNR
    leader = tax_id.strip().upper()[:1]
    token = "digit" if leader.isdigit() else leader
    value = resolve_form_codes(_REGIME_FACT).under("regime").get(token)
    try:
        return WithholdingRecipientTaxRegime(value) if value is not None else WithholdingRecipientTaxRegime.UNKNOWN
    except ValueError:
        return WithholdingRecipientTaxRegime.UNKNOWN


def withholding_subjectness(
    regime: WithholdingRecipientTaxRegime, income_kind: WithholdingIncomeKind, *, on: date
) -> tuple[bool | None, tuple[LegalRefId, ...]]:
    """Return whether ``regime``'s income of ``income_kind`` bears retención on ``on``, and the provisions saying so.

    ``None`` means the registry declares no row for the pair, which settles nothing.
    """
    codes = resolve_form_codes(_SUBJECT_FACT, effective_date=on)
    row = f"{regime.value}.{income_kind.value}"
    value = codes.under("subject").get(row)
    refs: tuple[LegalRefId, ...] = tuple((codes.under("cite").get(row) or "").split())
    if value == _SUBJECT:
        return True, refs
    if value == _NOT_SUBJECT:
        return False, refs
    return None, ()


def _states_retencion(invoice: Invoice) -> bool:
    return (
        invoice.kind is InvoiceKind.RECEIVED
        and invoice.retention_amount is not None
        and invoice.retention_amount > Decimal("0")
    )


def _live(transactions: TransactionCatalogue) -> dict[str, Transaction]:
    return {
        movement.transaction_id: movement
        for movement in transactions
        if movement.lifecycle_state is TransactionLifecycleState.ACTIVE
    }


def _payments(invoice: Invoice, live: Mapping[str, Transaction]) -> tuple[Transaction, ...]:
    return tuple(
        sorted(
            (live[transaction_id] for transaction_id in invoice.linked_transaction_ids if transaction_id in live),
            key=lambda movement: (_paid_on(movement), movement.transaction_id),
        )
    )


def _finding(
    invoice: Invoice,
    kind: ReceivedInvoiceWithholdingFindingKind,
    modelo: str | None,
    legal_refs: tuple[LegalRefId, ...] = (),
) -> ReceivedInvoiceWithholdingFinding:
    return ReceivedInvoiceWithholdingFinding(
        invoice_id=invoice.invoice_id,
        invoice_number=invoice.invoice_number,
        counterparty_name=invoice.counterparty_name,
        retencion=invoice.retention_amount or Decimal("0"),
        kind=kind,
        modelo=modelo,
        legal_refs=legal_refs,
    )


def _not_subject_finding(
    invoice: Invoice, payments: tuple[Transaction, ...]
) -> ReceivedInvoiceWithholdingFinding | None:
    """Return the finding for a retención an IS supplier's income of its kind does not bear, or ``None``.

    The income kind is the paying movements'; before any payment, a stated
    retención that conforms to an activity rate says it is an activity's fee.
    """
    if invoice_retencion_liability_defects(invoice):
        return None
    regime = recipient_tax_regime(invoice.counterparty_tax_id or "", country=invoice.counterparty_country)
    if regime is not WithholdingRecipientTaxRegime.IS:
        return None
    income_kind = _income_kind(payments) if payments else _activity_kind_by_rate(invoice)
    if income_kind is None:
        return None
    subject, refs = withholding_subjectness(regime, income_kind, on=invoice.issued_at)
    if subject is not False:
        return None
    return _finding(
        invoice,
        ReceivedInvoiceWithholdingFindingKind.ENTITY_PROFESSIONAL_FEE,
        modelo_for_income_kind(income_kind),
        refs,
    )


def _activity_kind_by_rate(invoice: Invoice) -> WithholdingIncomeKind | None:
    rates = statutory_activity_retencion_rates(effective_date=invoice.issued_at)
    retencion = invoice.retention_amount or Decimal("0")
    if any(conforms_to_fixed_rate(invoice.base_total, retencion, rate) for rate in rates):
        return WithholdingIncomeKind.PROFESSIONAL
    return None


def received_invoice_withholding(
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    modelo: str,
    period: Period,
    captured_invoice_ids: frozenset[str] = frozenset(),
) -> ReceivedInvoiceWithholding:
    """Read the bucket's received invoices into ``modelo``'s observations recognised in ``period``.

    ``captured_invoice_ids`` names invoices the per-perceptor store already holds
    an allocation of; their stored rows stand and they are not read again.
    Findings are those that concern ``modelo`` or whose modelo cannot be known.
    """
    live = _live(transactions)
    observations: list[RetencionObservation] = []
    findings: list[ReceivedInvoiceWithholdingFinding] = []
    for invoice, payments in _stated_invoices(invoices, live, bucket_id=bucket_id):
        if invoice.invoice_id in captured_invoice_ids:
            continue
        read = _read_invoice(_assess_invoice(invoice, payments), modelo=modelo, period=period)
        observations.extend(read.observations)
        found_on = _paid_on(payments[0]) if payments else invoice.issued_at
        if period.start_date <= found_on <= period.end_date:
            findings.extend(read.findings)
    return ReceivedInvoiceWithholding(observations=tuple(observations), findings=tuple(findings))


@dataclass(frozen=True, slots=True)
class MovementWithholding:
    """What one received invoice's retención means for one movement that pays it.

    Either the euro ``retencion`` the invoice recognises on this payment, read by
    the rules Modelo 111 and 115 calculate with, or the reason it reaches no
    declaration (``held_back``), so a movement the declaration waits on is never
    shown as a movement with no retención.
    """

    transaction_id: str
    invoice_id: str
    invoice_number: str
    modelo: str | None
    """The modelo the retención reaches, or ``None`` where the income kind is not known."""
    scheme: RetencionScheme | None
    retencion: Decimal | None
    """The euro retención recognised on this payment; ``None`` where the invoice is held back."""
    recognised_on: date | None
    held_back: ReceivedInvoiceWithholdingFindingKind | None


def states_received_retencion(invoices: InvoiceCatalogue, *, bucket_id: str) -> bool:
    """Return whether any received invoice of ``bucket_id`` states a retención; if none, no movement carries one."""
    return any(_states_retencion(invoice) and invoice.bucket_id in (None, bucket_id) for invoice in invoices.values())


def received_invoice_movement_withholding(
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
) -> dict[str, tuple[MovementWithholding, ...]]:
    """Return, by movement id, the retención each paying movement carries.

    It runs the same per-invoice assessment the declarations calculate with,
    over every period and modelo, so a listed movement and the modelo that
    declares it cannot disagree. A movement that pays no invoice stating a
    retención has no entry: its retención is absent, which is not zero.
    """
    live = _live(transactions)
    by_movement: dict[str, list[MovementWithholding]] = {}
    for invoice, payments in _stated_invoices(invoices, live, bucket_id=bucket_id):
        assessment = _assess_invoice(invoice, payments)
        finding = assessment.finding
        for payment in payments:
            recognised = next(
                (row for row in assessment.recognitions if row.payment_id == payment.transaction_id), None
            )
            if finding is None and recognised is None:
                continue
            by_movement.setdefault(payment.transaction_id, []).append(
                MovementWithholding(
                    transaction_id=payment.transaction_id,
                    invoice_id=invoice.invoice_id,
                    invoice_number=invoice.invoice_number,
                    modelo=assessment.target if finding is None else finding.modelo,
                    scheme=assessment.scheme,
                    retencion=None if recognised is None or finding is not None else recognised.retencion,
                    recognised_on=None if recognised is None or finding is not None else recognised.recognised_on,
                    held_back=None if finding is None else finding.kind,
                )
            )
    return {transaction_id: tuple(rows) for transaction_id, rows in by_movement.items()}


def _stated_invoices(
    invoices: InvoiceCatalogue, live: Mapping[str, Transaction], *, bucket_id: str
) -> Iterable[tuple[Invoice, tuple[Transaction, ...]]]:
    """Yield each received invoice stating a retención with its live paying movements."""
    received = tuple(
        invoice
        for invoice in invoices.values()
        if _states_retencion(invoice) and invoice.bucket_id in (None, bucket_id)
    )
    for invoice in with_movement_side_links(received, window=TransactionCatalogue.from_transactions(live.values())):
        yield invoice, _payments(invoice, live)


@dataclass(frozen=True, slots=True)
class _Recognition:
    """The euro base and retención an invoice recognises on one payment."""

    payment_id: str
    recognised_on: date
    base: Decimal
    retencion: Decimal


@dataclass(frozen=True, slots=True)
class _Assessment:
    """What one invoice's retención amounts to, before any modelo or period is chosen."""

    invoice: Invoice
    target: str | None
    """The modelo the retención reaches; ``None`` where nothing is recognised or the kind is unknown."""
    finding: ReceivedInvoiceWithholdingFinding | None
    scheme: RetencionScheme | None
    recognitions: tuple[_Recognition, ...]


def _assess_invoice(invoice: Invoice, payments: tuple[Transaction, ...]) -> _Assessment:
    """Decide, from the invoice and its payments alone, what its retención is and where it goes."""

    def held(kind: ReceivedInvoiceWithholdingFindingKind, target: str | None) -> _Assessment:
        return _Assessment(invoice, target, _finding(invoice, kind, target), None, ())

    not_subject = _not_subject_finding(invoice, payments)
    if not_subject is not None:
        return _Assessment(invoice, not_subject.modelo, not_subject, None, ())
    income_kind = _income_kind(payments)
    target = None if income_kind is None else modelo_for_income_kind(income_kind)
    defects = invoice_retencion_liability_defects(invoice)
    if InvoiceRetencionProjectionDefect.NON_RESIDENT_SUPPLIER in defects:
        return held(ReceivedInvoiceWithholdingFindingKind.NON_RESIDENT, target)
    if defects:
        return held(ReceivedInvoiceWithholdingFindingKind.INVOICE_INCOMPLETE, target)
    if not payments:
        # An unpaid invoice is not yet a retención for an IRPF supplier; rent owed
        # to an IS supplier falls due on its date, and needs its kind to know so.
        return _Assessment(invoice, None, None, None, ())
    if income_kind is None or target is None:
        return held(ReceivedInvoiceWithholdingFindingKind.INCOME_KIND_UNDECLARED, None)
    regime = recipient_tax_regime(invoice.counterparty_tax_id or "", country=invoice.counterparty_country)
    if regime is WithholdingRecipientTaxRegime.UNKNOWN:
        return held(ReceivedInvoiceWithholdingFindingKind.RECIPIENT_UNKNOWN, target)
    if regime is WithholdingRecipientTaxRegime.IRNR:
        return held(ReceivedInvoiceWithholdingFindingKind.NON_RESIDENT, target)
    if withholding_subjectness(regime, income_kind, on=invoice.issued_at)[0] is not True:
        return held(ReceivedInvoiceWithholdingFindingKind.RECIPIENT_UNKNOWN, target)
    scheme = _scheme(invoice, income_kind)
    if scheme is None:
        return held(ReceivedInvoiceWithholdingFindingKind.RATE_UNRECOGNISED, target)
    allocations = _allocations(invoice, payments, regime=regime, income_kind=income_kind)
    if allocations is None:
        return held(ReceivedInvoiceWithholdingFindingKind.INVOICE_INCOMPLETE, target)
    return _Assessment(invoice, target, None, scheme, allocations)


def _read_invoice(assessment: _Assessment, *, modelo: str, period: Period) -> ReceivedInvoiceWithholding:
    """Narrow one assessment to what ``modelo`` declares in ``period`` and what holds it back."""
    if assessment.finding is not None:
        if assessment.finding.modelo not in (None, modelo):
            return _NOTHING
        return ReceivedInvoiceWithholding(observations=(), findings=(assessment.finding,))
    if assessment.target != modelo or assessment.scheme is None:
        return _NOTHING
    invoice, scheme = assessment.invoice, assessment.scheme
    return ReceivedInvoiceWithholding(
        observations=tuple(
            RetencionObservation(
                source_kind=BindingSourceKind.PAYABLE_INVOICE,
                source_object_id=invoice.invoice_id,
                perceptor_nif=invoice.counterparty_tax_id or "",
                perceptor_name=invoice.counterparty_name,
                scheme=scheme,
                taxable_base=row.base,
                retencion_amount=row.retencion,
                accrued_on=row.recognised_on.isoformat(),
            )
            for row in assessment.recognitions
            if period.start_date <= row.recognised_on <= period.end_date and (row.base or row.retencion)
        ),
        findings=(),
    )


_NOTHING: Final = ReceivedInvoiceWithholding(observations=(), findings=())


def _paid_on(movement: Transaction) -> date:
    return movement.raw.value_date or movement.raw.booked_date


def _income_kind(payments: Iterable[Transaction]) -> WithholdingIncomeKind | None:
    """Return the one income kind the paying movements' IRPF categories state, or ``None``."""
    kinds: set[WithholdingIncomeKind] = set()
    for movement in payments:
        if has_rent_irpf_category(movement.irpf_category, direction=TransactionDirection.OUTGOING):
            kinds.add(WithholdingIncomeKind.URBAN_RENT)
        elif has_activity_irpf_category(movement.irpf_category, direction=TransactionDirection.OUTGOING):
            kinds.add(WithholdingIncomeKind.PROFESSIONAL)
        else:
            return None
    return next(iter(kinds)) if len(kinds) == 1 else None


def _scheme(invoice: Invoice, income_kind: WithholdingIncomeKind) -> RetencionScheme | None:
    """Return the scheme the retención falls under, from its income kind and the rate it conforms to."""
    if income_kind is WithholdingIncomeKind.URBAN_RENT:
        return RetencionScheme("arrendamiento_urbano")
    base = invoice.base_total
    retencion = invoice.retention_amount or Decimal("0")
    professional = professional_activity_retencion_rates(effective_date=invoice.issued_at)
    if any(conforms_to_fixed_rate(base, retencion, rate) for rate in professional):
        return RetencionScheme("actividades_profesionales")
    other = statutory_activity_retencion_rates(effective_date=invoice.issued_at) - professional
    if any(conforms_to_fixed_rate(base, retencion, rate) for rate in other):
        return RetencionScheme("actividades_economicas")
    return None


def _allocations(
    invoice: Invoice,
    payments: tuple[Transaction, ...],
    *,
    regime: WithholdingRecipientTaxRegime,
    income_kind: WithholdingIncomeKind,
) -> tuple[_Recognition, ...] | None:
    """Return each payment with the recognition date, euro base and retención recognised on it.

    An IS supplier's rent is recognised whole, when it falls due or when first
    paid if earlier. An IRPF supplier's retención is recognised as it is paid,
    each payment carrying its share of what the invoice leaves to be paid, with
    the cents placed so the shares add up to the invoice exactly.
    """
    base_eur = invoice.base_total_eur
    retencion_eur = invoice.retention_amount_eur
    if base_eur is None or retencion_eur is None:
        return None
    if regime is WithholdingRecipientTaxRegime.IS:
        first = payments[0]
        try:
            recognition = derive_withholding_recognition(
                _evidence(invoice, regime=regime, income_kind=income_kind, payment=first, exigible_on=invoice.issued_at)
            )
        except WithholdingRecognitionError:
            return None
        return (_Recognition(first.transaction_id, recognition.recognized_on, base_eur, retencion_eur),)
    allocations: list[_Recognition] = []
    recognised_base = Decimal("0")
    recognised_retencion = Decimal("0")
    for index, payment in enumerate(payments):
        if not row_settles_invoice(invoice, payment):
            continue
        comparison = settlement_comparison(invoice, payments[: index + 1])
        if comparison is None or comparison.owed <= Decimal("0"):
            return None
        share = (
            Decimal("1")
            if comparison.settled
            else min(Decimal("1"), max(Decimal("0"), comparison.cash / comparison.owed))
        )
        cumulative_base = round_to_cents(base_eur * share)
        cumulative_retencion = round_to_cents(retencion_eur * share)
        try:
            recognition = derive_withholding_recognition(
                _evidence(invoice, regime=regime, income_kind=income_kind, payment=payment, exigible_on=None)
            )
        except WithholdingRecognitionError:
            return None
        allocations.append(
            _Recognition(
                payment.transaction_id,
                recognition.recognized_on,
                cumulative_base - recognised_base,
                cumulative_retencion - recognised_retencion,
            )
        )
        recognised_base, recognised_retencion = cumulative_base, cumulative_retencion
    return tuple(allocations)


def _evidence(
    invoice: Invoice,
    *,
    regime: WithholdingRecipientTaxRegime,
    income_kind: WithholdingIncomeKind,
    payment: Transaction,
    exigible_on: date | None,
) -> WithholdingRecognitionEvidence:
    return WithholdingRecognitionEvidence(
        applicable_year=_paid_on(payment).year if exigible_on is None else exigible_on.year,
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=regime,
        income_kind=income_kind,
        operation_kind=WithholdingOperationKind.ORDINARY,
        payment_or_satisfaction=WithholdingDatedEvent(event_id=payment.transaction_id, occurred_on=_paid_on(payment)),
        exigibility=(
            None if exigible_on is None else WithholdingDatedEvent(event_id=invoice.invoice_id, occurred_on=exigible_on)
        ),
    )


def captured_invoice_ids(observations: Iterable[RetencionObservation]) -> frozenset[str]:
    """Return the invoices the per-perceptor store already holds an allocation of."""
    return frozenset(
        observation.source_object_id
        for observation in observations
        if observation.source_kind is BindingSourceKind.PAYABLE_INVOICE
    )


__all__ = [
    "MovementWithholding",
    "ReceivedInvoiceWithholding",
    "ReceivedInvoiceWithholdingFinding",
    "ReceivedInvoiceWithholdingFindingKind",
    "captured_invoice_ids",
    "received_invoice_movement_withholding",
    "received_invoice_withholding",
    "recipient_tax_regime",
    "states_received_retencion",
    "withholding_subjectness",
]
