"""Encrypted usage recorder for LLM calls.

Persists :class:`llm.UsageRecord` payloads under
:data:`adapters.persistence.storage.LLM_USAGE_NAMESPACE` in the encrypted
SQL secure-object backend and exposes load and aggregate helpers. Records are
routed through :func:`core.redaction.redact_structured` at
:class:`core.classification.SensitivityClass` ``DIAGNOSTIC`` before they
are encrypted, so NIFs and bearer-shaped tokens are redacted before
persistence.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from ....adapters.persistence.storage import LLM_USAGE_NAMESPACE, secure_object_repository_for_active_bucket
from ....adapters.persistence.storage.crypto.encrypted_columns import secure_object_key_digest
from ....core.classification import SensitivityClass
from ....core.config import load_settings
from ....core.hashing import canonical_json_bytes
from ....core.redaction import default_rules_for_class, redact_structured
from ....core.time import now
from ....llm import LLMCacheError, LLMResponse, UsageRecord, UsageSummary, select_retention_removal_keys

_USAGE_NAMESPACE = LLM_USAGE_NAMESPACE.namespace
_USAGE_VERSION = LLM_USAGE_NAMESPACE.schema_version
_USAGE_SENSITIVITY = LLM_USAGE_NAMESPACE.sensitivity


class UsageRecorder:
    """Append LLM usage records to encrypted secure objects.

    Each call to :meth:`record` stores one redacted
    :class:`llm.UsageRecord` through
    :func:`adapters.persistence.storage.secure_object_repository_for_active_bucket`
    under the recorder's logical root.

    Attributes:
        root_dir: Logical partition used for usage records.
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        """Initialize the recorder.

        Args:
            root_dir: Logical usage partition; defaults to the centralized
                ``cadrumo_llm_usage_dir`` setting.
        """
        self.root_dir = root_dir or load_settings().cadrumo_llm_usage_dir

    def build_record(self, response: LLMResponse, prompt_id: str, caller: str) -> UsageRecord:
        """Build a :class:`llm.UsageRecord` from a response.

        Args:
            response: Public :class:`llm.LLMResponse`
                model.
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
        :func:`core.redaction.redact_structured` at
        :class:`core.classification.SensitivityClass` ``DIAGNOSTIC``
        class before encoding so NIFs are SHA-256 prefixed, URLs are reduced
        to host-only, and bearer-shaped tokens are fingerprinted.

        Args:
            record: Usage record to append.

        Returns:
            Logical daily usage path for operator display only.

        Raises:
            :exc:`llm.LLMCacheError`: When the storage
            write fails.
        """
        path = self.root_dir / f"usage-{record.created_at.date().isoformat()}.jsonl"
        redacted = redact_structured(
            record.model_dump(mode="json"),
            rules=default_rules_for_class(SensitivityClass.DIAGNOSTIC),
        )
        # The uuid4 suffix is minted once here and persisted inside the payload
        # (rather than only folded into the object key) so ``prune`` can
        # reconstruct the exact save-time key from a listed record and issue a
        # matching ``delete`` -- there is no parallel index to keep in sync.
        object_key_uuid = uuid4().hex
        payload = {
            "logical_root": self._logical_root(),
            "object_key_uuid": object_key_uuid,
            "record": redacted,
        }
        try:
            secure_object_repository_for_active_bucket().save(
                namespace=_USAGE_NAMESPACE,
                object_key=self._object_key_for(record, object_key_uuid),
                classification=_USAGE_SENSITIVITY,
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
            Loaded :class:`llm.UsageRecord` entries in
            file-iteration order.
        """
        records: list[UsageRecord] = []
        for stored in secure_object_repository_for_active_bucket().list_records(
            _USAGE_NAMESPACE,
            expected_class=_USAGE_SENSITIVITY,
            max_supported_version=_USAGE_VERSION,
        ):
            decoded = self._decode_record_payload(stored.payload, stored.object_key)
            if decoded is None:
                continue
            record, _ = decoded
            record_date = record.created_at.date()
            if since is not None and record_date < since:
                continue
            if until is not None and record_date > until:
                continue
            records.append(record)
        return tuple(sorted(records, key=lambda item: (item.created_at, item.request_id, item.prompt_id, item.caller)))

    def _load_records_with_object_keys(self) -> tuple[tuple[UsageRecord, str], ...]:
        """Load usage records paired with their reconstructed save-time object key.

        Used only by :meth:`prune`. Payload validation is shared with
        :meth:`load_records`, so every read path rejects a record that does not
        carry the canonical save-time ``object_key_uuid``.
        """
        rows: list[tuple[UsageRecord, str]] = []
        for stored in secure_object_repository_for_active_bucket().list_records(
            _USAGE_NAMESPACE,
            expected_class=_USAGE_SENSITIVITY,
            max_supported_version=_USAGE_VERSION,
        ):
            decoded = self._decode_record_payload(stored.payload, stored.object_key)
            if decoded is None:
                continue
            record, object_key_uuid = decoded
            rows.append((record, self._object_key_for(record, object_key_uuid)))
        return tuple(
            sorted(rows, key=lambda item: (item[0].created_at, item[0].request_id, item[0].prompt_id, item[0].caller)),
        )

    def prune(self, *, retention_days: int | None = None, max_records: int | None = None) -> int:
        """Delete usage records older than the retention window or beyond the count cap.

        Applies the same two-stage bound as
        :meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.prune`: first every
        record older than ``retention_days`` (measured against the current time)
        is removed, then -- if more than ``max_records`` remain -- the oldest
        excess records beyond the cap are removed too. Both bounds default to the
        centralized ``cadrumo_llm_usage_retention_days`` and
        ``cadrumo_llm_usage_max_records`` settings.

        Like every usage-record read path, ``prune`` hard-refuses (raises
        ``LLMCacheError``) when a record lacks its ``object_key_uuid``. Every
        current writer emits that field, so absence is storage corruption.
        """
        settings = load_settings()
        effective_retention_days = (
            retention_days if retention_days is not None else settings.cadrumo_llm_usage_retention_days
        )
        effective_max_records = max_records if max_records is not None else settings.cadrumo_llm_usage_max_records

        cutoff = now() - timedelta(days=effective_retention_days)
        rows = self._load_records_with_object_keys()
        to_remove = select_retention_removal_keys(
            rows,
            cutoff=cutoff,
            max_records=effective_max_records,
            timestamp=lambda record: record.created_at,
        )

        repository = secure_object_repository_for_active_bucket()
        removed = 0
        for object_key in to_remove:
            if repository.delete(_USAGE_NAMESPACE, object_key):
                removed += 1
        return removed

    def summarize(self, since: date | None = None, until: date | None = None) -> UsageSummary:
        """Aggregate usage records into a :class:`llm.UsageSummary`.

        Args:
            since: Inclusive lower date bound, or ``None`` for no lower bound.
            until: Inclusive upper date bound, or ``None`` for no upper bound.

        Returns:
            Aggregate usage summary covering entries, total tokens, and
            estimated cost.
        """
        records = self.load_records(since=since, until=until)
        # An unpriced record poisons the total rather than being skipped. Summing
        # only the priced rows would return a smaller number that still reads as
        # the bill, which is the reported defect moved one layer up: the caller
        # cannot see that anything was left out. The count travels beside it so
        # the absence is attributable rather than merely total.
        unpriced = sum(1 for record in records if record.cost_estimate_usd is None)
        total_cost = (
            None
            if unpriced
            else sum((record.cost_estimate_usd or Decimal("0") for record in records), start=Decimal("0"))
        )
        return UsageSummary(
            entries=len(records),
            total_input_tokens=sum(record.input_tokens for record in records),
            total_output_tokens=sum(record.output_tokens for record in records),
            total_cost_estimate_usd=total_cost,
            unpriced_entries=unpriced,
            since=since,
            until=until,
        )

    def _logical_root(self) -> str:
        """Return the stable logical usage partition."""
        return self.root_dir.resolve().as_posix()

    def _decode_record_payload(self, payload: bytes, stored_key: bytes) -> tuple[UsageRecord, str] | None:
        """Decode one canonical usage payload for every read path.

        The reconstructed save-time key is compared against the digest of the
        row it was actually read from. The key was already being rebuilt here —
        from the record's own fields plus the persisted UUID — but never
        checked against the row holding it, so a valid record substituted under
        another row's key was returned as that row AND made pruning miss: the
        prune issued a delete for the key it reconstructed from the foreign
        payload, so the stored row survived every retention pass and the record
        the operator saw was not the record on disk.

        Returns ``None`` when the record belongs to another logical root.

        Raises:
            LLMCacheError: When a matching record lacks the save-time UUID
                emitted by every current writer, or when its reconstructed key
                does not derive the row it is stored in.
        """
        decoded = json.loads(payload.decode("utf-8"))
        if decoded.get("logical_root") != self._logical_root():
            return None
        object_key_uuid = decoded.get("object_key_uuid")
        if not isinstance(object_key_uuid, str) or not object_key_uuid:
            raise LLMCacheError(
                "LLM usage payload is missing its object_key_uuid; cannot validate its canonical save-time key.",
            )
        record = UsageRecord.model_validate_json(json.dumps(decoded["record"]))
        reconstructed = self._object_key_for(record, object_key_uuid)
        if secure_object_key_digest(reconstructed) != stored_key:
            raise LLMCacheError(
                "LLM usage record does not derive the row it is stored in; "
                f"decrypted payload reconstructs the key {reconstructed!r}.",
            )
        return record, object_key_uuid

    def _object_key_for(self, record: UsageRecord, object_key_uuid: str) -> str:
        """Return the unique natural key one usage record append was saved under.

        The random ``object_key_uuid`` minted at save time is persisted inside
        the record's payload, so the exact save-time key can be reconstructed
        later for pruning.
        """
        return "|".join(
            (
                self._logical_root(),
                record.created_at.isoformat(),
                record.request_id,
                object_key_uuid,
            ),
        )
