"""Strict read-only ledger diagnostic payload schemas for CLI commands."""

from __future__ import annotations

from ...core.identity.bucket import BucketId
from ...core.identity.transaction_ids import TransactionId
from ...core.invoice_link import LinkInconsistencyDirection
from ...core.json_contract import OutputSchema
from ...core.prose_elision import IssueDetail


class LedgerPeriodPayload(OutputSchema):
    """Nested filing-period projection used by ledger readiness surfaces.

    Carries the JSON-safe filing year plus period code derived from
    :class:`Period`; preflight/check reports use this shape instead
    of serialising the richer period object directly.
    """

    filing_year: int
    code: str


class LedgerPreflightIssuePayload(OutputSchema):
    """One readiness issue attached to a ledger transaction.

    Mirrors :class:`LedgerPreflightIssue`: the
    transaction id, machine-readable reason, and operator detail explaining which
    fact blocks or warns before modelo calculation.
    """

    transaction_id: TransactionId
    reason: str
    detail: IssueDetail


class LedgerLinkInconsistencyPayload(OutputSchema):
    """One one-sided invoice/transaction link found by the check verb.

    Mirrors :class:`~cadrumo.domain.invoices.service.LinkInconsistency`. ``direction``
    names which catalogue cites the other without being cited back:
    ``invoice-only`` when the invoice carries the transaction in its
    ``linked_transaction_ids`` but the transaction's ``invoice_id`` does not
    point back, ``transaction-only`` for the reverse. Either way the two
    catalogues disagree about a link and the association cannot be trusted
    until the operator re-runs ``link``.

    ``direction`` stays typed as the core
    :class:`~cadrumo.core.invoice_link.LinkInconsistencyDirection` all the way to the
    operator boundary, so the closed value set is validated here rather than
    degrading to a free-form string on the way out.
    """

    invoice_id: str
    transaction_id: TransactionId
    direction: LinkInconsistencyDirection


class LedgerCheckResult(OutputSchema):
    """JSON envelope for ``aeat app ledger check``.

    ``check`` is a report-only audit over one explicit period or every period the
    ledger touches.  It aggregates
    :func:`preflight_transaction_catalogue` issue rows
    into a bucket-level readiness verdict without mutating transactions.

    ``link_inconsistencies`` is the second, period-independent channel: the
    one-sided invoice/transaction links
    :func:`~cadrumo.application.invoices.catalogue_reads.verify_invoice_repository_links`
    reports over the whole bucket. ``ready`` is false when either channel is
    non-empty, because a disagreeing link makes the affected rows' invoice
    association untrustworthy just as a missing fact does.
    """

    bucket_id: BucketId
    periods: list[str]
    checked_transaction_count: int
    issues: list[LedgerPreflightIssuePayload]
    link_inconsistencies: list[LedgerLinkInconsistencyPayload] = []
    ready: bool


class LedgerPreflightResult(OutputSchema):
    """JSON envelope for ``aeat app ledger preflight``.

    Mirrors :class:`LedgerPreflightReport` produced by
    :func:`preflight_ledger_tax_readiness`. ``period``
    is the nested
    :class:`LedgerPeriodPayload` model
    dump, ``issues`` are
    :class:`LedgerPreflightIssuePayload`
    rows, and ``ready`` is the computed no-issues verdict.
    """

    bucket_id: BucketId
    period: LedgerPeriodPayload
    checked_transaction_count: int
    issues: list[LedgerPreflightIssuePayload]
    ready: bool


__all__ = [
    "LedgerCheckResult",
    "LedgerLinkInconsistencyPayload",
    "LedgerPeriodPayload",
    "LedgerPreflightIssuePayload",
    "LedgerPreflightResult",
]
