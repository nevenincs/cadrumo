"""Application-owned read capabilities for ledger LLM diagnostics.

The diagnostics projection aggregates two existing stores, but it does not own
either store's persistence details.  The application boundary therefore names
only the accounting facts it needs and lets an executable composition root
translate concrete records and failures before they cross inward.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from ...core.errors.hierarchy import CadrumoError
from ...domain.transactions.models import Transaction


@dataclass(frozen=True, slots=True)
class LlmUsageDiagnosticRecord:
    """Accounting-only usage fact supplied by an outer reader.

    Response text, request identifiers, and other transport/storage fields are
    intentionally absent: the diagnostics use case has no reason to receive
    them, and the DTO keeps that boundary explicit.
    """

    provider: str
    input_tokens: int
    output_tokens: int
    cost_estimate_usd: Decimal | None
    cache_hit: bool


class LlmUsageDiagnosticsReader(Protocol):
    """Read usage accounting facts within an inclusive date window."""

    def load_records(
        self,
        *,
        since: date | None,
        until: date | None,
    ) -> Sequence[LlmUsageDiagnosticRecord]:
        """Return translated usage facts for the requested window."""
        ...


class LlmTransactionDiagnosticsReader(Protocol):
    """Read the domain transaction facts used for confidence diagnostics."""

    def load_transactions(self) -> Sequence[Transaction]:
        """Return all transactions in the explicitly composed bucket."""
        ...


class LlmDiagnosticsReadError(CadrumoError):
    """A usage or transaction diagnostics read failed at the outer boundary."""


@dataclass(frozen=True, slots=True)
class LlmDiagnosticsPorts:
    """Required read capabilities for one ledger LLM diagnostics report."""

    usage_reader: LlmUsageDiagnosticsReader
    transaction_reader: LlmTransactionDiagnosticsReader


__all__ = [
    "LlmDiagnosticsPorts",
    "LlmDiagnosticsReadError",
    "LlmTransactionDiagnosticsReader",
    "LlmUsageDiagnosticRecord",
    "LlmUsageDiagnosticsReader",
]
