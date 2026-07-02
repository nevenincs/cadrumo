"""Core casilla-id primitive tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .. import validated_casilla_id, validated_casilla_id_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_validated_casilla_id_rejects_non_string_values_without_coercion() -> None:
    for value, error_match in (
        (1, r"example 1 is not a canonical casilla\.id"),
        (b"01", r"example b'01' is not a canonical casilla\.id"),
    ):
        with pytest.raises(ValueError, match=error_match):
            validated_casilla_id(value, surface="example")


def test_validated_casilla_id_map_rejects_non_string_keys_and_preserves_canonical_keys() -> None:
    with pytest.raises(ValueError, match=r"fixture key b'01' is not a canonical casilla\.id"):
        validated_casilla_id_map({b"01": Decimal("1")}, surface="fixture")

    assert validated_casilla_id_map({"DP200014B:00599": Decimal("1.25")}, surface="fixture") == {
        "DP200014B:00599": Decimal("1.25"),
    }
