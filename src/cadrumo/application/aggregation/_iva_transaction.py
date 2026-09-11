"""Canonical IVA transaction classification and observation projection.

This module owns the per-transaction IVA pipeline. Repository aggregation remains
in :mod:`.iva_ledger`; this module owns the transaction-level admission,
classification, and observation sinks consumed by that orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.period import Period
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.iva.classification import InvoiceKind, domestic_categories_by_rate_kind
from ...domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ...domain.iva.flow import IvaFlowDirection, derive_flow_for_classification
from ...domain.iva.prorrata import InputClassification
from ...domain.iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.models import Transaction
from .currency_predicates import is_non_eur_without_conversion
from .invoice_kind import invoice_kind_for_direction
from .iva_ledger import (
    IvaLedgerAggregationIssue,
    IvaLedgerAggregationIssueReason,
    ProrrataLedgerReference,
    business_proportionality_for,
    has_converted_non_eur_amount,
    iva_rate_kind_for,
    missing_tax_fact_detail,
    missing_tax_fact_reason,
    prorrata_reference_for,
)


def _resolve_iva_registry_declarations(*, effective_date: date) -> tuple[object, ...]:
    """Resolve the selected IVA model surfaces and governed fact catalogues."""
    authority = bundled_authority()
    query_service = RegistryQueryService(authority)
    modelo_303 = query_service.describe_modelo("303")
    modelo_390 = query_service.describe_modelo("390")
    fact_ids = (
        "iva-invoice-classification-catalogue",
        "iva-category-component-catalogue",
        "iva-deduction-applicability-catalogue",
        "iva-regime-legend-catalogue",
        "iva-supply-nature-citation-catalogue",
    )
    facts = tuple(
        authority.resolve_governed_fact(
            MappingFactQuery(
                fact_id=fact_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
        for fact_id in fact_ids
    )
    if not all(isinstance(fact, ResolvedMappingFact) for fact in facts):
        raise TypeError("IVA applicability and catalogue declarations must resolve as mapping facts")
    return (modelo_303, modelo_390, *facts)


@dataclass(frozen=True, slots=True)
class _IvaTransactionOutcome:
    """Per-transaction outcome carrying the typed sinks the orchestrator drains.

    A transaction either fails a pre-observation gate (``gate_issue``
    populated, nothing else) or it survives all pre-gates and produces
    an ``observation``. The observation path may additionally emit a
    ``prorrata_reference`` AND/OR a ``prorrata_issue`` — they are
    independent sinks: an invalid prorrata-reference attaches to the
    issue list, a valid one attaches to the prorrata-references list,
    and either way the observation itself is recorded.
    """

    gate_issue: IvaLedgerAggregationIssue | None = None
    observations: tuple[IvaLedgerObservation, ...] = ()
    prorrata_reference: ProrrataLedgerReference | None = None
    prorrata_issue: IvaLedgerAggregationIssue | None = None


@dataclass(frozen=True, slots=True)
class _IvaTransactionContext:
    transaction_id: str
    operation_date: date
    cash_treatment: IvaCashAccountingTreatment
    invoice_kind: InvoiceKind
    proportionality: Decimal


@dataclass(frozen=True, slots=True)
class _IvaTransactionAmounts:
    rate_kind: IvaRateKind
    base_amount: Decimal
    iva_amount: Decimal
    recargo_amount: Decimal


@dataclass(frozen=True, slots=True)
class _IvaTransactionClassification:
    category: IvaCategory
    flow_direction: IvaFlowDirection


def _substrate_admission_issue(
    transaction: Transaction,
    *,
    resolved_period: Period,
    operation_date: date,
    cash_treatment: IvaCashAccountingTreatment,
) -> IvaLedgerAggregationIssue | None:
    """Return why the row cannot be an IVA observation at all, or ``None``.

    These three screens run before anything is derived from the row because
    they are about whether a usable substrate EXISTS -- the operation falls in
    the period, the currency is settleable, and the tax figures are denominated
    in the currency the return is filed in. A row failing any of them yields no
    fact worth classifying, so nothing downstream needs their result beyond the
    refusal itself.
    """
    transaction_id = transaction.transaction_id
    if cash_treatment is IvaCashAccountingTreatment.NONE and not resolved_period.contains(operation_date):
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"transaction date {operation_date.isoformat()} is outside {resolved_period}",
        )
    if is_non_eur_without_conversion(transaction):
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for IVA aggregation",
        )
    if has_converted_non_eur_amount(transaction):
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE,
            detail=(
                f"transaction currency {transaction.raw.currency!r} has a converted gross value_in_eur "
                "but taxable_base/iva_amount remain native-currency facts; IVA aggregation requires "
                "explicit EUR tax substrate"
            ),
        )
    return None


def _resolve_iva_transaction_context(
    transaction: Transaction,
    *,
    resolved_period: Period,
) -> _IvaTransactionContext | _IvaTransactionOutcome:
    transaction_id = transaction.transaction_id
    ledger_date = transaction.raw.value_date or transaction.raw.booked_date
    operation_date = transaction.operation_date or ledger_date
    cash_treatment = transaction.cash_accounting_treatment
    substrate_issue = _substrate_admission_issue(
        transaction,
        resolved_period=resolved_period,
        operation_date=operation_date,
        cash_treatment=cash_treatment,
    )
    if substrate_issue is not None:
        return _IvaTransactionOutcome(gate_issue=substrate_issue)
    invoice_kind = invoice_kind_for_direction(transaction.direction)
    if invoice_kind is None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
                detail=f"transaction direction {transaction.direction.value!r} is not an IVA settlement flow",
            ),
        )
    proportionality = business_proportionality_for(transaction)
    if proportionality is None:
        reason = (
            IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION
            if transaction.business_classification is BusinessClassification.PERSONAL
            else IvaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
        )
        business_classification = transaction.business_classification.value
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=reason,
                detail=f"business classification {business_classification!r} cannot feed IVA aggregation",
            ),
        )
    return _IvaTransactionContext(
        transaction_id=transaction_id,
        operation_date=operation_date,
        cash_treatment=cash_treatment,
        invoice_kind=invoice_kind,
        proportionality=proportionality,
    )


def _resolve_iva_transaction_amounts(
    transaction: Transaction,
    *,
    operation_date: date,
    proportionality: Decimal,
) -> _IvaTransactionAmounts | _IvaTransactionOutcome:
    return _resolved_iva_transaction_amounts(
        transaction,
        operation_date=operation_date,
        proportionality=proportionality,
    )


def _resolved_iva_transaction_amounts(
    transaction: Transaction,
    *,
    operation_date: date,
    proportionality: Decimal,
) -> _IvaTransactionAmounts | _IvaTransactionOutcome:
    """Validate measured tax facts, then scale them for the business share."""
    transaction_id = transaction.transaction_id
    missing_reason = missing_tax_fact_reason(transaction)
    if missing_reason is not None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=missing_reason,
                detail=missing_tax_fact_detail(missing_reason),
            ),
        )
    taxable_base = transaction.taxable_base
    iva_amount = transaction.iva_amount
    iva_rate = transaction.iva_rate
    if taxable_base is None or iva_amount is None or iva_rate is None:
        msg = (
            f"transaction {transaction_id} cleared the IVA missing-fact screen while base, cuota or "
            "tipo is still unmeasured; the screen and the required tax facts disagree"
        )
        raise ValueError(msg)
    if iva_rate == Decimal("0") and iva_amount != Decimal("0"):
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.CUOTA_ON_ZERO_RATED_ROW,
                detail=(
                    f"row declares iva_rate 0 with iva_amount {iva_amount}; a zero tipo "
                    "admits only a zero cuota, so one of the two facts is wrong"
                ),
            ),
        )
    rate_kind = _canonical_iva_rate_kind(transaction, iva_rate=iva_rate, operation_date=operation_date)
    if isinstance(rate_kind, _IvaTransactionOutcome):
        return rate_kind
    return _IvaTransactionAmounts(
        rate_kind=rate_kind,
        base_amount=taxable_base * proportionality,
        iva_amount=iva_amount * proportionality,
        recargo_amount=(transaction.recargo_amount or Decimal("0")) * proportionality,
    )


def _canonical_iva_rate_kind(
    transaction: Transaction,
    *,
    iva_rate: Decimal,
    operation_date: date,
) -> IvaRateKind | _IvaTransactionOutcome:
    """Resolve a declared rate against the legal table available on its date."""
    rate_kind = iva_rate_kind_for(iva_rate, on_date=operation_date)
    if rate_kind is None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction.transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE,
                detail=(f"IVA rate {iva_rate} is not a canonical substrate IVA rate for {operation_date.isoformat()}"),
            ),
        )
    return rate_kind


def _resolve_iva_transaction_classification(
    transaction: Transaction,
    *,
    transaction_id: str,
    invoice_kind: InvoiceKind,
    rate_kind: IvaRateKind,
) -> _IvaTransactionClassification | _IvaTransactionOutcome:
    explicit_category = transaction.iva_category
    if explicit_category is not None:
        effective_category = explicit_category
    else:
        effective_category = domestic_categories_by_rate_kind()[rate_kind]
    flow_direction = derive_flow_for_classification(
        category=effective_category,
        invoice_direction=invoice_kind,
    )
    return _IvaTransactionClassification(category=effective_category, flow_direction=flow_direction)


def classify_iva_transaction(
    transaction: Transaction,
    *,
    resolved_period: Period,
) -> _IvaTransactionOutcome:
    """Filter + classify one ledger transaction against the IVA aggregation pipeline.

    Returns an :class:`_IvaTransactionOutcome` carrying the typed
    sinks the orchestrator drains. Each pre-observation gate projects
    to ``gate_issue`` with a typed
    :class:`IvaLedgerAggregationIssueReason`. The observation-eligible
    path constructs the observation and (when present) the prorrata
    reference; an invalid prorrata reference is reported as a
    ``prorrata_issue`` alongside the observation.
    """
    _resolve_iva_registry_declarations(effective_date=resolved_period.end_date)
    context = _resolve_iva_transaction_context(transaction, resolved_period=resolved_period)
    if isinstance(context, _IvaTransactionOutcome):
        return context
    amounts = _resolve_iva_transaction_amounts(
        transaction,
        operation_date=context.operation_date,
        proportionality=context.proportionality,
    )
    if isinstance(amounts, _IvaTransactionOutcome):
        return amounts
    classification = _resolve_iva_transaction_classification(
        transaction,
        transaction_id=context.transaction_id,
        invoice_kind=context.invoice_kind,
        rate_kind=amounts.rate_kind,
    )
    if isinstance(classification, _IvaTransactionOutcome):
        return classification
    return _project_iva_transaction(
        transaction,
        resolved_period=resolved_period,
        context=context,
        amounts=amounts,
        classification=classification,
    )


def _project_iva_transaction(
    transaction: Transaction,
    *,
    resolved_period: Period,
    context: _IvaTransactionContext,
    amounts: _IvaTransactionAmounts,
    classification: _IvaTransactionClassification,
) -> _IvaTransactionOutcome:
    prorrata_reference, prorrata_issue, linked_prorrata_id = _resolve_iva_prorrata_attachment(
        transaction,
        flow_direction=classification.flow_direction,
        operation_date=context.operation_date,
        base_amount=amounts.base_amount,
        iva_amount=amounts.iva_amount,
    )
    if context.cash_treatment is not IvaCashAccountingTreatment.NONE:
        observations = _cash_accounting_observations(
            transaction,
            resolved_period=resolved_period,
            operation_date=context.operation_date,
            category=classification.category,
            rate_kind=amounts.rate_kind,
            flow_direction=classification.flow_direction,
            proportionality=context.proportionality,
            full_base_amount=amounts.base_amount,
            full_iva_amount=amounts.iva_amount,
            linked_prorrata_id=linked_prorrata_id,
            deduction_fact_kind=transaction.deduction_fact_kind,
            deduction_provenance=transaction.deduction_provenance,
        )
        if not observations:
            return _IvaTransactionOutcome(
                gate_issue=IvaLedgerAggregationIssue(
                    transaction_id=context.transaction_id,
                    reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                    detail=(
                        "cash-accounting operation date, payment evidence dates, and fallback date "
                        f"are outside {resolved_period}"
                    ),
                ),
            )
        return _IvaTransactionOutcome(
            observations=observations,
            prorrata_reference=prorrata_reference,
            prorrata_issue=prorrata_issue,
        )
    observation = _iva_observation(
        ledger_id=transaction.transaction_id,
        transaction_date=context.operation_date,
        category=classification.category,
        exemption_article=transaction.exemption_article,
        rate_kind=amounts.rate_kind,
        flow_direction=classification.flow_direction,
        base_amount=amounts.base_amount,
        iva_amount=amounts.iva_amount,
        recargo_amount=amounts.recargo_amount,
        prorrata_reference_id=linked_prorrata_id,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
        input_classification=transaction.input_classification,
        prorrata_sector_id=transaction.prorrata_sector_id,
        # The rate the operator declared on the row, kept beside the tier it
        # resolved to. Read from the transaction rather than re-derived from
        # the tier: the tier-to-rate mapping is date-dependent, so re-deriving
        # would answer "what does this tier mean today" when the question is
        # "what was this line actually charged".
        applied_rate=transaction.iva_rate,
        deduction_fact_kind=transaction.deduction_fact_kind,
        deduction_provenance=transaction.deduction_provenance,
        investment_asset_id=transaction.investment_asset_id,
        rectifies_ledger_id=transaction.rectifies_ledger_id,
    )
    return _IvaTransactionOutcome(
        observations=(observation,),
        prorrata_reference=prorrata_reference,
        prorrata_issue=prorrata_issue,
    )


def _iva_observation(
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
    cash_accounting_treatment: IvaCashAccountingTreatment = IvaCashAccountingTreatment.NONE,
    observation_role: IvaLedgerObservationRole,
    input_classification: InputClassification | None = None,
    prorrata_sector_id: str | None = None,
    applied_rate: Decimal | None = None,
    deduction_fact_kind: IvaDeductionFactKind | None,
    deduction_provenance: IvaDeductionClassificationProvenance | None,
    investment_asset_id: str | None = None,
    rectifies_ledger_id: str | None = None,
) -> IvaLedgerObservation:
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


def _cash_accounting_observations(
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
) -> tuple[IvaLedgerObservation, ...]:
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
        observations.append(
            _iva_observation(
                ledger_id=transaction.transaction_id,
                transaction_date=payment_date,
                category=category,
                exemption_article=transaction.exemption_article,
                rate_kind=rate_kind,
                flow_direction=flow_direction,
                base_amount=base_amount * proportionality,
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
            ),
        )
    if resolved_period.contains(operation_date):
        observations.append(
            _iva_observation(
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


def _resolve_iva_prorrata_attachment(
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
    if flow_direction is not IvaFlowDirection.SOPORTADO:
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
