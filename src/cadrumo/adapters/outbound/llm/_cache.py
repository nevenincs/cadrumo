"""Encrypted content-addressed cache for LLM responses.

Each :class:`~llm.CachedEntry` is stored under
:data:`~adapters.persistence.storage.LLM_CACHE_NAMESPACE` as an encrypted
secure object with :class:`~core.classification.SensitivityClass`
``DIAGNOSTIC`` classification so operator-identifying inputs are redacted
before persistence.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ....core.classification.policies import SensitivityClass
from ....core.config import load_settings
from ....core.hashing import canonical_json_bytes, content_hash_hex, sha256_hex
from ....core.logging import get_logger
from ....core.redaction.rules import default_rules_for_class, redact_structured
from ....core.time.clock import now
from ....llm.errors import LLMCacheError
from ....llm.models import CachedEntry, CacheKey, CacheStats, LLMProvider, LLMRequest, LLMResponse
from ....llm.retention import select_retention_removal_keys
from ...persistence.storage._secure_object_namespaces import LLM_CACHE_NAMESPACE
from ...persistence.storage.runtime_repository import secure_object_repository_for_active_bucket

if TYPE_CHECKING:
    from ...persistence.storage.sql import SecureObjectRepository

_log = get_logger(__name__)

_CACHE_NAMESPACE = LLM_CACHE_NAMESPACE.namespace
_CACHE_VERSION = LLM_CACHE_NAMESPACE.schema_version
_CACHE_SENSITIVITY = LLM_CACHE_NAMESPACE.sensitivity


class LLMCache:
    """Persist LLM responses through encrypted secure objects.

    The cache derives :class:`~llm.CacheKey` values from
    :class:`~llm.LLMRequest` content and persists
    :class:`~llm.LLMResponse` payloads through
    :func:`~adapters.persistence.storage.secure_object_repository_for_active_bucket`.

    Args:
        root_dir: Optional logical cache partition override.
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or load_settings().cadrumo_llm_cache_dir

    def build_key(self, request: LLMRequest, provider: LLMProvider, model: str) -> CacheKey:
        """Derive a :class:`~llm.CacheKey` from the request.

        Args:
            request: Structured :class:`~llm.LLMRequest`.
            provider: Effective :class:`~llm.LLMProvider`.
            model: Effective model for the request.

        Returns:
            Deterministic :class:`~llm.CacheKey`
            components.
        """
        prompt_material = "\n".join([request.system or "", request.prompt])
        args_payload = {
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "language": request.language,
            "cache_key": request.cache_key,
            "model_override": request.model_override,
            # Fold each multimodal evidence input's content address (Attachment
            # SHA-256) into the key so two distinct evidence documents under an
            # identical prompt never collide on one cache entry. Only the content
            # address enters the key -- never the base64 bytes
            # (sensitive-financial-data-secure-storage-only).
            "image_content_addresses": [image.content_sha256 for image in request.images],
        }
        prompt_hash = sha256_hex(prompt_material.encode("utf-8"))
        args_hash = content_hash_hex(args_payload)
        return CacheKey(provider=provider, model=model, prompt_hash=prompt_hash, args_hash=args_hash)

    def read(self, request: LLMRequest, provider: LLMProvider, model: str) -> LLMResponse | None:
        """Read a cached response, if present.

        Args:
            request: Structured :class:`~llm.LLMRequest`.
            provider: Effective :class:`~llm.LLMProvider`.
            model: Effective model for the request.

        The decoded entry is bound back to the key that was asked for before
        it is returned. The object key is derived from the request, but until
        that check existed nothing tied the DECRYPTED payload's own
        provider / model / prompt hash / args hash to it: a valid entry
        re-encrypted under another entry's row was returned verbatim, so a
        caller asking one provider-and-model could be answered by another's
        text with ``cache_hit`` set. Successful decryption proves custody of
        the bucket key, never that the row holds what was requested.

        Returns:
            Cached :class:`~llm.LLMResponse` when
            present, otherwise ``None``.

        Raises:
            :exc:`~llm.LLMCacheError`: When the cached
            payload is present but cannot be parsed, or when it decodes to
            an entry belonging to a different cache key.
        """
        key = self.build_key(request, provider, model)
        requested_object_key = self._object_key_for(key)
        record = secure_object_repository_for_active_bucket().load(
            _CACHE_NAMESPACE,
            requested_object_key,
            expected_class=_CACHE_SENSITIVITY,
            max_supported_version=_CACHE_VERSION,
        )
        if record is None:
            _log.debug("llm_cache miss: provider=%s model=%s", provider.value, model)
            return None
        try:
            entry = self._entry_from_payload(record.payload)
        except (ValueError, ValidationError, KeyError, TypeError) as exc:
            msg = f"Failed to parse LLM cache entry for {provider.value}/{model}"
            raise LLMCacheError(msg) from exc
        self._assert_entry_bound_to_key(entry, requested_object_key)
        _log.debug("llm_cache hit: provider=%s model=%s", provider.value, model)
        return entry.response.model_copy(
            update={
                "cache_hit": True,
                # A cache hit costs nothing to serve, so a PRICED response
                # becomes free. An UNPRICED one stays unpriced: multiplying by
                # zero would turn "we cannot price this model" into "this was
                # free", which is the confusion this field exists to prevent --
                # and it would raise on None besides.
                "cost_estimate_usd": None if entry.response.cost_estimate_usd is None else Decimal("0"),
            },
        )

    def write(self, request: LLMRequest, response: LLMResponse) -> CachedEntry:
        """Write a response to the cache and return the stored entry.

        The serialised payload is routed through the substrate's
        :func:`~core.redaction.redact_structured` helper at
        :class:`~core.classification.SensitivityClass` ``DIAGNOSTIC``
        class before persistence (the CACHE-class default policy has an empty
        rule set because most caches are public reference data; the LLM cache
        carries identity-bearing inputs and therefore adopts the DIAGNOSTIC
        rule set, mirroring the run-trace sink's discipline). The redacted
        payload is stored as an encrypted SQL secure object rather than a
        materialized JSON file. The redaction is idempotent — re-reads of an
        already-redacted entry stay correct because the cache carries the
        redacted text only.

        Args:
            request: Structured :class:`~llm.LLMRequest`.
            response: Public :class:`~llm.LLMResponse`
                to persist.

        Returns:
            Persisted :class:`~llm.CachedEntry` model.

        Raises:
            :exc:`~llm.LLMCacheError`: When redaction
            produces a non-dict result or the storage write fails with an
            OS-level error.
        """
        key = self.build_key(request, response.provider, response.model)
        entry = CachedEntry(
            provider=response.provider,
            model=response.model,
            prompt_hash=key.prompt_hash,
            args_hash=key.args_hash,
            response=response,
            created_at=now(),
        )
        redacted = redact_structured(
            entry.model_dump(mode="json"),
            rules=default_rules_for_class(SensitivityClass.DIAGNOSTIC),
        )
        if not isinstance(redacted, dict):
            raise LLMCacheError("redacted LLM cache entry must be a JSON object")
        # ``redact_structured`` returns ``object``; the isinstance
        # narrow above promotes the value to a dict with JSON-shape
        # contents. Re-key as ``str`` so the typed boundary holds
        # without an Any leak; ``_payload_for_entry`` treats the
        # mapping opaquely (only ever serialises to JSON).
        redacted_entry: Mapping[str, object] = {str(k): v for k, v in redacted.items()}
        payload = self._payload_for_entry(redacted_entry)
        object_key = self._object_key_for(key)
        # Bind what is about to be STORED, not the in-memory entry: the entry
        # is built from ``key`` and so agrees with it by construction, while
        # the payload has been through redaction. A redaction rule that ever
        # touched a key-bearing field would file a row nothing could read
        # back, and the failure would surface as a permanent cache miss rather
        # than as the write fault it is.
        self._assert_entry_bound_to_key(self._entry_from_payload(payload), object_key)
        try:
            secure_object_repository_for_active_bucket().save(
                namespace=_CACHE_NAMESPACE,
                object_key=object_key,
                classification=_CACHE_SENSITIVITY,
                schema_version=_CACHE_VERSION,
                written_at=now(),
                payload=payload,
            )
        except OSError as exc:
            msg = f"Failed to write LLM cache entry for {response.provider.value}/{response.model}"
            raise LLMCacheError(msg) from exc
        return entry

    def stats(self) -> CacheStats:
        """Return encrypted cache counts as a :class:`~llm.CacheStats`.

        Returns:
            :class:`~llm.CacheStats` with aggregate
            entry count and total decrypted JSON byte size for this logical
            cache partition.
        """
        records = tuple(
            record
            for record in secure_object_repository_for_active_bucket().list_records(
                _CACHE_NAMESPACE,
                expected_class=_CACHE_SENSITIVITY,
                max_supported_version=_CACHE_VERSION,
            )
            if self._payload_root_matches(record.payload)
        )
        return CacheStats(entries=len(records), total_bytes=sum(len(record.payload) for record in records))

    def prune(self, *, retention_days: int | None = None, max_records: int | None = None) -> int:
        """Delete cached entries older than the retention window or beyond the count cap.

        Two-stage bound mirroring
        :meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.prune`: entries
        older than ``retention_days`` (measured against the current time) are
        removed, then -- if more than ``max_records`` remain -- the oldest excess
        entries beyond the cap are removed too. Both bounds default to the
        centralized ``cadrumo_llm_cache_retention_days`` /
        ``cadrumo_llm_cache_max_records`` settings, giving the response cache a
        declared retention lifecycle instead of unbounded growth.

        Returns:
            Number of removed cache objects.

        Raises:
            :exc:`~llm.LLMCacheError`: When a cache
            entry cannot be parsed during iteration.
        """
        settings = load_settings()
        effective_retention_days = (
            retention_days if retention_days is not None else settings.cadrumo_llm_cache_retention_days
        )
        effective_max_records = max_records if max_records is not None else settings.cadrumo_llm_cache_max_records

        repository = secure_object_repository_for_active_bucket()
        rows = self._collect_prunable_rows(repository)
        cutoff = now() - timedelta(days=effective_retention_days)
        to_remove = select_retention_removal_keys(
            rows,
            cutoff=cutoff,
            max_records=effective_max_records,
            timestamp=lambda entry: entry.created_at,
        )

        removed = 0
        for object_key in to_remove:
            if repository.delete(_CACHE_NAMESPACE, object_key):
                removed += 1
        return removed

    def _collect_prunable_rows(self, repository: SecureObjectRepository) -> list[tuple[CachedEntry, str]]:
        """Load and parse every root-matching cache entry, sorted oldest-first.

        The rows are read straight off the active bucket's
        :class:`SecureObjectRepository`, so retention pruning sees exactly the
        encrypted records the cache wrote.

        Raises:
            :exc:`~llm.LLMCacheError`: When a cache
            entry cannot be parsed during iteration.
        """
        rows: list[tuple[CachedEntry, str]] = []
        for record in repository.list_records(
            _CACHE_NAMESPACE,
            expected_class=_CACHE_SENSITIVITY,
            max_supported_version=_CACHE_VERSION,
        ):
            if not self._payload_root_matches(record.payload):
                continue
            try:
                entry = self._entry_from_payload(record.payload)
            except (ValueError, ValidationError, KeyError, TypeError) as exc:
                msg = "Failed to parse LLM cache entry while pruning"
                raise LLMCacheError(msg) from exc
            rows.append((entry, self._object_key_for(self._key_of(entry))))
        rows.sort(key=lambda item: item[0].created_at)
        return rows

    def _path_for(self, key: CacheKey) -> Path:
        """Return the logical cache path for a derived key.

        Args:
            key: Derived cache key.

        Returns:
            Logical path for displaying the cache entry location. The cache
            itself is persisted in encrypted SQL secure objects.
        """
        # Sanitise the operator-controllable model string before path
        # composition. ``model_override`` flows through provider
        # configuration / env vars, so a malicious or accidentally-
        # malformed value (``../../etc/passwd``, ``..\\foo``,
        # ``C:\\bar``) must not let the cache write outside
        # ``root_dir``. Forward slashes are normalised to ``__`` (a
        # legitimate convention for namespaced model names like
        # ``anthropic/claude-3-7-sonnet``); every other suspicious
        # token is rejected.
        sanitised_model = self._sanitise_model_for_path(key.model)
        return self.root_dir / key.provider.value.lower() / sanitised_model / f"{key.prompt_hash}-{key.args_hash}.json"

    @staticmethod
    def _key_of(entry: CachedEntry) -> CacheKey:
        """Reconstruct the cache key a stored entry claims to be filed under.

        One reconstruction, so the read-side binding check and the prune-side
        row keying cannot disagree about which row an entry belongs to.
        """
        return CacheKey(
            provider=entry.provider,
            model=entry.model,
            prompt_hash=entry.prompt_hash,
            args_hash=entry.args_hash,
        )

    def _assert_entry_bound_to_key(self, entry: CachedEntry, object_key: str) -> None:
        """Refuse an entry whose own identity does not derive the row it sat in.

        The comparison is made on the derived OBJECT KEY rather than field by
        field, so it is exactly the mapping the writer used — including the
        injective model-identity encoding. Distinct accepted model identifiers
        therefore cannot alias one secure-object row before this binding check.

        Raises:
            :exc:`~llm.LLMCacheError`: On any divergence.
        """
        stored_object_key = self._object_key_for(self._key_of(entry))
        if stored_object_key != object_key:
            msg = (
                "LLM cache entry does not belong to the requested key: "
                f"row {object_key!r} decoded to an entry filed under {stored_object_key!r}"
            )
            raise LLMCacheError(msg)

    def _object_key_for(self, key: CacheKey) -> str:
        """Return the natural secure-object key for a cache key."""
        encoded_model = self._encode_model_for_object_key(key.model)
        return "|".join(
            (
                self._logical_root(),
                key.provider.value,
                encoded_model,
                key.prompt_hash,
                key.args_hash,
            ),
        )

    @classmethod
    def _encode_model_for_object_key(cls, model: str) -> str:
        """Encode one accepted model identity injectively for secure storage.

        The filesystem display path deliberately keeps its compact, lossy
        normalisation (for example ``qwen:3b`` becomes ``qwen_3b``). Secure
        object identity cannot use that representation: an underscore-bearing
        model would alias the tagged model. Validate through the existing path
        safety boundary, then hex-encode the original UTF-8 bytes. Hex is
        reversible and contains neither the object-key delimiter nor path
        separators, so every accepted model string has one distinct safe token.
        """
        cls._sanitise_model_for_path(model)
        return model.encode("utf-8").hex()

    def _logical_root(self) -> str:
        """Return the stable logical cache partition."""
        return self.root_dir.resolve().as_posix()

    def _payload_for_entry(self, entry: Mapping[str, object]) -> bytes:
        """Wrap a redacted entry with its logical partition before encryption.

        Serialised through :func:`~core.hashing.canonical_json_bytes`, the same
        helper the sibling usage and run-telemetry stores write their payloads
        with, so all three diagnostic stores in this package produce one byte
        shape. ``entry`` reaches here as ``model_dump(mode="json")`` output that
        has been through redaction, so it is JSON-native and the helper's
        refusal of anything else is a guard rather than a constraint.
        """
        payload = {
            "logical_root": self._logical_root(),
            "entry": entry,
        }
        return canonical_json_bytes(payload)

    def _entry_from_payload(self, payload: bytes) -> CachedEntry:
        """Decode a secure-object payload into a cached entry."""
        # secure-object payload is opaque bytes from SQLAlchemy; downstream
        # re-serialisation guards type at storage boundary.
        decoded = json.loads(payload.decode("utf-8"))  # JSON-LOADS-RATIONALE-LLM-CACHE-SECURE-OBJECT
        if decoded.get("logical_root") != self._logical_root():
            raise LLMCacheError("LLM cache payload belongs to a different logical partition")
        return CachedEntry.model_validate_json(json.dumps(decoded["entry"]))

    def _payload_root_matches(self, payload: bytes) -> bool:
        """Return whether ``payload`` belongs to this cache partition."""
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (ValueError, TypeError):
            _log.debug("ignoring malformed LLM cache payload while filtering logical root", exc_info=True)
            return False
        if not isinstance(decoded, dict):
            return False
        logical_root = decoded.get("logical_root")
        return isinstance(logical_root, str) and logical_root == self._logical_root()

    @staticmethod
    def _sanitise_model_for_path(model: str) -> str:
        """Normalise a model identifier into a single safe path segment.

        Forward slashes (used for vendor-prefixed names like
        ``anthropic/claude-3-7-sonnet``) are replaced with ``__`` so
        the model becomes a single directory segment under the
        provider directory. A colon (the Ollama ``name:tag`` separator,
        e.g. ``qwen2.5vl:3b``) is normalised to ``_`` so the tag is
        carried into a safe single segment rather than rejected. Every
        other path-shaped or unsafe value raises.

        Path-traversal and drive-letter shapes stay rejected: a Windows
        drive path carries a backslash and is refused by the backslash
        check before any colon is considered, and the sanitised colon
        is a literal token inside one path segment joined under
        ``root_dir`` — it can never re-introduce a drive prefix or an
        alternate-data-stream separator.
        """
        if not model:
            raise LLMCacheError("LLM cache: model identifier must be non-empty")
        if "\x00" in model:
            raise LLMCacheError("LLM cache: model identifier contains a NUL byte")
        if "\\" in model:
            raise LLMCacheError(
                f"LLM cache: model identifier must not contain backslashes: {model!r}",
            )
        # Split and normalise on forward slashes so each segment is
        # validated against path-traversal tokens individually.
        segments = model.split("/")
        sanitised_segments: list[str] = []
        for segment in segments:
            if not segment:
                raise LLMCacheError(
                    f"LLM cache: model identifier contains an empty segment: {model!r}",
                )
            if segment in {".", ".."}:
                raise LLMCacheError(
                    f"LLM cache: model identifier contains a relative-path token: {model!r}",
                )
            if segment.startswith("."):
                raise LLMCacheError(
                    f"LLM cache: model identifier segment must not start with '.': {model!r}",
                )
            # Normalise the Ollama ``name:tag`` separator into a safe
            # single-character token. The backslash rejection above has
            # already refused Windows drive paths (``C:\\foo``), so a
            # residual colon here is a legitimate tag separator, not a
            # drive letter; folding it to ``_`` keeps the segment a
            # literal, traversal-free path token.
            sanitised_segments.append(segment.replace(":", "_"))
        return "__".join(sanitised_segments)
