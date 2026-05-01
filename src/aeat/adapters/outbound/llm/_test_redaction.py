"""Wave-6 tests: LLM cache + usage redaction discipline.

The LLM cache and usage log persist response text that may echo NIF /
counterparty context from the prompt. Wave 6 wraps both writers so the
substrate's CACHE-class / DIAGNOSTIC-class redaction discipline applies
before persistence.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ._cache import LLMCache
from ._models import (
    CachedEntry,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    UsageRecord,
)
from ._usage import UsageRecorder

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]

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
    def test_nif_canary_does_not_land_plaintext_in_cache(self, tmp_path: Path) -> None:
        cache = LLMCache(root_dir=tmp_path / "cache")
        request = _make_request()
        response = _make_response(text=f"the customer's tax id is {_NIF_CANARY}")
        cache.write(request, response)

        # Walk every cache file written and confirm the NIF canary is
        # not present verbatim.
        for path in (tmp_path / "cache").rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            assert _NIF_CANARY not in text

    def test_bearer_token_redacted_in_cache(self, tmp_path: Path) -> None:
        cache = LLMCache(root_dir=tmp_path / "cache")
        request = _make_request()
        response = _make_response(text=f"the auth header was {_BEARER_CANARY}")
        cache.write(request, response)

        for path in (tmp_path / "cache").rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            assert _BEARER_TAIL not in text

    def test_cache_entry_remains_parseable(self, tmp_path: Path) -> None:
        cache = LLMCache(root_dir=tmp_path / "cache")
        request = _make_request()
        response = _make_response(text="non sensitive output")
        cache.write(request, response)
        for path in (tmp_path / "cache").rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            # The redacted JSON round-trips back to a CachedEntry —
            # strict-mode validation requires model_validate_json
            # rather than model_validate(json.loads(...)) because
            # JSON strings need pydantic's coercion path.
            entry = CachedEntry.model_validate_json(text)
            assert entry.response.text == "non sensitive output"

    def test_idempotent_re_read(self, tmp_path: Path) -> None:
        """A cache hit re-reads the (already-redacted) text. Re-applying
        the redaction rules to a redacted string is a no-op."""
        cache = LLMCache(root_dir=tmp_path / "cache")
        request = _make_request()
        response = _make_response(text=f"the NIF is {_NIF_CANARY}")
        cache.write(request, response)
        first = cache.read(request, LLMProvider.ANTHROPIC, "claude-test")
        assert first is not None
        # Re-write the same response (simulate re-cache) — still no
        # plaintext NIF on disk.
        cache.write(request, first.model_copy(update={"cache_hit": False}))
        for path in (tmp_path / "cache").rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            assert _NIF_CANARY not in text


class TestUsageRedaction:
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

    def test_nif_canary_does_not_land_plaintext_in_usage(self, tmp_path: Path) -> None:
        recorder = UsageRecorder(root_dir=tmp_path / "usage")
        record = self._make_record(text=f"customer NIF: {_NIF_CANARY}")
        path = recorder.record(record)
        assert _NIF_CANARY not in path.read_text(encoding="utf-8")

    def test_bearer_token_redacted_in_usage(self, tmp_path: Path) -> None:
        recorder = UsageRecorder(root_dir=tmp_path / "usage")
        record = self._make_record(text=f"saw header {_BEARER_CANARY}")
        path = recorder.record(record)
        assert _BEARER_TAIL not in path.read_text(encoding="utf-8")

    def test_each_record_is_one_jsonl_line(self, tmp_path: Path) -> None:
        recorder = UsageRecorder(root_dir=tmp_path / "usage")
        for _ in range(3):
            recorder.record(self._make_record(text="non sensitive"))
        path = tmp_path / "usage" / "usage-2026-04-30.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        for line in lines:
            decoded = json.loads(line)
            assert decoded["caller"] == "test-caller"
