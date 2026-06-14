"""Strict roundtrip across the encrypted ``LLMCache`` boundary.

``LLMCache`` persists :class:`CachedEntry` records under the
``aeat.outbound.llm.cache`` namespace at
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

from .....tests.secure_sql import TestRuntimeProfile
from .._cache import LLMCache
from .._models import LLMProvider, LLMRequest, LLMResponse

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


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


def _populated_response(created_at: datetime) -> LLMResponse:
    return LLMResponse(
        text="Casilla 03 records the cumulative net revenue for the reporting period.",
        provider=LLMProvider.ANTHROPIC,
        model="claude-opus-4-7",
        input_tokens=137,
        output_tokens=64,
        cost_estimate_usd=Decimal("0.0145"),
        cache_hit=False,
        created_at=created_at,
        request_id="a" * 64,
    )


def test_llm_cache_entry_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A populated CachedEntry round-trips through the encrypted LLM cache."""

    created_at = datetime.now(UTC).replace(microsecond=0)
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

    import json as _json

    from sqlalchemy import select

    from ....persistence.storage.crypto._encrypted_columns import (
        decrypt_secure_object_payload,
        encrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ....persistence.storage.sql._orm import SecureObjectRow
    from ....persistence.storage.sql.session import session_scope
    from .._cache import _CACHE_NAMESPACE
    from .._errors import LLMCacheError

    created_at = datetime.now(UTC).replace(microsecond=0)
    request = _populated_request()
    response = _populated_response(created_at)
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    cache.write(request, response)

    # Reach into the encrypted row and surgically delete ``text``
    # from the nested response on the redacted entry. The column
    # accessor handles encrypt/decrypt automatically; the
    # _CACHE_NAMESPACE filter pins the right row.
    with session_scope(secure_object_test_profile.repository._engine) as session:
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == _CACHE_NAMESPACE,
        )
        row = session.execute(stmt).scalar_one()
        _h3_aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
        _h3_plain = decrypt_secure_object_payload(bytes(row.payload), associated_data=_h3_aad)
        decoded = _json.loads(_h3_plain.decode("utf-8"))
        entry_payload = decoded["entry"]
        assert "text" in entry_payload["response"], (
            "fixture must serialise response.text into the redacted entry for this proof test to be meaningful"
        )
        del entry_payload["response"]["text"]
        decoded["entry"] = entry_payload
        row.payload = encrypt_secure_object_payload(_json.dumps(decoded).encode("utf-8"), associated_data=_h3_aad)

    # Now read() must reject the mutated entry. LLMResponse.text
    # is required (no default), so the strict pydantic re-parse
    # must raise. The cache wraps re-parse failures in
    # LLMCacheError.
    with pytest.raises(LLMCacheError):
        cache.read(request, response.provider, response.model)
