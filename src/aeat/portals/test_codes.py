"""Unit tests for :class:`aeat.portals.Portal`."""

from __future__ import annotations

import pytest

from aeat.portals._codes import Portal

pytestmark = pytest.mark.unit


def test_portal_has_exactly_41_members() -> None:
    """Membership is fixed at 41 (ADR §2)."""
    assert len(list(Portal)) == 41


def test_portal_values_are_member_names_lowercased() -> None:
    """Every member's value equals its name in lowercase."""
    for member in Portal:
        assert member.value == member.name.lower()


def test_portal_values_are_unique() -> None:
    """No duplicate values across members."""
    values = [m.value for m in Portal]
    assert len(values) == len(set(values))


def test_portal_roundtrip_from_string() -> None:
    """``Portal(value)`` round-trips every member."""
    for member in Portal:
        assert Portal(member.value) is member


def test_portal_unknown_string_raises() -> None:
    """Unknown values raise :class:`ValueError`."""
    with pytest.raises(ValueError):
        Portal("not_a_portal")
