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

from ....core.config import Settings
from ...persistence.storage import EphemeralMasterKeyProvider
from ...persistence.storage.sql import SecureObjectRepository
from ...persistence.storage.sql._orm import Base
from ...persistence.storage.sql.engine import create_engine_from_settings
from ._cache import LLMCache
from ._models import LLMProvider, LLMRequest, LLMResponse

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A populated CachedEntry round-trips through the encrypted LLM cache."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "llm-cache-roundtrip.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

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
        finally:
            engine.dispose()


def test_llm_cache_entry_with_dropped_text_field_surfaces_at_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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

    from ...persistence.storage.sql._orm import SecureObjectRow
    from ...persistence.storage.sql.session import session_scope
    from ._cache import _CACHE_NAMESPACE
    from ._errors import LLMCacheError

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "llm-cache-anti-tautology.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            created_at = datetime.now(UTC).replace(microsecond=0)
            request = _populated_request()
            response = _populated_response(created_at)
            cache = LLMCache(root_dir=tmp_path / "llm-cache")
            cache.write(request, response)

            # Reach into the encrypted row and surgically delete ``text``
            # from the nested response on the redacted entry. The column
            # accessor handles encrypt/decrypt automatically; the
            # _CACHE_NAMESPACE filter pins the right row.
            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == _CACHE_NAMESPACE,
                )
                row = session.execute(stmt).scalar_one()
                decoded = _json.loads(row.payload.decode("utf-8"))
                entry_payload = decoded["entry"]
                assert "text" in entry_payload["response"], (
                    "fixture must serialise response.text into the redacted "
                    "entry for this proof test to be meaningful"
                )
                del entry_payload["response"]["text"]
                decoded["entry"] = entry_payload
                row.payload = _json.dumps(decoded).encode("utf-8")

            # Now read() must reject the mutated entry. LLMResponse.text
            # is required (no default), so the strict pydantic re-parse
            # must raise. The cache wraps re-parse failures in
            # LLMCacheError.
            regression_caught = False
            try:
                cache.read(request, response.provider, response.model)
            except LLMCacheError:
                regression_caught = True
            assert regression_caught, (
                "anti-tautology proof failed: deleting LLMResponse.text from "
                "the persisted cache entry did NOT surface as LLMCacheError. "
                "The cache boundary is tautological and every LLM cache "
                "roundtrip in the suite is suspect."
            )
        finally:
            engine.dispose()
