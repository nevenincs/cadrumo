"""Transaction-identity alias for ledger transaction records.

The transaction identity is a hex-64 content-addressed sha-256 value
minted by the transaction domain when a ledger entry is persisted. The
alias lives in :mod:`core.identity` because the constraint shape
is consumed by sibling domains (notably :mod:`domain.invoices` for
reconciliation models), the application ledger service, and the
persistence adapters. Promoting the alias to core lets each consumer
import it without crossing a sibling-domain boundary.
"""

from __future__ import annotations

from .._hex import Hex64Str

TransactionId = Hex64Str
"""Hex-64 content-addressed ledger-transaction identity."""

__all__ = ("TransactionId",)
