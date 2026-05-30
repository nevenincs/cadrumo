"""Transaction-identity alias for ledger transaction records.

The transaction identity is a hex-64 content-addressed sha-256 value
minted by the transaction domain when a ledger entry is persisted. The
alias lives in :mod:`aeat.core.identity` because the constraint shape
is consumed by sibling domains (notably :mod:`aeat.domain.invoices` for
reconciliation models), the application ledger service, and the
persistence adapters. Promoting the alias to core lets each consumer
import it without crossing a sibling-domain boundary.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

TransactionId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 content-addressed ledger-transaction identity."""

__all__ = ("TransactionId",)
