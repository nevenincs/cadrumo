"""A cache row written before the write-side redaction refusal is evicted, never replayed.

Such a row holds the model's reply with identifiers already replaced by
redaction placeholders. Replaying it hands an invoice read ``sha256:...`` where
the document printed a tax identifier, so the read refuses a document it would
otherwise accept. The row is seeded here exactly as the earlier write path
stored it -- the entry run through the diagnostic redaction rules, then saved
to the real encrypted store -- because the current write path refuses to
produce it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from .....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from .....core.classification.policies import SensitivityClass
from .....core.config_support import LLMProvider
from .....core.redaction.rules import (
    carries_redaction_placeholder,
    default_rules_for_class,
    redact_for_log,
    redact_structured,
)
from ..cache import _CACHE_NAMESPACE, _CACHE_SENSITIVITY, _CACHE_VERSION, LLMCache
from ..models import CachedEntry, LLMRequest, LLMResponse

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_MODEL = "qwen3:1.7b"
_NIF = "12345678Z"


def _request() -> LLMRequest:
    return LLMRequest(
        prompt="read this invoice",
        system=None,
        max_tokens=128,
        temperature=0.0,
        language=None,
        cache_key=None,
        provider_override=None,
        model_override=None,
    )


def _response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        provider=LLMProvider.LOCAL,
        model=_MODEL,
        input_tokens=10,
        output_tokens=20,
        cost_estimate_usd=Decimal("0"),
        cache_hit=False,
        created_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        request_id="req-legacy",
    )


def _seed_legacy_row(cache: LLMCache, request: LLMRequest, response: LLMResponse) -> str:
    """Store ``response`` redacted, as the cache wrote it before refusing to."""
    key = cache.build_key(request, response.provider, response.model)
    entry = CachedEntry(
        provider=response.provider,
        model=response.model,
        prompt_hash=key.prompt_hash,
        args_hash=key.args_hash,
        response=response,
        created_at=response.created_at,
    )
    redacted = redact_structured(
        entry.model_dump(mode="json"),
        rules=default_rules_for_class(SensitivityClass.DIAGNOSTIC),
    )
    assert isinstance(redacted, dict)
    object_key = cache._object_key_for(key)
    secure_object_repository_for_active_bucket().save(
        namespace=_CACHE_NAMESPACE,
        object_key=object_key,
        classification=_CACHE_SENSITIVITY,
        schema_version=_CACHE_VERSION,
        written_at=response.created_at,
        payload=cache._payload_for_entry({str(k): v for k, v in redacted.items()}),
    )
    return object_key


def _stored(object_key: str) -> bool:
    return (
        secure_object_repository_for_active_bucket().load(
            _CACHE_NAMESPACE,
            object_key,
            expected_class=_CACHE_SENSITIVITY,
            max_supported_version=_CACHE_VERSION,
        )
        is not None
    )


def test_a_row_carrying_a_redaction_placeholder_is_evicted_and_never_returned() -> None:
    cache = LLMCache()
    request = _request()
    object_key = _seed_legacy_row(cache, request, _response(f'{{"supplier_tax_id": "{_NIF}"}}'))
    assert _stored(object_key), "the seed must reach the real store for the eviction to mean anything"

    assert cache.read(request, LLMProvider.LOCAL, _MODEL) is None
    assert not _stored(object_key), "the replayable row must be gone, not merely skipped"
    # A second read is an ordinary miss: nothing was reinstated.
    assert cache.read(request, LLMProvider.LOCAL, _MODEL) is None


def test_a_clean_row_is_still_served() -> None:
    """Positive control: eviction is keyed on the placeholder, not on every legacy row."""
    cache = LLMCache()
    request = _request()
    object_key = _seed_legacy_row(cache, request, _response('{"supplier_name": "Hardware Profesional Sur SL"}'))

    served = cache.read(request, LLMProvider.LOCAL, _MODEL)

    assert served is not None
    assert served.text == '{"supplier_name": "Hardware Profesional Sur SL"}'
    assert _stored(object_key)


def test_the_detector_reads_exactly_what_redaction_writes() -> None:
    """Both hashing placeholders are detected, and an unredacted identifier is not."""
    assert carries_redaction_placeholder(redact_for_log(f"nif {_NIF}"))
    assert carries_redaction_placeholder({"auth": [redact_for_log("Bearer " + "a" * 44)]})
    assert not carries_redaction_placeholder({"supplier_tax_id": _NIF})
    assert not carries_redaction_placeholder("sha256:not-hex")
