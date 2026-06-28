"""Pin behavioural invariants of the shared group_and_collect_names helper."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from .._grouping import group_and_collect_names

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class _Obs:
    """Minimal test record covering all helper-relevant fields."""

    source_kind: str
    nif: str
    kind: str
    name: str | None


def _name(obs: _Obs) -> str | None:
    return obs.name


def _group_key(obs: _Obs) -> tuple[str, str, str]:
    return (obs.source_kind, obs.nif, obs.kind)


def _identity_key(obs: _Obs) -> tuple[str, str]:
    return (obs.source_kind, obs.nif)


def test_group_and_collect_names_buckets_by_composite_key() -> None:
    observations = (
        _Obs("ledger", "A", "k1", "Alpha"),
        _Obs("ledger", "A", "k1", "Alpha"),
        _Obs("ledger", "A", "k2", "Alpha"),
        _Obs("ledger", "B", "k1", "Beta"),
    )
    grouped, _ = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert set(grouped.keys()) == {
        ("ledger", "A", "k1"),
        ("ledger", "A", "k2"),
        ("ledger", "B", "k1"),
    }
    assert len(grouped[("ledger", "A", "k1")]) == 2
    assert len(grouped[("ledger", "A", "k2")]) == 1
    assert len(grouped[("ledger", "B", "k1")]) == 1


def test_group_and_collect_names_preserves_iteration_order_within_bucket() -> None:
    first = _Obs("ledger", "A", "k1", "Alpha")
    second = _Obs("ledger", "A", "k1", "Alpha-2nd")
    third = _Obs("ledger", "A", "k1", "Alpha-3rd")
    grouped, _ = group_and_collect_names(
        (first, second, third),
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert grouped[("ledger", "A", "k1")] == [first, second, third]


def test_group_and_collect_names_first_non_empty_name_wins() -> None:
    observations = (
        _Obs("ledger", "A", "k1", None),
        _Obs("ledger", "A", "k1", "First Real Name"),
        _Obs("ledger", "A", "k1", "Later Name"),
    )
    _, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names[("ledger", "A")] == "First Real Name"


def test_group_and_collect_names_skips_empty_names_without_clearing_prior_win() -> None:
    observations = (
        _Obs("ledger", "A", "k1", "Real Name"),
        _Obs("ledger", "A", "k1", ""),
        _Obs("ledger", "A", "k1", None),
    )
    _, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names[("ledger", "A")] == "Real Name"


def test_group_and_collect_names_separate_identities_get_separate_names() -> None:
    observations = (
        _Obs("ledger", "A", "k1", "Alpha"),
        _Obs("ledger", "B", "k1", "Beta"),
        _Obs("invoice", "A", "k1", "Alpha-Invoice"),
    )
    _, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names == {
        ("ledger", "A"): "Alpha",
        ("ledger", "B"): "Beta",
        ("invoice", "A"): "Alpha-Invoice",
    }


def test_group_and_collect_names_empty_iterable_returns_empty_maps() -> None:
    grouped, names = group_and_collect_names(
        (),
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert grouped == {}
    assert names == {}


def test_group_and_collect_names_identity_subset_of_group_key_is_consistent() -> None:
    # When two different group keys share the same identity key (e.g.
    # same (source, nif) but different kind), the name cache must be
    # consistent — first non-empty name wins regardless of which group
    # observed it.
    observations = (
        _Obs("ledger", "A", "k1", None),
        _Obs("ledger", "A", "k2", "Name From K2"),
        _Obs("ledger", "A", "k1", "Name From K1"),
    )
    grouped, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names[("ledger", "A")] == "Name From K2"
    assert len(grouped[("ledger", "A", "k1")]) == 2
    assert len(grouped[("ledger", "A", "k2")]) == 1
