"""Whether a ledger is ready, and what is standing in the way.

Readiness draws on two independent sources: the preflight issues that block
modelo calculation, and the one-sided invoice links that mean the two
catalogues disagree with each other. A ledger is ready only when both are
clean, and that conjunction is the decision this module owns.

It had been made three times in the CLI verb -- once per branch, spelled
differently each time (``report.ready and not links``, ``not issues and not
links``, ``not links``). The three agree today only because the preflight's
``ready`` happens to be ``not issues``; nothing held them together, and a
second frontend asking "is my ledger ready" would have had to pick one of the
three spellings to copy.

Choosing the periods to check is the other decision here. With no period given
the sweep covers every year the ledger actually spans, derived from the
transactions themselves rather than a calendar assumption, and each year is
checked over its annual period.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, NonNegativeInt

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.invoices.service import LinkInconsistency
from ..invoices.catalogue_reads import verify_invoice_repository_links
from .preflight import LedgerPreflightIssue, preflight_transaction_catalogue

if TYPE_CHECKING:
    from ...domain.transactions.models import TransactionCatalogue

#: The AEAT period code covering a whole filing year, used by the sweep.
_ANNUAL_PERIOD_CODE = "0A"

type LinkInconsistencyReaderV1 = Callable[..., tuple[LinkInconsistency, ...]]


class LedgerCheckV1(BaseModel):
    """One readiness verdict with the findings that produced it."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: str
    periods: tuple[str, ...]
    checked_transaction_count: NonNegativeInt
    issues: tuple[LedgerPreflightIssue, ...]
    link_inconsistencies: tuple[LinkInconsistency, ...]
    ready: bool


def ledger_check_years(transactions: TransactionCatalogue) -> tuple[int, ...]:
    """Return every filing year the stored transactions actually fall in.

    Derived from the rows rather than assumed from a calendar, so a sweep never
    reports on a year the operator has no ledger for, and never misses one they
    do. ``booked_date`` is required, so the fallback always yields a date.
    """
    return tuple(
        sorted(
            {(transaction.raw.value_date or transaction.raw.booked_date).year for transaction in transactions.values()}
        )
    )


def read_ledger_check(
    *,
    bucket_id: str,
    transactions: TransactionCatalogue,
    period: Period | None = None,
    link_reader: LinkInconsistencyReaderV1 = verify_invoice_repository_links,
) -> LedgerCheckV1:
    """Assess one ledger's readiness over a period, or over everything it spans.

    Args:
        bucket_id: The owning profile bucket.
        transactions: The live ledger to assess.
        period: One period to check; when omitted, every year the ledger spans
            is swept over its annual period.
        link_reader: The invoice-link consistency read, injectable so the
            readiness conjunction can be exercised without a live catalogue.

    Returns:
        The verdict, the periods it covers, and the findings behind it.
    """
    link_inconsistencies = tuple(link_reader(bucket_id=bucket_id))

    if period is not None:
        report = preflight_transaction_catalogue(bucket_id=bucket_id, period=period, transactions=transactions)
        periods = (str(period),)
        checked = report.checked_transaction_count
        issues = tuple(report.issues)
    else:
        years = ledger_check_years(transactions)
        periods = tuple(str(year) for year in years)
        checked = 0
        collected: list[LedgerPreflightIssue] = []
        for year in years:
            report = preflight_transaction_catalogue(
                bucket_id=bucket_id,
                period=Period.from_year_and_code(year, _ANNUAL_PERIOD_CODE),
                transactions=transactions,
            )
            checked += report.checked_transaction_count
            collected.extend(report.issues)
        issues = tuple(collected)

    return LedgerCheckV1(
        bucket_id=bucket_id,
        periods=periods,
        checked_transaction_count=checked,
        issues=issues,
        link_inconsistencies=link_inconsistencies,
        # The one place the conjunction is stated. A ledger with no preflight
        # issue but a one-sided invoice link is NOT ready: the catalogues
        # disagree about a fact a filing would rest on.
        ready=not issues and not link_inconsistencies,
    )


__all__ = ["LedgerCheckV1", "LinkInconsistencyReaderV1", "ledger_check_years", "read_ledger_check"]
