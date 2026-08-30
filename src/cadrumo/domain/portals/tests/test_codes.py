"""Unit tests for :class:`cadrumo.domain.portals.Portal`."""

from __future__ import annotations

import pytest

from ..codes import Portal

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_portal_has_exactly_41_members() -> None:
    """Membership is fixed at exactly 41 portals."""
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
    with pytest.raises(ValueError, match=r"Portal|not a valid|not_a_portal"):
        Portal("not_a_portal")
