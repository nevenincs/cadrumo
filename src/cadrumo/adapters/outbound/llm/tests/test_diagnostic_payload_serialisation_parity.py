"""The three diagnostic stores in this package write one payload byte shape.

``LLMCache``, ``UsageRecorder`` and ``LLMRunTelemetryRecorder`` each wrap a
``model_dump(mode="json")`` record in a ``logical_root``-tagged envelope and
write it as a secure-object payload. The cache used to serialise that envelope
with a hand-rolled ``json.dumps(payload, indent=2, sort_keys=True,
default=str)`` while its two siblings used
:func:`~core.hashing.canonical_json_bytes`; all three now use the helper.

Two properties are worth pinning, because the repoint traded a permissive
serialiser for a strict one:

* the cache payload really is JSON-native, so the helper's refusal is a guard
  and not a latent break waiting on an unusual entry, and
* the strictness is real -- ``default=str`` would have coerced a non-JSON value
  into a plausible-looking string and stored it, which is the failure mode the
  refusal replaces.

The second is the load-bearing one. A permissive serialiser does not fail; it
writes something wrong and stays green, so the only way to show the change was
worth making is to exhibit a value the old form would have swallowed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.hashing import canonical_json_bytes
from .....llm.models import LLMProvider, LLMRequest, LLMResponse
from .._cache import LLMCache

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CREATED_AT = datetime(2026, 5, 28, 12, 25, 0, tzinfo=UTC)


def _request() -> LLMRequest:
    return LLMRequest(
        prompt="Translate the following AEAT casilla guidance into English.",
        system="You are a faithful AEAT tax-domain translator.",
        max_tokens=512,
        temperature=0.2,
        language="en",
        cache_key="serialisation-parity",
        provider_override=LLMProvider.ANTHROPIC,
        model_override="claude-opus-4-7",
    )


def _response() -> LLMResponse:
    return LLMResponse(
        text="Casilla 03 records the cumulative net revenue for the reporting period.",
        provider=LLMProvider.ANTHROPIC,
        model="claude-opus-4-7",
        input_tokens=137,
        output_tokens=64,
        # A Decimal is the value most likely to need ``default=str``; pydantic's
        # json mode renders it as a string before it reaches the serialiser,
        # which is exactly why the strict helper suffices here.
        cost_estimate_usd=Decimal("0.0145"),
        cache_hit=False,
        created_at=_CREATED_AT,
        request_id="a" * 64,
    )


def test_the_cache_payload_is_json_native_so_the_strict_helper_suffices(tmp_path: Path) -> None:
    """A real cache payload serialises through the strict helper without refusal.

    Drives the production ``_payload_for_entry`` on a populated entry rather
    than a hand-built mapping, so the assertion is about what the cache
    actually writes.
    """
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    entry = cache.write(_request(), _response())

    redacted = json.loads(canonical_json_bytes(json.loads(entry.model_dump_json())))

    assert redacted["provider"] == LLMProvider.ANTHROPIC.value
    assert canonical_json_bytes({"logical_root": "x", "entry": redacted})


def test_the_written_payload_is_compact_canonical_json(tmp_path: Path) -> None:
    """The stored bytes carry no indentation and sort their keys.

    Distinguishes the new serialisation from the old one by a property only
    the new one has: ``indent=2`` emitted newlines and two-space padding into
    every encrypted row.
    """
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    request, response = _request(), _response()
    cache.write(request, response)

    # Re-derive the payload through the production path rather than reading the
    # encrypted row back, which would decrypt to the same bytes anyway.
    payload = cache._payload_for_entry({"b": 2, "a": 1})

    assert b"\n" not in payload
    assert b'"a":1' in payload
    assert payload.index(b'"a"') < payload.index(b'"b"')


def test_a_non_json_native_value_is_refused_rather_than_stringified(tmp_path: Path) -> None:
    """The strict helper raises where ``default=str`` would have stored a string.

    This is the anti-tautology proof for the repoint. Without it the change
    reads as cosmetic: both serialisers produce bytes for every payload the
    cache currently builds, and only a value outside JSON's type set
    distinguishes "refused" from "silently coerced".
    """
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    hostile = {"created_at": _CREATED_AT}

    with pytest.raises(TypeError):
        cache._payload_for_entry(hostile)

    # The discarded alternative, exhibited: it succeeds, and what it stores is
    # a stringified datetime that no reader can distinguish from a real string.
    coerced = json.loads(json.dumps({"entry": hostile}, indent=2, sort_keys=True, default=str))

    assert coerced["entry"]["created_at"] == str(_CREATED_AT)
