"""Focused dev-tool tests for _parity_tapes._diff_paths.

The recursive diff walker is the correctness gate for parity-tape
replay verification: `replay_parity_tape` compares the stored
`ParityTape` against a freshly-recomputed tape via this function,
and any returned path is treated as a regression. If the walker
silently mishandled missing-key, length-mismatch, or path-prefix
construction, diverged tapes would replay green and the workbook-
parity-as-AEAT-oracle invariant would erode without anyone noticing.

Tests here are structural / algorithmic — they fix the contract of
the diff walker, not any calculation result.
"""

from __future__ import annotations

import pytest

from ..parity._parity_tapes import _diff_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_diff_paths_returns_empty_for_identical_scalars() -> None:
    for value in (5, "abc", None):
        assert _diff_paths(value, value) == (), value


def test_diff_paths_returns_empty_for_identical_dicts() -> None:
    payload = {"a": 1, "b": [2, 3], "c": {"d": "e"}}
    assert _diff_paths(payload, payload) == ()


def test_diff_paths_reports_scalar_inequality() -> None:
    cases = (
        ("", ": 1 != 2"),
        ("report.value", "report.value: 1 != 2"),
    )

    for prefix, expected in cases:
        assert _diff_paths(1, 2, prefix) == (expected,), prefix


def test_diff_paths_top_level_dict_keys_have_no_leading_dot() -> None:
    """At the top level (empty prefix), dict keys appear as `key` not `.key`."""
    diff = _diff_paths({"value": 1}, {"value": 2})

    assert diff == ("value: 1 != 2",)


def test_diff_paths_nested_dict_keys_use_dot_separator() -> None:
    diff = _diff_paths({"outer": {"inner": 1}}, {"outer": {"inner": 2}})

    assert diff == ("outer.inner: 1 != 2",)


def test_diff_paths_reports_key_missing_from_one_side() -> None:
    """The convention: `left` is the stored tape, `right` is current."""
    cases = (
        ({}, {"value": 1}, "value: missing from stored tape"),
        ({"value": 1}, {}, "value: missing from current tape"),
    )

    for stored, current, expected in cases:
        assert _diff_paths(stored, current) == (expected,), expected


def test_diff_paths_reports_asymmetric_keys_in_sorted_order() -> None:
    """Keys are walked in sorted union order so diff output is deterministic."""
    diff = _diff_paths({"a": 1, "c": 3}, {"b": 2, "c": 3})

    assert diff == (
        "a: missing from current tape",
        "b: missing from stored tape",
    )


def test_diff_paths_reports_list_length_mismatch_at_top_level() -> None:
    """An empty-prefix top-level list emits `: length differs (...)`."""
    diff = _diff_paths([1, 2, 3], [1, 2])

    assert diff[0] == ": length differs (3 != 2)"


def test_diff_paths_walks_list_positionally_with_index_brackets() -> None:
    diff = _diff_paths([{"id": 1}, {"id": 2}], [{"id": 1}, {"id": 3}])

    assert diff == ("[1].id: 2 != 3",)


def test_diff_paths_zips_to_shorter_length_after_reporting_mismatch() -> None:
    """When lengths differ, the walker still recurses over zip (no strict);
    extra elements in the longer side are silently dropped from positional
    diff because they have no peer to compare against."""
    diff = _diff_paths([1, 2, 3], [1, 9])

    assert diff == (
        ": length differs (3 != 2)",
        "[1]: 2 != 9",
    )


def test_diff_paths_tracks_mixed_dict_of_list_of_dict_paths() -> None:
    """Real parity tapes nest dicts inside lists inside dicts (e.g. the
    report.diff structure). Path tracking must compose `key[index].key`."""
    stored = {"report": {"diff": [{"field": "casilla-01", "value": 100}]}}
    current = {"report": {"diff": [{"field": "casilla-01", "value": 200}]}}

    diff = _diff_paths(stored, current)

    assert diff == ("report.diff[0].value: 100 != 200",)


def test_diff_paths_returns_empty_for_empty_containers() -> None:
    for stored, current in (({}, {}), ([], [])):
        assert _diff_paths(stored, current) == (), (stored, current)


def test_diff_paths_distinguishes_dict_vs_list_at_the_same_path() -> None:
    """A node that is a dict on one side and a list on the other falls
    through to the scalar-inequality branch (neither both-dicts nor
    both-lists holds), producing a single inequality report."""
    diff = _diff_paths({"node": {"a": 1}}, {"node": [1, 2]})

    assert len(diff) == 1
    assert diff[0].startswith("node: ")
