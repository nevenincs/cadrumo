"""Encrypted usage recorder for LLM calls.

Persists :class:`aeat.adapters.outbound.llm.UsageRecord` payloads to the
encrypted SQL secure-object backend and exposes load and aggregate helpers.
Records are routed through :func:`aeat.core.redaction.redact_structured` at
:class:`SensitivityClass` DIAGNOSTIC before they are encrypted, so NIFs and
bearer-shaped tokens are redacted before persistence.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from ....adapters.persistence.storage import LLM_USAGE_NAMESPACE
from ....core.config import load_settings
from ....core.hashing import canonical_json_bytes
from ._errors import LLMCacheError
from ._models import LLMResponse, UsageRecord, UsageSummary

_USAGE_NAMESPACE = LLM_USAGE_NAMESPACE.namespace
_USAGE_VERSION = 1


class UsageRecorder:
    """Append LLM usage records to encrypted secure objects.

    Each call to :meth:`record` appends a single redacted JSON line to
    the secure-object backend under the recorder's logical root.

    Attributes:
        root_dir: Logical partition used for usage records.
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        """Initialize the recorder.

        Args:
            root_dir: Logical usage partition; defaults to the centralized
                ``aeat_llm_usage_dir`` setting.
        """
        self.root_dir = root_dir or load_settings().aeat_llm_usage_dir

    def build_record(self, response: LLMResponse, prompt_id: str, caller: str) -> UsageRecord:
        """Build a :class:`UsageRecord` from a public LLM response.

        Args:
            response: Public LLM response model.
            prompt_id: Stable prompt identifier (e.g. ``"translation_v1"``).
            caller: Stable caller identifier used for cost attribution.

        Returns:
            Persistable usage record carrying the response text and accounting
            metadata.
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
        """Append a redacted ``record`` to encrypted secure-object storage.

        The record is routed through
        :func:`aeat.core.redaction.redact_structured` at DIAGNOSTIC class
        before encoding so NIFs are SHA-256 prefixed, URLs are reduced to
        host-only, and bearer-shaped tokens are fingerprinted. Storage-layer
        imports are deferred to the method body so that CLI commands which
        never touch the recorder do not pull Alembic plugin discovery into
        their import graph.

        Args:
            record: Usage record to append.

        Returns:
            Logical daily usage path for operator display only.

        Raises:
            LLMCacheError: When the storage write fails.
        """
        from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
        from ....core.classification import SensitivityClass
        from ....core.redaction import default_rules_for_class, redact_structured

        path = self.root_dir / f"usage-{record.created_at.date().isoformat()}.jsonl"
        redacted = redact_structured(
            record.model_dump(mode="json"),
            rules=default_rules_for_class(SensitivityClass.DIAGNOSTIC),
        )
        payload = {
            "logical_root": self._logical_root(),
            "record": redacted,
        }
        try:
            secure_object_repository_for_active_bucket().save(
                namespace=_USAGE_NAMESPACE,
                object_key=self._object_key_for(record),
                classification=SensitivityClass.DIAGNOSTIC,
                schema_version=_USAGE_VERSION,
                written_at=record.created_at,
                payload=canonical_json_bytes(payload),
            )
        except OSError as exc:
            msg = "Failed to append LLM usage record."
            raise LLMCacheError(msg) from exc
        return path

    def load_records(self, since: date | None = None, until: date | None = None) -> tuple[UsageRecord, ...]:
        """Load usage records, optionally filtered by an inclusive date range.

        Args:
            since: Inclusive lower date bound, or ``None`` for no lower bound.
            until: Inclusive upper date bound, or ``None`` for no upper bound.

        Returns:
            Loaded :class:`UsageRecord` entries in file-iteration order.
        """
        from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
        from ....core.classification import SensitivityClass

        records: list[UsageRecord] = []
        for stored in secure_object_repository_for_active_bucket().list_records(
            _USAGE_NAMESPACE,
            expected_class=SensitivityClass.DIAGNOSTIC,
            max_supported_version=_USAGE_VERSION,
        ):
            decoded = json.loads(stored.payload.decode("utf-8"))
            if decoded.get("logical_root") != self._logical_root():
                continue
            record = UsageRecord.model_validate_json(json.dumps(decoded["record"]))
            record_date = record.created_at.date()
            if since is not None and record_date < since:
                continue
            if until is not None and record_date > until:
                continue
            records.append(record)
        return tuple(sorted(records, key=lambda item: (item.created_at, item.request_id, item.prompt_id, item.caller)))

    def summarize(self, since: date | None = None, until: date | None = None) -> UsageSummary:
        """Aggregate usage records into a :class:`UsageSummary`.

        Args:
            since: Inclusive lower date bound, or ``None`` for no lower bound.
            until: Inclusive upper date bound, or ``None`` for no upper bound.

        Returns:
            Aggregate usage summary covering entries, total tokens, and
            estimated cost.
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

    def _logical_root(self) -> str:
        """Return the stable logical usage partition."""
        return self.root_dir.resolve().as_posix()

    def _object_key_for(self, record: UsageRecord) -> str:
        """Return a unique natural key for one usage record append."""
        return "|".join(
            (
                self._logical_root(),
                record.created_at.isoformat(),
                record.request_id,
                uuid4().hex,
            ),
        )
