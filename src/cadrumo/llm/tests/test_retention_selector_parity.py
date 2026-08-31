"""The one retention selector the cache, usage, and telemetry stores share.

The three LLM stores bound their growth under a single operational
obligation -- age cutoff, then oldest-first count cap -- while carrying
different record types and different retention timestamp fields
(``created_at`` for cache and usage, ``started_at`` for run telemetry).
These tests pin the *policy* on the canonical selector so the three stores
cannot drift apart on ordering or on either boundary, and prove each real
store's ``prune`` reaches that selector with its own timestamp projection.

No mocks: the real record models are constructed and the real selector runs.
The per-store persistence behaviour (encrypted save, namespace deletion,
missing-key contracts) stays covered by the three existing retention suites.

Each test states whether it is DISCRIMINATING (fails when the policy is
mutated) or SUPPORTING. The classification was established by running four
mutations against the selector -- inclusive cutoff, newest-end eviction, cap
measured over all rows, and a store re-inlining its own copy -- and recording
which tests each one flipped. Every boundary assertion here is discriminating;
the only deliberately supporting assertion is the three-way equality, which
cannot fail while the stores share one selector.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ...adapters.outbound.llm._run_telemetry import LLMRunRecord
from ..models import CachedEntry, LLMProvider, LLMResponse, UsageRecord
from ..retention import select_retention_removal_keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CUTOFF = datetime(2026, 6, 1, tzinfo=UTC)
_PROVIDER = LLMProvider.ANTHROPIC
_MODEL = "claude-sonnet-4-6"


def _response(created_at: datetime) -> LLMResponse:
    return LLMResponse(
        text="response",
        provider=_PROVIDER,
        model=_MODEL,
        input_tokens=10,
        output_tokens=2,
        cost_estimate_usd=Decimal("0.01"),
        cache_hit=False,
        created_at=created_at,
        request_id="req",
    )


def _cache_row(created_at: datetime, key: str) -> tuple[CachedEntry, str]:
    return (
        CachedEntry(
            provider=_PROVIDER,
            model=_MODEL,
            prompt_hash="prompt",
            args_hash="args",
            response=_response(created_at),
            created_at=created_at,
        ),
        key,
    )


def _usage_row(created_at: datetime, key: str) -> tuple[UsageRecord, str]:
    return (
        UsageRecord(
            prompt_id="prompt",
            caller="tests",
            text="response",
            provider=_PROVIDER,
            model=_MODEL,
            input_tokens=10,
            output_tokens=2,
            cost_estimate_usd=Decimal("0.01"),
            cache_hit=False,
            created_at=created_at,
            request_id="req",
        ),
        key,
    )


def _telemetry_row(started_at: datetime, key: str) -> tuple[LLMRunRecord, str]:
    return (
        LLMRunRecord(
            run_id=key,
            caller="tests",
            provider=str(_PROVIDER.value),
            model=_MODEL,
            duration_ms=5,
            succeeded=True,
            started_at=started_at,
        ),
        key,
    )


def _ages(*offsets_days: int) -> list[datetime]:
    """Return timestamps oldest-first at the given day offsets from the cutoff."""
    return [_CUTOFF + timedelta(days=offset) for offset in offsets_days]


# ---------------------------------------------------------------------------
# The shared policy: age cutoff, count cap, and their boundaries
# ---------------------------------------------------------------------------


def test_age_cutoff_is_exclusive_so_a_record_exactly_at_cutoff_is_retained() -> None:
    """A record strictly older than the cutoff goes; one exactly at it stays.

    DISCRIMINATING. Fails when the cutoff comparison is made inclusive
    (``<=`` / ``>``). The boundary is the whole reason the three stores must
    not each own a copy: an inclusive cutoff in one store and an exclusive
    cutoff in another silently expire different records on the same policy.
    """
    older, exactly, newer = _ages(-1, 0, 1)
    rows = [_cache_row(older, "old"), _cache_row(exactly, "boundary"), _cache_row(newer, "new")]

    removed = select_retention_removal_keys(
        rows, cutoff=_CUTOFF, max_records=100, timestamp=lambda entry: entry.created_at
    )

    assert removed == ["old"]


def test_count_cap_evicts_the_oldest_survivors_first() -> None:
    """The cap keeps the newest ``max_records``, evicting oldest excess.

    DISCRIMINATING. Fails when the excess slice is taken from the newest end
    (``remaining[-excess:]``), which would evict the records the operator most
    likely still needs.
    """
    rows = [_cache_row(stamp, f"r{index}") for index, stamp in enumerate(_ages(1, 2, 3, 4, 5))]

    removed = select_retention_removal_keys(
        rows, cutoff=_CUTOFF, max_records=2, timestamp=lambda entry: entry.created_at
    )

    assert removed == ["r0", "r1", "r2"]


def test_count_cap_is_applied_only_to_records_surviving_the_age_cutoff() -> None:
    """Age-expired records must not consume the retention budget.

    DISCRIMINATING. Fails when the cap is measured over all rows rather than
    the age-cutoff survivors: an old store would then evict live records it is
    entitled to keep.
    """
    rows = [
        _cache_row(stamp, key) for stamp, key in zip(_ages(-2, -1, 1, 2), ("x0", "x1", "keep0", "keep1"), strict=True)
    ]

    removed = select_retention_removal_keys(
        rows, cutoff=_CUTOFF, max_records=2, timestamp=lambda entry: entry.created_at
    )

    assert removed == ["x0", "x1"]


def test_a_key_is_never_selected_twice_when_both_bounds_bite() -> None:
    """Age and count stages are disjoint, so deletion counts stay truthful.

    DISCRIMINATING. Fails when the cap is measured over all rows (a key is
    then selected by both stages and the reported removal count double-counts)
    and when the excess slice is taken from the newest end.
    """
    rows = [
        _cache_row(stamp, key)
        for stamp, key in zip(_ages(-2, -1, 1, 2, 3), ("e0", "e1", "c0", "c1", "keep"), strict=True)
    ]

    removed = select_retention_removal_keys(
        rows, cutoff=_CUTOFF, max_records=1, timestamp=lambda entry: entry.created_at
    )

    assert removed == ["e0", "e1", "c0", "c1"]
    assert len(removed) == len(set(removed))


# ---------------------------------------------------------------------------
# Cross-store parity: one policy, three record shapes
# ---------------------------------------------------------------------------


def test_all_three_stores_select_identically_for_the_same_ages() -> None:
    """Cache, usage, and telemetry agree on age, count, order and boundary.

    MIXED, deliberately. The three-way equality assertion is SUPPORTING: now
    that the stores share one selector they cannot diverge, so that assertion
    cannot fail while the wiring holds (the wiring itself is what
    ``test_each_store_prune_reaches_the_canonical_selector`` guards). The
    exact-list assertion is DISCRIMINATING: it pins the hand-off between the
    two stages across a record sitting exactly on the cutoff, and fails under
    both the newest-end eviction and the cap-counts-expired mutations.
    """
    stamps = _ages(-2, -1, 0, 1, 2, 3)
    keys = [f"k{index}" for index in range(len(stamps))]

    cache = select_retention_removal_keys(
        [_cache_row(s, k) for s, k in zip(stamps, keys, strict=True)],
        cutoff=_CUTOFF,
        max_records=2,
        timestamp=lambda entry: entry.created_at,
    )
    usage = select_retention_removal_keys(
        [_usage_row(s, k) for s, k in zip(stamps, keys, strict=True)],
        cutoff=_CUTOFF,
        max_records=2,
        timestamp=lambda record: record.created_at,
    )
    telemetry = select_retention_removal_keys(
        [_telemetry_row(s, k) for s, k in zip(stamps, keys, strict=True)],
        cutoff=_CUTOFF,
        max_records=2,
        timestamp=lambda record: record.started_at,
    )

    assert cache == usage == telemetry
    # k0/k1 are strictly older than the cutoff. k2 sits exactly at it, so it
    # survives the age stage -- and is then evicted by the cap alongside k3,
    # leaving the newest two (k4, k5). That hand-off between the two stages is
    # the ordering all three stores must agree on.
    assert cache == ["k0", "k1", "k2", "k3"]


def test_each_store_prune_reaches_the_canonical_selector() -> None:
    """Every store's ``prune`` routes through the one selector.

    DISCRIMINATING, and the only test here that catches silent
    re-duplication. A store that reinstated a byte-identical private copy
    passes every behavioural assertion above -- verified by mutation:
    re-inlining the telemetry copy left the other five tests green and failed
    only this one. Behaviour cannot detect a duplicate that has not yet
    drifted, so the wiring is asserted directly.
    """
    import inspect

    from ...adapters.outbound.llm import _cache, _run_telemetry, _usage

    for module in (_cache, _usage, _run_telemetry):
        assert module.select_retention_removal_keys is select_retention_removal_keys, module.__name__

    for source_owner, prune in (
        (_cache.LLMCache, _cache.LLMCache.prune),
        (_usage.UsageRecorder, _usage.UsageRecorder.prune),
        (_run_telemetry.LLMRunTelemetryRecorder, _run_telemetry.LLMRunTelemetryRecorder.prune),
    ):
        source = inspect.getsource(prune)
        assert "select_retention_removal_keys(" in source, source_owner.__name__
