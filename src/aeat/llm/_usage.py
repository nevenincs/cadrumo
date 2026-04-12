"""Append-only usage recorder for LLM calls."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from aeat.config import PROJECT_ROOT
from aeat.llm._errors import LLMCacheError
from aeat.llm._models import LLMResponse, UsageRecord, UsageSummary


class UsageRecorder:
    """Append LLM usage records to daily JSONL files.

    TODO #10: replace the file-backed implementation with the storage-layer
    persistence once issue ``#10`` lands on this branch.
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or (PROJECT_ROOT / "var" / "llm-usage")
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def build_record(self, response: LLMResponse, prompt_id: str, caller: str) -> UsageRecord:
        """Create a usage record from a public response.

        Args:
            response: Public LLM response model.
            prompt_id: Stable prompt identifier.
            caller: Stable caller identifier.

        Returns:
            Persistable usage record.
        """

        return UsageRecord(
            prompt_id=prompt_id,
            caller=caller,
            text=response.text,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_estimate_usd=response.cost_estimate_usd,
            cache_hit=response.cache_hit,
            created_at=response.created_at,
            request_id=response.request_id,
        )

    def record(self, record: UsageRecord) -> Path:
        """Append a record to the daily JSONL file.

        Args:
            record: Usage record to append.

        Returns:
            Path to the JSONL file that received the record.
        """

        path = self.root_dir / f"usage-{record.created_at.date().isoformat()}.jsonl"
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(record.model_dump_json())
                handle.write("\n")
        except OSError as exc:  # pragma: no cover - defensive filesystem path
            msg = f"Failed to append usage record to {path}"
            raise LLMCacheError(msg) from exc
        return path

    def load_records(self, since: date | None = None, until: date | None = None) -> tuple[UsageRecord, ...]:
        """Load usage records within an optional inclusive date range.

        Args:
            since: Optional inclusive lower date bound.
            until: Optional inclusive upper date bound.

        Returns:
            Loaded usage records.
        """

        records: list[UsageRecord] = []
        for path in sorted(self.root_dir.glob("usage-*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = UsageRecord.model_validate_json(line)
                record_date = record.created_at.date()
                if since is not None and record_date < since:
                    continue
                if until is not None and record_date > until:
                    continue
                records.append(record)
        return tuple(records)

    def summarize(self, since: date | None = None, until: date | None = None) -> UsageSummary:
        """Summarize usage within an optional inclusive date range.

        Args:
            since: Optional inclusive lower date bound.
            until: Optional inclusive upper date bound.

        Returns:
            Aggregate usage summary.
        """

        records = self.load_records(since=since, until=until)
        total_cost = sum((record.cost_estimate_usd for record in records), start=Decimal("0"))
        return UsageSummary(
            entries=len(records),
            total_input_tokens=sum(record.input_tokens for record in records),
            total_output_tokens=sum(record.output_tokens for record in records),
            total_cost_estimate_usd=total_cost,
            since=since,
            until=until,
        )
