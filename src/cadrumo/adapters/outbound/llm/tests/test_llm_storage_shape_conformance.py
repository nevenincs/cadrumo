"""The LLM usage/telemetry/cache logical paths match their declared grammar shapes.

Three of ``STORAGE_PATH_DEFINITIONS``' filesystem-kind entries are NOT
materialised as files: :class:`~adapters.outbound.llm.UsageRecorder`,
:class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`, and
:class:`~adapters.outbound.llm.LLMCache` all persist through
``secure_object_repository_for_active_bucket().save(...)`` (encrypted SQL
secure objects); each producer's own docstring says its returned path is
"logical ... for operator display only" (usage, run-telemetry) or that "the
cache itself is persisted in encrypted SQL secure objects" (cache). The
existing ``test_usage.py`` module already asserts ``not path.exists()``
directly against this real, produced value.

These tests drive each real production writer and assert the REAL RETURNED
PATH (not a fabricated one) against its declared grammar -- proving the
declaration matches the real production contract for the logical/display
path, while being explicit that this is not a real-filesystem-write
conformance check. Positive controls prove the matcher can still fail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from .....core.config import override_settings
from .....core.storage_taxonomy import StorageCategory
from .....llm.models import LLMProvider, LLMRequest, LLMResponse
from .....tests import assert_path_matches_grammar
from .....tests.storage_scope import storage_overrides
from ..cache import LLMCache
from ..run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ..usage import UsageRecorder

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"cache", "llm-cache", "llm-usage"})
"""Taxonomy-vocabulary literals this module deliberately pins.

``tmp_path / "cache" / "llm-cache" / "not-nested-enough.json"`` in the
positive-control test is the real declared grammar shape, deliberately
mis-nested to prove the matcher can still fail -- both segments, "cache" and
"llm-cache", are the shape under test. ``"llm-usage"`` is the sibling
positive-control's malformed filename test
(``tmp_path / "llm-usage" / "usage-not-a-date.jsonl"``).
"""

_CREATED_AT = datetime(2026, 5, 28, 12, 20, 0, tzinfo=UTC)


def _response() -> LLMResponse:
    return LLMResponse(
        text="ok",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=15,
        output_tokens=6,
        cost_estimate_usd=Decimal("0.000135"),
        cache_hit=False,
        created_at=_CREATED_AT,
        request_id="request-id",
    )


def test_the_usage_record_logical_path_matches_its_declared_shape(tmp_path: Path) -> None:
    root = tmp_path
    with override_settings(**storage_overrides(tmp_path, StorageCategory.LLM_USAGE)):
        recorder = UsageRecorder()
        response = _response()
        record = recorder.build_record(response, prompt_id="translation_v1", caller="test-suite")
        path = recorder.record(record)

    # Real production contract, asserted directly (mirrors test_usage.py):
    # this is the LOGICAL display path, never a materialised file.
    assert not path.exists()
    assert_path_matches_grammar(key="llm_usage_record", root=root, produced=path)


def test_the_run_telemetry_logical_path_matches_its_declared_shape(tmp_path: Path) -> None:
    root = tmp_path
    with override_settings(**storage_overrides(tmp_path, StorageCategory.LLM_RUN_TELEMETRY)):
        recorder = LLMRunTelemetryRecorder()
        record = LLMRunRecord(
            run_id="run-0001",
            caller="test-suite",
            provider="claude",
            model="claude-sonnet-4-6",
            duration_ms=120,
            succeeded=True,
            started_at=_CREATED_AT,
        )
        path = recorder.record(record)

    assert not path.exists()
    assert_path_matches_grammar(key="llm_run_telemetry_record", root=root, produced=path)


def test_the_cache_entry_logical_path_matches_its_declared_shape(tmp_path: Path) -> None:
    root = tmp_path
    with override_settings(**storage_overrides(tmp_path, StorageCategory.LLM_CACHE)):
        cache = LLMCache()
        request = LLMRequest(prompt="Hello", temperature=0.0, language="es")
        response = _response()
        cache.write(request, response)
        # ``write`` returns the persisted CachedEntry, not the logical path --
        # the path is a separate helper, exactly as ``_path_for``'s docstring
        # says: "Logical path for displaying the cache entry location."
        key = cache.build_key(request, response.provider, response.model)
        path = cache._path_for(key)

    assert not path.exists()
    assert_path_matches_grammar(key="llm_cache_entry", root=root, produced=path)


def test_a_non_conforming_usage_filename_is_rejected_by_the_grammar(tmp_path: Path) -> None:
    """Positive control: the matcher can still fail."""
    malformed = tmp_path / "llm-usage" / "usage-not-a-date.jsonl"
    with pytest.raises(AssertionError):
        assert_path_matches_grammar(key="llm_usage_record", root=tmp_path, produced=malformed)


def test_a_non_conforming_cache_path_is_rejected_by_the_grammar(tmp_path: Path) -> None:
    """Positive control: a cache path missing the provider/model nesting fails."""
    malformed = tmp_path / "cache" / "llm-cache" / "not-nested-enough.json"
    with pytest.raises(AssertionError):
        assert_path_matches_grammar(key="llm_cache_entry", root=tmp_path, produced=malformed)
