"""Readiness issues joined to the ledger facts that explain them.

A preflight issue names a transaction and a reason. On its own that tells an
operator a row is not ready without telling them why, so the facts a reader
needs to act -- the classification and the four tax fields a deductible row must
carry -- are joined on here. Choosing WHICH facts accompany an issue is a
diagnostic decision, not formatting, and it had been made inside the CLI status
verb where no second surface could reach it.

The join can miss. The preflight and the join read one catalogue here, but a
caller may join a report against rows it holds, and a period-level issue names
no row at all. The adapter dropped such issues silently, which makes the issues
an operator sees fewer than the count reported beside them with nothing saying
so. Here the issue survives with ``transaction_present`` false and its facts
absent, because a readiness problem whose row has vanished is a stronger
signal than one whose row is merely incomplete -- not a reason to say nothing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from .preflight import LedgerPreflightReport, load_period_preflight_catalogue, preflight_ledger_tax_readiness

if TYPE_CHECKING:
    from ...core.period import Period
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.transactions.models import TransactionCatalogue

from .protocols import TransactionCatalogueCoCommitWriterProtocol
from .usage_ratio_repository import UsageRatioProfileLoader


class LedgerReadinessIssueV1(BaseModel):
    """One readiness issue with the ledger facts that explain it.

    Every fact is optional because it is optional on the row: a deductible
    transaction missing its category is exactly the case this reports, so an
    absent value is the finding rather than a gap in the read.
    """

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: str
    reason: str
    detail: str
    transaction_present: bool
    business_classification: str | None = None
    category_id: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None


def read_ledger_readiness(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol,
    usage_ratio_profile_loader: UsageRatioProfileLoader,
    operation: PinnedAuthorityOperation,
    catalogue: TransactionCatalogue | None = None,
) -> tuple[LedgerReadinessIssueV1, ...]:
    """Report this period's readiness issues with their explaining facts.

    One read serves both the preflight and the join: the period's rows when
    the caller holds none, so the explaining facts come from the same rows the
    preflight inspected.

    Args:
        bucket_id: The owning profile bucket.
        period: The filing period to assess.
        transaction_repository: Explicit bucket-scoped catalogue port.
        usage_ratio_profile_loader: Profile-scoped declared ratio reader.
        operation: Caller-owned authority pin shared with the ledger workflow.
        catalogue: The bucket's rows as a :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`
            when the caller already holds them,
            either the whole catalogue or any superset of the period's rows.

    Returns:
        Every issue the preflight raised, in report order, each carrying the
        row's facts when the row is still present.
    """
    from .actions_common import resolve_transaction_repository

    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transactions = catalogue if catalogue is not None else load_period_preflight_catalogue(repository, period)
    report = preflight_ledger_tax_readiness(
        bucket_id=bucket_id,
        period=period,
        transaction_repository=repository,
        usage_ratio_profile_loader=usage_ratio_profile_loader,
        operation=operation,
        catalogue=transactions,
    )
    return ledger_readiness_issues(report, transactions)


def ledger_readiness_issues(
    report: LedgerPreflightReport,
    catalogue: TransactionCatalogue,
) -> tuple[LedgerReadinessIssueV1, ...]:
    """Join each issue of ``report`` to the explaining facts of its row in ``catalogue``.

    ``catalogue`` is a :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`
    that must hold every row the report could name: the catalogue the
    report was computed from, or the whole bucket. An issue whose row it does
    not hold is kept with ``transaction_present`` false.
    """
    issues: list[LedgerReadinessIssueV1] = []
    for issue in report.issues:
        transaction = catalogue.get(issue.transaction_id)
        if transaction is None:
            issues.append(
                LedgerReadinessIssueV1(
                    transaction_id=issue.transaction_id,
                    reason=issue.reason.value,
                    detail=issue.detail,
                    transaction_present=False,
                )
            )
            continue
        issues.append(
            LedgerReadinessIssueV1(
                transaction_id=issue.transaction_id,
                reason=issue.reason.value,
                detail=issue.detail,
                transaction_present=True,
                business_classification=transaction.business_classification.value,
                category_id=transaction.category_id,
                taxable_base=transaction.taxable_base,
                iva_rate=transaction.iva_rate,
                iva_amount=transaction.iva_amount,
            )
        )
    return tuple(issues)


__all__ = ["LedgerReadinessIssueV1", "ledger_readiness_issues", "read_ledger_readiness"]
