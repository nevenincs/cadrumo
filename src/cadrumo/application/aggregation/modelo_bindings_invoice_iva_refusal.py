"""Invoice-to-ledger IVA refusal policy for modelo-binding resolution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from ...core.i18n.translatable import Translatable as tr
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ...domain.calculations.registry.ledger_iva_screen_bindings import (
    IvaLedgerScreenBinding,
    invoice_ledger_screen_binding_ids,
    invoice_ledger_screen_bindings,
)
from ...domain.invoices.models import Invoice
from ...domain.iva.flow import IvaFlowDirection, issued_flow_direction, received_flow_direction
from ...domain.iva.schema import InvoiceKind
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from .errors import AggregationValidationError
from .iva_ledger import IvaLedgerProrrataApportionment
from .iva_ledger_apportionment import resolve_iva_ledger_binding_values
from .modelo_bindings_invoice_iva import (
    M303_INVOICE_EVIDENCE_SAMPLE_LIMIT,
    InvoiceIvaSilenceReport,
    ScreenedInvoiceIva,
    line_contributes_to_the_iva_screen,
    line_eur_amounts_or_refuse,
    screened_invoice_iva_observations,
)
from .preconditions import AggregationPreconditionCondition, aggregation_no_recovery_verdict
from .source_mesh import (
    CalculationSourceContext,
)


def uncovered_withheld_invoice_cuota(
    invoices: Sequence[Invoice],
    *,
    screen_bindings: Sequence[IvaLedgerScreenBinding],
    transaction_binding_values: Mapping[BindingId, Decimal],
) -> Decimal:
    """Return the withheld invoices' cuota that the transaction ledger does not carry.

    These invoices were withheld because no linked frozen ledger observation
    supplies their deduction identity, so they contribute no
    :class:`IvaLedgerObservation` and cannot be compared binding-by-binding the
    way a projected invoice is. Their cuota is therefore weighed against the
    transaction-ledger total across the screened cuota bindings of the SAME IVA
    flow.

    That total is the right comparator rather than a per-binding one: the
    withheld invoice has no resolved binding to be compared against, and the
    question being asked is the coarse one -- is this cuota already somewhere in
    the ledger the filing is about to use, or is it absent from it entirely? A
    positive result means the ledger is genuinely short by at least this much and
    the filing would under-declare; zero means the operation is already recorded
    and the invoice merely is not linked to it.

    Two comparisons keep that coarse question honest. Invoice lines are
    denominated in the invoice's currency while ledger values are EUR, so each
    line is converted through the shared EUR conversion (refusing when the
    invoice cannot convert). And each flow is weighed only against its own
    slots: received-invoice cuota against the input slot, issued against the
    output slots, so sales IVA cannot cover a missing purchase cuota.
    """
    received_flow = received_flow_direction()
    evidence_by_flow: dict[IvaFlowDirection, Decimal] = {}
    for invoice in invoices:
        flow = received_flow if invoice.kind is InvoiceKind.RECEIVED else issued_flow_direction()
        for line_index, line in enumerate(invoice.lines):
            if not line_contributes_to_the_iva_screen(line.subtotal, line.iva_amount):
                continue
            _base_eur, iva_amount_eur = line_eur_amounts_or_refuse(invoice, line_index, line)
            evidence_by_flow[flow] = evidence_by_flow.get(flow, Decimal("0")) + iva_amount_eur
    uncovered = Decimal("0")
    for flow, evidence in evidence_by_flow.items():
        ledger_total = sum(
            (
                transaction_binding_values.get(screen_binding.binding_id, Decimal("0"))
                for screen_binding in screen_bindings
                if screen_binding.selector.flow_direction == flow
            ),
            Decimal("0"),
        )
        uncovered += max(evidence - ledger_total, Decimal("0"))
    return uncovered


def raise_if_invoice_iva_would_be_silent(
    *,
    context: CalculationSourceContext,
    period: Period,
    operation: PinnedAuthorityOperation,
    transaction_binding_values: Mapping[BindingId, Decimal],
    ledger_observations: Sequence[IvaLedgerObservation] = (),
    ports: InvoiceCatalogueReadPorts,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None,
    screened_bindings: tuple[BindingId, ...] | None = None,
) -> InvoiceIvaSilenceReport:
    """Refuse a filing whose invoice IVA would be absent from its ledger totals.

    The IVA cuota boxes are sourced from ``ledger_iva_aggregation``: the
    transaction ledger is the filing authority. A bucket can also carry real
    invoice catalogue evidence, and there is no invoice binding family for
    these boxes. If invoice IVA exists for the period and would exceed the
    transaction-ledger cuota the filing is about to use, calculating a
    zero/subtotal filing would silently under-declare. Refuse, and require the
    operator to link and classify the transactions that feed the canonical
    ledger path.

    **Applies to M303 and M390 revisions whose typed screen shapes resolve the
    seven conceptual slots.** M390 declares the same seven concepts M303 does
    under its own id prefix, so the selected revision supplies the IDs rather
    than a second Python table. Two implementations of one comparison would be
    free to drift, and a widening applied to one and not the other is invisible
    until a filing is wrong -- which is exactly how the ES-only counterparty
    filter and the missing recargo tiers survived on the M303 side.

    The annual modelo needs this more than the quarterly one, not less. Its
    390-to-303 reconciliation BLOCKING_RULE compares two figures that both root
    in the same ledger, so it detects a transaction booked into the wrong
    quarter and cannot detect one that was never recorded at all: both sides
    are equally short and the rule passes.

    Returns:
        A pair. First, the invoices whose IVA was compared against the ledger,
        so the caller can disclose how their period placement was arrived at.
        Second, the invoices withheld because their declared category and their
        counterparty country contradict each other -- carried out separately
        because they reached NO casilla, so the caller must report them rather
        than describe their placement. Both empty when the modelo is not
        screened or there was nothing to compare.

        The second element survives the early return below: a period whose
        every invoice was withheld produces no observations at all, and that is
        precisely the case where staying silent would be worst.

    screened_bindings may be supplied by the source-mesh resolver after it
    resolves the selected revision. Direct callers that omit it receive the
    same typed revision-selected query here; no static model-to-binding table
    is consulted.
    """
    if screened_bindings is None:
        screened_bindings = invoice_ledger_screen_binding_ids(
            context.revision,
            modelo=context.modelo,
        )
    if not screened_bindings:
        return InvoiceIvaSilenceReport()
    screened = screened_invoice_iva_observations(
        context=context,
        period=period,
        ledger_observations=ledger_observations,
        ports=ports,
        operation=operation,
    )
    # A withheld invoice's cuota is gross, so it is weighed against the ledger's
    # gross cuota: a prorrata reduces what the ledger deducts, not what it records.
    gross_transaction_binding_values = (
        transaction_binding_values
        if prorrata_apportionment is None
        else resolve_iva_ledger_binding_values(
            context.revision,
            ledger_observations,
            prorrata_apportionment=None,
            operation=operation,
        )
    )
    return raise_if_screened_invoice_iva_would_be_silent(
        context=context,
        screened_bindings=screened_bindings,
        screened=screened,
        transaction_binding_values=transaction_binding_values,
        gross_transaction_binding_values=gross_transaction_binding_values,
        prorrata_apportionment=prorrata_apportionment,
        operation=operation,
    )


def raise_if_screened_invoice_iva_would_be_silent(
    *,
    context: CalculationSourceContext,
    screened_bindings: tuple[BindingId, ...],
    screened: ScreenedInvoiceIva,
    transaction_binding_values: Mapping[BindingId, Decimal],
    gross_transaction_binding_values: Mapping[BindingId, Decimal],
    prorrata_apportionment: IvaLedgerProrrataApportionment | None,
    operation: PinnedAuthorityOperation,
) -> InvoiceIvaSilenceReport:
    """Compare screened invoice facts with the canonical ledger projection.

    The repository-backed wrapper owns acquisition and period screening. This
    deterministic half owns the one refusal policy over that frozen result, so
    callers and proofs use the same IVA binding projector and terminal facts.
    Withheld invoices carry no binding of their own, so their gross cuota is
    weighed against ``gross_transaction_binding_values`` -- the ledger before
    any prorrata -- while projected invoices are apportioned like the ledger
    and compared with ``transaction_binding_values``.
    """
    # Withholding an unauthorised input row is unconditional; REFUSING the whole
    # filing over it is not. This guard's criterion, stated in its own docstring,
    # is invoice IVA that would EXCEED the transaction-ledger cuota -- that is the
    # under-declaration. An unlinked purchase invoice whose cuota the ledger
    # already carries is corroborating evidence of an operation that IS declared,
    # so refusing there blocks a filing whose totals are correct. It stays
    # withheld (no invented deduction family reaches a casilla) and the operator
    # is told through the diagnostic channel instead.
    uncovered_authority_evidence = uncovered_withheld_invoice_cuota(
        screened.deduction_authority_missing,
        screen_bindings=tuple(
            screen_binding
            for screen_binding in invoice_ledger_screen_bindings(context.revision, modelo=context.modelo)
            if screen_binding.binding_id in screened_bindings
        ),
        transaction_binding_values=gross_transaction_binding_values,
    )
    if uncovered_authority_evidence > Decimal("0"):
        missing_invoice_ids = tuple(sorted(invoice.invoice_id for invoice in screened.deduction_authority_missing))
        raise AggregationValidationError(
            tr("errors.error.error_modelo_aggregation_binding"),
            context={
                "reason": "invoice_deduction_authority_missing_from_transaction_ledger",
                "modelo": context.modelo,
                "filing_year": str(context.filing_year),
                "period": context.period.registry_token,
                "source_kind": "ledger_iva_aggregation",
                "invoice_ids": missing_invoice_ids[:M303_INVOICE_EVIDENCE_SAMPLE_LIMIT],
                "invoice_count": str(len(missing_invoice_ids)),
                "invoice_cuota_exceeding_ledger": str(uncovered_authority_evidence),
            },
            precondition_verdict=aggregation_no_recovery_verdict(
                AggregationPreconditionCondition.INVOICE_LEDGER_COMPLETE,
                facts={
                    "modelo": str(context.modelo),
                    "filing_year": str(context.filing_year),
                    "period": context.period.registry_token,
                    "source_kind": "ledger_iva_aggregation",
                    "invoice_count": len(missing_invoice_ids),
                    "missing_binding_count": 0,
                },
            ),
        )
    if not screened.observations:
        return InvoiceIvaSilenceReport(
            category_counterparty_mismatches=screened.category_counterparty_mismatches,
            reverse_charge_underivable=screened.reverse_charge_underivable,
            deduction_authority_missing=screened.deduction_authority_missing,
            recargo_rate_divergences=screened.recargo_rate_divergences,
            recargo_unattributable=screened.recargo_unattributable,
            storage_degraded=screened.storage_degraded,
        )
    invoice_binding_values = resolve_iva_ledger_binding_values(
        context.revision,
        screened.observations,
        prorrata_apportionment=prorrata_apportionment,
        operation=operation,
    )
    missing_binding_values = {
        binding_id: invoice_value - transaction_value
        for binding_id in screened_bindings
        if (invoice_value := invoice_binding_values.get(binding_id, Decimal("0")))
        > (transaction_value := transaction_binding_values.get(binding_id, Decimal("0")))
    }
    if not missing_binding_values:
        return InvoiceIvaSilenceReport(
            compared=screened.compared,
            category_counterparty_mismatches=screened.category_counterparty_mismatches,
            reverse_charge_underivable=screened.reverse_charge_underivable,
            deduction_authority_missing=screened.deduction_authority_missing,
            recargo_rate_divergences=screened.recargo_rate_divergences,
            recargo_unattributable=screened.recargo_unattributable,
            storage_degraded=screened.storage_degraded,
        )
    raise AggregationValidationError(
        tr("errors.error.error_modelo_aggregation_binding"),
        context={
            "reason": "invoice_domestic_iva_not_in_transaction_ledger",
            "modelo": context.modelo,
            "filing_year": str(context.filing_year),
            "period": context.period.registry_token,
            "source_kind": "ledger_iva_aggregation",
            "invoice_domestic_iva_excess_by_binding": {
                binding_id: str(amount) for binding_id, amount in missing_binding_values.items()
            },
            "invoice_ids": tuple(sorted(screened.invoice_ids)[:M303_INVOICE_EVIDENCE_SAMPLE_LIMIT]),
            "invoice_count": str(len(screened.invoice_ids)),
        },
        precondition_verdict=aggregation_no_recovery_verdict(
            AggregationPreconditionCondition.INVOICE_LEDGER_COMPLETE,
            facts={
                "modelo": str(context.modelo),
                "filing_year": str(context.filing_year),
                "period": context.period.registry_token,
                "source_kind": "ledger_iva_aggregation",
                "invoice_count": len(screened.invoice_ids),
                "missing_binding_count": len(missing_binding_values),
            },
        ),
    )
