"""Local-only LLM run-timing record recorder.

Persists one :class:`LLMRunRecord` per completed (or failed) LLM
classification/completion invocation to encrypted secure-object storage under
:data:`~adapters.persistence.storage.secure_object_namespaces.LLM_RUN_RECORD_NAMESPACE`, mirroring
:class:`~adapters.persistence.llm.usage.UsageRecorder`'s persistence shape. Every
record is written at :class:`~core.classification.policies.SensitivityClass`
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

:meth:`~LLMRunRecorder.prune` bounds this store's growth with a
retention window (:attr:`~core.config.Settings.cadrumo_llm_run_record_retention_days`)
and a maximum record count
(:attr:`~core.config.Settings.cadrumo_llm_run_record_max_records`),
mirroring :meth:`~adapters.persistence.llm.cache.LLMCache.prune`'s
list-then-delete-by-reconstructed-key shape. The object key each record was
saved under embeds a random UUID4 suffix (so two runs starting in the same
microsecond never collide); that suffix is persisted inside the record's own
payload alongside its natural fields so pruning can reconstruct the exact
save-time key and issue a matching delete, without a parallel index.

See Also:
    :class:`~adapters.persistence.llm.run_records.LLMRunRecorder`
        Public recorder that appends and reads these local-only records.
    :class:`~adapters.persistence.llm.run_records.LLMRunRecord`
        Timing/outcome-only payload stored for each completed LLM run.
    :func:`~application.diagnostics_run_health.build_run_health_report`
        Application diagnostic that aggregates these records for operators.
    :data:`~adapters.persistence.storage.secure_object_namespaces.LLM_RUN_RECORD_NAMESPACE`
        Secure-object namespace used for the encrypted local store.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import override
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ....application.diagnostics_run_health_ports import (
    DiagnosticRunRecord,
    DiagnosticRunRecordError,
    DiagnosticRunRecordPort,
)
from ....core.config import load_settings
from ....core.external_constants import UTF_8_ENCODING
from ....core.hashing import canonical_json_bytes
from ....core.time.clock import now
from ....core.time.utc import UtcInstant
from ...outbound.llm.errors import LLMCacheError
from ...outbound.llm.retention import select_retention_removal_keys
from ..storage.crypto.encrypted_columns import secure_object_key_digest
from ..storage.runtime_repository import secure_object_repository_for_active_bucket
from ..storage.secure_object_namespaces import LLM_RUN_RECORD_NAMESPACE

__all__ = [
    "LLMRunRecord",
    "LLMRunRecordDiagnosticsAdapter",
    "LLMRunRecorder",
]

_RUN_RECORD_NAMESPACE = LLM_RUN_RECORD_NAMESPACE.namespace
_RUN_RECORD_VERSION = LLM_RUN_RECORD_NAMESPACE.schema_version
_RUN_RECORD_SENSITIVITY = LLM_RUN_RECORD_NAMESPACE.sensitivity


#: Deliberately NOT the canonical ``STRICT_FROZEN_CONFIG``: the records below are
#: ``RootModel`` subclasses, and pydantic refuses ``extra`` on a root model
#: outright -- ``PydanticUserError: RootModel does not support setting
#: model_config['extra']``. The canonical config carries ``extra="forbid"``, so it
#: cannot be applied here at all. This is a constraint-shape divergence, not a
#: weaker config nobody chose.
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
    started_at: UtcInstant = Field(description="UTC timestamp the run started.")


class LLMRunRecorder:
    """Append local LLM run-timing records to encrypted secure-object storage.

    Mirrors :class:`~adapters.persistence.llm.usage.UsageRecorder`'s persistence
    shape: each :meth:`record` call appends one redacted-free
    :class:`LLMRunRecord` (there is no free text to redact -- the model
    carries only accounting metadata) through
    :func:`~adapters.persistence.storage.runtime_repository.secure_object_repository_for_active_bucket`.

    Attributes:
        root_dir: Logical partition used for run-record records.
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        """Initialize the recorder.

        Args:
            root_dir: Logical run-record partition; defaults to the
                centralized ``cadrumo_llm_run_record_dir`` setting.
        """
        self.root_dir = root_dir or load_settings().cadrumo_llm_run_record_dir

    def record(self, record: LLMRunRecord) -> Path:
        """Append ``record`` to encrypted secure-object storage.

        Args:
            record: Run-timing record to append.

        Returns:
            Logical daily run-record path for operator display only.

        Raises:
            :exc:`~llm.LLMCacheError`: When the storage
            write fails.
        """
        path = self.root_dir / f"run-record-{record.started_at.date().isoformat()}.jsonl"
        # The uuid4 suffix is minted once here and persisted inside the
        # payload (rather than only folded into the object key) so
        # ``prune`` can reconstruct the exact save-time key from a listed
        # record and issue a matching ``delete`` -- there is no parallel
        # index to keep in sync.
        object_key_uuid = uuid4().hex
        payload = {
            "logical_root": self._logical_root(),
            "object_key_uuid": object_key_uuid,
            "record": record.model_dump(mode="json"),
        }
        try:
            secure_object_repository_for_active_bucket().save(
                namespace=_RUN_RECORD_NAMESPACE,
                object_key=self._object_key_for(record, object_key_uuid),
                classification=_RUN_RECORD_SENSITIVITY,
                schema_version=_RUN_RECORD_VERSION,
                written_at=record.started_at,
                payload=canonical_json_bytes(payload),
            )
        except OSError as exc:
            msg = "Failed to append LLM run-record record."
            raise LLMCacheError(msg) from exc
        return path

    def load_records(self, since: date | None = None, until: date | None = None) -> tuple[LLMRunRecord, ...]:
        """Load run-record records, optionally filtered by an inclusive date range.

        Args:
            since: Inclusive lower date bound, or ``None`` for no lower bound.
            until: Inclusive upper date bound, or ``None`` for no upper bound.

        Returns:
            Loaded :class:`LLMRunRecord` entries in file-iteration order.
        """
        return tuple(record for record, _ in self._load_records_with_object_keys(since=since, until=until))

    def _load_records_with_object_keys(
        self,
        since: date | None = None,
        until: date | None = None,
    ) -> tuple[tuple[LLMRunRecord, str], ...]:
        """Load run-record records paired with their reconstructed save-time object key.

        Internal helper shared by :meth:`load_records` and :meth:`prune`;
        the object key is needed only for pruning and is not part of the
        public :meth:`load_records` contract.
        """
        rows: list[tuple[LLMRunRecord, str]] = []
        for stored in secure_object_repository_for_active_bucket().list_records(
            _RUN_RECORD_NAMESPACE,
            expected_class=_RUN_RECORD_SENSITIVITY,
            max_supported_version=_RUN_RECORD_VERSION,
        ):
            decoded = json.loads(stored.payload.decode(UTF_8_ENCODING))
            if decoded.get("logical_root") != self._logical_root():
                continue
            record = LLMRunRecord.model_validate_json(json.dumps(decoded["record"]))
            record_date = record.started_at.date()
            if since is not None and record_date < since:
                continue
            if until is not None and record_date > until:
                continue
            try:
                object_key_uuid = decoded["object_key_uuid"]
            except KeyError as exc:
                msg = "LLM run-record payload is missing its object_key_uuid; cannot reconstruct its save-time key."
                raise LLMCacheError(msg) from exc
            reconstructed = self._object_key_for(record, object_key_uuid)
            # The key was already being rebuilt from the record's own fields
            # plus the persisted UUID, but never checked against the row
            # holding it. A valid record substituted under another row's key
            # was therefore returned as that row AND made pruning miss: the
            # prune issues a delete for the key reconstructed from the foreign
            # payload, so the stored row survives every retention pass and the
            # record the operator reads is not the record on disk.
            if secure_object_key_digest(reconstructed) != stored.object_key:
                msg = (
                    "LLM run-record record does not derive the row it is stored in; "
                    f"decrypted payload reconstructs the key {reconstructed!r}."
                )
                raise LLMCacheError(msg)
            rows.append((record, reconstructed))
        return tuple(sorted(rows, key=lambda item: (item[0].started_at, item[0].run_id)))

    def prune(
        self,
        *,
        retention_days: int | None = None,
        max_records: int | None = None,
    ) -> int:
        """Delete records older than the retention window or beyond the count cap.

        Applies a two-stage bound, mirroring
        :meth:`~adapters.persistence.llm.cache.LLMCache.prune`'s
        list-then-delete-by-reconstructed-key shape: first every record
        older than ``retention_days`` (measured against the current time) is
        removed, then -- if more than ``max_records`` remain -- the oldest
        excess records beyond the cap are removed too. Both bounds default to
        the centralized :attr:`~core.config.Settings.cadrumo_llm_run_record_retention_days`
        and :attr:`~core.config.Settings.cadrumo_llm_run_record_max_records`
        settings.

        Args:
            retention_days: Age cutoff in days; records strictly older than
                this are removed. Defaults to the centralized setting.
            max_records: Maximum record count to retain after the age cutoff
                is applied; the oldest excess records beyond this count are
                removed. Defaults to the centralized setting.

        Returns:
            Number of removed run-record objects. A record whose key no
            longer resolves (e.g. removed by a concurrent prune) is silently
            skipped rather than counted or raised.
        """
        settings = load_settings()
        effective_retention_days = (
            retention_days if retention_days is not None else settings.cadrumo_llm_run_record_retention_days
        )
        effective_max_records = max_records if max_records is not None else settings.cadrumo_llm_run_record_max_records

        cutoff = now() - timedelta(days=effective_retention_days)
        rows = self._load_records_with_object_keys()

        # ``rows`` is sorted oldest-first (see ``_load_records_with_object_keys``),
        # which is what lets the count cap evict the oldest excess.
        to_remove = select_retention_removal_keys(
            rows,
            cutoff=cutoff,
            max_records=effective_max_records,
            timestamp=lambda record: record.started_at,
        )

        repository = secure_object_repository_for_active_bucket()
        removed = 0
        for object_key in to_remove:
            if repository.delete(_RUN_RECORD_NAMESPACE, object_key):
                removed += 1
        return removed

    def _logical_root(self) -> str:
        """Return the stable logical run-record partition."""
        return self.root_dir.resolve().as_posix()

    def _object_key_for(self, record: LLMRunRecord, object_key_uuid: str) -> str:
        """Return the unique natural key one run-record append was saved under.

        Args:
            record: The run-timing record.
            object_key_uuid: The random suffix minted at save time and
                persisted inside the record's payload, so the exact save-time
                key can be reconstructed later for pruning.
        """
        return "|".join(
            (
                self._logical_root(),
                record.started_at.isoformat(),
                record.run_id,
                object_key_uuid,
            ),
        )


class LLMRunRecordDiagnosticsAdapter(DiagnosticRunRecordPort):
    """Adapt encrypted LLM run records to the application diagnostics port."""

    def __init__(self, recorder: LLMRunRecorder) -> None:
        """Bind the recorder used to load encrypted run record."""
        self._recorder = recorder

    @override
    def load_records(
        self,
        *,
        since: date | None,
        until: date | None,
    ) -> tuple[DiagnosticRunRecord, ...]:
        """Read and translate local run record at the application boundary."""
        try:
            records = self._recorder.load_records(since=since, until=until)
            return tuple(
                DiagnosticRunRecord(
                    run_id=record.run_id,
                    caller=record.caller,
                    provider=record.provider,
                    model=record.model,
                    duration_ms=record.duration_ms,
                    succeeded=record.succeeded,
                    error_kind=record.error_kind,
                    started_at=record.started_at,
                )
                for record in records
            )
        except Exception as exc:
            raise DiagnosticRunRecordError("Unable to load diagnostic run record.") from exc
