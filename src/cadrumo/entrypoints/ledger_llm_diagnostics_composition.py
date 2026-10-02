"""Outer composition for the ledger LLM-diagnostics read capabilities.

Core types:
:class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from ..application.ledger.llm_diagnostics_ports import (
    LlmDiagnosticsPorts,
    LlmDiagnosticsReadError,
    LlmUsageDiagnosticRecord,
)
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.transactions.models import Transaction

if TYPE_CHECKING:
    from ..application.ledger.llm_diagnostics_operation import LedgerLlmDiagnosticsOperationPorts


def compose_ledger_llm_diagnostics_ports(*, bucket_id: str) -> LlmDiagnosticsPorts:
    """Bind the diagnostics readers to the encrypted usage and ledger stores."""
    from ..adapters.persistence.llm.usage import UsageRecorder
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository

    normalized_bucket_id = bucket_id.strip()
    usage_recorder = UsageRecorder()
    transaction_repository = TransactionCatalogueRepository(bucket_id=normalized_bucket_id)

    class UsageDiagnosticsAdapter:
        """Translate persisted usage records to accounting-only application facts."""

        def load_records(
            self,
            *,
            since: date | None,
            until: date | None,
        ) -> tuple[LlmUsageDiagnosticRecord, ...]:
            try:
                records = usage_recorder.load_records(since=since, until=until)
                return tuple(
                    LlmUsageDiagnosticRecord(
                        provider=record.provider.value,
                        input_tokens=record.input_tokens,
                        output_tokens=record.output_tokens,
                        cost_estimate_usd=record.cost_estimate_usd,
                        cache_hit=record.cache_hit,
                    )
                    for record in records
                )
            except Exception as exc:
                raise LlmDiagnosticsReadError("Unable to load LLM usage diagnostics.") from exc

    class TransactionDiagnosticsAdapter:
        """Translate the bucket catalogue to the domain facts the report needs."""

        def load_transactions(self) -> tuple[Transaction, ...]:
            try:
                return tuple(transaction_repository.load().values())
            except Exception as exc:
                raise LlmDiagnosticsReadError("Unable to load ledger confidence diagnostics.") from exc

    return LlmDiagnosticsPorts(
        usage_reader=UsageDiagnosticsAdapter(),
        transaction_reader=TransactionDiagnosticsAdapter(),
    )


def build_ledger_llm_diagnostics_operation_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> LedgerLlmDiagnosticsOperationPorts:
    """Bind canonical accounting readers inside the exact profile worker."""
    from ..application.ledger.llm_diagnostics_operation import LedgerLlmDiagnosticsOperationPorts

    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LedgerLlmDiagnosticsOperationPorts(
        profile_id=profile_id,
        operation=operation,
        diagnostics=compose_ledger_llm_diagnostics_ports(bucket_id=str(profile_id)),
    )


__all__ = ["build_ledger_llm_diagnostics_operation_ports", "compose_ledger_llm_diagnostics_ports"]
