"""Typed ledger date partitions and plaintext out-of-window diagnostics."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .errors import TransactionValidationError
from .models import TransactionCatalogue


class OutOfWindowTransactionIndexEntry(BaseModel):
    """A catalogue transaction outside a requested date window, undecrypted.

    Carries ONLY the two plaintext, non-sensitive facts a period-scoped
    aggregator needs to report the transaction as excluded --
    ``transaction_id`` and its ``filing_date`` -- never any decrypted field
    (amount, category, counterparty, direction, business classification).
    This is the period-first partition contract: an out-of-window row is
    diagnosed from the plaintext date-index fact alone, without paying the
    decrypt-and-validate cost, and without leaking anything the index itself
    does not already carry.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    filing_date: date


class OutOfWindowTransactionSummary(BaseModel):
    """Compact diagnostics-only summary for out-of-window catalogue rows.

    Carries only the excluded-row count and the filing-date span covered
    by those rows. It never carries decrypted transaction facts.
    """

    model_config = _STRICT_FROZEN

    count: int = Field(ge=1)
    min_filing_date: date
    max_filing_date: date

    @classmethod
    def from_index_entries(cls, index_entries: Iterable[OutOfWindowTransactionIndexEntry]) -> Self | None:
        """Build a summary from plaintext date-index entries, or ``None`` when empty."""
        materialized = tuple(index_entries)
        if not materialized:
            return None
        filing_dates = tuple(entry.filing_date for entry in materialized)
        return cls(
            count=len(materialized),
            min_filing_date=min(filing_dates),
            max_filing_date=max(filing_dates),
        )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_date_span(self) -> Self:
        if self.max_filing_date < self.min_filing_date:
            raise TransactionValidationError("out-of-window summary date span must be ordered")
        return self


class LedgerDatePartition(BaseModel):
    """A ledger catalogue split into an in-window and an out-of-window half.

    ``in_window`` is a real, fully decrypted :class:`TransactionCatalogue`
    scoped to ``[start, end]`` -- every regulated classifier gate runs over it
    unchanged. ``out_of_window`` is the plaintext-only remainder
    (:class:`OutOfWindowTransactionIndexEntry` rows): transactions the catalogue
    holds outside the window, reported without decryption so a caller can
    still surface a period-exclusion diagnostic for them.

    ``out_of_window_summary`` is the compact diagnostics-channel replacement:
    count plus filing-date span, with no decrypted fields and no row-level
    allocation requirement. During the migration, callers may see either the
    row-level index entries, the summary, or both.

    ``index_complete`` records whether the partition was served from a
    complete plaintext date index (``True``) or from a full-scan fallback
    after a completeness-gate mismatch (``False`` -- see
    ``aeat-ledger-contract``): both cases return
    an identical partition shape, so a caller cannot observe which path
    served it except through this flag and through latency.
    """

    model_config = _STRICT_FROZEN

    in_window: TransactionCatalogue
    out_of_window: tuple[OutOfWindowTransactionIndexEntry, ...] = ()
    out_of_window_summary: OutOfWindowTransactionSummary | None = None
    index_complete: bool
