"""Ajuste extracontable shape rules, keyed on permanente vs temporaria."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..ajuste import AjusteClase, AjusteDireccion, AjusteExtracontable

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _permanente(**kw: object) -> AjusteExtracontable:
    base: dict[str, object] = {
        "clase": AjusteClase.PERMANENTE,
        "direccion": AjusteDireccion.AUMENTO,
        "origen_ejercicio_amount": Decimal("150"),
    }
    return AjusteExtracontable(**(base | kw))


def _temporaria(**kw: object) -> AjusteExtracontable:
    base: dict[str, object] = {
        "clase": AjusteClase.TEMPORARIA,
        "direccion": AjusteDireccion.AUMENTO,
        "origen_ejercicio_amount": Decimal("1000"),
        "pendiente_inicio_amount": Decimal("0"),
        "pendiente_fin_amount": Decimal("1000"),
    }
    return AjusteExtracontable(**(base | kw))


def test_a_permanent_correction_carries_no_pending_balance() -> None:
    ajuste = _permanente()

    assert not ajuste.carries_pending_balance
    assert ajuste.pendiente_inicio_amount is None
    assert ajuste.pendiente_fin_amount is None
    assert ajuste.period_amount == Decimal("150")


def test_a_permanent_correction_with_a_pending_balance_is_refused() -> None:
    """The detector tooth for the Manual's 'No podra cumplimentarse' rule."""
    with pytest.raises(ValidationError, match="never reverses"):
        _permanente(pendiente_fin_amount=Decimal("0"))


def test_a_permanent_correction_cannot_arise_from_an_earlier_ejercicio() -> None:
    with pytest.raises(ValidationError, match="no balance to carry forward"):
        _permanente(origen_anterior_amount=Decimal("50"))


def test_a_zero_pending_balance_is_not_the_same_as_no_pending_balance() -> None:
    """A temporaria whose balance is nil still has one; a permanente has none."""
    temporaria = _temporaria(
        origen_ejercicio_amount=Decimal("0"), pendiente_fin_amount=Decimal("0")
    )

    assert temporaria.pendiente_inicio_amount == Decimal("0")
    assert temporaria.carries_pending_balance
    assert _permanente().pendiente_inicio_amount is None


def test_a_temporary_correction_must_state_both_pending_balances() -> None:
    with pytest.raises(ValidationError, match="must state both pending balances"):
        AjusteExtracontable(
            clase=AjusteClase.TEMPORARIA,
            direccion=AjusteDireccion.AUMENTO,
            origen_ejercicio_amount=Decimal("100"),
            pendiente_inicio_amount=Decimal("0"),
        )


def test_a_reversal_may_not_exceed_the_balance_it_reverses() -> None:
    with pytest.raises(ValidationError, match="cannot exceed the pending balance"):
        _temporaria(
            origen_ejercicio_amount=Decimal("0"),
            origen_anterior_amount=Decimal("500"),
            pendiente_inicio_amount=Decimal("300"),
            pendiente_fin_amount=Decimal("0"),
        )


def test_a_reversal_within_the_balance_is_accepted() -> None:
    ajuste = _temporaria(
        direccion=AjusteDireccion.DISMINUCION,
        origen_ejercicio_amount=Decimal("0"),
        origen_anterior_amount=Decimal("300"),
        pendiente_inicio_amount=Decimal("1000"),
        pendiente_fin_amount=Decimal("700"),
    )

    assert ajuste.period_amount == Decimal("300")
    assert ajuste.direccion is AjusteDireccion.DISMINUCION


def test_both_directions_are_expressible_for_either_clase() -> None:
    assert _permanente(direccion=AjusteDireccion.DISMINUCION).direccion is (
        AjusteDireccion.DISMINUCION
    )
    assert _temporaria().direccion is AjusteDireccion.AUMENTO


def test_negative_amounts_are_refused() -> None:
    with pytest.raises(ValidationError):
        _permanente(origen_ejercicio_amount=Decimal("-1"))
