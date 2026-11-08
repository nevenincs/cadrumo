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
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field

from ...core.i18n.translatable import Translatable as tr
from ...core.identity.hex_ids import InvoiceId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.iva_deduction_catalogue import is_iva_deduction_kind
from ...domain.invoices.models import Invoice, InvoiceKind
from ...domain.invoices.payment_matching import suggest_payments
from ...domain.transactions.models import Transaction, TransactionCatalogue
from .errors import AggregationValidationError
from .invoice_devengo import invoice_devengo_in_period
from .source_mesh import CalculationSourceDiagnostic

if TYPE_CHECKING:
    from ...domain.attachments.protocols import AttachmentStoreProtocol
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
    from ...domain.user_profile.values import UserProfileRecord
    from .modelo_bindings_invoice_iva import ScreenedInvoiceIva


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


class InvoiceIvaFinding(BaseModel):
    """One blocking finding about the invoice side of an IVA period."""

    model_config = STRICT_FROZEN_CONFIG

    reason: InvoiceIvaFindingReason
    #: ``None`` only for a finding about the whole period, never one invoice.
    invoice_id: InvoiceId | None = None
    transaction_id: str | None = Field(default=None, min_length=1, max_length=128)


@dataclass(frozen=True, slots=True)
class InvoicePaymentPartition:
    """Which movements are an invoice's payment, and which invoices are the IVA source."""

    #: Movements that pay an invoice and so contribute no IVA observation of their own.
    paid_transaction_ids: frozenset[str]
    #: The invoices whose lines are the IVA source.
    source_invoices: tuple[Invoice, ...]
    #: Every movement an invoice names, by id, for the classification it may record.
    linked_movements: Mapping[str, Transaction] = field(default_factory=dict[str, Transaction])


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
    """
    bucket_invoices = tuple(invoice for invoice in invoices if invoice.bucket_id in (None, bucket_id))
    movements = {movement.transaction_id: movement for movement in linked_movements.values()}
    register_bound = frozenset(
        transaction_id
        for transaction_id, movement in movements.items()
        if movement.deduction_fact_kind is not None
        and is_iva_deduction_kind(movement.deduction_fact_kind, "kind.investment_acquisition", authority=operation)
    )
    source_invoices = tuple(
        invoice for invoice in bucket_invoices if not register_bound.intersection(invoice.linked_transaction_ids)
    )
    paid = frozenset(transaction_id for invoice in source_invoices for transaction_id in invoice.linked_transaction_ids)
    return InvoicePaymentPartition(
        paid_transaction_ids=paid,
        source_invoices=source_invoices,
        linked_movements=movements,
    )


def contradicting_linked_invoices(partition: InvoicePaymentPartition) -> tuple[Invoice, ...]:
    """Return the invoices whose paying movements state a different base or cuota.

    A movement may carry its own figures; when every movement paying an invoice
    does, their sum must equal the invoice's EUR totals. A partial set of
    figures is payment evidence only and is not compared.
    """
    contradicted: list[Invoice] = []
    for invoice in partition.source_invoices:
        movements = tuple(
            movement
            for transaction_id in invoice.linked_transaction_ids
            if (movement := partition.linked_movements.get(transaction_id)) is not None
        )
        if not movements or any(movement.taxable_base is None or movement.iva_amount is None for movement in movements):
            continue
        stated_base = sum((movement.taxable_base or Decimal("0") for movement in movements), Decimal("0"))
        stated_cuota = sum((movement.iva_amount or Decimal("0") for movement in movements), Decimal("0"))
        if (stated_base, stated_cuota) != (invoice.base_total_eur, invoice.iva_total_eur):
            contradicted.append(invoice)
    return tuple(contradicted)


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
    """
    named = {transaction_id for invoice in invoices for transaction_id in invoice.linked_transaction_ids}
    in_window = [transaction for transaction in window if transaction.transaction_id in named]
    window_ids = {transaction.transaction_id for transaction in in_window}
    outside = {
        transaction_id
        for invoice in invoices
        if invoice_devengo_in_period(invoice, period=period)
        for transaction_id in invoice.linked_transaction_ids
        if transaction_id not in window_ids
    }
    if not outside:
        return TransactionCatalogue.from_transactions(in_window)
    return TransactionCatalogue.from_transactions((*in_window, *repository.load_by_ids(outside)))


def with_movement_side_links(invoices: Sequence[Invoice], *, window: TransactionCatalogue) -> tuple[Invoice, ...]:
    """Add to each invoice the window's movements that name it from their own side.

    A link is one fact stored on both records; a record written before the two
    were kept together can hold it on the movement alone. Reading either side
    keeps such a movement from carrying its own IVA beside its invoice's.
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
    """
    linked = with_movement_side_links(invoices, window=window)
    missing: list[Invoice] = []
    for invoice in linked:
        if invoice.kind is not InvoiceKind.RECEIVED or not any(line.iva_amount > 0 for line in invoice.lines):
            continue
        if invoice.invoice_id in documented:
            continue
        paying = (window.get(transaction_id) for transaction_id in invoice.linked_transaction_ids)
        if any(movement is not None and movement.purchase_invoice_evidence_id is not None for movement in paying):
            continue
        missing.append(invoice)
    return tuple(sorted(missing, key=lambda invoice: invoice.invoice_id))


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


def invoice_iva_source(
    partition: InvoicePaymentPartition,
    *,
    bucket_id: str,
    period: Period,
    unlinked_movements: Sequence[Transaction],
    operation: PinnedAuthorityOperation,
) -> InvoiceIvaSource:
    """Project the period's source invoices and report what blocks filing grade."""
    from .modelo_bindings_invoice_iva import invoice_iva_in_period, screened_invoice_iva_observations

    screen = screened_invoice_iva_observations(
        partition.source_invoices,
        bucket_id=bucket_id,
        period=period,
        linked_movements=partition.linked_movements,
        operation=operation,
    )
    findings = [
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.DEDUCTION_FAMILY_UNRESOLVED, invoice_id=invoice.invoice_id)
        for invoice in screen.deduction_authority_missing
    ]
    findings.extend(
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.CATEGORY_CONTRADICTED, invoice_id=invoice.invoice_id)
        for invoice in screen.category_counterparty_mismatches
    )
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
    findings.extend(
        InvoiceIvaFinding(
            reason=InvoiceIvaFindingReason.MOVEMENT_DOUBLE_COUNT,
            invoice_id=suggestion.pair.invoice.invoice_id,
            transaction_id=suggestion.pair.transaction.transaction_id,
        )
        for suggestion in suggest_payments(self_figured, in_period)
    )
    return InvoiceIvaSource(observations=screen.observations, findings=tuple(findings), screen=screen)


def cash_accounting_enrolled(record: UserProfileRecord | None, *, as_of: date) -> bool:
    """Whether the profile declares the criterio de caja in force on ``as_of``."""
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
    "linked_movements_for_period",
    "partition_invoice_payments",
    "period_invoice_iva_findings",
    "period_invoice_iva_side",
    "refuse_contradicting_linked_movements",
    "with_movement_side_links",
]
