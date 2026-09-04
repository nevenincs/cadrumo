"""Trial-balance line and set invariants."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..cuenta import CuentaPgc
from ..direccion import ContabilidadDireccion
from ..saldo import SaldoCuenta, SumasYSaldos

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

DEBE = ContabilidadDireccion.DEBE
HABER = ContabilidadDireccion.HABER


def _linea(
    cuenta: str,
    opening: str = "0",
    opening_dir: ContabilidadDireccion = DEBE,
    debe: str = "0",
    haber: str = "0",
    closing: str | None = None,
    closing_dir: ContabilidadDireccion | None = None,
) -> SaldoCuenta:
    signed = Decimal(opening) * opening_dir.sign + Decimal(debe) - Decimal(haber)
    if closing is None:
        closing = str(abs(signed))
        closing_dir = DEBE if signed >= 0 else HABER
    return SaldoCuenta(
        cuenta=CuentaPgc(cuenta),
        opening_amount=Decimal(opening),
        opening_direccion=opening_dir,
        debe_amount=Decimal(debe),
        haber_amount=Decimal(haber),
        closing_amount=Decimal(closing),
        closing_direccion=closing_dir or DEBE,
    )


def test_closing_follows_from_opening_and_movements() -> None:
    linea = _linea("430", opening="1000", debe="500", haber="200")

    assert linea.signed_opening == Decimal("1000")
    assert linea.signed_closing == Decimal("1300")
    assert linea.closing_direccion is DEBE


def test_a_credit_balance_is_a_magnitude_plus_a_direction() -> None:
    """No negative number is stored; HABER carries the direction."""
    linea = _linea("100", opening="3000", opening_dir=HABER)

    assert linea.opening_amount == Decimal("3000")
    assert linea.signed_opening == Decimal("-3000")


def test_movements_can_flip_a_balance_across_sides() -> None:
    linea = _linea("572", opening="100", opening_dir=DEBE, haber="400")

    assert linea.closing_direccion is HABER
    assert linea.closing_amount == Decimal("300")


def test_an_inconsistent_closing_balance_is_refused() -> None:
    with pytest.raises(ValidationError, match="does not follow from"):
        SaldoCuenta(
            cuenta=CuentaPgc("430"),
            opening_amount=Decimal("1000"),
            opening_direccion=DEBE,
            debe_amount=Decimal("500"),
            haber_amount=Decimal("0"),
            closing_amount=Decimal("1400"),
            closing_direccion=DEBE,
        )


def test_a_zero_balance_may_not_claim_the_haber_side() -> None:
    with pytest.raises(ValidationError, match="canonical"):
        SaldoCuenta(
            cuenta=CuentaPgc("430"),
            opening_amount=Decimal("0"),
            opening_direccion=HABER,
            debe_amount=Decimal("0"),
            haber_amount=Decimal("0"),
            closing_amount=Decimal("0"),
            closing_direccion=DEBE,
        )


def test_negative_magnitudes_are_refused() -> None:
    with pytest.raises(ValidationError):
        SaldoCuenta(
            cuenta=CuentaPgc("430"),
            opening_amount=Decimal("-1"),
            opening_direccion=DEBE,
            debe_amount=Decimal("0"),
            haber_amount=Decimal("0"),
            closing_amount=Decimal("-1"),
            closing_direccion=DEBE,
        )


def test_a_squared_trial_balance_reports_cuadrado() -> None:
    balance = SumasYSaldos(
        ejercicio=2025,
        lineas=(
            _linea("572", opening="1000", debe="400"),
            _linea("700", opening="0", haber="400"),
        ),
    )

    assert balance.total_debe == Decimal("400")
    assert balance.total_haber == Decimal("400")
    assert balance.is_cuadrado


def test_an_unsquared_trial_balance_constructs_but_reports_it() -> None:
    """Refusing construction would leave an operator unable to see the defect."""
    balance = SumasYSaldos(ejercicio=2025, lineas=(_linea("572", debe="400"),))

    assert not balance.is_cuadrado


def test_duplicate_cuentas_are_refused() -> None:
    with pytest.raises(ValidationError, match="unique"):
        SumasYSaldos(
            ejercicio=2025,
            lineas=(_linea("572", debe="100"), _linea("572", debe="200")),
        )


def test_a_populated_resultado_del_ejercicio_is_refused() -> None:
    """The detector tooth for D1's pre-close rule.

    A trial balance carrying a closing balance on 129 was exported after the
    asiento de cierre; deriving the estados contables from it double-counts the
    period result.
    """
    with pytest.raises(ValidationError, match="after the asiento de cierre"):
        SumasYSaldos(
            ejercicio=2025,
            lineas=(_linea("129", opening="0", haber="5000"),),
        )


def test_a_subaccount_of_129_is_also_refused() -> None:
    with pytest.raises(ValidationError, match="after the asiento de cierre"):
        SumasYSaldos(
            ejercicio=2025,
            lineas=(_linea("1290", opening="0", haber="5000"),),
        )


def test_an_empty_129_line_is_accepted() -> None:
    balance = SumasYSaldos(ejercicio=2025, lineas=(_linea("129"),))

    assert balance.lineas[0].closing_amount == Decimal("0")
