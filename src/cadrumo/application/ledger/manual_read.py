"""Manual ledger transaction services and read projections.

The services build :class:`~cadrumo.domain.transactions.models.Transaction` records from
:class:`~cadrumo.application.ledger.models.ManualLedgerTransactionCommand`, persist them
in a loaded :class:`TransactionCatalogue`, append bucket events, and return
:class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult` values.
Evidence paths validate purchase-invoice, attachment, and
:class:`~cadrumo.domain.usage_ratios.model.UsageRatioProfile` references before
persistence.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

from ...core.errors.hierarchy import CadrumoError, InternalInvariantError
from ...core.period import Period
from ...domain.iva.schema import EUMemberState, IvaCategory
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import (
    BucketTransactionRef,
    Transaction,
    TransactionCatalogue,
)
from ..aggregation.currency_predicates import effective_eur_amount, is_non_eur_without_conversion
from ..review.filter import LedgerReviewStatus
from .action_ports import LedgerActionPorts
from .actions_common import (
    build_manual_ledger_result,
    display_decimal,
    require_transaction,
    resolve_transaction_repository,
)
from .models import (
    LedgerReviewQuery,
    LedgerReviewQueryResult,
    LedgerStatusReport,
    LedgerTransactionPayload,
    LedgerTransactionResultPayload,
    LedgerTransactionReviewPayload,
    LedgerTransactionTrackingPayload,
    ManualLedgerTransactionResult,
)
from .preflight import LedgerPreflightReport, preflight_ledger_tax_readiness
from .protocols import (
    TransactionCatalogueCoCommitWriterProtocol,
)
from .read_ports import LedgerReadPorts
from .review_projection import ledger_transaction_review_status, project_ledger_review_query
from .usage_ratio_repository import UsageRatioProfileLoader


def get_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    ports: LedgerActionPorts,
    catalogue: TransactionCatalogue | None = None,
) -> ManualLedgerTransactionResult:
    """Return one :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult` from a bucket catalogue.

    ``catalogue`` is a :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`
    the caller already read that holds the row,
    such as the one its id was resolved against; otherwise the bucket's
    catalogue is loaded here. A row the catalogue does not hold is refused as
    not found either way.
    """
    if catalogue is None:
        repository = resolve_transaction_repository(bucket_id=bucket_id, repository=ports.transaction_repository)
        catalogue = repository.load()
    transaction = require_transaction(catalogue, transaction_id)
    return build_manual_ledger_result(bucket_id, transaction, ())


def list_manual_transactions(
    *,
    bucket_id: str,
    ports: LedgerReadPorts,
    catalogue: TransactionCatalogue | None = None,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Return every transaction in a bucket, sorted by effective date and id.

    Each element is a
    :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult` for one
    stored transaction. ``catalogue`` is the bucket's already-loaded catalogue
    when the caller holds one; otherwise it is loaded here.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    if catalogue is None:
        repository = resolve_transaction_repository(bucket_id=bucket_id, repository=ports.transaction_repository)
        catalogue = repository.load()
    transactions = sorted(
        catalogue.values(),
        key=lambda transaction: (
            transaction.raw.value_date or transaction.raw.booked_date,
            transaction.transaction_id,
        ),
    )
    return tuple(_catalogue_member_result(bucket_id, transaction) for transaction in transactions)


def _catalogue_member_result(bucket_id: str, transaction: Transaction) -> ManualLedgerTransactionResult:
    """Wrap one catalogue member as a listing result without validating it again.

    Pydantic re-runs every ``Transaction`` model validator, including the
    derived-id hash and the registry-backed tax couplings, whenever an
    existing instance is assigned to a model field. A catalogue member is a
    frozen instance that already passed those validators when it was decoded
    or constructed, so repeating them here only multiplied the listing cost.
    The reference is still validated, and the result carries exactly the
    values the validated constructor would.
    """
    return ManualLedgerTransactionResult.model_construct(
        ref=BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction.transaction_id),
        transaction=transaction,
        bucket_event_ids=(),
        stale_finalized_revisions=(),
    )


def query_ledger_review_rows(
    query: LedgerReviewQuery,
    *,
    ports: LedgerReadPorts,
    catalogue: TransactionCatalogue | None = None,
) -> LedgerReviewQueryResult:
    """Return review rows for bucket-local ledger transactions.

    Returns a :class:`~cadrumo.application.ledger.models.LedgerReviewQueryResult`.
    ``catalogue`` is the query bucket's already-loaded catalogue when the caller
    holds one; otherwise it is loaded here.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    if catalogue is None:
        repository = resolve_transaction_repository(bucket_id=query.bucket_id, repository=ports.transaction_repository)
        catalogue = repository.load()
    return project_ledger_review_query(
        query=query,
        catalogue=catalogue,
        bucket_event_repository=ports.bucket_event_repository,
        transaction_payload_builder=ledger_transaction_payload,
    )


def _display_optional_decimal(value: Decimal | None) -> str | None:
    """Render an optional Decimal exactly as a ledger read projection expects."""
    if value is None:
        return None
    return display_decimal(value)


def _optional_iso_date(value: date | None) -> str | None:
    """Render an optional ledger date as an ISO calendar date."""
    if value is None:
        return None
    return value.isoformat()


def _optional_iso_datetime(value: datetime | None) -> str | None:
    """Render an optional ledger timestamp as an ISO-8601 string."""
    if value is None:
        return None
    return value.isoformat()


def _optional_ledger_enum_value(value: IvaCategory | EUMemberState | None) -> str | None:
    """Project a nullable string-valued ledger enum without changing its token."""
    if value is None:
        return None
    return value.value


def ledger_transaction_payload(transaction: Transaction) -> LedgerTransactionPayload:
    """Return the :class:`~cadrumo.application.ledger.models.LedgerTransactionPayload` for one ledger transaction."""
    raw = transaction.raw
    return LedgerTransactionPayload(
        transaction_id=transaction.transaction_id,
        date=(raw.value_date or raw.booked_date).isoformat(),
        booked_date=raw.booked_date.isoformat(),
        value_date=_optional_iso_date(raw.value_date),
        amount=display_decimal(raw.amount),
        currency=raw.currency,
        direction=transaction.direction.value,
        counterparty=raw.display_counterparty,
        description=raw.description,
        business_classification=transaction.business_classification.value,
        business_pct=_display_optional_decimal(transaction.business_pct),
        category_id=transaction.category_id,
        taxable_base=_display_optional_decimal(transaction.taxable_base),
        iva_rate=_display_optional_decimal(transaction.iva_rate),
        iva_amount=_display_optional_decimal(transaction.iva_amount),
        iva_category=_optional_ledger_enum_value(transaction.iva_category),
        counterparty_country=transaction.counterparty_country,
        counterparty_identification_state=_optional_ledger_enum_value(
            transaction.counterparty_identification_state,
        ),
        irpf_category=transaction.irpf_category,
        m210_income_classification=transaction.m210_income_classification,
        usage_ratio_id=transaction.usage_ratio_id,
        prorrata_reference=transaction.prorrata_reference,
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id,
        invoice_id=transaction.invoice_id,
        attachment_ids=transaction.attachment_ids,
        notes=transaction.notes,
        lifecycle_state=transaction.lifecycle_state.value,
        classified_by=transaction.classified_by,
        classified_at=_optional_iso_datetime(transaction.classified_at),
        classification_reason=transaction.classification_reason,
        classification_confidence=_display_optional_decimal(transaction.classification_confidence),
        source_jurisdiction=transaction.source_jurisdiction,
        value_in_eur=_display_optional_decimal(transaction.value_in_eur),
        fx_rate=_display_optional_decimal(transaction.fx_rate),
        created_at=transaction.created_at.isoformat(),
        modified_at=transaction.modified_at.isoformat(),
    )


def ledger_transaction_review_payload(transaction: Transaction) -> LedgerTransactionReviewPayload:
    """Return one ledger transaction projection plus derived operator review status.

    Returns a
    :class:`~cadrumo.application.ledger.models.LedgerTransactionReviewPayload` with all
    operator-facing fields populated from the transaction record.
    """
    base = ledger_transaction_payload(transaction)
    return LedgerTransactionReviewPayload(
        **base.model_dump(),
        review_status=ledger_transaction_review_status(transaction),
    )


def ledger_transaction_result_payload(result: ManualLedgerTransactionResult) -> LedgerTransactionResultPayload:
    """Return the canonical result payload for one ledger mutation/read result.

    Returns a :class:`~cadrumo.application.ledger.models.LedgerTransactionResultPayload`.
    """
    return LedgerTransactionResultPayload(
        bucket_id=result.ref.bucket_id,
        transaction_id=result.ref.transaction_id,
        review_status=ledger_transaction_review_status(result.transaction),
        transaction=ledger_transaction_payload(result.transaction),
    )


def ledger_transaction_tracking_payload(transaction: Transaction) -> LedgerTransactionTrackingPayload:
    """Return durable event lineage fields for one ledger transaction.

    Returns a
    :class:`~cadrumo.application.ledger.models.LedgerTransactionTrackingPayload`.
    """
    return LedgerTransactionTrackingPayload(
        transaction_id=transaction.transaction_id,
        created_event_id=transaction.created_event_id,
        evidence_provenance=transaction.evidence_provenance,
        edit_lineage=transaction.edit_lineage,
        lifecycle_state=transaction.lifecycle_state.value,
        lifecycle_lineage=transaction.lifecycle_lineage,
    )


def _manual_transaction_snapshot(
    *,
    bucket_id: str,
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol | None,
    catalogue: TransactionCatalogue | None,
) -> TransactionCatalogue:
    """Load one stable transaction snapshot, reusing a caller-owned catalogue."""
    if catalogue is None:
        catalogue = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository).load()
    return catalogue


def _review_status_counts(transactions: tuple[Transaction, ...]) -> dict[LedgerReviewStatus, int]:
    """Count review statuses for active transactions in one snapshot.

    Keyed from the enum itself, so every status a row can project to has a slot.
    """
    status_counts = dict.fromkeys(LedgerReviewStatus, 0)
    for transaction in transactions:
        if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE:
            status_counts[ledger_transaction_review_status(transaction)] += 1
    return status_counts


def _readiness_summary(
    *,
    bucket_id: str,
    period: Period | None,
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol | None,
    usage_ratio_profile_loader: UsageRatioProfileLoader,
    operation: PinnedAuthorityOperation,
    catalogue: TransactionCatalogue,
    preflight: LedgerPreflightReport | None,
) -> tuple[int, int, bool | None]:
    """Return readiness counts for ``period`` from the summarised snapshot.

    A caller that already ran the period's preflight on this snapshot passes
    its report; otherwise the preflight inspects the snapshot itself rather
    than reading the bucket a second time.
    """
    if period is None:
        if preflight is not None:
            raise InternalInvariantError("a ledger summary without a period received a preflight report")
        return 0, 0, None
    if preflight is None:
        preflight = preflight_ledger_tax_readiness(
            bucket_id=bucket_id,
            period=period,
            transaction_repository=resolve_transaction_repository(
                bucket_id=bucket_id,
                repository=transaction_repository,
            ),
            usage_ratio_profile_loader=usage_ratio_profile_loader,
            operation=operation,
            catalogue=catalogue,
        )
    elif preflight.bucket_id != bucket_id or preflight.period != period:
        raise InternalInvariantError("a ledger summary received the preflight report of another bucket or period")
    return preflight.checked_transaction_count, len(preflight.issues), preflight.ready


def _business_money_contribution(
    transaction: Transaction,
    *,
    period: Period | None,
) -> tuple[Decimal, Decimal, int]:
    """Return income, expense, and unconverted counts for one eligible row."""
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return Decimal("0"), Decimal("0"), 0
    if transaction.business_classification not in {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
    }:
        return Decimal("0"), Decimal("0"), 0
    if period is not None and not period.contains(transaction.raw.value_date or transaction.raw.booked_date):
        return Decimal("0"), Decimal("0"), 0
    if is_non_eur_without_conversion(transaction):
        return Decimal("0"), Decimal("0"), 1
    eur = abs(effective_eur_amount(transaction))
    if transaction.direction is TransactionDirection.INCOMING:
        return eur, Decimal("0"), 0
    if transaction.direction is TransactionDirection.OUTGOING:
        return Decimal("0"), eur, 0
    return Decimal("0"), Decimal("0"), 0


def _business_money_summary(
    transactions: tuple[Transaction, ...],
    *,
    period: Period | None,
) -> tuple[Decimal, Decimal, int]:
    """Aggregate active business/mixed rows into gross EUR totals."""
    income_total = Decimal("0")
    expense_total = Decimal("0")
    unconverted_count = 0
    for transaction in transactions:
        income, expense, unconverted = _business_money_contribution(transaction, period=period)
        income_total += income
        expense_total += expense
        unconverted_count += unconverted
    return income_total, expense_total, unconverted_count


def _count_lifecycle_state(
    transactions: tuple[Transaction, ...],
    state: TransactionLifecycleState,
) -> int:
    """Count rows carrying one lifecycle state in the snapshot."""
    return sum(1 for transaction in transactions if transaction.lifecycle_state is state)


def _lifecycle_counts(transactions: tuple[Transaction, ...]) -> tuple[int, int, int, int]:
    """Return active, archived, stashed, and split counts in report order."""
    return (
        _count_lifecycle_state(transactions, TransactionLifecycleState.ACTIVE),
        _count_lifecycle_state(transactions, TransactionLifecycleState.ARCHIVED),
        _count_lifecycle_state(transactions, TransactionLifecycleState.STASHED),
        _count_lifecycle_state(transactions, TransactionLifecycleState.SPLIT),
    )


class LedgerSummaryPeriodWithoutSpanError(CadrumoError):
    """A ledger summary was asked to scope its money totals to a period without dates.

    Instalment claves (``1P``-``4P``) and extended union members are filing or
    payment events, not calendar spans, so no transaction falls inside them and
    a total for one would read as a proven zero.
    """

    def __init__(self, period: Period) -> None:
        """Keep the refused period for the structured error context."""
        super().__init__(
            translated_message="errors.refused.ledger_summary_period_without_span",
            context={"period": str(period)},
        )


def require_summary_period_span(period: Period | None) -> None:
    """Refuse a summary period that cannot select transactions by their filing date."""
    if period is not None and not period.has_date_span():
        raise LedgerSummaryPeriodWithoutSpanError(period)


def summarize_manual_transactions(
    *,
    bucket_id: str,
    period: Period | None = None,
    ports: LedgerActionPorts,
    catalogue: TransactionCatalogue | None = None,
    preflight: LedgerPreflightReport | None = None,
) -> LedgerStatusReport:
    """Return a read-only :class:`~cadrumo.application.ledger.models.LedgerStatusReport` for one bucket.

    ``catalogue`` lets a caller that has already loaded this bucket's
    transactions summarise that exact snapshot. Reloading would cost a second
    decrypted read and, if a write interleaved, would describe a different
    instant from the rows the caller is projecting beside it. The period's
    readiness preflight inspects the same snapshot, and ``preflight`` lets a
    caller that already ran it on that snapshot reuse its report.

    A period without a calendar date span is refused with
    :class:`LedgerSummaryPeriodWithoutSpanError` before anything is read.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    require_summary_period_span(period)
    snapshot = _manual_transaction_snapshot(
        bucket_id=bucket_id,
        transaction_repository=ports.transaction_repository,
        catalogue=catalogue,
    )
    transactions = tuple(snapshot.values())
    status_counts = _review_status_counts(transactions)
    checked, issue_count, ready = _readiness_summary(
        bucket_id=bucket_id,
        period=period,
        transaction_repository=ports.transaction_repository,
        usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
        operation=ports.operation,
        catalogue=snapshot,
        preflight=preflight,
    )
    # Money roll-up over active business/mixed rows (period-filtered when given):
    # the year-end / readiness money picture the personas asked for. Gross EUR
    # (value_in_eur for foreign rows), not a registry calculation.
    income_total, expense_total, unconverted_count = _business_money_summary(transactions, period=period)
    active_count, archived_count, stashed_count, split_count = _lifecycle_counts(transactions)
    return LedgerStatusReport(
        bucket_id=bucket_id,
        business_income_total=display_decimal(income_total),
        business_expense_total=display_decimal(expense_total),
        business_net_total=display_decimal(income_total - expense_total),
        total_count=len(transactions),
        active_count=active_count,
        archived_count=archived_count,
        stashed_count=stashed_count,
        split_count=split_count,
        pending_review_count=status_counts[LedgerReviewStatus.PENDING],
        reviewed_count=status_counts[LedgerReviewStatus.REVIEWED],
        skipped_count=status_counts[LedgerReviewStatus.SKIPPED],
        period=period,
        checked_transaction_count=checked,
        readiness_issue_count=issue_count,
        unconverted_currency_count=unconverted_count,
        ready=ready,
    )
