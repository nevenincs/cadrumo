"""The invoice catalogue as the IVA source of the canonical ledger aggregation.

LIVA art. 75 accrues IVA on the operation, not on its payment, and art. 97 with
RIVA art. 99 makes the factura the document that grants a deduction. So every
invoice that accrues in a period contributes its lines to that period's IVA
observations, linked to a payment or not, and the bank movement an invoice
names is its payment evidence: it contributes no IVA observation of its own.

Two bounds keep this honest. A movement carrying a bienes de inversión
classification stays the observation carrier, because the register
(LIVA arts. 107-110) is keyed by that movement. And a linked movement whose own
base or cuota contradicts its invoices is refused rather than reconciled.

What still needs the person is returned as typed findings that block filing
grade: an invoice whose deduction family cannot be grounded, an invoice whose
category and counterparty contradict each other, and an unlinked movement with
its own IVA figures that the payment matcher pairs with an in-period invoice --
the same operation would otherwise be declared twice.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field

from ...core.i18n.translatable import Translatable as tr
from ...core.identity.hex_ids import InvoiceId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.iva_deduction_catalogue import is_iva_deduction_kind
from ...domain.invoices.enums import RectificationFact
from ...domain.invoices.models import Invoice
from ...domain.invoices.payment_matching import suggest_payments
from ...domain.invoices.rectification import missing_rectification_facts
from ...domain.invoices.rectification_modification import (
    RectificationModification,
    RectificationModificationRefusal,
)
from ...domain.invoices.rectification_period import RectificationPeriodRefusal
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ..invoices.source_observations import is_rectificativa
from .errors import AggregationValidationError
from .invoice_devengo import invoice_devengo_in_period
from .renta_income_evidence import iva_amount_comparison, taxable_base_comparison
from .source_mesh import CalculationSourceDiagnostic

if TYPE_CHECKING:
    from ...domain.attachments.protocols import AttachmentStoreProtocol
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
    from ...domain.user_profile.values import UserProfileRecord
    from .modelo_bindings_invoice_iva import ScreenedInvoiceIva, ScreenedRectificativa


class TransactionCatalogueByIdReader(Protocol):
    """Read named movements of one bucket by id."""

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        """Return the stored movements among ``transaction_ids``."""
        ...


class InvoiceIvaFindingReason(StrEnum):
    """Why an invoice-sourced IVA period cannot reach filing grade yet."""

    #: A received invoice whose deduction family no evidence grounds: a line at
    #: or above the art. 108 escaso-valor threshold, an import or intra-EU
    #: acquisition, or linked movements that disagree.
    DEDUCTION_FAMILY_UNRESOLVED = "invoice_deduction_family_unresolved"
    #: An invoice whose declared category its counterparty contradicts.
    CATEGORY_CONTRADICTED = "invoice_category_contradicted"
    #: An unlinked movement with its own IVA figures that the payment matcher
    #: pairs with an in-period invoice.
    MOVEMENT_DOUBLE_COUNT = "movement_invoice_double_count"
    #: A taxpayer under the régimen especial del criterio de caja (LIVA
    #: art. 163 terdecies) whose period holds invoices: accrual follows payment
    #: there, and invoices carry no payment-date schedule to place it.
    CASH_ACCOUNTING_UNMODELLED = "invoice_cash_accounting_regime_unmodelled"
    #: An issued invoice whose one recargo de equivalencia spans several IVA
    #: rates and differs from the sum of each rate's LIVA art. 161 share, so no
    #: figure says which Modelo 303 recargo casilla holds which part.
    RECARGO_SPLIT_UNRESOLVED = "invoice_recargo_split_unresolved"
    #: An issued invoice whose recargo de equivalencia at one IVA rate is more
    #: than a cent from base times the LIVA art. 161 rate for that date, is the
    #: labores del tabaco rate no casilla is bound for, or has no published rate.
    RECARGO_NOT_DECLARABLE = "invoice_recargo_not_declarable"
    #: A factura rectificativa whose record does not support a modification at
    #: all: it states none of the facts its side needs, or it substitutes
    #: figures whose original is absent, ambiguous, in another currency, or
    #: runs against the recorded direction. The finding carries the missing
    #: facts and the refusal that names which, so the person can supply or
    #: correct them.
    RECTIFICATIVA_MODIFICATION_UNMODELLED = "invoice_rectificativa_modification_unmodelled"
    #: A factura rectificativa whose signed modification IS derived and whose
    #: period the record does not yet place: the election LIVA art. 89.Cinco or
    #: art. 114.Dos leaves the taxpayer is unrecorded, or an art. 80.Tres
    #: modification carries no attestation of the RIVA art. 24 obligations. The
    #: finding names the invoice field the person opens, and the figures beside
    #: it. Placing it in the period being calculated because it is the one in
    #: hand is exactly the guess the governing decision refuses.
    RECTIFICATIVA_PERIOD_NEEDS_FACT = "invoice_rectificativa_period_needs_fact"
    #: A received modification whose period is this one and whose casilla 40/41
    #: observation could not be built: the invoice it corrects resolves to no
    #: single catalogue record, so the deduction family that routes the box is
    #: unknown, or a row carries a base the deducible-cuota boxes cannot hold.
    RECTIFICATIVA_DEDUCTION_ROW_UNDECLARABLE = "invoice_rectificativa_deduction_row_undeclarable"
    #: An ISSUED modification whose period is this one and whose casilla 14/15
    #: observation could not be built: a row carries a rate the dated tier
    #: table places in no slot, or the modification moves a recargo de
    #: equivalencia, which casillas 25 and 26 hold and no binding reads yet.
    #: Declaring the rest silently would file the period short.
    RECTIFICATIVA_ISSUED_ROW_UNDECLARABLE = "invoice_rectificativa_issued_row_undeclarable"
    #: An issued invoice under the régimen especial de los bienes usados. Its
    #: taxable base is the margin de beneficio, IVA included (LIVA art. 137),
    #: and its cuota is never stated on the invoice (art. 138), so no rate row
    #: declares it; the operator enters the margin base and its cuota.
    USED_GOODS_MARGIN_UNMODELLED = "invoice_used_goods_margin_unmodelled"


class InvoiceIvaFinding(BaseModel):
    """One blocking finding about the invoice side of an IVA period."""

    model_config = STRICT_FROZEN_CONFIG

    reason: InvoiceIvaFindingReason
    #: ``None`` only for a finding about the whole period, never one invoice.
    invoice_id: InvoiceId | None = None
    transaction_id: str | None = Field(default=None, min_length=1, max_length=128)
    #: The rectification facts the invoice's side needs and the record does not
    #: hold, in declaration order, so the finding names the fields the person
    #: opens rather than the family. Empty on every other reason, and also
    #: empty on a rectificativa that states them all: a complete record can
    #: still be held, for a reason that is not a missing fact.
    missing_rectification_facts: tuple[RectificationFact, ...] = ()
    #: Why a rectificativa's modification could not be derived at all. Set only
    #: beside :attr:`InvoiceIvaFindingReason.RECTIFICATIVA_MODIFICATION_UNMODELLED`,
    #: and ``None`` there when the facts are simply absent, which
    #: :attr:`missing_rectification_facts` already names.
    rectification_refusal: RectificationModificationRefusal | None = None
    #: The signed per-rate modification the document makes, carried so the
    #: person sees the figures the derivation read out of it. Set on every
    #: rectificativa finding whose modification IS derived; nothing declares it
    #: there, because the finding is what stands in the way.
    rectification_modification: RectificationModification | None = None
    #: The invoice field a held modification needs before any period holds it,
    #: and the refusal a stated denial produces. Set only beside
    #: :attr:`InvoiceIvaFindingReason.RECTIFICATIVA_PERIOD_NEEDS_FACT`, and
    #: exactly one of the two.
    rectification_period_need: RectificationFact | None = None
    rectification_period_refusal: RectificationPeriodRefusal | None = None


@dataclass(frozen=True, slots=True)
class InvoicePaymentPartition:
    """Which movements are an invoice's payment, and which invoices are the IVA source."""

    #: Movements that pay an invoice and so contribute no IVA observation of their own.
    paid_transaction_ids: frozenset[str]
    #: The invoices whose lines are the IVA source.
    source_invoices: tuple[Invoice, ...]
    #: Every movement an invoice names, by id, for the classification it may record.
    linked_movements: Mapping[str, Transaction] = field(default_factory=dict[str, Transaction])


def _register_bound_ids(movements: Mapping[str, Transaction], *, operation: PinnedAuthorityOperation) -> frozenset[str]:
    """Return the movements classified as a bien de inversión acquisition."""
    return frozenset(
        transaction_id
        for transaction_id, movement in movements.items()
        if movement.deduction_fact_kind is not None
        and is_iva_deduction_kind(movement.deduction_fact_kind, "kind.investment_acquisition", authority=operation)
    )


def partition_invoice_payments(
    invoices: Iterable[Invoice],
    *,
    bucket_id: str,
    linked_movements: TransactionCatalogue,
    operation: PinnedAuthorityOperation,
) -> InvoicePaymentPartition:
    """Split the bucket's invoices into IVA sources and their paying movements.

    A movement classified as a bien de inversión acquisition keeps carrying its
    own observation, and the invoices it pays leave the invoice source, because
    the bienes de inversión register pairs each record with that movement.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    bucket_invoices = tuple(invoice for invoice in invoices if invoice.bucket_id in (None, bucket_id))
    movements = {movement.transaction_id: movement for movement in linked_movements.values()}
    register_bound = _register_bound_ids(movements, operation=operation)
    source_invoices = tuple(
        invoice for invoice in bucket_invoices if not register_bound.intersection(invoice.linked_transaction_ids)
    )
    paid = frozenset(transaction_id for invoice in source_invoices for transaction_id in invoice.linked_transaction_ids)
    return InvoicePaymentPartition(
        paid_transaction_ids=paid,
        source_invoices=source_invoices,
        linked_movements=movements,
    )


def _fully_figured_payments(invoice: Invoice, linked_movements: Mapping[str, Transaction]) -> tuple[Transaction, ...]:
    """Return the paying movements when every one states both a base and a cuota, else nothing."""
    movements = tuple(
        movement
        for transaction_id in invoice.linked_transaction_ids
        if (movement := linked_movements.get(transaction_id)) is not None
    )
    if any(movement.taxable_base is None or movement.iva_amount is None for movement in movements):
        return ()
    return movements


def _paying_movements_contradict(invoice: Invoice, linked_movements: Mapping[str, Transaction]) -> bool:
    """Whether every paying movement states figures that sum to a different base or cuota.

    The figures meet in one currency by the settlement rule: as stated in the invoice's
    own currency, otherwise in EUR. A side with no EUR value leaves nothing to compare.
    """
    movements = _fully_figured_payments(invoice, linked_movements)
    if not movements:
        return False
    base = taxable_base_comparison(invoice, movements)
    cuota = iva_amount_comparison(invoice, movements)
    return any(comparison is not None and comparison.cash != comparison.owed for comparison in (base, cuota))


def contradicting_linked_invoices(partition: InvoicePaymentPartition) -> tuple[Invoice, ...]:
    """Return the invoices whose paying movements state a different base or cuota.

    A movement may carry its own figures; when every movement paying an invoice
    does, their sum must equal the invoice's totals in one currency. A partial set of
    figures is payment evidence only and is not compared.
    """
    return tuple(
        invoice
        for invoice in partition.source_invoices
        if _paying_movements_contradict(invoice, partition.linked_movements)
    )


def refuse_contradicting_linked_movements(contradicted: Sequence[Invoice]) -> None:
    """Refuse a calculation in which a paying movement contradicts its invoice."""
    if contradicted:
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.linked_movement_contradicts_invoice"),
            context={
                "invoice_id": contradicted[0].invoice_id,
                "invoice_count": str(len(contradicted)),
            },
        )


def _outside_window_ids(invoices: Sequence[Invoice], *, period: Period, window_ids: set[str]) -> set[str]:
    """Return the movement ids that invoices accruing in ``period`` name outside the window."""
    return {
        transaction_id
        for invoice in invoices
        if invoice_devengo_in_period(invoice, period=period)
        for transaction_id in invoice.linked_transaction_ids
        if transaction_id not in window_ids
    }


def linked_movements_for_period(
    invoices: Sequence[Invoice],
    *,
    period: Period,
    window: TransactionCatalogue,
    repository: TransactionCatalogueByIdReader,
) -> TransactionCatalogue:
    """Read the movements an invoice names that this period needs.

    The window's own linked rows are already decrypted. An invoice accruing in
    the period may be paid outside it, so its movements are read by id: their
    recorded deduction classification is that invoice's authority.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    named = {transaction_id for invoice in invoices for transaction_id in invoice.linked_transaction_ids}
    in_window = [transaction for transaction in window if transaction.transaction_id in named]
    outside = _outside_window_ids(invoices, period=period, window_ids={t.transaction_id for t in in_window})
    if not outside:
        return TransactionCatalogue.from_transactions(in_window)
    return TransactionCatalogue.from_transactions((*in_window, *repository.load_by_ids(outside)))


def with_movement_side_links(invoices: Sequence[Invoice], *, window: TransactionCatalogue) -> tuple[Invoice, ...]:
    """Add to each invoice the window's movements that name it from their own side.

    A link is one fact stored on both records; a record written before the two
    were kept together can hold it on the movement alone. Reading either side
    keeps such a movement from carrying its own IVA beside its invoice's.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    named: dict[str, set[str]] = {}
    for movement in window:
        if movement.invoice_id is not None:
            named.setdefault(movement.invoice_id, set()).add(movement.transaction_id)
    return tuple(
        invoice
        if not (extra := named.get(invoice.invoice_id, set()) - set(invoice.linked_transaction_ids))
        else invoice.model_copy(
            update={"linked_transaction_ids": tuple(sorted({*invoice.linked_transaction_ids, *extra}))}
        )
        for invoice in invoices
    )


def documented_invoice_ids(store: AttachmentStoreProtocol) -> frozenset[str]:
    """The invoices a stored document belongs to.

    A confirmed PDF or structured e-invoice, or a document attached to the
    invoice afterwards, lists the invoice in its manifest's ``linked_invoice_ids``.
    """
    return frozenset(invoice_id for manifest in store.iter_manifests() for invoice_id in manifest.linked_invoice_ids)


def invoices_missing_source_document(
    invoices: Sequence[Invoice],
    *,
    documented: frozenset[str],
    window: TransactionCatalogue,
) -> tuple[Invoice, ...]:
    """The received invoices claiming a cuota whose factura the records do not hold.

    LIVA art. 97 grants the deduction on the factura itself, so an invoice row
    typed from the Libro de facturas is not that document. It is held when a
    stored document belongs to the invoice, or when a movement paying it carries
    registered purchase-invoice evidence.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    linked = with_movement_side_links(invoices, window=window)
    missing = (
        invoice
        for invoice in linked
        if invoice.kind is InvoiceKind.RECEIVED
        and any(line.iva_amount > 0 for line in invoice.lines)
        and not _holds_its_received_document(invoice, documented=documented, window=window)
    )
    return tuple(sorted(missing, key=lambda invoice: invoice.invoice_id))


def _holds_its_received_document(
    invoice: Invoice,
    *,
    documented: frozenset[str],
    window: TransactionCatalogue,
) -> bool:
    """Whether the records hold the received invoice's own factura (LIVA art. 97).

    The one test for the document behind an input-side claim: a stored document
    belongs to the invoice, or a movement paying it carries registered
    purchase-invoice evidence.
    """
    if invoice.invoice_id in documented:
        return True
    paying = (window.get(transaction_id) for transaction_id in invoice.linked_transaction_ids)
    return any(movement is not None and movement.purchase_invoice_evidence_id is not None for movement in paying)


def rectification_evidence_grounding_invoices(
    invoices: Sequence[Invoice],
    *,
    documented: frozenset[str],
    window: TransactionCatalogue,
) -> tuple[Invoice, ...]:
    """The received facturas rectificativas that ground the ``rectification_evidence`` authority.

    Fact 0085 requires that authority of a rectificación de deducciones, and the
    document that establishes one is the rectificativa itself (LIVA art. 114.Dos,
    RIVA art. 24.2.b). A rectificativa grounds it only when the records hold the
    document, by the same LIVA art. 97 test an ordinary received invoice passes,
    and when it holds the ``document_received_on`` the period rule consumes: a
    typed row with neither is the Libro entry, not the document.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    linked = with_movement_side_links(invoices, window=window)
    grounding = (
        invoice
        for invoice in linked
        if invoice.kind is InvoiceKind.RECEIVED
        and is_rectificativa(invoice)
        and invoice.document_received_on is not None
        and _holds_its_received_document(invoice, documented=documented, window=window)
    )
    return tuple(sorted(grounding, key=lambda invoice: invoice.invoice_id))


def issued_invoices_missing_source_document(
    invoices: Sequence[Invoice],
    *,
    documented: frozenset[str],
    window: TransactionCatalogue,
) -> tuple[Invoice, ...]:
    """The issued invoices charging a cuota whose copy the records do not hold.

    RD 1619/2012 art. 2 obliges the issuer to issue the factura, and the output
    side keeps the visibility standard the movement-side advisory applied before
    the invoice became the IVA source: any stored document belonging to the
    invoice, or any document attached to a movement paying it, holds it.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    linked = with_movement_side_links(invoices, window=window)
    missing = (
        invoice
        for invoice in linked
        if _charges_output_cuota(invoice)
        and invoice.invoice_id not in documented
        and not _paid_by_documented_movement(invoice, window=window)
    )
    return tuple(sorted(missing, key=lambda invoice: invoice.invoice_id))


def _charges_output_cuota(invoice: Invoice) -> bool:
    """Whether ``invoice`` is an issued invoice whose lines charge a cuota."""
    return invoice.kind is InvoiceKind.ISSUED and any(line.iva_amount > 0 for line in invoice.lines)


def _paid_by_documented_movement(invoice: Invoice, *, window: TransactionCatalogue) -> bool:
    """Whether a movement paying ``invoice`` carries an attachment or registered invoice evidence."""
    paying = (window.get(transaction_id) for transaction_id in invoice.linked_transaction_ids)
    return any(
        movement is not None and (movement.purchase_invoice_evidence_id is not None or bool(movement.attachment_ids))
        for movement in paying
    )


@dataclass(frozen=True, slots=True)
class PeriodInvoiceIvaSide:
    """The invoice side of one period, as calculation and ledger readiness both read it."""

    payments: InvoicePaymentPartition
    #: The window's movements no source invoice names: they keep their own IVA facts.
    unpaid_window: TransactionCatalogue
    source: InvoiceIvaSource
    #: Invoices whose paying movements contradict them; calculation refuses these.
    contradicted: tuple[Invoice, ...]


def period_invoice_iva_side(
    invoices: Sequence[Invoice],
    *,
    bucket_id: str,
    period: Period,
    window: TransactionCatalogue,
    repository: TransactionCatalogueByIdReader,
    operation: PinnedAuthorityOperation,
) -> PeriodInvoiceIvaSide:
    """Partition the window by payment and project the period's invoices.

    The one check calculation and ledger readiness share: the ledger says a
    period is ready only when calculation would find the same invoices, the
    same paying movements and the same findings.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    invoices = with_movement_side_links(invoices, window=window)
    payments = partition_invoice_payments(
        invoices,
        bucket_id=bucket_id,
        linked_movements=linked_movements_for_period(invoices, period=period, window=window, repository=repository),
        operation=operation,
    )
    unpaid_window = TransactionCatalogue.from_transactions(
        transaction for transaction in window if transaction.transaction_id not in payments.paid_transaction_ids
    )
    return PeriodInvoiceIvaSide(
        payments=payments,
        unpaid_window=unpaid_window,
        source=invoice_iva_source(
            payments,
            bucket_id=bucket_id,
            period=period,
            unlinked_movements=tuple(unpaid_window),
            operation=operation,
        ),
        contradicted=contradicting_linked_invoices(payments),
    )


@dataclass(frozen=True, slots=True)
class InvoiceIvaSource:
    """The invoice side of one IVA period: observations, findings, and the screen's advisories."""

    observations: tuple[IvaLedgerObservation, ...]
    findings: tuple[InvoiceIvaFinding, ...]
    screen: ScreenedInvoiceIva


def _rectificativa_finding(screened: ScreenedRectificativa) -> InvoiceIvaFinding | None:
    """Hold one rectificativa, or answer ``None`` when nothing about it blocks this period.

    Four blocking outcomes, each naming a different thing the person does: a
    record that supports no modification at all, a modification no period holds
    yet, a received modification this period declares whose casilla could not
    be built, and an issued one whose casilla could not be built.

    ``None`` is the two non-blocking outcomes. A modification declared in THIS
    period and projected into its observations needs no finding: it is
    declared. One declared in ANOTHER period contributes nothing here, which is
    correct rather than a defect, and is disclosed as an excluded contribution
    through :func:`excluded_rectification_diagnostics` instead.
    """
    derived = screened.derived
    modification = derived.modification
    if modification is None:
        return InvoiceIvaFinding(
            reason=InvoiceIvaFindingReason.RECTIFICATIVA_MODIFICATION_UNMODELLED,
            invoice_id=screened.invoice.invoice_id,
            missing_rectification_facts=missing_rectification_facts(screened.invoice),
            rectification_refusal=(
                None if derived.refusal is RectificationModificationRefusal.FACTS_NOT_STATED else derived.refusal
            ),
        )
    decided = screened.decided
    if decided.need is not None or decided.refusal is not None:
        return InvoiceIvaFinding(
            reason=InvoiceIvaFindingReason.RECTIFICATIVA_PERIOD_NEEDS_FACT,
            invoice_id=screened.invoice.invoice_id,
            rectification_modification=modification,
            rectification_period_need=decided.need,
            rectification_period_refusal=decided.refusal,
        )
    if screened.issued_declaration_refusal is not None:
        return InvoiceIvaFinding(
            reason=InvoiceIvaFindingReason.RECTIFICATIVA_ISSUED_ROW_UNDECLARABLE,
            invoice_id=screened.invoice.invoice_id,
            rectification_modification=modification,
        )
    if screened.declaration_refusal is not None:
        return InvoiceIvaFinding(
            reason=InvoiceIvaFindingReason.RECTIFICATIVA_DEDUCTION_ROW_UNDECLARABLE,
            invoice_id=screened.invoice.invoice_id,
            rectification_modification=modification,
        )
    return None


def _screen_findings(screen: ScreenedInvoiceIva) -> list[InvoiceIvaFinding]:
    """Return the findings the invoice screen itself raises, in their reported order."""
    findings = [
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.DEDUCTION_FAMILY_UNRESOLVED, invoice_id=invoice.invoice_id)
        for invoice in screen.deduction_authority_missing
    ]
    findings.extend(
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.CATEGORY_CONTRADICTED, invoice_id=invoice.invoice_id)
        for invoice in screen.category_counterparty_mismatches
    )
    findings.extend(
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.RECARGO_SPLIT_UNRESOLVED, invoice_id=invoice.invoice_id)
        for invoice in screen.recargo_split_unresolved
    )
    findings.extend(
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.RECARGO_NOT_DECLARABLE, invoice_id=invoice.invoice_id)
        for invoice in screen.recargo_not_declarable
    )
    findings.extend(
        finding for screened in screen.rectificativas if (finding := _rectificativa_finding(screened)) is not None
    )
    findings.extend(
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.USED_GOODS_MARGIN_UNMODELLED, invoice_id=invoice.invoice_id)
        for invoice in screen.used_goods_margin_unmodelled
    )
    return findings


def _double_count_findings(
    partition: InvoicePaymentPartition,
    *,
    bucket_id: str,
    period: Period,
    unlinked_movements: Sequence[Transaction],
) -> list[InvoiceIvaFinding]:
    """Return a finding per unlinked self-figured movement the matcher pairs with an in-period invoice."""
    from .modelo_bindings_invoice_iva import invoice_iva_in_period

    in_period = tuple(
        invoice
        for invoice in partition.source_invoices
        if invoice_iva_in_period(invoice, bucket_id=bucket_id, period=period)
    )
    self_figured = tuple(
        movement
        for movement in unlinked_movements
        if movement.transaction_id not in partition.paid_transaction_ids
        and (movement.taxable_base is not None or movement.iva_amount is not None)
    )
    return [
        InvoiceIvaFinding(
            reason=InvoiceIvaFindingReason.MOVEMENT_DOUBLE_COUNT,
            invoice_id=suggestion.pair.invoice.invoice_id,
            transaction_id=suggestion.pair.transaction.transaction_id,
        )
        for suggestion in suggest_payments(self_figured, in_period)
    ]


def invoice_iva_source(
    partition: InvoicePaymentPartition,
    *,
    bucket_id: str,
    period: Period,
    unlinked_movements: Sequence[Transaction],
    operation: PinnedAuthorityOperation,
) -> InvoiceIvaSource:
    """Project the period's source invoices and report what blocks filing grade."""
    from .modelo_bindings_invoice_iva import screened_invoice_iva_observations

    screen = screened_invoice_iva_observations(
        partition.source_invoices,
        bucket_id=bucket_id,
        period=period,
        linked_movements=partition.linked_movements,
        operation=operation,
    )
    findings = _screen_findings(screen)
    findings.extend(
        _double_count_findings(partition, bucket_id=bucket_id, period=period, unlinked_movements=unlinked_movements)
    )
    return InvoiceIvaSource(observations=screen.observations, findings=tuple(findings), screen=screen)


def cash_accounting_enrolled(record: UserProfileRecord | None, *, as_of: date) -> bool:
    """Whether the profile declares the criterio de caja in force on ``as_of``.

    Core types:
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """
    if record is None:
        return False
    from ..user_profile.projections import record_to_path_values

    return record_to_path_values(record, as_of=as_of).get("iva.cash_accounting_regime_enrolled") == "true"


def period_invoice_iva_findings(
    findings: Sequence[InvoiceIvaFinding],
    *,
    invoice_ids: Sequence[str],
    cash_accounting_enrolled: bool,
) -> tuple[InvoiceIvaFinding, ...]:
    """Return every finding that blocks the period, adding the criterio de caja one.

    This is the one check calculation and ledger readiness share, so the
    ledger never says a period is ready that calculation then refuses.
    """
    if cash_accounting_enrolled and invoice_ids:
        return (*findings, InvoiceIvaFinding(reason=InvoiceIvaFindingReason.CASH_ACCOUNTING_UNMODELLED))
    return tuple(findings)


def invoice_iva_finding_diagnostics(
    findings: Sequence[InvoiceIvaFinding],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Persist each finding as a selected-scope evidence failure, which blocks verification and export."""
    return tuple(
        CalculationSourceDiagnostic(
            reason="iva_selected_scope_evidence_failure",
            source_kind="ledger_iva_aggregation",
            resolver_id=resolver_id,
            source_ref=(
                f"transaction:{finding.transaction_id}"
                if finding.transaction_id is not None
                else f"invoice:{finding.invoice_id}"
                if finding.invoice_id is not None
                else None
            ),
            message=f"selected-scope IVA evidence failure: {finding.reason.value}",
        )
        for finding in findings
    )


__all__ = [
    "InvoiceIvaFinding",
    "InvoiceIvaFindingReason",
    "InvoiceIvaSource",
    "InvoicePaymentPartition",
    "PeriodInvoiceIvaSide",
    "TransactionCatalogueByIdReader",
    "cash_accounting_enrolled",
    "contradicting_linked_invoices",
    "documented_invoice_ids",
    "invoice_iva_finding_diagnostics",
    "invoice_iva_source",
    "invoices_missing_source_document",
    "issued_invoices_missing_source_document",
    "linked_movements_for_period",
    "partition_invoice_payments",
    "period_invoice_iva_findings",
    "period_invoice_iva_side",
    "rectification_evidence_grounding_invoices",
    "refuse_contradicting_linked_movements",
    "with_movement_side_links",
]
