"""Encrypted content-addressed cache for LLM responses.

Each cache entry is stored as an encrypted secure object under
:class:`SensitivityClass` DIAGNOSTIC so operator-identifying inputs are
redacted before persistence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from ....adapters.persistence.storage import LLM_CACHE_NAMESPACE
from ....core.config import load_settings
from ....core.hashing import sha256_hex
from ....core.logging import get_logger
from ....core.time import now
from ._errors import LLMCacheError
from ._models import (
    CachedEntry,
    CacheKey,
    CacheStats,
    LLMProvider,
    LLMRequest,
    LLMResponse,
)

_log = get_logger(__name__)

_CACHE_NAMESPACE = LLM_CACHE_NAMESPACE.namespace
_CACHE_VERSION = 1


class LLMCache:
    """Persist LLM responses through encrypted secure objects.

    Args:
        root_dir: Optional logical cache partition override.
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or load_settings().aeat_llm_cache_dir

    def build_key(self, request: LLMRequest, provider: LLMProvider, model: str) -> CacheKey:
        """Derive a :class:`CacheKey` from the content-addressed request.

        Args:
            request: Structured completion request.
            provider: Effective provider for the request.
            model: Effective model for the request.

        Returns:
            Deterministic :class:`CacheKey` components.
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
        args_hash = hashlib.sha256(
            json.dumps(args_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        ).hexdigest()
        return CacheKey(provider=provider, model=model, prompt_hash=prompt_hash, args_hash=args_hash)

    def read(self, request: LLMRequest, provider: LLMProvider, model: str) -> LLMResponse | None:
        """Read a cached response, if present.

        Args:
            request: Structured completion request.
            provider: Effective provider for the request.
            model: Effective model for the request.

        Returns:
            Cached :class:`LLMResponse` when present, otherwise ``None``.

        Raises:
            LLMCacheError: When the cached payload is present but cannot be parsed.
        """
        from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
        from ....core.classification import SensitivityClass

        key = self.build_key(request, provider, model)
        record = secure_object_repository_for_active_bucket().load(
            _CACHE_NAMESPACE,
            self._object_key_for(key),
            expected_class=SensitivityClass.DIAGNOSTIC,
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
        _log.debug("llm_cache hit: provider=%s model=%s", provider.value, model)
        return entry.response.model_copy(
            update={
                "cache_hit": True,
                "cost_estimate_usd": entry.response.cost_estimate_usd * 0,
            },
        )

    def write(self, request: LLMRequest, response: LLMResponse) -> CachedEntry:
        """Write a response to the cache and return the stored entry.

        The serialised payload is routed through the substrate's
        :func:`redact_structured` helper at DIAGNOSTIC class before
        persistence (the CACHE-class default policy has an empty
        rule set because most caches are public reference data;
        the LLM cache carries identity-bearing inputs and therefore
        adopts the DIAGNOSTIC rule set, mirroring the run-trace sink's
        discipline). The redacted payload is stored as an encrypted SQL
        secure object rather than a materialized JSON file. The redaction
        is idempotent — re-reads of an already-redacted entry stay correct
        because the cache carries the redacted text only. Storage imports
        are deferred inside this method body so the LLM package's import
        chain does not pull Alembic plugin discovery into CLI commands that
        never touch the cache.

        Args:
            request: Structured completion request.
            response: Public response to persist.

        Returns:
            Persisted :class:`CachedEntry` model.

        Raises:
            LLMCacheError: When redaction produces a non-dict result or the storage
                write fails with an OS-level error.
        """
        from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
        from ....core.classification import SensitivityClass
        from ....core.redaction import default_rules_for_class, redact_structured

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
        try:
            secure_object_repository_for_active_bucket().save(
                namespace=_CACHE_NAMESPACE,
                object_key=self._object_key_for(key),
                classification=SensitivityClass.DIAGNOSTIC,
                schema_version=_CACHE_VERSION,
                written_at=now(),
                payload=payload,
            )
        except OSError as exc:
            msg = f"Failed to write LLM cache entry for {response.provider.value}/{response.model}"
            raise LLMCacheError(msg) from exc
        return entry

    def stats(self) -> CacheStats:
        """Return a :class:`CacheStats` with entry count and encrypted payload size estimate.

        Returns:
            :class:`CacheStats` with aggregate entry count and total decrypted
            JSON byte size for this logical cache partition.
        """
        from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
        from ....core.classification import SensitivityClass

        records = tuple(
            record
            for record in secure_object_repository_for_active_bucket().list_records(
                _CACHE_NAMESPACE,
                expected_class=SensitivityClass.DIAGNOSTIC,
                max_supported_version=_CACHE_VERSION,
            )
            if self._payload_root_matches(record.payload)
        )
        return CacheStats(entries=len(records), total_bytes=sum(len(record.payload) for record in records))

    def prune(self) -> int:
        """Delete every cached entry in this logical partition.

        Returns:
            Number of removed cache objects.

        Raises:
            LLMCacheError: When a cache entry cannot be parsed during iteration.
        """
        from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
        from ....core.classification import SensitivityClass

        removed = 0
        repository = secure_object_repository_for_active_bucket()
        for record in repository.list_records(
            _CACHE_NAMESPACE,
            expected_class=SensitivityClass.DIAGNOSTIC,
            max_supported_version=_CACHE_VERSION,
        ):
            if not self._payload_root_matches(record.payload):
                continue
            try:
                entry = self._entry_from_payload(record.payload)
            except (ValueError, ValidationError, KeyError, TypeError) as exc:
                msg = "Failed to parse LLM cache entry while pruning"
                raise LLMCacheError(msg) from exc
            key = CacheKey(
                provider=entry.provider,
                model=entry.model,
                prompt_hash=entry.prompt_hash,
                args_hash=entry.args_hash,
            )
            if repository.delete(_CACHE_NAMESPACE, self._object_key_for(key)):
                removed += 1
        return removed

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

    def _object_key_for(self, key: CacheKey) -> str:
        """Return the natural secure-object key for a cache key."""
        sanitised_model = self._sanitise_model_for_path(key.model)
        return "|".join(
            (
                self._logical_root(),
                key.provider.value,
                sanitised_model,
                key.prompt_hash,
                key.args_hash,
            ),
        )

    def _logical_root(self) -> str:
        """Return the stable logical cache partition."""
        return self.root_dir.resolve().as_posix()

    def _payload_for_entry(self, entry: Mapping[str, object]) -> bytes:
        """Wrap a redacted entry with its logical partition before encryption."""
        payload = {
            "logical_root": self._logical_root(),
            "entry": entry,
        }
        return json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")

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
        return decoded.get("logical_root") == self._logical_root()

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
