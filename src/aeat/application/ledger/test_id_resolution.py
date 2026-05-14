"""Tests for transaction-id prefix resolution and display-id width."""

from __future__ import annotations

import pytest

from ...domain.transactions import TransactionIdPrefixError
from ._id_resolution import (
    MINIMUM_DISPLAY_ID_WIDTH,
    compute_display_id_width,
    resolve_transaction_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_ID_A = "a" * 64
_ID_B = "b" * 64
_ID_AA = "a" + "0" * 63
_ID_AB = "a" + "1" * 63


def test_display_id_width_floors_at_minimum_for_empty_bucket() -> None:
    assert compute_display_id_width([]) == MINIMUM_DISPLAY_ID_WIDTH


def test_display_id_width_floors_at_minimum_for_well_separated_ids() -> None:
    assert compute_display_id_width([_ID_A, _ID_B]) == MINIMUM_DISPLAY_ID_WIDTH


def test_display_id_width_grows_when_minimum_collides() -> None:
    # _ID_A and _ID_AA share the first character "a"; their first 8 chars
    # are "aaaaaaaa" and "a0000000". They diverge at character 2 (index 1),
    # so width must be at least 2 to keep them unique. Since
    # MINIMUM_DISPLAY_ID_WIDTH=8 already separates them, width stays at 8.
    assert compute_display_id_width([_ID_A, _ID_AA]) == MINIMUM_DISPLAY_ID_WIDTH


def test_display_id_width_grows_when_ids_share_long_prefix() -> None:
    shared = "c" * 12
    a = shared + "1" * 52
    b = shared + "2" * 52
    # First 12 chars collide; first 13 diverge. With floor of 8 the
    # computed width must rise to 13.
    assert compute_display_id_width([a, b]) == 13


def test_resolve_full_id_passes_through() -> None:
    assert resolve_transaction_id(_ID_A, [_ID_A, _ID_B]) == _ID_A


def test_resolve_unique_prefix_resolves() -> None:
    assert resolve_transaction_id("a", [_ID_A, _ID_B]) == _ID_A


def test_resolve_ambiguous_prefix_refuses_with_collisions_listed() -> None:
    with pytest.raises(TransactionIdPrefixError) as exc_info:
        resolve_transaction_id("a", [_ID_A, _ID_AA, _ID_AB])
    message = str(exc_info.value)
    assert _ID_A in message
    assert _ID_AA in message
    assert _ID_AB in message
    assert "matches 3 transactions" in message


def test_resolve_no_match_refuses() -> None:
    with pytest.raises(TransactionIdPrefixError):
        resolve_transaction_id("deadbeef", [_ID_A, _ID_B])


def test_resolve_empty_prefix_refuses() -> None:
    with pytest.raises(TransactionIdPrefixError):
        resolve_transaction_id("", [_ID_A])


def test_resolve_non_hex_prefix_refuses() -> None:
    with pytest.raises(TransactionIdPrefixError):
        resolve_transaction_id("xyz", [_ID_A])


def test_resolve_prefix_is_case_insensitive_on_input() -> None:
    assert resolve_transaction_id(_ID_A.upper(), [_ID_A]) == _ID_A
