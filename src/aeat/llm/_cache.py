"""On-disk content-addressed cache for LLM responses."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from ..config import PROJECT_ROOT
from ._errors import LLMCacheError
from ._models import (
    CachedEntry,
    CacheKey,
    CacheStats,
    LLMProvider,
    LLMRequest,
    LLMResponse,
)


class LLMCache:
    """Persist LLM responses on disk using content-addressed keys.

    Args:
        root_dir: Optional cache directory override.
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or (PROJECT_ROOT / "var" / "llm-cache")
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def build_key(self, request: LLMRequest, provider: LLMProvider, model: str) -> CacheKey:
        """Derive the content-addressed cache key for a request.

        Args:
            request: Structured completion request.
            provider: Effective provider for the request.
            model: Effective model for the request.

        Returns:
            Deterministic cache key components.
        """

        prompt_material = "\n".join([request.system or "", request.prompt])
        args_payload = {
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "language": request.language,
            "cache_key": request.cache_key,
            "model_override": request.model_override,
        }
        prompt_hash = hashlib.sha256(prompt_material.encode("utf-8")).hexdigest()
        args_hash = hashlib.sha256(
            json.dumps(args_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return CacheKey(provider=provider, model=model, prompt_hash=prompt_hash, args_hash=args_hash)

    def read(self, request: LLMRequest, provider: LLMProvider, model: str) -> LLMResponse | None:
        """Read a cached response, if present.

        Args:
            request: Structured completion request.
            provider: Effective provider for the request.
            model: Effective model for the request.

        Returns:
            Cached response when present, otherwise `None`.
        """

        path = self._path_for(self.build_key(request, provider, model))
        if not path.exists():
            return None
        try:
            entry = CachedEntry.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive filesystem path
            msg = f"Failed to parse cache entry at {path}"
            raise LLMCacheError(msg) from exc
        return entry.response.model_copy(
            update={
                "cache_hit": True,
                "cost_estimate_usd": entry.response.cost_estimate_usd * 0,
            }
        )

    def write(self, request: LLMRequest, response: LLMResponse) -> CachedEntry:
        """Write a response to the cache and return the stored entry.

        The serialised payload is routed through the substrate's
        :func:`redact_structured` helper at DIAGNOSTIC class before
        persistence (the CACHE-class default policy has an empty
        rule set because most caches are public reference data;
        the LLM cache carries identity-bearing inputs and therefore
        adopts the DIAGNOSTIC rule set, mirroring the run-trace
        sink's discipline). The redaction is idempotent — re-reads
        of an already-redacted entry stay correct because the cache
        carries the redacted text only. Storage imports are deferred
        inside this method body so the LLM package's import chain does
        not pull Alembic plugin discovery into CLI commands that never
        touch the cache.

        Args:
            request: Structured completion request.
            response: Public response to persist.

        Returns:
            Persisted cache entry model.
        """
        from ..storage import SensitivityClass, redact_structured
        from ..storage._redaction import default_rules_for_class

        key = self.build_key(request, response.provider, response.model)
        entry = CachedEntry(
            provider=response.provider,
            model=response.model,
            prompt_hash=key.prompt_hash,
            args_hash=key.args_hash,
            response=response,
            created_at=datetime.now(UTC),
        )
        redacted = redact_structured(
            entry.model_dump(mode="json"),
            rules=default_rules_for_class(SensitivityClass.DIAGNOSTIC),
        )
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(redacted, indent=2, sort_keys=True), encoding="utf-8")
        except OSError as exc:  # pragma: no cover - defensive filesystem path
            msg = f"Failed to write cache entry to {path}"
            raise LLMCacheError(msg) from exc
        return entry

    def stats(self) -> CacheStats:
        """Return cache entry count and size.

        Returns:
            Aggregate entry count and total byte size.
        """

        files = tuple(self.root_dir.rglob("*.json"))
        return CacheStats(entries=len(files), total_bytes=sum(file.stat().st_size for file in files))

    def prune(self) -> int:
        """Delete every cached entry and return the number of files removed.

        Returns:
            Number of removed cache files.
        """

        removed = 0
        for path in self.root_dir.rglob("*.json"):
            path.unlink(missing_ok=True)
            removed += 1
        return removed

    def _path_for(self, key: CacheKey) -> Path:
        """Return the cache file path for a derived key.

        Args:
            key: Derived cache key.

        Returns:
            On-disk cache path for the entry.

        Raises:
            LLMCacheError: When the model identifier contains path-
                traversal segments (``..``, leading dots), backslashes,
                drive letters, NUL bytes, or other characters that
                would compose a path outside ``root_dir``.
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
    def _sanitise_model_for_path(model: str) -> str:
        """Normalise a model identifier into a single safe path segment.

        Forward slashes (used for vendor-prefixed names like
        ``anthropic/claude-3-7-sonnet``) are replaced with ``__`` so
        the model becomes a single directory segment under the
        provider directory. Every other path-shaped or unsafe value
        raises.
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
            # Drive letters / colons are file-shape-suspicious on
            # Windows (``C:\\foo``) and POSIX-portable identifiers
            # do not need them.
            if ":" in segment:
                raise LLMCacheError(
                    f"LLM cache: model identifier must not contain ':': {model!r}",
                )
        return "__".join(segments)
