"""Redaction discipline tests for the LLM cache and usage log.

The LLM cache and usage log persist response text that may echo NIF or
counterparty context from the original prompt. Both writers must apply the
substrate's DIAGNOSTIC-class redaction rules
(:func:`cadrumo.core.redaction.redact_structured`) before any payload reaches
the encrypted secure-object backend; these tests exercise canary NIF and
bearer-token strings to prove that discipline holds without materializing
JSON files.

``"probe-cache"`` is a fictional directory: ``LLMCache.root_dir`` is a
constructor parameter, never a taxonomy accessor, and the ``not (...).exists()``
assertions prove the plaintext directory it names is never created regardless
of what it is called.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.outbound.llm.cache import LLMCache
from ...adapters.outbound.llm.usage import UsageRecorder
from ...tests.secure_sql import TestRuntimeProfile, read_db_at_rest_bytes
from ..models import (
    CachedEntry,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    UsageRecord,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NIF_CANARY = "12345678Z"
_BEARER_TAIL = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_BEARER_CANARY = f"Bearer {_BEARER_TAIL}"


def _make_request() -> LLMRequest:
    return LLMRequest(
        prompt="classify this counterparty",
        system=None,
        max_tokens=128,
        temperature=0.0,
        language=None,
        cache_key=None,
        provider_override=None,
        model_override=None,
    )


def _make_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        provider=LLMProvider.ANTHROPIC,
        model="claude-test",
        input_tokens=10,
        output_tokens=20,
        cost_estimate_usd=Decimal("0.001"),
        cache_hit=False,
        created_at=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
        request_id="req-test-001",
    )


class TestCacheRedaction:
    """Verify CACHE-class redaction is applied before any cache write."""

    def test_nif_canary_does_not_land_plaintext_in_cache(
        self,
        tmp_path: Path,
        secure_object_test_profile: TestRuntimeProfile,
    ) -> None:
        cache = LLMCache(root_dir=tmp_path / "probe-cache")
        request = _make_request()
        response = _make_response(text=f"the customer's tax id is {_NIF_CANARY}")
        cache.write(request, response)

        assert not (tmp_path / "probe-cache").exists()
        db_path = secure_object_test_profile.paths.database_file
        assert _NIF_CANARY.encode() not in read_db_at_rest_bytes(db_path)

    def test_bearer_token_redacted_in_cache(
        self,
        tmp_path: Path,
        secure_object_test_profile: TestRuntimeProfile,
    ) -> None:
        cache = LLMCache(root_dir=tmp_path / "probe-cache")
        request = _make_request()
        response = _make_response(text=f"the auth header was {_BEARER_CANARY}")
        cache.write(request, response)

        assert not (tmp_path / "probe-cache").exists()
        db_path = secure_object_test_profile.paths.database_file
        assert _BEARER_TAIL.encode() not in read_db_at_rest_bytes(db_path)

    def test_cache_entry_remains_parseable(self, tmp_path: Path) -> None:
        cache = LLMCache(root_dir=tmp_path / "probe-cache")
        request = _make_request()
        response = _make_response(text="non sensitive output")
        cache.write(request, response)
        cached = cache.read(request, LLMProvider.ANTHROPIC, "claude-test")
        assert cached is not None
        entry = CachedEntry(
            provider=cached.provider,
            model=cached.model,
            prompt_hash=cache.build_key(request, cached.provider, cached.model).prompt_hash,
            args_hash=cache.build_key(request, cached.provider, cached.model).args_hash,
            response=cached.model_copy(update={"cache_hit": False}),
            created_at=cached.created_at,
        )
        assert entry.response.text == "non sensitive output"

    def test_idempotent_re_read(self, tmp_path: Path, secure_object_test_profile: TestRuntimeProfile) -> None:
        """A cache hit re-reads the (already-redacted) text. Re-applying
        the redaction rules to a redacted string is a no-op."""
        cache = LLMCache(root_dir=tmp_path / "probe-cache")
        request = _make_request()
        response = _make_response(text=f"the NIF is {_NIF_CANARY}")
        cache.write(request, response)
        first = cache.read(request, LLMProvider.ANTHROPIC, "claude-test")
        assert first is not None
        # Re-write the same response (simulate re-cache) — still no
        # plaintext NIF in the encrypted database bytes.
        cache.write(request, first.model_copy(update={"cache_hit": False}))
        assert not (tmp_path / "probe-cache").exists()
        db_path = secure_object_test_profile.paths.database_file
        assert _NIF_CANARY.encode() not in read_db_at_rest_bytes(db_path)


class TestUsageRedaction:
    """Verify DIAGNOSTIC-class redaction is applied before any usage write."""

    def _make_record(self, text: str) -> UsageRecord:
        return UsageRecord(
            prompt_id="prompt-test",
            caller="test-caller",
            text=text,
            provider=LLMProvider.ANTHROPIC,
            model="claude-test",
            input_tokens=10,
            output_tokens=20,
            cost_estimate_usd=Decimal("0.001"),
            cache_hit=False,
            created_at=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
            request_id="req-test-001",
        )

    def test_nif_canary_does_not_land_plaintext_in_usage(
        self,
        tmp_path: Path,
        secure_object_test_profile: TestRuntimeProfile,
    ) -> None:
        recorder = UsageRecorder(root_dir=tmp_path / "usage")
        record = self._make_record(text=f"customer NIF: {_NIF_CANARY}")
        path = recorder.record(record)
        assert not path.exists()
        db_path = secure_object_test_profile.paths.database_file
        assert _NIF_CANARY.encode() not in read_db_at_rest_bytes(db_path)

    def test_bearer_token_redacted_in_usage(
        self,
        tmp_path: Path,
        secure_object_test_profile: TestRuntimeProfile,
    ) -> None:
        recorder = UsageRecorder(root_dir=tmp_path / "usage")
        record = self._make_record(text=f"saw header {_BEARER_CANARY}")
        path = recorder.record(record)
        assert not path.exists()
        db_path = secure_object_test_profile.paths.database_file
        assert _BEARER_TAIL.encode() not in read_db_at_rest_bytes(db_path)

    def test_each_record_is_one_jsonl_line(self, tmp_path: Path) -> None:
        recorder = UsageRecorder(root_dir=tmp_path / "usage")
        for _ in range(3):
            recorder.record(self._make_record(text="non sensitive"))
        assert not (tmp_path / "usage").exists()
        records = recorder.load_records()
        assert len(records) == 3
        for record in records:
            decoded = json.loads(record.model_dump_json())
            assert decoded["caller"] == "test-caller"
