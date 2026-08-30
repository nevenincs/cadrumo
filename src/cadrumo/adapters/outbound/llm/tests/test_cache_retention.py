"""Retention-window pruning for :class:`~adapters.outbound.llm.LLMCache`.

``prune`` bounds the response cache's growth in two stages mirroring
:meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.prune`: an age cutoff
(``retention_days``) then a record-count cap (``max_records``), both defaulting
to central settings.

The cache stamps ``created_at = now()`` at write time (unlike telemetry, which
takes the timestamp from the record). A frozen clock cannot establish a past
age here: freezing to any instant unrelated to the real session deadline
expires the active bucket session (see the run-telemetry retention test). So an
aged entry is written by replicating the real write path (real redaction, real
encrypted save) with an explicit past ``created_at`` under the real clock,
which keeps the session valid while giving ``prune`` a genuinely old entry to
act on. ``read`` is used to assert survivor identity.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from .....adapters.persistence.storage import secure_object_repository_for_active_bucket
from .....core.classification import SensitivityClass
from .....core.redaction import default_rules_for_class, redact_structured
from .....llm.models import CachedEntry, LLMProvider, LLMRequest, LLMResponse
from .. import LLMCache
from .._cache import _CACHE_NAMESPACE, _CACHE_VERSION

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PROVIDER = LLMProvider.ANTHROPIC
_MODEL = "claude-sonnet-4-6"


def _response(request_id: str) -> LLMResponse:
    return LLMResponse(
        text="cached response",
        provider=_PROVIDER,
        model=_MODEL,
        input_tokens=10,
        output_tokens=2,
        cost_estimate_usd=Decimal("0.000060"),
        cache_hit=False,
        created_at=datetime.now(UTC),
        request_id=request_id,
    )


def _write_at(cache: LLMCache, request: LLMRequest, request_id: str, created_at: datetime) -> None:
    """Persist a cache entry with an explicit ``created_at`` via the real save path.

    Mirrors ``LLMCache.write`` (real redaction, real encrypted secure-object
    save) but stamps a caller-chosen ``created_at`` so ``prune`` sees a genuinely
    aged entry, all under the real clock so the bucket session stays valid.
    """
    key = cache.build_key(request, _PROVIDER, _MODEL)
    entry = CachedEntry(
        provider=_PROVIDER,
        model=_MODEL,
        prompt_hash=key.prompt_hash,
        args_hash=key.args_hash,
        response=_response(request_id),
        created_at=created_at,
    )
    redacted = redact_structured(
        entry.model_dump(mode="json"),
        rules=default_rules_for_class(SensitivityClass.DIAGNOSTIC),
    )
    assert isinstance(redacted, dict)
    payload = cache._payload_for_entry({str(k): v for k, v in redacted.items()})
    secure_object_repository_for_active_bucket().save(
        namespace=_CACHE_NAMESPACE,
        object_key=cache._object_key_for(key),
        classification=SensitivityClass.DIAGNOSTIC,
        schema_version=_CACHE_VERSION,
        written_at=created_at,
        payload=payload,
    )


def test_prune_removes_entries_older_than_retention_window(tmp_path: Path) -> None:
    anchor = datetime.now(UTC)
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    fresh = LLMRequest(prompt="fresh", temperature=0.0, language="es")
    stale = LLMRequest(prompt="stale", temperature=0.0, language="es")
    _write_at(cache, fresh, "fresh", anchor - timedelta(days=1))
    _write_at(cache, stale, "stale", anchor - timedelta(days=45))

    removed = cache.prune(retention_days=30, max_records=1000)

    assert removed == 1
    assert cache.read(fresh, _PROVIDER, _MODEL) is not None
    assert cache.read(stale, _PROVIDER, _MODEL) is None


def test_prune_keeps_entries_inside_both_bounds(tmp_path: Path) -> None:
    anchor = datetime.now(UTC)
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    a = LLMRequest(prompt="a", temperature=0.0, language="es")
    b = LLMRequest(prompt="b", temperature=0.0, language="es")
    _write_at(cache, a, "a", anchor - timedelta(days=1))
    _write_at(cache, b, "b", anchor - timedelta(days=2))

    removed = cache.prune(retention_days=30, max_records=1000)

    assert removed == 0
    assert cache.read(a, _PROVIDER, _MODEL) is not None
    assert cache.read(b, _PROVIDER, _MODEL) is not None


def test_prune_enforces_max_records_cap_evicting_oldest_first(tmp_path: Path) -> None:
    anchor = datetime.now(UTC)
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    newest = LLMRequest(prompt="newest", temperature=0.0, language="es")
    middle = LLMRequest(prompt="middle", temperature=0.0, language="es")
    oldest = LLMRequest(prompt="oldest", temperature=0.0, language="es")
    # All inside the age window, so only the count cap applies.
    _write_at(cache, newest, "newest", anchor - timedelta(days=1))
    _write_at(cache, middle, "middle", anchor - timedelta(days=2))
    _write_at(cache, oldest, "oldest", anchor - timedelta(days=4))

    removed = cache.prune(retention_days=3650, max_records=1)

    assert removed == 2
    assert cache.read(newest, _PROVIDER, _MODEL) is not None
    assert cache.read(middle, _PROVIDER, _MODEL) is None
    assert cache.read(oldest, _PROVIDER, _MODEL) is None


def test_client_construction_sweeps_the_cache_store(tmp_path: Path) -> None:
    """Building an LLMClient fires the retention sweep over its response cache.

    A stale entry (written via the real save path with a past created_at) is
    pruned by the once-per-client retention sweep when an ``LLMClient`` is
    constructed around the cache, while a fresh entry survives - proving
    retention fires in production rather than depending on a manual prune()
    call.
    """
    from .....llm.client import LLMClient

    anchor = datetime.now(UTC)
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    fresh = LLMRequest(prompt="fresh", temperature=0.0, language="es")
    stale = LLMRequest(prompt="stale", temperature=0.0, language="es")
    _write_at(cache, fresh, "fresh", anchor - timedelta(days=1))
    _write_at(cache, stale, "stale", anchor - timedelta(days=45))

    LLMClient(cache=cache)

    assert cache.read(fresh, _PROVIDER, _MODEL) is not None
    assert cache.read(stale, _PROVIDER, _MODEL) is None
