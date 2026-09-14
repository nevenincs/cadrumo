"""Outer composition for the ledger LLM-diagnostics read capabilities."""

from __future__ import annotations

from datetime import date

from ..application.ledger.llm_diagnostics_ports import (
    LlmDiagnosticsPorts,
    LlmDiagnosticsReadError,
    LlmUsageDiagnosticRecord,
)
from ..domain.transactions.models import Transaction


def compose_ledger_llm_diagnostics_ports(*, bucket_id: str) -> LlmDiagnosticsPorts:
    """Bind the diagnostics readers to the encrypted usage and ledger stores."""
    from ..adapters.outbound.llm.usage import UsageRecorder
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


__all__ = ["compose_ledger_llm_diagnostics_ports"]
