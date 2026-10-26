"""Readiness issues joined to the ledger facts that explain them.

A preflight issue names a transaction and a reason. On its own that tells an
operator a row is not ready without telling them why, so the facts a reader
needs to act -- the classification and the four tax fields a deductible row must
carry -- are joined on here. Choosing WHICH facts accompany an issue is a
diagnostic decision, not formatting, and it had been made inside the CLI status
verb where no second surface could reach it.

The join can miss. A caller joins a report against the rows it holds, and a
period-level issue names no row at all. The adapter dropped such issues
silently, which makes the issues an operator sees fewer than the count reported
beside them with nothing saying so. Here the issue survives with
``transaction_present`` false and its facts absent, because a readiness problem
whose row has vanished is a stronger signal than one whose row is merely
incomplete -- not a reason to say nothing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG

if TYPE_CHECKING:
    from ...domain.transactions.models import TransactionCatalogue
    from .preflight import LedgerPreflightReport


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


__all__ = ["LedgerReadinessIssueV1", "ledger_readiness_issues"]
