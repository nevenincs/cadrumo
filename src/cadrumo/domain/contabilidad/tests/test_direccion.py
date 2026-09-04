"""Direction/sign separation for contabilidad amounts."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..direccion import ContabilidadDireccion

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_sign_projection_matches_the_debit_credit_convention() -> None:
    assert ContabilidadDireccion.DEBE.sign == 1
    assert ContabilidadDireccion.HABER.sign == -1


def test_opposite_is_involutive() -> None:
    for direccion in ContabilidadDireccion:
        assert direccion.opposite.opposite is direccion
        assert direccion.opposite is not direccion


def test_magnitude_times_sign_nets_a_balanced_pair_to_zero() -> None:
    """A magnitude plus a direction reproduces signed arithmetic without a signed store."""
    magnitude = Decimal("1250.00")

    net = magnitude * ContabilidadDireccion.DEBE.sign + magnitude * ContabilidadDireccion.HABER.sign

    assert net == Decimal("0")


def test_direction_is_a_stable_transport_token() -> None:
    """The stored value is the lowercase token, not a locale-facing label."""
    assert ContabilidadDireccion.DEBE.value == "debe"
    assert ContabilidadDireccion.HABER.value == "haber"
    assert ContabilidadDireccion("haber") is ContabilidadDireccion.HABER


def test_the_enum_is_closed() -> None:
    assert {d.value for d in ContabilidadDireccion} == {"debe", "haber"}
    with pytest.raises(ValueError):
        ContabilidadDireccion("credit")
