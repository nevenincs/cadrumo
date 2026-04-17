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

        Args:
            request: Structured completion request.
            response: Public response to persist.

        Returns:
            Persisted cache entry model.
        """

        key = self.build_key(request, response.provider, response.model)
        entry = CachedEntry(
            provider=response.provider,
            model=response.model,
            prompt_hash=key.prompt_hash,
            args_hash=key.args_hash,
            response=response,
            created_at=datetime.now(UTC),
        )
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")
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
        """

        return (
            self.root_dir
            / key.provider.value.lower()
            / key.model.replace("/", "__")
            / f"{key.prompt_hash}-{key.args_hash}.json"
        )
