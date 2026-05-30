"""Backend readiness preflight for bucket-scoped ledger transactions."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer, field_validator

from ...core.external_constants import DEFAULT_CURRENCY
from ...core.identity import BucketId
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
)
from ..aggregation import IvaLedgerAggregationIssueReason, Period, iva_ledger_missing_fact_reasons

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_CLASSIFIED_TAX_STATES = frozenset(
    {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
        BusinessClassification.PERSONAL,
    }
)


class LedgerPreflightIssueReason(StrEnum):
    """Machine-readable ledger facts missing before modelo calculation."""

    MISSING_BUSINESS_CLASSIFICATION = "missing_business_classification"
    MISSING_CATEGORY = "missing_category"
    MISSING_TAXABLE_BASE = "missing_taxable_base"
    MISSING_IVA_AMOUNT = "missing_iva_amount"
    MISSING_IVA_RATE = "missing_iva_rate"
    MISSING_PROPORTIONALITY_REFERENCE = "missing_proportionality_reference"
    UNSUPPORTED_CURRENCY = "unsupported_currency"


class LedgerPreflightIssue(BaseModel):
    """One model-readiness issue attached to a bucket-local transaction."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    reason: LedgerPreflightIssueReason
    detail: str = Field(min_length=1, max_length=512)


class LedgerPreflightReport(BaseModel):
    """Readiness report for ledger facts consumed by modelo calculation."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    period: Period
    checked_transaction_count: int = Field(ge=0)
    issues: Sequence[LedgerPreflightIssue] = Field(default_factory=tuple)

    @field_validator("issues")
    @classmethod
    def _freeze_issues(cls, value: Sequence[LedgerPreflightIssue]) -> tuple[LedgerPreflightIssue, ...]:
        return tuple(value)

    @field_serializer("issues")
    def _serialize_issues(self, value: Sequence[LedgerPreflightIssue]) -> tuple[LedgerPreflightIssue, ...]:
        return tuple(value)

    @computed_field
    @property
    def ready(self) -> bool:
        return not self.issues


def preflight_ledger_tax_readiness(
    *,
    bucket_id: str,
    period: Period | str,
    transaction_repository: TransactionCatalogueRepository | None = None,
) -> LedgerPreflightReport:
    """Load a bucket-local catalogue and report modelo-readiness gaps."""

    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise TransactionValidationError(
            "transaction repository bucket_id does not match the ledger preflight bucket",
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    return preflight_transaction_catalogue(
        bucket_id=bucket_id,
        period=period,
        transactions=repository.load(),
    )


def preflight_transaction_catalogue(
    *,
    bucket_id: str,
    period: Period | str,
    transactions: TransactionCatalogue,
) -> LedgerPreflightReport:
    """Report missing ledger facts without mutating the transaction catalogue."""

    resolved_period = period if isinstance(period, Period) else Period.model_validate(period)
    issues: list[LedgerPreflightIssue] = []
    checked = 0
    for transaction in _sorted_transactions(transactions):
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        operation_date = transaction.raw.value_date or transaction.raw.booked_date
        if not resolved_period.contains(operation_date):
            continue
        checked += 1
        issues.extend(_issues_for_transaction(transaction))
    return LedgerPreflightReport(
        bucket_id=bucket_id,
        period=resolved_period,
        checked_transaction_count=checked,
        issues=tuple(issues),
    )


def _sorted_transactions(transactions: TransactionCatalogue) -> tuple[Transaction, ...]:
    return tuple(
        sorted(
            transactions.values(),
            key=lambda transaction: (
                transaction.raw.value_date or transaction.raw.booked_date,
                transaction.transaction_id,
            ),
        )
    )


def _transaction_needs_expense_category(transaction: Transaction) -> bool:
    """Return whether the transaction feeds the deductible-expense pipeline.

    ``category_id`` is a :class:`SpendingCategory` foreign key — a
    deductible-expense taxonomy. The only modelo binding that consumes
    it is the Renta first-slice expense aggregation, which only admits
    OUTGOING transactions (expenses) and INCOMING transactions that
    carry a purchase-invoice evidence id (expense refunds). Pure income
    (INCOMING with no purchase-invoice evidence) is classified solely
    by direction and never reads a spending category, so it must not
    be flagged as ``missing_category``.
    """

    if transaction.direction is TransactionDirection.OUTGOING:
        return True
    return (
        transaction.direction is TransactionDirection.INCOMING
        and transaction.purchase_invoice_evidence_id is not None
    )


def _issues_for_transaction(transaction: Transaction) -> tuple[LedgerPreflightIssue, ...]:
    issues: list[LedgerPreflightIssue] = []
    common = {"transaction_id": transaction.transaction_id}
    if transaction.direction not in {
        TransactionDirection.INCOMING,
        TransactionDirection.OUTGOING,
    }:
        return ()
    if transaction.business_classification not in _CLASSIFIED_TAX_STATES:
        return (
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_BUSINESS_CLASSIFICATION,
                detail=(
                    f"business classification {transaction.business_classification.value!r} "
                    "is not ready for modelo calculation"
                ),
            ),
        )
    if transaction.business_classification is BusinessClassification.PERSONAL:
        return ()
    if transaction.raw.currency != DEFAULT_CURRENCY:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.UNSUPPORTED_CURRENCY,
                detail=f"transaction currency {transaction.raw.currency!r} is not supported for modelo aggregation",
            )
        )
        return tuple(issues)
    if _transaction_needs_expense_category(transaction) and transaction.category_id is None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_CATEGORY,
                detail="deductible-expense ledger transaction has no category_id",
            )
        )
    if transaction.business_classification is BusinessClassification.MIXED and transaction.usage_ratio_id is None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_PROPORTIONALITY_REFERENCE,
                detail="mixed ledger transaction has no usage_ratio_id proportionality reference",
            )
        )
    for reason in iva_ledger_missing_fact_reasons(transaction):
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=_preflight_reason_for_iva_issue(reason),
                detail=_preflight_detail_for_iva_issue(reason),
            )
        )
    return tuple(issues)


def _preflight_reason_for_iva_issue(reason: IvaLedgerAggregationIssueReason) -> LedgerPreflightIssueReason:
    return {
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: LedgerPreflightIssueReason.MISSING_TAXABLE_BASE,
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: LedgerPreflightIssueReason.MISSING_IVA_AMOUNT,
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: LedgerPreflightIssueReason.MISSING_IVA_RATE,
    }[reason]


def _preflight_detail_for_iva_issue(reason: IvaLedgerAggregationIssueReason) -> str:
    return {
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: "transaction has no taxable_base fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: "transaction has no iva_amount fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: "transaction has no iva_rate fact",
    }[reason]


__all__ = [
    "LedgerPreflightIssue",
    "LedgerPreflightIssueReason",
    "LedgerPreflightReport",
    "preflight_ledger_tax_readiness",
    "preflight_transaction_catalogue",
]
