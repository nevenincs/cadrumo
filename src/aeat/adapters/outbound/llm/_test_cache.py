"""Unit tests for the on-disk cache."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from . import LLMCache, LLMProvider, LLMRequest, LLMResponse

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _response() -> LLMResponse:
    return LLMResponse(
        text="cached response",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=10,
        output_tokens=2,
        cost_estimate_usd=Decimal("0.000060"),
        cache_hit=False,
        created_at=datetime.now(UTC),
        request_id="request-id",
    )


def test_cache_key_is_deterministic(tmp_path: Path) -> None:
    """The same request should derive the same cache key every time."""

    cache = LLMCache(root_dir=tmp_path)
    request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    assert cache.build_key(request, LLMProvider.ANTHROPIC, "claude-sonnet-4-6") == cache.build_key(
        request, LLMProvider.ANTHROPIC, "claude-sonnet-4-6"
    )


def test_cache_hit_miss_and_stats(tmp_path: Path) -> None:
    """Cache should miss before write and hit after write."""

    cache = LLMCache(root_dir=tmp_path)
    request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    assert cache.read(request, LLMProvider.ANTHROPIC, "claude-sonnet-4-6") is None
    cache.write(request, _response())
    cached = cache.read(request, LLMProvider.ANTHROPIC, "claude-sonnet-4-6")
    assert cached is not None
    assert cached.cache_hit is True
    assert cached.cost_estimate_usd == Decimal("0")
    assert cache.stats().entries == 1


@pytest.mark.parametrize(
    "model",
    [
        "../escape",
        "..\\escape",
        "../../etc/passwd",
        ".hidden",
        "anthropic/../escape",
        "C:\\Windows\\System32",
        "model:with-colon",
        "model\x00with-null",
        "",
    ],
)
def test_cache_path_rejects_unsafe_model_identifiers(tmp_path: Path, model: str) -> None:
    # regression: ``key.model`` flows from the operator-
    # configured registry / env-driven ``model_override``. A path-
    # shaped value must not let the cache write outside ``root_dir``.
    from . import LLMCacheError

    cache = LLMCache(root_dir=tmp_path)
    request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    key = cache.build_key(request, LLMProvider.ANTHROPIC, model)
    with pytest.raises(LLMCacheError):
        cache._path_for(key)


def test_cache_path_normalises_namespaced_model(tmp_path: Path) -> None:
    # Forward slashes in legitimate vendor-prefixed names
    # (``anthropic/claude-3-7-sonnet``) become ``__`` so the model
    # is a single directory segment under the provider directory.
    cache = LLMCache(root_dir=tmp_path)
    request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    key = cache.build_key(request, LLMProvider.ANTHROPIC, "anthropic/claude-3-7-sonnet")
    composed = cache._path_for(key)
    assert composed.is_relative_to(tmp_path)
    assert composed.parent.name == "anthropic__claude-3-7-sonnet"
