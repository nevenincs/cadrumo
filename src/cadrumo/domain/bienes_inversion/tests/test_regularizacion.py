"""LIVA art-107/109 single-good annual regularización compute.

Expected values are the load-bearing regulatory figures read verbatim from the
bundled consolidated LIVA corpus — the over-10-point gate (art. 107.Uno "una
diferencia superior a diez puntos"), the /5 and /10 divisors (art. 109.3.º "se
dividirá por cinco o … por diez"), and the 4/9-year windows (art. 107.Uno / .Tres)
— together with worked cases whose arithmetic is derived term by term from the
art-109 ordinal procedure, not by re-running the function under test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.external_constants import (
    IVA_BIEN_INVERSION_INMUEBLE_DIVISOR,
    IVA_BIEN_INVERSION_MUEBLE_DIVISOR,
    IVA_BIEN_INVERSION_REGULARIZACION_UMBRAL_PUNTOS,
)
from ..register import (
    BienInversionKind,
    BienInversionValidationError,
    RegularizacionDireccion,
    compute_regularizacion_anual,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_corpus_constants_match_verbatim_liva_text() -> None:
    """The gate and divisors equal the figures the BOE corpus states.

    art. 107.Uno: "una diferencia superior a diez puntos" → 10.
    art. 109.3.º: "se dividirá por cinco o … por diez" → 5 (mueble) / 10 (inmueble).
    """
    assert Decimal("10") == IVA_BIEN_INVERSION_REGULARIZACION_UMBRAL_PUNTOS
    assert Decimal("5") == IVA_BIEN_INVERSION_MUEBLE_DIVISOR
    assert Decimal("10") == IVA_BIEN_INVERSION_INMUEBLE_DIVISOR
    assert BienInversionKind.MUEBLE.divisor == Decimal("5")
    assert BienInversionKind.INMUEBLE.divisor == Decimal("10")
    assert BienInversionKind.MUEBLE.ventana_anos == 4
    assert BienInversionKind.INMUEBLE.ventana_anos == 9


def test_movable_good_prorrata_drop_yields_ingreso_complementario() -> None:
    """Worked case derived step-by-step from the art-109 procedure (mueble).

    Inputs: cuota soportada 12.600,00 €; acquisition-year definitive prorrata 70 %;
    regularisation-year definitive prorrata 50 % (a 20-point drop, > 10 → gate fires).

    art-109.1.º deducción que procedería = 12.600 × 50 % = 6.300,00.
    art-109.2.º deducción efectuada (acquisition year) = 12.600 × 70 % = 8.820,00;
                difference = 8.820,00 − 6.300,00 = 2.520,00.
    art-109.3.º ÷ 5 (mueble) = 504,00 → ingreso complementario (positive).
    """
    result = compute_regularizacion_anual(
        cuota_soportada=Decimal("12600.00"),
        prorrata_inicial_pct=Decimal("70"),
        prorrata_anio_pct=Decimal("50"),
        kind=BienInversionKind.MUEBLE,
    )
    assert result.aplica is True
    assert result.diferencia_puntos == Decimal("20")
    assert result.divisor == Decimal("5")
    assert result.importe == Decimal("504.00")
    assert result.direccion is RegularizacionDireccion.INGRESO


def test_real_estate_good_uses_the_ten_divisor() -> None:
    """Same inputs on an inmueble apply the /10 divisor (art-109.3.º).

    2.520,00 ÷ 10 = 252,00 → ingreso complementario.
    """
    result = compute_regularizacion_anual(
        cuota_soportada=Decimal("12600.00"),
        prorrata_inicial_pct=Decimal("70"),
        prorrata_anio_pct=Decimal("50"),
        kind=BienInversionKind.INMUEBLE,
    )
    assert result.aplica is True
    assert result.divisor == Decimal("10")
    assert result.importe == Decimal("252.00")
    assert result.direccion is RegularizacionDireccion.INGRESO


def test_prorrata_rise_yields_deduccion_complementaria() -> None:
    """A rise in the definitive percentage is a negative quotient (deducción).

    cuota 12.600,00; acquisition 50 %, regularisation 75 % (25-point rise).
    efectuada = 6.300,00; procedería = 9.450,00; difference = −3.150,00; ÷ 5 = −630,00.
    """
    result = compute_regularizacion_anual(
        cuota_soportada=Decimal("12600.00"),
        prorrata_inicial_pct=Decimal("50"),
        prorrata_anio_pct=Decimal("75"),
        kind=BienInversionKind.MUEBLE,
    )
    assert result.aplica is True
    assert result.importe == Decimal("-630.00")
    assert result.direccion is RegularizacionDireccion.DEDUCCION


def test_exactly_ten_points_does_not_regularise() -> None:
    """The gate is STRICT: 10 points is not "superior a diez puntos" (art-107.Uno)."""
    result = compute_regularizacion_anual(
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        prorrata_anio_pct=Decimal("50"),
        kind=BienInversionKind.MUEBLE,
    )
    assert result.diferencia_puntos == Decimal("10")
    assert result.aplica is False
    assert result.importe == Decimal("0.00")
    assert result.direccion is RegularizacionDireccion.NINGUNA


def test_just_over_ten_points_regularises() -> None:
    """A difference strictly greater than 10 points fires the gate."""
    result = compute_regularizacion_anual(
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        prorrata_anio_pct=Decimal("49.99"),
        kind=BienInversionKind.MUEBLE,
    )
    assert result.diferencia_puntos == Decimal("10.01")
    assert result.aplica is True


def test_non_positive_cuota_is_refused() -> None:
    """A non-positive cuota soportada is an instructive refusal, not a silent zero."""
    with pytest.raises(BienInversionValidationError, match="cuota_soportada"):
        compute_regularizacion_anual(
            cuota_soportada=Decimal("0"),
            prorrata_inicial_pct=Decimal("70"),
            prorrata_anio_pct=Decimal("50"),
            kind=BienInversionKind.MUEBLE,
        )


def test_out_of_range_percentage_is_refused() -> None:
    """A percentage outside 0-100 is refused."""
    with pytest.raises(BienInversionValidationError, match="prorrata_anio_pct"):
        compute_regularizacion_anual(
            cuota_soportada=Decimal("1000"),
            prorrata_inicial_pct=Decimal("70"),
            prorrata_anio_pct=Decimal("120"),
            kind=BienInversionKind.MUEBLE,
        )
