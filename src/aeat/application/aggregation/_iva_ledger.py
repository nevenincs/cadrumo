"""Repository-backed IVA observation projection from ledger catalogues."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from ...domain.calculations.registry import IvaLedgerObservation
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionLifecycleState,
)
from ...domain.transactions import (
    TransactionDirection as LedgerTransactionDirection,
)
from ...domain.vat import (
    EUMemberState,
    IvaFlowDirection,
    ProrrataInputError,
    ProrrataReference,
    IvaCategory,
    IvaRateKind,
    IvaRateNotFoundError,
    lookup_rate,
    validate_prorrata_reference,
)
from ._errors import AggregationValidationError, t
from ._models import Period

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_RATE_KIND_TO_DOMESTIC_CATEGORY: dict[IvaRateKind, IvaCategory] = {
    IvaRateKind.ZERO: IvaCategory.DOMESTIC_ZERO,
    IvaRateKind.SUPER_REDUCED: IvaCategory.DOMESTIC_SUPER_REDUCED_4,
    IvaRateKind.REDUCED: IvaCategory.DOMESTIC_REDUCED_10,
    IvaRateKind.GENERAL: IvaCategory.DOMESTIC_GENERAL_21,
}


class IvaLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce IVA observations."""

    UNSUPPORTED_DIRECTION = "unsupported_direction"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    UNCLASSIFIED_BUSINESS_STATE = "unclassified_business_state"
    PERSONAL_TRANSACTION = "personal_transaction"
    OUTSIDE_PERIOD = "outside_period"
    MISSING_TAXABLE_BASE = "missing_taxable_base"
    MISSING_IVA_AMOUNT = "missing_iva_amount"
    MISSING_IVA_RATE = "missing_iva_rate"
    UNSUPPORTED_IVA_RATE = "unsupported_iva_rate"
    INVALID_PRORRATA_REFERENCE = "invalid_prorrata_reference"


class IvaLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while projecting IVA ledger observations."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    reason: IvaLedgerAggregationIssueReason
    detail: str = Field(min_length=1, max_length=512)


class ProrrataLedgerReference(BaseModel):
    """Bucket-local ledger row pointer to a legal IVA prorrata reference."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    transaction_date: date
    reference: ProrrataReference
    base_amount: Decimal = Field(..., ge=Decimal("0"))
    input_vat_amount: Decimal = Field(..., ge=Decimal("0"))


class IvaLedgerAggregation(BaseModel):
    """IVA observations produced from one bucket-local transaction catalogue."""

    model_config = _STRICT_FROZEN

    period: Period
    observations: Sequence[IvaLedgerObservation] = Field(default_factory=tuple)
    prorrata_references: Sequence[ProrrataLedgerReference] = Field(default_factory=tuple)
    issues: Sequence[IvaLedgerAggregationIssue] = Field(default_factory=tuple)

    @field_validator("observations")
    @classmethod
    def _freeze_observations(cls, value: Sequence[IvaLedgerObservation]) -> tuple[IvaLedgerObservation, ...]:
        return tuple(value)

    @field_validator("prorrata_references")
    @classmethod
    def _freeze_prorrata_references(
        cls,
        value: Sequence[ProrrataLedgerReference],
    ) -> tuple[ProrrataLedgerReference, ...]:
        return tuple(value)

    @field_validator("issues")
    @classmethod
    def _freeze_issues(cls, value: Sequence[IvaLedgerAggregationIssue]) -> tuple[IvaLedgerAggregationIssue, ...]:
        return tuple(value)

    @field_serializer("observations")
    def _serialize_observations(
        self,
        value: Sequence[IvaLedgerObservation],
    ) -> tuple[IvaLedgerObservation, ...]:
        return tuple(value)

    @field_serializer("prorrata_references")
    def _serialize_prorrata_references(
        self,
        value: Sequence[ProrrataLedgerReference],
    ) -> tuple[ProrrataLedgerReference, ...]:
        return tuple(value)

    @field_serializer("issues")
    def _serialize_issues(
        self,
        value: Sequence[IvaLedgerAggregationIssue],
    ) -> tuple[IvaLedgerAggregationIssue, ...]:
        return tuple(value)


def aggregate_iva_ledger_observations_from_repositories(
    *,
    bucket_id: str,
    period: Period | str,
    transaction_repository: TransactionCatalogueRepository | None = None,
) -> IvaLedgerAggregation:
    """Load the bucket-local transaction catalogue and project IVA observations."""

    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    return aggregate_iva_ledger_observations(repository.load(), period=period)


def aggregate_iva_ledger_observations(
    transactions: TransactionCatalogue,
    *,
    period: Period | str,
) -> IvaLedgerAggregation:
    """Project classified ledger transaction tax facts into IVA observations."""

    resolved_period = period if isinstance(period, Period) else Period.model_validate(period)
    observations: list[IvaLedgerObservation] = []
    prorrata_references: list[ProrrataLedgerReference] = []
    issues: list[IvaLedgerAggregationIssue] = []
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_iva_transaction(transaction, resolved_period=resolved_period)
        if outcome.gate_issue is not None:
            issues.append(outcome.gate_issue)
            continue
        if outcome.prorrata_issue is not None:
            issues.append(outcome.prorrata_issue)
        if outcome.prorrata_reference is not None:
            prorrata_references.append(outcome.prorrata_reference)
        if outcome.observation is not None:
            observations.append(outcome.observation)
    return IvaLedgerAggregation(
        period=resolved_period,
        observations=tuple(observations),
        prorrata_references=tuple(prorrata_references),
        issues=tuple(issues),
    )


@dataclass(frozen=True)
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
    observation: IvaLedgerObservation | None = None
    prorrata_reference: ProrrataLedgerReference | None = None
    prorrata_issue: IvaLedgerAggregationIssue | None = None


def _classify_iva_transaction(
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
    transaction_id = transaction.transaction_id
    operation_date = transaction.raw.value_date or transaction.raw.booked_date
    if not resolved_period.contains(operation_date):
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                detail=f"transaction date {operation_date.isoformat()} is outside {resolved_period.raw}",
            )
        )
    if transaction.raw.currency != "EUR":
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
                detail=f"transaction currency {transaction.raw.currency!r} is not supported for IVA aggregation",
            )
        )
    flow_direction = _flow_direction_for(transaction.direction)
    if flow_direction is None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
                detail=f"transaction direction {transaction.direction.value!r} is not an IVA settlement flow",
            )
        )
    proportionality = _business_proportionality(transaction)
    if proportionality is None:
        reason = (
            IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION
            if transaction.business_classification is BusinessClassification.PERSONAL
            else IvaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
        )
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=reason,
                detail=(
                    f"business classification {transaction.business_classification.value!r} "
                    "cannot feed IVA aggregation"
                ),
            )
        )
    missing_reason = _missing_tax_fact_reason(transaction)
    if missing_reason is not None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=missing_reason,
                detail=_missing_tax_fact_detail(missing_reason),
            )
        )
    assert transaction.taxable_base is not None
    assert transaction.iva_amount is not None
    assert transaction.iva_rate is not None
    rate_kind = _iva_rate_kind_for(transaction.iva_rate, on_date=operation_date)
    if rate_kind is None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE,
                detail=f"IVA rate {transaction.iva_rate} is not a canonical substrate IVA rate",
            )
        )
    base_amount = transaction.taxable_base * proportionality
    iva_amount = transaction.iva_amount * proportionality
    prorrata_reference, prorrata_issue, linked_prorrata_id = _resolve_iva_prorrata_attachment(
        transaction,
        flow_direction=flow_direction,
        operation_date=operation_date,
        base_amount=base_amount,
        iva_amount=iva_amount,
    )
    observation = IvaLedgerObservation(
        ledger_id=transaction.transaction_id,
        transaction_date=operation_date,
        category=_RATE_KIND_TO_DOMESTIC_CATEGORY[rate_kind],
        rate_kind=rate_kind,
        flow_direction=flow_direction,
        base_amount=base_amount,
        iva_amount=iva_amount,
        prorrata_reference_id=linked_prorrata_id,
    )
    return _IvaTransactionOutcome(
        observation=observation,
        prorrata_reference=prorrata_reference,
        prorrata_issue=prorrata_issue,
    )


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
    reference fails parsing OR the row is not a supported-input VAT
    row (prorrata only attaches to SOPORTADO flows). Returns
    ``(reference, None, transaction_id)`` for a valid attachment.
    """
    raw_reference = _prorrata_reference_for(
        transaction.prorrata_reference,
        transaction_id=transaction.transaction_id,
    )
    if isinstance(raw_reference, IvaLedgerAggregationIssue):
        return None, raw_reference, None
    if raw_reference is None:
        return None, None, None
    if flow_direction is not IvaFlowDirection.SOPORTADO:
        return None, IvaLedgerAggregationIssue(
            transaction_id=transaction.transaction_id,
            reason=IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE,
            detail="prorrata_reference may only be attached to supported input VAT rows",
        ), None
    return (
        ProrrataLedgerReference(
            transaction_id=transaction.transaction_id,
            transaction_date=operation_date,
            reference=raw_reference,
            base_amount=base_amount,
            input_vat_amount=iva_amount,
        ),
        None,
        transaction.transaction_id,
    )


def _flow_direction_for(direction: LedgerTransactionDirection) -> IvaFlowDirection | None:
    if direction is LedgerTransactionDirection.INCOMING:
        return IvaFlowDirection.REPERCUTIDO
    if direction is LedgerTransactionDirection.OUTGOING:
        return IvaFlowDirection.SOPORTADO
    return None


def _business_proportionality(transaction: Transaction) -> Decimal | None:
    if transaction.business_classification is BusinessClassification.BUSINESS:
        return Decimal("1")
    if transaction.business_classification is BusinessClassification.MIXED:
        assert transaction.business_pct is not None
        return transaction.business_pct
    return None


def _missing_tax_fact_reason(transaction: Transaction) -> IvaLedgerAggregationIssueReason | None:
    reasons = iva_ledger_missing_fact_reasons(transaction)
    return reasons[0] if reasons else None


def iva_ledger_missing_fact_reasons(transaction: Transaction) -> tuple[IvaLedgerAggregationIssueReason, ...]:
    """Return missing IVA fact reasons for a transaction without projecting it."""

    reasons: list[IvaLedgerAggregationIssueReason] = []
    if transaction.taxable_base is None:
        reasons.append(IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE)
    if transaction.iva_amount is None:
        reasons.append(IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT)
    if transaction.iva_rate is None:
        reasons.append(IvaLedgerAggregationIssueReason.MISSING_IVA_RATE)
    return tuple(reasons)


def _missing_tax_fact_detail(reason: IvaLedgerAggregationIssueReason) -> str:
    return {
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: "transaction has no taxable_base fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: "transaction has no iva_amount fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: "transaction has no iva_rate fact",
    }[reason]


def _prorrata_reference_for(
    reference_id: str | None,
    *,
    transaction_id: str,
) -> ProrrataReference | IvaLedgerAggregationIssue | None:
    if reference_id is None:
        return None
    try:
        return validate_prorrata_reference(reference_id)
    except ProrrataInputError as exc:
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE,
            detail=str(exc),
        )


def _iva_rate_kind_for(rate: Decimal, *, on_date: date) -> IvaRateKind | None:
    for kind in _RATE_KIND_TO_DOMESTIC_CATEGORY:
        try:
            rate_record = lookup_rate(EUMemberState.ES, kind, on_date)
        except IvaRateNotFoundError:
            continue
        if rate_record.pct / Decimal("100") == rate:
            return kind
    return None


__all__ = [
    "IvaLedgerAggregation",
    "IvaLedgerAggregationIssue",
    "IvaLedgerAggregationIssueReason",
    "ProrrataLedgerReference",
    "aggregate_iva_ledger_observations",
    "aggregate_iva_ledger_observations_from_repositories",
    "iva_ledger_missing_fact_reasons",
]
