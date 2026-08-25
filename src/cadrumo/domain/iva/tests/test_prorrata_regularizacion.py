"""Annual prorrata-general regularización (LIVA arts. 104-105).

Grounding discipline (``aeat-quality-gates``): the definitive
percentage is produced by the art-104 substrate (:func:`compute_prorrata_general`
via :func:`compute_prorrata_definitiva_anual`, which rounds UP per art. 104.Dos),
and the expected regularización cuota is derived from the art-105.Cuatro legal
procedure computed by an INDEPENDENT path — the deduction that definitively
applies minus the deduction already practised provisionally, each as its own
cuota × percentage step — never by re-running the function's own single
expression. The percentages therefore come from the registry substrate and the
delta from the statutory procedure, not from a synthetic formula authored here.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest

from ..errors import ProrrataInputError
from .._prorrata import (
    ProrrataInputs,
    ProrrataKind,
    RegularizacionProrrataDireccion,
    compute_prorrata_definitiva_anual,
    compute_regularizacion_prorrata_anual,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _deduccion(cuotas: Decimal, pct: Decimal) -> Decimal:
    """Independent cuota × percentage step (the art-105 deduction at a percentage).

    The rounding mode is stated explicitly rather than inherited. A bare
    ``.quantize()`` takes the ambient decimal context, which is
    ``ROUND_HALF_EVEN`` -- banker's rounding, the mode ``core.money`` says
    "must never" be used at the euro-cent boundary for a filed value, while
    production rounds half-up. This oracle is only independent of production's
    *arithmetic*; leaving the mode ambient made it silently dependent on a
    convention production deliberately rejects. Current parameters miss the
    ``.005`` boundary so the two agreed, which is exactly why the divergence
    would first appear as a mystifying failure when someone parametrised a
    boundary value -- and would most likely be "fixed" by loosening the test.
    """
    return (cuotas * pct / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def test_definitiva_percentage_comes_from_the_full_year_art104_substrate() -> None:
    """The definitive percentage is the art-104 round-up over full-year volumes.

    con-derecho 90.000 / total 100.000 = 90% exactly (no rounding needed); the
    result is a DEFINITIVA/annual :class:`~cadrumo.domain.iva.ProrrataResult`.
    """
    result = compute_prorrata_definitiva_anual(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=Decimal("90000"),
            operaciones_sin_derecho_deduccion=Decimal("10000"),
        ),
        year=2025,
    )
    assert result.kind is ProrrataKind.DEFINITIVA
    assert result.period == "annual"
    assert result.percentage == Decimal("90")


def test_definitiva_percentage_rounds_up_per_art_104_dos() -> None:
    """art. 104.Dos: 70.000 / 100.001 = 69.999...% rounds UP to 70%.

    A naive per-period truncation would report 69%; the substrate round-up is the
    load-bearing behaviour the regularización depends on.
    """
    result = compute_prorrata_definitiva_anual(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=Decimal("70000"),
            operaciones_sin_derecho_deduccion=Decimal("30001"),
        ),
        year=2025,
    )
    assert result.percentage == Decimal("70")


def test_regularizacion_is_deduccion_complementaria_when_definitiva_exceeds_provisional() -> None:
    """art. 105.Cuatro: definitiva 90% > provisional 80% ⇒ deducción complementaria.

    Provisional = prior-year definitive (art. 105.Uno) = 80%. Definitive from the
    art-104 substrate over full-year volumes = 90%. The expected importe is the
    independent two-step art-105.Cuatro procedure:
    ``deducción definitiva − deducción provisional``.
    """
    cuotas = Decimal("20000.00")
    definitiva = compute_prorrata_definitiva_anual(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=Decimal("90000"),
            operaciones_sin_derecho_deduccion=Decimal("10000"),
        ),
        year=2025,
    ).percentage
    provisional = Decimal("80")

    expected_importe = _deduccion(cuotas, definitiva) - _deduccion(cuotas, provisional)
    assert expected_importe == Decimal("2000.00")  # 18.000 − 16.000, from the substrate + procedure

    result = compute_regularizacion_prorrata_anual(
        cuotas_soportadas_deducibles=cuotas,
        prorrata_provisional_pct=provisional,
        prorrata_definitiva_pct=definitiva,
    )
    assert result.deduccion_provisional == Decimal("16000.00")
    assert result.deduccion_definitiva == Decimal("18000.00")
    assert result.importe == expected_importe
    assert result.direccion is RegularizacionProrrataDireccion.DEDUCCION


def test_regularizacion_is_ingreso_when_definitiva_below_provisional() -> None:
    """art. 105.Cuatro: definitiva 70% < provisional 85% ⇒ ingreso (repay).

    The provisional deductions were excessive; the regularización is negative and
    reduces the deductible cuota (casilla 44 negative).
    """
    cuotas = Decimal("12000.00")
    definitiva = compute_prorrata_definitiva_anual(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=Decimal("70000"),
            operaciones_sin_derecho_deduccion=Decimal("30000"),
        ),
        year=2025,
    ).percentage
    provisional = Decimal("85")

    expected_importe = _deduccion(cuotas, definitiva) - _deduccion(cuotas, provisional)
    assert expected_importe == Decimal("-1800.00")  # 8.400 − 10.200

    result = compute_regularizacion_prorrata_anual(
        cuotas_soportadas_deducibles=cuotas,
        prorrata_provisional_pct=provisional,
        prorrata_definitiva_pct=definitiva,
    )
    assert result.importe == expected_importe
    assert result.direccion is RegularizacionProrrataDireccion.INGRESO


def test_no_regularizacion_when_percentages_coincide() -> None:
    """Equal provisional and definitive percentages leave nothing to regularise."""
    result = compute_regularizacion_prorrata_anual(
        cuotas_soportadas_deducibles=Decimal("50000.00"),
        prorrata_provisional_pct=Decimal("88"),
        prorrata_definitiva_pct=Decimal("88"),
    )
    assert result.importe == Decimal("0.00")
    assert result.direccion is RegularizacionProrrataDireccion.NINGUNA


def test_negative_cuota_is_refused() -> None:
    with pytest.raises(ProrrataInputError):
        compute_regularizacion_prorrata_anual(
            cuotas_soportadas_deducibles=Decimal("-1"),
            prorrata_provisional_pct=Decimal("50"),
            prorrata_definitiva_pct=Decimal("60"),
        )


def test_out_of_range_percentage_is_refused() -> None:
    for pct in (Decimal("-1"), Decimal("101")):
        with pytest.raises(ProrrataInputError):
            compute_regularizacion_prorrata_anual(
                cuotas_soportadas_deducibles=Decimal("1000.00"),
                prorrata_provisional_pct=pct,
                prorrata_definitiva_pct=Decimal("60"),
            )
