"""Local-only LLM run-timing telemetry recorder.

Persists one :class:`LLMRunRecord` per completed (or failed) LLM
classification/completion invocation to encrypted secure-object storage under
:data:`adapters.persistence.storage.LLM_RUN_TELEMETRY_NAMESPACE`, mirroring
:class:`~aeat.adapters.outbound.llm.UsageRecorder`'s persistence shape. Every
record is written at :class:`core.classification.SensitivityClass`
``DIAGNOSTIC`` and carries ONLY timing and outcome metadata (provider label,
duration, success flag, optional error-kind string) -- never prompt text,
response text, or any transaction/financial content, honouring
``sensitive-financial-data-secure-storage-only``. Nothing here ever leaves the
host: there is no network transport, only the same encrypted local
secure-object backend every other diagnostic store uses.

This is the durable capture half of the local-only run-diagnostics surface
(``aeat app diagnostics run-health``): a slow or failing LLM-backed
classification run is otherwise invisible until an operator notices a stuck
CLI invocation.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ....adapters.persistence.storage import LLM_RUN_TELEMETRY_NAMESPACE
from ....core.config import load_settings
from ....core.hashing import canonical_json_bytes
from ._errors import LLMCacheError

__all__ = ["LLMRunRecord", "LLMRunTelemetryRecorder", "LLMRunTelemetrySummary"]

_RUN_TELEMETRY_NAMESPACE = LLM_RUN_TELEMETRY_NAMESPACE.namespace
_RUN_TELEMETRY_VERSION = 1

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True)


class LLMRunRecord(BaseModel):
    """One local LLM run-timing record: duration, provider, and outcome only.

    Carries no prompt or response text and no transaction content -- only the
    accounting metadata needed to diagnose a slow or failing run.
    """

    model_config = _STRICT_FROZEN

    run_id: str = Field(min_length=1, description="Stable id for this run (a UUID4 hex is typical).")
    caller: str = Field(min_length=1, description="Logical caller/command that initiated the run.")
    provider: str = Field(min_length=1, description="Provider label (e.g. 'claude', 'antigravity', 'local-vision').")
    model: str = Field(default="", description="Resolved model identifier, when known.")
    duration_ms: int = Field(ge=0, description="Wall-clock run duration in milliseconds.")
    succeeded: bool = Field(description="Whether the run completed without raising.")
    error_kind: str = Field(default="", description="Exception class name when the run failed; empty on success.")
    started_at: datetime = Field(description="UTC timestamp the run started.")


class LLMRunTelemetrySummary(BaseModel):
    """Aggregated :class:`LLMRunTelemetryRecorder` statistics for one provider or overall."""

    model_config = _STRICT_FROZEN

    entries: int = Field(ge=0, description="Number of run records included.")
    succeeded: int = Field(ge=0, description="Number of runs that completed without raising.")
    failed: int = Field(ge=0, description="Number of runs that raised.")
    min_duration_ms: int | None = Field(default=None, description="Fastest recorded run duration.")
    max_duration_ms: int | None = Field(default=None, description="Slowest recorded run duration.")
    mean_duration_ms: Decimal | None = Field(default=None, description="Mean recorded run duration.")


class LLMRunTelemetryRecorder:
    """Append local LLM run-timing records to encrypted secure-object storage.

    Mirrors :class:`~aeat.adapters.outbound.llm.UsageRecorder`'s persistence
    shape: each :meth:`record` call appends one redacted-free
    :class:`LLMRunRecord` (there is no free text to redact -- the model
    carries only accounting metadata) through
    :func:`adapters.persistence.storage.secure_object_repository_for_active_bucket`.

    Attributes:
        root_dir: Logical partition used for run-telemetry records.
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        """Initialize the recorder.

        Args:
            root_dir: Logical run-telemetry partition; defaults to the
                centralized ``aeat_llm_run_telemetry_dir`` setting.
        """
        self.root_dir = root_dir or load_settings().aeat_llm_run_telemetry_dir

    def record(self, record: LLMRunRecord) -> Path:
        """Append ``record`` to encrypted secure-object storage.

        Storage-layer imports are deferred to the method body so that
        callers which never touch the recorder do not pull storage-layer
        plugin discovery into their import graph.

        Args:
            record: Run-timing record to append.

        Returns:
            Logical daily run-telemetry path for operator display only.

        Raises:
            :exc:`adapters.outbound.llm.LLMCacheError`: When the storage
            write fails.
        """
        from ....adapters.persistence.storage import secure_object_repository_for_active_bucket
        from ....core.classification import SensitivityClass

        path = self.root_dir / f"run-telemetry-{record.started_at.date().isoformat()}.jsonl"
        payload = {
            "logical_root": self._logical_root(),
            "record": record.model_dump(mode="json"),
        }
        try:
            secure_object_repository_for_active_bucket().save(
                namespace=_RUN_TELEMETRY_NAMESPACE,
                object_key=self._object_key_for(record),
                classification=SensitivityClass.DIAGNOSTIC,
                schema_version=_RUN_TELEMETRY_VERSION,
                written_at=record.started_at,
                payload=canonical_json_bytes(payload),
            )
        except OSError as exc:
            msg = "Failed to append LLM run-telemetry record."
            raise LLMCacheError(msg) from exc
        return path

    def load_records(self, since: date | None = None, until: date | None = None) -> tuple[LLMRunRecord, ...]:
        """Load run-telemetry records, optionally filtered by an inclusive date range.

        Args:
            since: Inclusive lower date bound, or ``None`` for no lower bound.
            until: Inclusive upper date bound, or ``None`` for no upper bound.

        Returns:
            Loaded :class:`LLMRunRecord` entries in file-iteration order.
        """
        from ....adapters.persistence.storage import secure_object_repository_for_active_bucket
        from ....core.classification import SensitivityClass

        records: list[LLMRunRecord] = []
        for stored in secure_object_repository_for_active_bucket().list_records(
            _RUN_TELEMETRY_NAMESPACE,
            expected_class=SensitivityClass.DIAGNOSTIC,
            max_supported_version=_RUN_TELEMETRY_VERSION,
        ):
            decoded = json.loads(stored.payload.decode("utf-8"))
            if decoded.get("logical_root") != self._logical_root():
                continue
            record = LLMRunRecord.model_validate_json(json.dumps(decoded["record"]))
            record_date = record.started_at.date()
            if since is not None and record_date < since:
                continue
            if until is not None and record_date > until:
                continue
            records.append(record)
        return tuple(sorted(records, key=lambda item: (item.started_at, item.run_id)))

    def summarize(
        self,
        since: date | None = None,
        until: date | None = None,
        *,
        provider: str | None = None,
    ) -> LLMRunTelemetrySummary:
        """Aggregate run records into a :class:`LLMRunTelemetrySummary`.

        Args:
            since: Inclusive lower date bound, or ``None`` for no lower bound.
            until: Inclusive upper date bound, or ``None`` for no upper bound.
            provider: Optional provider filter; ``None`` aggregates every provider.

        Returns:
            Aggregate run-timing summary.
        """
        records = self.load_records(since=since, until=until)
        if provider is not None:
            records = tuple(item for item in records if item.provider == provider)
        if not records:
            return LLMRunTelemetrySummary(entries=0, succeeded=0, failed=0)
        durations = [Decimal(item.duration_ms) for item in records]
        return LLMRunTelemetrySummary(
            entries=len(records),
            succeeded=sum(1 for item in records if item.succeeded),
            failed=sum(1 for item in records if not item.succeeded),
            min_duration_ms=min(item.duration_ms for item in records),
            max_duration_ms=max(item.duration_ms for item in records),
            mean_duration_ms=(sum(durations, start=Decimal("0")) / Decimal(len(durations))).quantize(Decimal("0.01")),
        )

    def _logical_root(self) -> str:
        """Return the stable logical run-telemetry partition."""
        return self.root_dir.resolve().as_posix()

    def _object_key_for(self, record: LLMRunRecord) -> str:
        """Return a unique natural key for one run-telemetry append."""
        return "|".join(
            (
                self._logical_root(),
                record.started_at.isoformat(),
                record.run_id,
                uuid4().hex,
            ),
        )
