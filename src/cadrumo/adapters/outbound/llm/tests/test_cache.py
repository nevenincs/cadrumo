"""Unit tests for the encrypted LLM cache.

Covers cache key determinism, hit/miss accounting, statistics, and the
defensive containment checks in :class:`cadrumo.adapters.outbound.llm.LLMCache`
that prevent operator-supplied model identifiers from composing unsafe logical
cache paths.

``"probe-cache"`` is a fictional directory: ``LLMCache.root_dir`` is a
constructor parameter, never a taxonomy accessor, and the test proves the
plaintext directory it names is never created regardless of what it is
called.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.directory_scan import scan_directory
from .....llm.models import LLMProvider, LLMRequest, LLMResponse
from .. import LLMCache

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CREATED_AT = datetime(2026, 5, 28, 12, 20, 0, tzinfo=UTC)


def _response() -> LLMResponse:
    return LLMResponse(
        text="cached response",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=10,
        output_tokens=2,
        cost_estimate_usd=Decimal("0.000060"),
        cache_hit=False,
        created_at=_CREATED_AT,
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

    keys = [base_key, different_prompt, different_temperature, different_language, different_model]
    # Verify all keys are distinct by comparing each pair
    assert len(keys) == len(set(k.model_dump_json() for k in keys))


def test_cache_key_distinguishes_multimodal_evidence(tmp_path: Path) -> None:
    """Two evidence documents under one prompt must yield distinct cache keys.

    The cache key folds each multimodal input's content address (the
    :class:`Attachment` SHA-256). A text-only request and two requests carrying
    evidence with different content addresses must all map to distinct keys, and
    the same content address must reproduce the same key even when the base64
    payload differs (the key folds the content address, never the bytes).
    """
    from .....core import ImageMediaType
    from .....llm.models import MultimodalImageInput

    cache = LLMCache(root_dir=tmp_path)
    sha_a = "a" * 64
    sha_b = "b" * 64
    prompt = "Read the attached invoice and report the total."

    text_only = cache.build_key(LLMRequest(prompt=prompt), LLMProvider.LOCAL, "gpt-oss")
    with_a = cache.build_key(
        LLMRequest(
            prompt=prompt,
            images=(MultimodalImageInput(content_sha256=sha_a, base64_data="QQ==", media_type=ImageMediaType.PNG),),
        ),
        LLMProvider.LOCAL,
        "gpt-oss",
    )
    with_b = cache.build_key(
        LLMRequest(
            prompt=prompt,
            images=(MultimodalImageInput(content_sha256=sha_b, base64_data="Qg==", media_type=ImageMediaType.PNG),),
        ),
        LLMProvider.LOCAL,
        "gpt-oss",
    )
    with_a_other_bytes = cache.build_key(
        LLMRequest(
            prompt=prompt,
            images=(
                MultimodalImageInput(content_sha256=sha_a, base64_data="ZGlmZmVyZW50", media_type=ImageMediaType.PNG),
            ),
        ),
        LLMProvider.LOCAL,
        "gpt-oss",
    )

    assert len({text_only.args_hash, with_a.args_hash, with_b.args_hash}) == 3
    assert with_a.args_hash == with_a_other_bytes.args_hash


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
    # The cache persists entries as encrypted secure objects (see LLMCache),
    # never a plaintext JSON file under its logical partition. The only JSON
    # under the shared tmp root is the active bucket's encrypted-DEK keystore
    # (cadrumo-storage/keystore/.../bucket.dek.json) — storage infrastructure, not
    # a cache entry — so exclude that subtree from the no-plaintext assertion.
    cache_entries = [
        p for p in scan_directory(tmp_path, pattern="*.json", recursive=True) if "cadrumo-storage" not in p.parts
    ]
    assert not cache_entries, f"cache must not materialise plaintext entries: {cache_entries}"


def test_cache_default_root_uses_central_settings(tmp_path: Path) -> None:
    """Direct cache construction must honor the centralized cache directory setting."""

    configured_root = tmp_path / "configured-cache"
    with override_settings(cadrumo_llm_cache_dir=configured_root):
        cache = LLMCache()

    request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    response = _response()
    cache.write(request, response)
    cached = cache.read(request, response.provider, response.model)

    assert cache.root_dir == configured_root
    assert cached is not None
    assert cached.cache_hit is True
    assert not configured_root.exists()


def test_cache_path_rejects_unsafe_model_identifiers(tmp_path: Path) -> None:
    # regression: ``key.model`` flows from the operator-
    # configured registry / env-driven ``model_override``. A path-
    # shaped value must not let the cache write outside ``root_dir``.
    from .....llm.errors import LLMCacheError

    cache = LLMCache(root_dir=tmp_path)
    request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    unsafe_models = (
        "../escape",
        "..\\escape",
        "../../etc/passwd",
        ".hidden",
        "anthropic/../escape",
        "C:\\Windows\\System32",
        "model\x00with-null",
        "",
    )
    for model in unsafe_models:
        key = cache.build_key(request, LLMProvider.ANTHROPIC, model)
        try:
            with pytest.raises(LLMCacheError):
                cache._path_for(key)
        except AssertionError as exc:
            raise AssertionError(f"unsafe model identifier was accepted: {model!r}") from exc


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


def test_cache_path_normalises_ollama_tag_model(tmp_path: Path) -> None:
    # The Ollama ``name:tag`` separator (``qwen2.5vl:3b``) is folded to
    # ``_`` so the tagged model becomes a single, traversal-free path
    # segment under the provider directory rather than being rejected.
    cache = LLMCache(root_dir=tmp_path)
    request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    key = cache.build_key(request, LLMProvider.LOCAL, "qwen2.5vl:3b")
    composed = cache._path_for(key)
    assert composed.is_relative_to(tmp_path)
    assert composed.parent.name == "qwen2.5vl_3b"
    assert ":" not in composed.parent.name


def test_cache_payload_canary_is_encrypted_in_database(tmp_path: Path) -> None:
    cache = LLMCache(root_dir=tmp_path / "probe-cache")
    request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    response = _response().model_copy(update={"text": "CACHE-CANARY-123"})

    cache.write(request, response)

    assert not (tmp_path / "probe-cache").exists()
    # The encrypted store lives under the secure-object bucket layout, not
    # directly at tmp_path.  Search all .db files under tmp_path to
    # confirm the canary text is absent from every encrypted file.
    from .....tests.secure_sql import read_db_at_rest_bytes

    db_files = list(scan_directory(tmp_path, pattern="*.db", recursive=True))
    assert db_files, "expected at least one database file under tmp_path after cache write"
    for db_path in db_files:
        # Scan the main file AND its -wal sidecar: under WAL a just-written row
        # lives in <db>-wal until checkpoint, so a main-only read would pass
        # tautologically.
        assert b"CACHE-CANARY-123" not in read_db_at_rest_bytes(db_path), (
            f"canary text found unencrypted in {db_path.relative_to(tmp_path)}"
        )


def test_entry_from_payload_rejects_malformed_bytes(tmp_path: Path) -> None:
    # ``_entry_from_payload`` calls ``CachedEntry.model_validate_json``
    # before consuming any field; malformed or structurally invalid
    # payloads must raise rather than silently producing a corrupt entry.
    from .....llm.errors import LLMCacheError

    cache = LLMCache(root_dir=tmp_path)
    corrupted_payloads = (
        b"not-json-at-all",
        b"",
        b"{]",
        b'{"logical_root": "/some/path", "entry": "not-a-dict"}',
        b'{"logical_root": "/some/path", "entry": {"response": {}}}',
    )
    for corrupted_payload in corrupted_payloads:
        try:
            with pytest.raises((LLMCacheError, ValueError, KeyError)):
                cache._entry_from_payload(corrupted_payload)
        except AssertionError as exc:
            raise AssertionError(f"malformed cache payload was accepted: {corrupted_payload!r}") from exc


def test_entry_from_payload_rejects_wrong_logical_root(tmp_path: Path) -> None:
    # A payload that belongs to a different logical partition must be
    # rejected: the ``_entry_from_payload`` guard checks
    # ``logical_root`` equality before re-validating the entry.
    import json as _json

    from .....llm.errors import LLMCacheError

    request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
    cache = LLMCache(root_dir=tmp_path)
    cache.write(request, _response())

    # Build a syntactically valid payload whose logical_root points
    # at a different partition so the guard fires.
    foreign_payload = _json.dumps({"logical_root": "/entirely/different/partition", "entry": {}}).encode("utf-8")
    with pytest.raises(LLMCacheError, match="different logical partition"):
        cache._entry_from_payload(foreign_payload)
