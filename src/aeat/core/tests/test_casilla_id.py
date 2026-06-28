"""Core casilla-id primitive tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .. import validated_casilla_id, validated_casilla_id_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_validated_casilla_id_rejects_non_string_values_without_coercion() -> None:
    with pytest.raises(ValueError, match=r"example 1 is not a canonical casilla\.id"):
        validated_casilla_id(1, surface="example")

    with pytest.raises(ValueError, match=r"example b'01' is not a canonical casilla\.id"):
        validated_casilla_id(b"01", surface="example")


def test_validated_casilla_id_map_rejects_non_string_keys_without_coercion() -> None:
    with pytest.raises(ValueError, match=r"fixture key b'01' is not a canonical casilla\.id"):
        validated_casilla_id_map({b"01": Decimal("1")}, surface="fixture")


def test_validated_casilla_id_map_preserves_canonical_string_keys() -> None:
    assert validated_casilla_id_map({"DP200014B:00599": Decimal("1.25")}, surface="fixture") == {
        "DP200014B:00599": Decimal("1.25"),
    }
