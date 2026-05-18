"""Unit tests for the encrypted LLM cache.

Covers cache key determinism, hit/miss accounting, statistics, and the
defensive containment checks in :class:`aeat.adapters.outbound.llm.LLMCache`
that prevent operator-supplied model identifiers from composing unsafe logical
cache paths.
"""

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


def test_cache_key_distinguishes_request_axes(tmp_path: Path) -> None:
    """The cache key must vary across every dimension that should miss the cache."""

    cache = LLMCache(root_dir=tmp_path)
    base = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    base_key = cache.build_key(base, LLMProvider.ANTHROPIC, "claude-sonnet-4-6")

    different_prompt = cache.build_key(
        LLMRequest(prompt="World", temperature=0.0, language="es"),
        LLMProvider.ANTHROPIC,
        "claude-sonnet-4-6",
    )
    different_temperature = cache.build_key(
        LLMRequest(prompt="Hello", temperature=0.7, language="es"),
        LLMProvider.ANTHROPIC,
        "claude-sonnet-4-6",
    )
    different_language = cache.build_key(
        LLMRequest(prompt="Hello", temperature=0.0, language="en"),
        LLMProvider.ANTHROPIC,
        "claude-sonnet-4-6",
    )
    different_model = cache.build_key(base, LLMProvider.ANTHROPIC, "claude-haiku-4-5")

    assert len({base_key, different_prompt, different_temperature, different_language, different_model}) == 5


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
    assert not any(tmp_path.rglob("*.json"))


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


def test_cache_payload_canary_is_encrypted_in_database(tmp_path: Path) -> None:
    cache = LLMCache(root_dir=tmp_path / "cache")
    request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    response = _response().model_copy(update={"text": "CACHE-CANARY-123"})

    cache.write(request, response)

    assert not (tmp_path / "cache").exists()
    assert b"CACHE-CANARY-123" not in (tmp_path / "aeat.db").read_bytes()
