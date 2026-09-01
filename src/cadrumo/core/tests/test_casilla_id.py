"""Core casilla-id primitive tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ...domain.calculations import registry
from ..casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_casilla_id_capabilities_have_exactly_one_owning_module() -> None:
    """One definition, at its own module, not re-declared by the registry.

    This also asserted membership in the ``cadrumo.core`` facade's ``__all__``.
    That facade is now an inert namespace, so the assertion is dropped rather
    than relaxed: what it protected -- a single owning module, and no rival
    definition in the registry -- is asserted here directly and is the part
    that bites.
    """
    canonical_capabilities = {
        "CasillaId": CasillaId,
        "validated_casilla_id": validated_casilla_id,
        "validated_casilla_id_map": validated_casilla_id_map,
    }

    for name, capability in canonical_capabilities.items():
        assert capability.__module__ == "cadrumo.core.casilla_id"
        assert not hasattr(registry, name)
        assert name not in registry.__all__


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
