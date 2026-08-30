"""Strict roundtrip across the encrypted ``LLMCache`` boundary.

``LLMCache`` persists :class:`CachedEntry` records under the
``cadrumo.outbound.llm.cache`` namespace at
``SensitivityClass.DIAGNOSTIC``.

Anti-tautology: the fixture populates every defaultable field on
``LLMRequest`` and ``LLMResponse`` with non-default, non-zero values
(model_override, language, max_tokens, temperature, system,
input_tokens > 0, cost_estimate_usd > 0). The redaction stage runs
unmodified so the roundtrip witnesses the post-redaction shape that
would surface a drift between save and load.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....llm.models import LLMProvider, LLMRequest, LLMResponse
from .....tests.secure_sql import TestRuntimeProfile, mutate_encrypted_secure_object_json
from .._cache import LLMCache

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CREATED_AT = datetime(2026, 5, 28, 12, 25, 0, tzinfo=UTC)


def _populated_request() -> LLMRequest:
    return LLMRequest(
        prompt="Translate the following AEAT casilla guidance into English.",
        system="You are a faithful AEAT tax-domain translator.",
        max_tokens=512,
        temperature=0.2,
        language="en",
        cache_key="translation-batch-2026Q1",
        provider_override=LLMProvider.ANTHROPIC,
        model_override="claude-opus-4-7",
    )


def _populated_response(
    created_at: datetime,
    *,
    provider: LLMProvider = LLMProvider.ANTHROPIC,
    model: str = "claude-opus-4-7",
    text: str = "Casilla 03 records the cumulative net revenue for the reporting period.",
    request_id: str = "a" * 64,
) -> LLMResponse:
    return LLMResponse(
        text=text,
        provider=provider,
        model=model,
        input_tokens=137,
        output_tokens=64,
        cost_estimate_usd=Decimal("0.0145"),
        cache_hit=False,
        created_at=created_at,
        request_id=request_id,
    )


def test_llm_cache_entry_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A populated CachedEntry round-trips through the encrypted LLM cache."""

    created_at = _CREATED_AT
    request = _populated_request()
    response = _populated_response(created_at)
    cache = LLMCache(root_dir=tmp_path / "llm-cache")

    stored = cache.write(request, response)
    loaded = cache.read(request, response.provider, response.model)

    assert loaded is not None
    # ``read`` flips ``cache_hit`` and zeroes the cost on the
    # returned response (cached responses are free). The stored
    # entry retains the originals.
    assert loaded.cache_hit is True
    assert loaded.cost_estimate_usd == Decimal("0E-4")
    assert loaded.text == response.text
    assert loaded.provider == response.provider
    assert loaded.model == response.model
    assert loaded.input_tokens == response.input_tokens
    assert loaded.output_tokens == response.output_tokens
    assert loaded.request_id == response.request_id
    assert loaded.created_at == response.created_at
    # Witness the persisted ``CachedEntry`` skeleton too.
    assert stored.provider == LLMProvider.ANTHROPIC
    assert stored.model == "claude-opus-4-7"
    assert stored.prompt_hash and len(stored.prompt_hash) == 64
    assert stored.args_hash and len(stored.args_hash) == 64

    stats = cache.stats()
    assert stats.entries == 1
    assert stats.total_bytes > 0


def test_llm_cache_keeps_tagged_and_underscore_models_in_distinct_encrypted_entries(
    tmp_path: Path,
) -> None:
    """Lossy display-path aliases must remain distinct secure cache identities."""

    request = _populated_request()
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    tagged = _populated_response(
        _CREATED_AT,
        provider=LLMProvider.LOCAL,
        model="qwen:3b",
        text="TAGGED-MODEL-RESPONSE",
        request_id="b" * 64,
    )
    underscored = _populated_response(
        _CREATED_AT,
        provider=LLMProvider.LOCAL,
        model="qwen_3b",
        text="UNDERSCORE-MODEL-RESPONSE",
        request_id="c" * 64,
    )

    cache.write(request, tagged)
    cache.write(request, underscored)

    tagged_loaded = cache.read(request, LLMProvider.LOCAL, tagged.model)
    underscored_loaded = cache.read(request, LLMProvider.LOCAL, underscored.model)

    assert tagged_loaded is not None
    assert tagged_loaded.model == "qwen:3b"
    assert tagged_loaded.text == "TAGGED-MODEL-RESPONSE"
    assert underscored_loaded is not None
    assert underscored_loaded.model == "qwen_3b"
    assert underscored_loaded.text == "UNDERSCORE-MODEL-RESPONSE"
    assert cache.stats().entries == 2


def test_llm_cache_entry_with_dropped_text_field_surfaces_at_read(
    tmp_path: Path,
    secure_object_test_profile: TestRuntimeProfile,
) -> None:
    """Anti-tautology proof: deleting ``response.text`` from the persisted entry must surface.

    Builds a populated cache entry, persists it, surgically mutates
    the encrypted JSON payload to delete the ``text`` field on the
    nested response, then calls ``read()``. The cache module's
    ``_entry_from_payload`` re-validates the dict against
    :class:`CachedEntry` via ``model_validate_json``, so a missing
    required ``text`` field must raise ``LLMCacheError`` (the cache's
    declared boundary error). If the read returns silently with a
    None / default text, every LLM cache roundtrip in the suite is
    tautological.
    """

    from sqlalchemy import select

    from .....llm.errors import LLMCacheError
    from ....persistence.storage.sql import SecureObjectRow
    from .._cache import _CACHE_NAMESPACE

    created_at = _CREATED_AT
    request = _populated_request()
    response = _populated_response(created_at)
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    cache.write(request, response)

    # Reach into the encrypted row and surgically delete ``text``
    # from the nested response on the redacted entry. The column
    # accessor handles encrypt/decrypt automatically; the
    # _CACHE_NAMESPACE filter pins the right row.
    stmt = select(SecureObjectRow).where(
        SecureObjectRow.namespace == _CACHE_NAMESPACE,
    )

    def mutate(decoded):
        entry_payload = decoded["entry"]
        assert "text" in entry_payload["response"], (
            "fixture must serialise response.text into the redacted entry for this proof test to be meaningful"
        )
        del entry_payload["response"]["text"]
        decoded["entry"] = entry_payload

    mutate_encrypted_secure_object_json(
        secure_object_test_profile.repository._engine,
        row_statement=stmt,
        mutate=mutate,
    )

    # Now read() must reject the mutated entry. LLMResponse.text
    # is required (no default), so the strict pydantic re-parse
    # must raise. The cache wraps re-parse failures in
    # LLMCacheError.
    with pytest.raises(LLMCacheError):
        cache.read(request, response.provider, response.model)
