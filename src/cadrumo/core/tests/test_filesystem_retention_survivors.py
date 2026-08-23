"""Regression coverage for the shared filesystem retention-survivor selector.

:func:`~cadrumo.core.paths.select_filesystem_retention_survivors` converges
the four hand-rolled raw-filesystem retention walkers found in
:mod:`cadrumo.core.observability`,
:mod:`cadrumo.adapters.outbound.aeat.sede`, an external adapter, and
:mod:`cadrumo.domain.calculations.registry`.

Each bound (age cutoff, count cap, byte ceiling) is pinned alone and then
composed. The ``combine="union"`` mode and
``protect_newest`` are pinned directly here because they are the two
correctness-critical axes the real callers (session telemetry; the
run-trace size ceiling) depend on: a wrong default on either would silently
change which files survive a real prune with no other test catching it.
"""

from __future__ import annotations

import pytest

from ..paths import select_filesystem_retention_survivors

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _entry(name: str, ts: int, size: int = 0) -> tuple[str, int, int]:
    return (name, ts, size)


def _names(pairs: list[tuple[str, int, int]]) -> set[str]:
    return {pair[0] for pair in pairs}


def _timestamp(pair: tuple[str, int, int]) -> int:
    return pair[1]


def _size(pair: tuple[str, int, int]) -> int:
    return pair[2]


# --------------------------------------------------------------------- #
# Validation                                                             #
# --------------------------------------------------------------------- #


def test_requires_at_least_one_bound() -> None:
    with pytest.raises(ValueError, match="at least one"):
        select_filesystem_retention_survivors([_entry("a", 1)], timestamp=_timestamp)


def test_max_total_bytes_requires_size_fn() -> None:
    with pytest.raises(ValueError, match="size_fn"):
        select_filesystem_retention_survivors(
            [_entry("a", 1)],
            timestamp=_timestamp,
            max_total_bytes=10,
        )


def test_union_does_not_support_max_total_bytes() -> None:
    with pytest.raises(ValueError, match="union"):
        select_filesystem_retention_survivors(
            [_entry("a", 1, 5)],
            timestamp=_timestamp,
            max_total_bytes=10,
            size_fn=_size,
            combine="union",
        )


# --------------------------------------------------------------------- #
# Each bound alone (sequential, the default)                            #
# --------------------------------------------------------------------- #


def test_cutoff_alone_removes_only_expired_entries() -> None:
    entries = [_entry("fresh", 10), _entry("stale", 1)]

    keep, remove = select_filesystem_retention_survivors(entries, timestamp=_timestamp, cutoff=5)

    assert _names(keep) == {"fresh"}
    assert _names(remove) == {"stale"}


def test_cutoff_boundary_is_exclusive() -> None:
    """An entry exactly at the cutoff survives; strictly older is removed."""
    entries = [_entry("at_cutoff", 5), _entry("just_older", 4)]

    keep, remove = select_filesystem_retention_survivors(entries, timestamp=_timestamp, cutoff=5)

    assert _names(keep) == {"at_cutoff"}
    assert _names(remove) == {"just_older"}


def test_max_count_alone_keeps_the_newest_n() -> None:
    entries = [_entry(f"e{i}", i) for i in range(5)]  # e4 newest .. e0 oldest

    keep, remove = select_filesystem_retention_survivors(entries, timestamp=_timestamp, max_count=2)

    assert _names(keep) == {"e4", "e3"}
    assert _names(remove) == {"e0", "e1", "e2"}


def test_max_total_bytes_alone_removes_oldest_first_until_it_fits() -> None:
    entries = [_entry("oldest", 1, 100), _entry("middle", 2, 100), _entry("newest", 3, 100)]

    keep, remove = select_filesystem_retention_survivors(
        entries,
        timestamp=_timestamp,
        max_total_bytes=210,
        size_fn=_size,
    )

    assert _names(remove) == {"oldest"}
    assert _names(keep) == {"middle", "newest"}


# --------------------------------------------------------------------- #
# Composed bounds (sequential)                                          #
# --------------------------------------------------------------------- #


def test_cutoff_then_max_count_composed() -> None:
    entries = [
        _entry("expired", 1),
        _entry("survivor_a", 10),
        _entry("survivor_b", 11),
        _entry("survivor_c", 12),
    ]

    keep, remove = select_filesystem_retention_survivors(
        entries,
        timestamp=_timestamp,
        cutoff=5,
        max_count=2,
    )

    # cutoff removes "expired" first; the count cap then keeps only the
    # newest two of the three survivors.
    assert _names(remove) == {"expired", "survivor_a"}
    assert _names(keep) == {"survivor_b", "survivor_c"}


def test_cutoff_then_bytes_composed_mirrors_run_trace_shape() -> None:
    entries = [
        _entry("expired", 1, 5000),
        _entry("oldest", 10, 1000),
        _entry("middle", 11, 1000),
        _entry("newest", 12, 1000),
    ]

    keep, remove = select_filesystem_retention_survivors(
        entries,
        timestamp=_timestamp,
        cutoff=5,
        max_total_bytes=2100,
        size_fn=_size,
        protect_newest=1,
    )

    assert _names(remove) == {"expired", "oldest"}
    assert _names(keep) == {"middle", "newest"}


# --------------------------------------------------------------------- #
# protect_newest                                                        #
# --------------------------------------------------------------------- #


def test_protect_newest_survives_a_byte_ceiling_it_alone_exceeds() -> None:
    """The run-trace 'never size-prune the newest' rule, pinned directly."""
    entries = [_entry("older", 1, 500), _entry("newest", 2, 5000)]

    keep, remove = select_filesystem_retention_survivors(
        entries,
        timestamp=_timestamp,
        max_total_bytes=100,
        size_fn=_size,
        protect_newest=1,
    )

    assert _names(remove) == {"older"}
    assert _names(keep) == {"newest"}


def test_protect_newest_counts_toward_the_byte_total() -> None:
    """A protected entry's bytes still count when deciding whether to prune others."""
    entries = [_entry("prunable", 1, 100), _entry("newest", 2, 100)]

    # Ceiling of 150: without the protected entry's 100 bytes counted, the
    # single prunable entry alone (100) would already fit and nothing would
    # be removed. With it counted (200 total), the prunable entry is pruned.
    keep, remove = select_filesystem_retention_survivors(
        entries,
        timestamp=_timestamp,
        max_total_bytes=150,
        size_fn=_size,
        protect_newest=1,
    )

    assert _names(remove) == {"prunable"}
    assert _names(keep) == {"newest"}


def test_protect_newest_single_entry_is_never_a_removal_candidate() -> None:
    entries = [_entry("only", 1, 5000)]

    keep, remove = select_filesystem_retention_survivors(
        entries,
        timestamp=_timestamp,
        max_total_bytes=1,
        size_fn=_size,
        protect_newest=1,
    )

    assert _names(keep) == {"only"}
    assert remove == []


# --------------------------------------------------------------------- #
# combine="union" -- the session-telemetry disjunction                   #
# --------------------------------------------------------------------- #


def test_union_removes_an_entry_matching_either_bound() -> None:
    """Rank-3 within the age window is still removed for being beyond the count bound."""
    entries = [_entry(f"s{i}", 10 - i) for i in range(6)]  # s0 newest .. s5 oldest

    keep, remove = select_filesystem_retention_survivors(
        entries,
        timestamp=_timestamp,
        cutoff=0,  # none are old enough to expire by age alone
        max_count=3,
        combine="union",
    )

    assert _names(keep) == {"s0", "s1", "s2"}
    assert _names(remove) == {"s3", "s4", "s5"}


def test_union_age_bound_bites_independently_of_rank() -> None:
    entries = [_entry("fresh", 10), _entry("stale", 1)]

    keep, remove = select_filesystem_retention_survivors(
        entries,
        timestamp=_timestamp,
        cutoff=5,
        max_count=100,  # count bound is slack; only age bites
        combine="union",
    )

    assert _names(keep) == {"fresh"}
    assert _names(remove) == {"stale"}


def test_union_protect_newest_survives_even_when_every_bound_is_violated() -> None:
    """Pin the session-telemetry contract: keep_newest wins over both bounds."""
    entries = [_entry(f"s{i}", 100 - i) for i in range(6)]  # all "stale", s0 least stale

    keep, remove = select_filesystem_retention_survivors(
        entries,
        timestamp=_timestamp,
        cutoff=1000,  # every entry is older than this cutoff -> all "expired"
        max_count=1,  # and the count bound alone would keep only s0
        combine="union",
        protect_newest=3,
    )

    assert _names(keep) == {"s0", "s1", "s2"}
    assert _names(remove) == {"s3", "s4", "s5"}


def test_union_protect_newest_occupies_rank_slots_in_the_count_bound() -> None:
    """The count bound's rank threshold is global, not counted only over non-protected entries.

    This is the exact shape ``test_prune_bounds_session_count_dropping_the_oldest``
    in the session telemetry suite depends on: with ``max_count=5`` and
    ``protect_newest=2``, only 5 total survive (not 5 *plus* the 2
    protected) -- the protected entries occupy ranks 0 and 1 within the
    count bound, they are not additive to it.
    """
    entries = [_entry(f"s{i}", 9 - i) for i in range(10)]  # s0 newest .. s9 oldest

    keep, remove = select_filesystem_retention_survivors(
        entries,
        timestamp=_timestamp,
        cutoff=-1000,  # generous; age never bites
        max_count=5,
        combine="union",
        protect_newest=2,
    )

    assert _names(keep) == {"s0", "s1", "s2", "s3", "s4"}
    assert _names(remove) == {"s5", "s6", "s7", "s8", "s9"}


# --------------------------------------------------------------------- #
# Tie-break: caller pre-sort order survives a timestamp tie             #
# --------------------------------------------------------------------- #


def test_stable_sort_preserves_input_order_among_timestamp_ties() -> None:
    """Equal timestamps keep their relative input order (a stable sort).

    A caller wanting a secondary tie-break (e.g. filename) pre-sorts its
    input list by that key; ranking here by timestamp alone then preserves
    it for ties, exactly as the session telemetry ``(mtime, name)`` tie-break
    needs.
    """
    entries = [_entry("b_first_in_input", 5), _entry("a_second_in_input", 5)]

    keep, remove = select_filesystem_retention_survivors(entries, timestamp=_timestamp, max_count=1)

    assert _names(keep) == {"b_first_in_input"}
    assert _names(remove) == {"a_second_in_input"}
