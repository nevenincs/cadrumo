"""Backend readiness preflight for bucket-scoped ledger transactions.

:func:`preflight_ledger_tax_readiness` loads a
:class:`~cadrumo.domain.transactions.TransactionCatalogue` via
:class:`~cadrumo.domain.transactions.TransactionCatalogueRepository` from the
active bucket and delegates to :func:`preflight_transaction_catalogue` for pure
in-memory analysis. The report is consumed by modelo readiness projection and
ledger read surfaces; it is not a calculation engine and never mutates the
catalogue it inspects.

See Also:
    :func:`~cadrumo.application.state_projection.build_operator_state_projection`
        Modelo readiness consumer that embeds blocking ledger issues in the
        operator state projection.
    :mod:`cadrumo.entrypoints.cli._ledger_read_cli`
        CLI read surface that reports these preflight issues without mutating
        ledger state.
    :mod:`cadrumo.application.aggregation`
        Calculation source mesh that consumes ledger facts only after this
        readiness layer has reported operator-facing gaps.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field, field_serializer, field_validator

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.profile.usage_ratios import load_usage_ratios_with_censo_guard
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.identity import BucketId
from ...domain.categories import SpendingCategory, SpendingCategoryFamily, family_for
from ...domain.iva import IvaCategory
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
    has_employment_irpf_category,
)
from ...domain.usage_ratios import CensoRatioMismatchError
from ..aggregation import (
    IvaLedgerAggregationIssueReason,
    iva_ledger_missing_fact_reasons,
    validate_iva_ledger_counterparty_category,
)

_CLASSIFIED_TAX_STATES = frozenset(
    {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
        BusinessClassification.PERSONAL,
    },
)


class LedgerPreflightIssueReason(StrEnum):
    """Machine-readable ledger facts missing before modelo calculation."""

    MISSING_BUSINESS_CLASSIFICATION = "missing_business_classification"
    MISSING_CATEGORY = "missing_category"
    MISSING_TAXABLE_BASE = "missing_taxable_base"
    MISSING_IVA_AMOUNT = "missing_iva_amount"
    MISSING_IVA_RATE = "missing_iva_rate"
    MISSING_EUR_TAX_SUBSTRATE = "missing_eur_tax_substrate"
    MISSING_COUNTERPARTY_EU_MEMBER_STATE = "missing_counterparty_eu_member_state"
    DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION = "domestic_counterparty_on_intra_community_transaction"
    EU_MEMBER_STATE_ON_EXPORT_TRANSACTION = "eu_member_state_on_export_transaction"
    MISSING_PROPORTIONALITY_REFERENCE = "missing_proportionality_reference"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    UNSUPPORTED_PERIOD = "unsupported_period"
    CENSO_RATIO_MISMATCH = "censo_ratio_mismatch"
    # Anomaly channel: present-but-suspicious rows (distinct from missing-fact),
    # so an asesor sees real anomalies without first classifying every row.
    ANOMALY_NON_DECLARABLE_IVA_CATEGORY = "anomaly_non_declarable_iva_category"
    ANOMALY_NON_DECLARABLE_RECARGO_EQUIVALENCIA = "anomaly_non_declarable_recargo_equivalencia"


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
    period: Period,
    transaction_repository: TransactionCatalogueRepository | None = None,
    raw_afectacion_ratio: Decimal | None = None,
) -> LedgerPreflightReport:
    """Load a bucket-local catalogue and report modelo-readiness gaps.

    Args:
        bucket_id: Bucket whose ledger catalogue is being checked.
        period: Filing period used to decide whether each transaction belongs in
            the readiness window.
        transaction_repository: Optional
            :class:`~cadrumo.domain.transactions.TransactionCatalogueRepository`
            used to load the bucket-local catalogue; a default repository is
            constructed when ``None``.
        raw_afectacion_ratio: Optional home-office usage ratio from censo data,
            used only to surface proportionality mismatches.

    Returns:
        A :class:`LedgerPreflightReport` describing blocking or advisory ledger
        facts for modelo-readiness projection.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise TransactionValidationError(
            "transaction repository bucket_id does not match the ledger preflight bucket",
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    transactions = repository.load()
    censo_ratio_mismatch_detail = None
    if _catalogue_uses_home_office_usage_ratio(period=period, transactions=transactions):
        censo_ratio_mismatch_detail = _censo_ratio_mismatch_detail(
            bucket_id=bucket_id,
            raw_afectacion_ratio=raw_afectacion_ratio,
        )
    return preflight_transaction_catalogue(
        bucket_id=bucket_id,
        period=period,
        transactions=transactions,
        censo_ratio_mismatch_detail=censo_ratio_mismatch_detail,
    )


def preflight_transaction_catalogue(
    *,
    bucket_id: str,
    period: Period,
    transactions: TransactionCatalogue,
    censo_ratio_mismatch_detail: str | None = None,
) -> LedgerPreflightReport:
    """Report missing ledger facts without mutating the transaction catalogue.

    Args:
        bucket_id: Stable bucket identifier for the ledger being checked.
        period: Filing period as a typed :class:`Period` instance.
        transactions: The :class:`TransactionCatalogue` to inspect for missing facts.
        censo_ratio_mismatch_detail: Optional censo mismatch detail previously
            resolved from the secure ratio profile. When supplied, active
            HOME_OFFICE ratio rows surface it as a preflight issue.

    Returns a :class:`LedgerPreflightReport`.
    """
    resolved_period = period
    if not resolved_period.has_date_span():
        return LedgerPreflightReport(
            bucket_id=bucket_id,
            period=resolved_period,
            checked_transaction_count=0,
            issues=(_unsupported_period_issue(resolved_period),),
        )
    issues: list[LedgerPreflightIssue] = []
    checked = 0
    for transaction in _sorted_transactions(transactions):
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        operation_date = transaction.raw.value_date or transaction.raw.booked_date
        if not resolved_period.contains(operation_date):
            continue
        checked += 1
        issues.extend(
            _issues_for_transaction(
                transaction,
                censo_ratio_mismatch_detail=censo_ratio_mismatch_detail,
            ),
        )
    return LedgerPreflightReport(
        bucket_id=bucket_id,
        period=resolved_period,
        checked_transaction_count=checked,
        issues=tuple(issues),
    )


def _unsupported_period_issue(period: Period) -> LedgerPreflightIssue:
    return LedgerPreflightIssue(
        transaction_id="__period__",
        reason=LedgerPreflightIssueReason.UNSUPPORTED_PERIOD,
        detail=(
            f"ledger preflight requires a calendar date-span period; {period.registry_token!r} has no date span "
            "and cannot be checked through ledger aggregation"
        ),
    )


def _sorted_transactions(transactions: TransactionCatalogue) -> tuple[Transaction, ...]:
    return tuple(
        sorted(
            transactions.values(),
            key=lambda transaction: (
                transaction.raw.value_date or transaction.raw.booked_date,
                transaction.transaction_id,
            ),
        ),
    )


def _period_transactions(*, period: Period, transactions: TransactionCatalogue) -> tuple[Transaction, ...]:
    if not period.has_date_span():
        return ()
    return tuple(
        transaction
        for transaction in _sorted_transactions(transactions)
        if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
        and period.contains(transaction.raw.value_date or transaction.raw.booked_date)
    )


_HOME_OFFICE_FAMILIES = frozenset(
    {
        SpendingCategoryFamily.HOME_OFFICE_SUMINISTROS,
        SpendingCategoryFamily.HOME_OFFICE_OWNERSHIP,
    },
)


def _bound_raw_afectacion_ratio(*, bucket_id: str) -> Decimal | None:
    from ..user_profile import CensoSyncService

    return CensoSyncService(bucket_id=bucket_id).bound_raw_afectacion_ratio(profile_id=bucket_id)


def _censo_ratio_mismatch_detail(*, bucket_id: str, raw_afectacion_ratio: Decimal | None) -> str | None:
    resolved_raw = raw_afectacion_ratio
    if resolved_raw is None:
        resolved_raw = _bound_raw_afectacion_ratio(bucket_id=bucket_id)
    try:
        load_usage_ratios_with_censo_guard(
            bucket_id=bucket_id,
            raw_afectacion_ratio=resolved_raw,
        )
    except CensoRatioMismatchError as exc:
        return str(exc)
    return None


def _is_home_office_usage_ratio_id(value: str | None) -> bool:
    if value is None:
        return False
    try:
        category = SpendingCategory(value.strip())
    except ValueError:
        return False
    return family_for(category) in _HOME_OFFICE_FAMILIES


def _catalogue_uses_home_office_usage_ratio(*, period: Period, transactions: TransactionCatalogue) -> bool:
    return any(
        _is_home_office_usage_ratio_id(transaction.usage_ratio_id)
        for transaction in _period_transactions(period=period, transactions=transactions)
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
        transaction.direction is TransactionDirection.INCOMING and transaction.purchase_invoice_evidence_id is not None
    )


_ANOMALY_IVA_REASONS: dict[IvaCategory, tuple[LedgerPreflightIssueReason, str]] = {
    IvaCategory.UNKNOWN: (
        LedgerPreflightIssueReason.ANOMALY_NON_DECLARABLE_IVA_CATEGORY,
        "iva_category 'unknown' is not declarable; classify the row or query the source",
    ),
    IvaCategory.ERRONEOUS_INVOICE: (
        LedgerPreflightIssueReason.ANOMALY_NON_DECLARABLE_IVA_CATEGORY,
        "iva_category 'erroneous_invoice' marks a rectified/void row; not declarable",
    ),
}


def _issues_for_transaction(
    transaction: Transaction,
    *,
    censo_ratio_mismatch_detail: str | None = None,
) -> tuple[LedgerPreflightIssue, ...]:
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
    iva_cat = transaction.iva_category
    anomaly = _ANOMALY_IVA_REASONS.get(iva_cat) if iva_cat is not None else None
    if anomaly is not None:
        reason, detail = anomaly
        return (LedgerPreflightIssue(**common, reason=reason, detail=detail),)
    if iva_cat is IvaCategory.RECARGO_EQUIVALENCIA:
        return (
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.ANOMALY_NON_DECLARABLE_RECARGO_EQUIVALENCIA,
                detail=_recargo_equivalencia_preflight_detail(transaction),
            ),
        )
    # A foreign row is only unsupported when no EUR conversion was applied at
    # import; converted rows still need explicit EUR-denominated tax substrate.
    if transaction.raw.currency != DEFAULT_CURRENCY and transaction.value_in_eur is None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.UNSUPPORTED_CURRENCY,
                detail=f"transaction currency {transaction.raw.currency!r} is not supported for modelo aggregation",
            ),
        )
        return tuple(issues)
    if transaction.raw.currency != DEFAULT_CURRENCY and transaction.value_in_eur is not None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_EUR_TAX_SUBSTRATE,
                detail=(
                    f"transaction currency {transaction.raw.currency!r} has value_in_eur but taxable_base and "
                    "iva_amount remain native-currency facts; supply explicit EUR tax substrate or exclude the "
                    "row before modelo calculation"
                ),
            ),
        )
        return tuple(issues)
    if _transaction_needs_expense_category(transaction) and transaction.category_id is None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_CATEGORY,
                detail="deductible-expense ledger transaction has no category_id",
            ),
        )
    if transaction.business_classification is BusinessClassification.MIXED and transaction.usage_ratio_id is None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_PROPORTIONALITY_REFERENCE,
                detail=(
                    "mixed ledger transaction has no usage_ratio_id; use an existing configured "
                    "eligible category id from 'aeat app ledger ratios list' or 'aeat app ledger "
                    "ratios eligible', create one with 'aeat app ledger ratios set <category-id> "
                    "<ratio>', then allocate with --usage-ratio-id <category-id>"
                ),
            ),
        )
    if censo_ratio_mismatch_detail is not None and _is_home_office_usage_ratio_id(transaction.usage_ratio_id):
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH,
                detail=(
                    f"{censo_ratio_mismatch_detail}; update your censo vivienda_office data with "
                    "'aeat config profile edit', or unset the HOME_OFFICE ratio before using it in modelo "
                    "calculations"
                ),
            ),
        )
    # Trabajo (nómina) incoming rows are IVA-exempt by definition: an
    # employer-paid wage/salary carries no taxable_base / iva_rate /
    # iva_amount because the IRPF retenciones flow consumes the row,
    # not the IVA aggregation. Skip the IVA-fact preflight on these
    # rows so a payroll-receipt entry does not surface as three false-
    # positive missing_iva_* findings every period.
    if _transaction_is_trabajo_income(transaction):
        return tuple(issues)
    for reason in iva_ledger_missing_fact_reasons(transaction):
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=_preflight_reason_for_iva_issue(reason),
                detail=_preflight_detail_for_iva_issue(reason),
            ),
        )
    d5_issue = validate_iva_ledger_counterparty_category(transaction)
    if d5_issue is not None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=_preflight_reason_for_iva_issue(d5_issue.reason),
                detail=d5_issue.detail,
            ),
        )
    return tuple(issues)


def _recargo_equivalencia_preflight_detail(transaction: Transaction) -> str:
    if transaction.direction is TransactionDirection.OUTGOING:
        return (
            "iva_category 'recargo_equivalencia' is the retailer purchase-side surcharge; "
            "IVA+RE is non-deductible acquisition cost and is not declared as M303 input IVA"
        )
    if transaction.direction is TransactionDirection.INCOMING:
        return (
            "iva_category 'recargo_equivalencia' is not the supplier-side recargo sales channel; "
            "record supplier recargo on a taxable output sale through recargo_amount"
        )
    return "iva_category 'recargo_equivalencia' is not declarable through IVA ledger aggregation"


def _transaction_is_trabajo_income(transaction: Transaction) -> bool:
    """Return whether the transaction is a nómina (trabajo) income row.

    AEAT classifies an IRPF rendimiento del trabajo (wage/salary)
    received from an employer as an income flow that never carries an
    IVA component; the row's IRPF-side retenciones binding consumes
    the gross amount and the IVA aggregation never reads it. The
    preflight must therefore skip the IVA-fact checks on these rows.

    Resolved through the closed catalogue so this reader and the gross
    invariant agree on what a token names. Comparing the stripped, lowercased
    string to a local ``"trabajo"`` literal here meant ``TRABAJO`` classified
    as employment in the preflight while naming no descriptor at all in the
    gross invariant.
    """
    return has_employment_irpf_category(transaction.irpf_category, direction=transaction.direction)


def _preflight_reason_for_iva_issue(reason: IvaLedgerAggregationIssueReason) -> LedgerPreflightIssueReason:
    return {
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: LedgerPreflightIssueReason.MISSING_TAXABLE_BASE,
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: LedgerPreflightIssueReason.MISSING_IVA_AMOUNT,
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: LedgerPreflightIssueReason.MISSING_IVA_RATE,
        IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE: (
            LedgerPreflightIssueReason.MISSING_EUR_TAX_SUBSTRATE
        ),
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_EU_MEMBER_STATE: (
            LedgerPreflightIssueReason.MISSING_COUNTERPARTY_EU_MEMBER_STATE
        ),
        IvaLedgerAggregationIssueReason.DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION: (
            LedgerPreflightIssueReason.DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION
        ),
        IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION: (
            LedgerPreflightIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION
        ),
    }[reason]


def _preflight_detail_for_iva_issue(reason: IvaLedgerAggregationIssueReason) -> str:
    return {
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: "transaction has no taxable_base fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: "transaction has no iva_amount fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: "transaction has no iva_rate fact",
        IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE: (
            "converted non-EUR transaction requires explicit EUR tax substrate"
        ),
    }[reason]


__all__ = [
    "LedgerPreflightIssue",
    "LedgerPreflightIssueReason",
    "LedgerPreflightReport",
    "preflight_ledger_tax_readiness",
    "preflight_transaction_catalogue",
]
