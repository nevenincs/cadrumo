"""Canonical IVA transaction classification and observation projection.

This module owns the per-transaction IVA pipeline. Repository aggregation remains
in :mod:`.iva_ledger`; this module owns the transaction-level admission,
classification, and observation sinks consumed by that orchestrator.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...core.i18n.render import tr as render_tr
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ...domain.iva.deduction_facts import (
    IvaDeductionClassificationProvenance,
    admits_iva_deduction_classification,
    validate_iva_deduction_fact,
)
from ...domain.iva.errors import IvaValidationError
from ...domain.iva.flow import (
    IvaFlowDirection,
    is_deducible_flow,
    received_flow_direction,
)
from ...domain.iva.prorrata import InputClassification
from ...domain.iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
    default_iva_cash_accounting_treatment,
)
from ...domain.transactions.models import Transaction
from .iva_ledger import IvaLedgerAggregationIssue, IvaLedgerAggregationIssueReason, ProrrataLedgerReference
from .iva_ledger_classification import (
    prorrata_reference_for,
)


def inadmissible_deduction_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
    base_amount: Decimal,
    iva_amount: Decimal,
) -> IvaLedgerAggregationIssue | None:
    """Return why a PRESENT deduction classification is inadmissible, or ``None``.

    Asks the domain validator the observation's own model validator asks, from
    the exact facts the caller is about to put on an observation. The validator
    remains the sole authority on admissibility -- the deduction applicability
    catalogue's closed pairing table -- and this adds no rule to it. What it adds
    is a boundary the refusal can be REPORTED at: consulted only inside the
    observation, the answer arrives as a payload-boundary defect naming a model
    class, with no ledger row, no field and no remedy for the operator whose data
    is wrong.

    The row's deduction identity fields travel with the transaction, while the
    monetary facts are passed: a criterio-de-caja split carries a payment's share
    of the base and cuota rather than the operation's, and the rectification
    contract reads those amounts.

    Absence is deliberately not this gate's business. A deducible row with no
    kind or no provenance is
    :attr:`IvaLedgerAggregationIssueReason.MISSING_DEDUCTION_CLASSIFICATION`;
    answering ``None`` for it here keeps the two remedies distinct, because an
    absent classification is SUPPLIED and an inadmissible one is CORRECTED.
    """
    deduction_fact_kind = transaction.deduction_fact_kind
    deduction_provenance = transaction.deduction_provenance
    if deduction_fact_kind is None and deduction_provenance is None:
        return None
    if deduction_fact_kind is None or deduction_provenance is None:
        # Half declared: a kind with no evidence behind it, or evidence naming no
        # kind. The pairing validator below needs both to say anything, so the one
        # question answerable here is whether the row bears a deducible cuota for
        # an authority to attach to at all. Where it does, the gap is ABSENCE and
        # MISSING_DEDUCTION_CLASSIFICATION owns it; where it does not -- an output
        # row's repercutida cuota, an exempt or not-subject purchase, a recargo de
        # equivalencia acquisition cost -- there is nothing to complete and the
        # half-declaration is itself the error. Falling through, it reached the
        # operator as a payload-boundary defect from the observation's validator.
        if is_deducible_flow(flow_direction) and admits_iva_deduction_classification(
            category=category,
            flow_direction=flow_direction,
        ):
            return None
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
            detail=render_tr(
                "aggregation.iva_ledger.errors.deduction_authority_on_non_deducible_row",
                category=category.value,
                flow_direction=flow_direction.value,
            ),
        )
    # A COMPLETE classification is refused by the validator itself, which names
    # the declared kind and the exact refusal. Screening the flow and the
    # admissible families here first would answer the same rows with a message
    # that names neither, so the specific answer is left to speak: fact 0085's
    # family table is what :func:`admits_iva_deduction_classification` reads, so a
    # row it admits nothing for cannot pass the validator either.
    try:
        validate_iva_deduction_fact(
            kind=deduction_fact_kind,
            provenance=deduction_provenance,
            category=category,
            rate_kind=rate_kind,
            flow_direction=flow_direction,
            base_amount=base_amount,
            iva_amount=iva_amount,
            investment_asset_id=transaction.investment_asset_id,
            rectifies_ledger_id=transaction.rectifies_ledger_id,
        )
    except IvaValidationError as exc:
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
            detail=render_tr(
                "aggregation.iva_ledger.errors.inadmissible_deduction_classification",
                deduction_fact_kind=deduction_fact_kind.value,
                iva_category=category.value,
                refusal=str(exc),
            ),
        )
    return None


def iva_observation(
    *,
    ledger_id: str,
    transaction_date: date,
    category: IvaCategory,
    exemption_article: IvaExemptionArticle | None,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
    base_amount: Decimal,
    iva_amount: Decimal,
    recargo_amount: Decimal = Decimal("0"),
    prorrata_reference_id: str | None = None,
    cash_accounting_treatment: IvaCashAccountingTreatment | None = None,
    observation_role: IvaLedgerObservationRole,
    input_classification: InputClassification | None = None,
    prorrata_sector_id: str | None = None,
    applied_rate: Decimal | None = None,
    deduction_fact_kind: IvaDeductionFactKind | None,
    deduction_provenance: IvaDeductionClassificationProvenance | None,
    investment_asset_id: str | None = None,
    rectifies_ledger_id: str | None = None,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerObservation:
    """Build an observation from the admitted transaction facts."""
    if cash_accounting_treatment is None:
        cash_accounting_treatment = default_iva_cash_accounting_treatment(authority=operation)
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=transaction_date,
        category=category,
        exemption_article=exemption_article,
        rate_kind=rate_kind,
        applied_rate=applied_rate,
        flow_direction=flow_direction,
        base_amount=base_amount,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
        prorrata_reference_id=prorrata_reference_id,
        cash_accounting_treatment=cash_accounting_treatment,
        observation_role=observation_role,
        input_classification=input_classification,
        prorrata_sector_id=prorrata_sector_id,
        deduction_fact_kind=deduction_fact_kind,
        deduction_provenance=deduction_provenance,
        investment_asset_id=investment_asset_id,
        rectifies_ledger_id=rectifies_ledger_id,
    )


def cash_accounting_observations(
    transaction: Transaction,
    *,
    resolved_period: Period,
    operation_date: date,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
    proportionality: Decimal,
    full_base_amount: Decimal,
    full_iva_amount: Decimal,
    linked_prorrata_id: str | None,
    deduction_fact_kind: IvaDeductionFactKind | None,
    deduction_provenance: IvaDeductionClassificationProvenance | None,
    operation: PinnedAuthorityOperation,
) -> tuple[IvaLedgerObservation, ...] | IvaLedgerAggregationIssue:
    """Project payment settlements and the operation information row."""
    # Carried onto every observation this producer emits, exactly as the
    # ordinary path carries it. ``applied_rate is None`` is a claim that the
    # rate is genuinely UNKNOWN, and it makes an observation match no
    # rate-specific binding at all -- but a cash-accounting row knows its rate
    # as well as any other, having just had ``rate_kind`` resolved FROM it.
    # Omitting it filed a criterio-de-caja return whose tier totals were
    # populated while every official rate box beneath them was blank.
    applied_rate = transaction.iva_rate
    observations: list[IvaLedgerObservation] = []
    for payment_date, base_amount, iva_amount, recargo_amount in _cash_accounting_settlement_parts(transaction):
        if not resolved_period.contains(payment_date):
            continue
        # Re-asked per settlement part, not once for the operation. The
        # deduction contract reads the base and cuota, and a criterio-de-caja
        # split gives each observation a payment's share of both, so the
        # operation-level answer does not settle the part's.
        inadmissible_deduction = inadmissible_deduction_issue(
            transaction,
            transaction_id=transaction.transaction_id,
            category=category,
            rate_kind=rate_kind,
            flow_direction=flow_direction,
            base_amount=base_amount,
            iva_amount=iva_amount * proportionality,
        )
        if inadmissible_deduction is not None:
            return inadmissible_deduction
        observations.append(
            iva_observation(
                ledger_id=transaction.transaction_id,
                transaction_date=payment_date,
                category=category,
                exemption_article=transaction.exemption_article,
                rate_kind=rate_kind,
                flow_direction=flow_direction,
                base_amount=base_amount,
                iva_amount=iva_amount * proportionality,
                recargo_amount=recargo_amount * proportionality,
                prorrata_reference_id=linked_prorrata_id,
                cash_accounting_treatment=transaction.cash_accounting_treatment,
                observation_role=IvaLedgerObservationRole.SETTLEMENT,
                input_classification=transaction.input_classification,
                prorrata_sector_id=transaction.prorrata_sector_id,
                applied_rate=applied_rate,
                deduction_fact_kind=deduction_fact_kind,
                deduction_provenance=deduction_provenance,
                investment_asset_id=transaction.investment_asset_id,
                rectifies_ledger_id=transaction.rectifies_ledger_id,
                operation=operation,
            ),
        )
    if resolved_period.contains(operation_date):
        observations.append(
            iva_observation(
                ledger_id=transaction.transaction_id,
                transaction_date=operation_date,
                category=category,
                exemption_article=transaction.exemption_article,
                rate_kind=rate_kind,
                flow_direction=flow_direction,
                base_amount=full_base_amount,
                iva_amount=full_iva_amount,
                cash_accounting_treatment=transaction.cash_accounting_treatment,
                observation_role=IvaLedgerObservationRole.OPERATION_INFORMATIONAL,
                input_classification=transaction.input_classification,
                prorrata_sector_id=transaction.prorrata_sector_id,
                applied_rate=applied_rate,
                deduction_fact_kind=deduction_fact_kind,
                deduction_provenance=deduction_provenance,
                investment_asset_id=transaction.investment_asset_id,
                rectifies_ledger_id=transaction.rectifies_ledger_id,
                operation=operation,
            ),
        )
    return tuple(observations)


def _append_unpaid_cash_accounting_remainder(
    transaction: Transaction,
    parts: list[tuple[date, Decimal, Decimal, Decimal]],
    *,
    taxable_base: Decimal,
    iva_amount: Decimal,
    operation_date: date,
) -> None:
    remainder = (
        taxable_base - sum((part[1] for part in parts), Decimal("0")),
        iva_amount - sum((part[2] for part in parts), Decimal("0")),
        (transaction.recargo_amount or Decimal("0")) - sum((part[3] for part in parts), Decimal("0")),
    )
    if any(amount > Decimal("0") for amount in remainder):
        fallback_date = date(operation_date.year + 1, 12, 31)
        parts.append((fallback_date, *remainder))


def _cash_accounting_settlement_parts(
    transaction: Transaction,
) -> tuple[tuple[date, Decimal, Decimal, Decimal], ...]:
    operation_date = transaction.operation_date
    taxable_base = transaction.taxable_base
    iva_amount = transaction.iva_amount
    if operation_date is None or taxable_base is None or iva_amount is None:
        msg = (
            f"transaction {transaction.transaction_id} reached criterio-de-caja settlement without an "
            "operation date, taxable base or cuota; a devengo split cannot be measured from it"
        )
        raise ValueError(msg)
    parts = [
        (
            evidence.payment_date,
            evidence.taxable_base,
            evidence.iva_amount,
            evidence.recargo_amount,
        )
        for evidence in transaction.cash_accounting_payment_evidence
    ]
    _append_unpaid_cash_accounting_remainder(
        transaction,
        parts,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        operation_date=operation_date,
    )
    return tuple(sorted(parts, key=lambda part: part[0]))


def resolve_iva_prorrata_attachment(
    transaction: Transaction,
    *,
    flow_direction: IvaFlowDirection,
    operation_date: date,
    base_amount: Decimal,
    iva_amount: Decimal,
) -> tuple[ProrrataLedgerReference | None, IvaLedgerAggregationIssue | None, str | None]:
    """Resolve the (prorrata-reference, prorrata-issue, linked-id) triple.

    Returns ``(None, None, None)`` when the transaction carries no
    prorrata_reference. Returns ``(None, issue, None)`` when the
    reference fails parsing OR the row is not a supported-input IVA
    row (prorrata only attaches to SOPORTADO flows). Returns
    ``(reference, None, transaction_id)`` for a valid attachment.
    """
    raw_reference = prorrata_reference_for(
        transaction.prorrata_reference,
        transaction_id=transaction.transaction_id,
    )
    if isinstance(raw_reference, IvaLedgerAggregationIssue):
        return None, raw_reference, None
    if raw_reference is None:
        return None, None, None
    if flow_direction != received_flow_direction():
        return (
            None,
            IvaLedgerAggregationIssue(
                transaction_id=transaction.transaction_id,
                reason=IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE,
                detail="prorrata_reference may only be attached to supported input IVA rows",
            ),
            None,
        )
    return (
        ProrrataLedgerReference(
            transaction_id=transaction.transaction_id,
            transaction_date=operation_date,
            reference=raw_reference,
            base_amount=base_amount,
            input_iva_amount=iva_amount,
        ),
        None,
        transaction.transaction_id,
    )
