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

from collections.abc import Iterator
from decimal import ROUND_HALF_UP, Decimal

import pytest
from pydantic import ValidationError

from ...calculations.registry.authority import bundled_indexed_authority
from ..prorrata import (
    ProrrataInputs,
    ProrrataKind,
    RegularizacionProrrataDireccion,
    RegularizacionProrrataParticion,
    RegularizacionProrrataParticionadaResult,
    compute_prorrata_definitiva_anual,
    compute_regularizacion_prorrata_particionada,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module", autouse=True)
def _registry_authority_scope() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


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


def _regularizar(
    *,
    cuotas_soportadas_deducibles: Decimal,
    deducciones_provisionales_practicadas: Decimal,
    prorrata_definitiva_pct: Decimal,
) -> RegularizacionProrrataParticionadaResult:
    """Regularise a whole-entity general prorrata, which is a single partition."""
    return compute_regularizacion_prorrata_particionada(
        particiones=(
            RegularizacionProrrataParticion(
                cuotas_soportadas_deducibles=cuotas_soportadas_deducibles,
                prorrata_definitiva_pct=prorrata_definitiva_pct,
            ),
        ),
        deducciones_provisionales_practicadas=deducciones_provisionales_practicadas,
    )


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
    assert result.kind == ProrrataKind.from_registry("definitiva")
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

    result = _regularizar(
        cuotas_soportadas_deducibles=cuotas,
        deducciones_provisionales_practicadas=_deduccion(cuotas, provisional),
        prorrata_definitiva_pct=definitiva,
    )
    assert result.deduccion_provisional == Decimal("16000.00")
    assert result.deduccion_definitiva == Decimal("18000.00")
    assert result.importe == expected_importe
    assert result.direccion is RegularizacionProrrataDireccion.DEDUCCION


def test_aeat_manual_example_regularises_only_the_earlier_quarters() -> None:
    """Manual práctico de IVA 2025, prorrata general regularisation example.

    Provisional 73%; the year's volumes 25.000 con derecho over 45.000 total
    give 55,56% rounded up to a definitive 56% (art. 104.Dos). The fourth
    quarter deducts its own cuotas at 56% directly, so the regularisation box
    covers only the first three quarters: gross cuotas 400 + 420 + 460 = 1.280,
    deducted at 73% as 292,00 + 306,60 + 335,80 = 934,40. The manual's box is
    1.280 x 56% - 934,40 = -217,60.
    """
    definitiva = compute_prorrata_definitiva_anual(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=Decimal("25000"),
            operaciones_sin_derecho_deduccion=Decimal("20000"),
        ),
        year=2025,
    ).percentage
    provisional = Decimal("73")
    quarters = (Decimal("400.00"), Decimal("420.00"), Decimal("460.00"))
    practised = sum((_deduccion(cuota, provisional) for cuota in quarters), Decimal("0"))

    result = _regularizar(
        cuotas_soportadas_deducibles=sum(quarters, Decimal("0")),
        deducciones_provisionales_practicadas=practised,
        prorrata_definitiva_pct=definitiva,
    )

    assert definitiva == Decimal("56")
    assert practised == Decimal("934.40")
    assert result.importe == Decimal("-217.60")
    assert result.direccion is RegularizacionProrrataDireccion.INGRESO


def test_regularizacion_subtracts_the_deductions_actually_practised() -> None:
    """Each liquidation rounded its own boxes, so the practised total is taken as filed.

    Two quarters of 0,03 at 50% each practised 0,02 (half-up), 0,04 in all,
    while 50% of the summed 0,06 is 0,03. At an unchanged definitive 50% the
    rounding excess is regularised: 0,03 - 0,04 = -0,01. Re-deriving the
    practised deduction from the summed cuotas would hide it.
    """
    result = _regularizar(
        cuotas_soportadas_deducibles=Decimal("0.06"),
        deducciones_provisionales_practicadas=_deduccion(Decimal("0.03"), Decimal("50")) * 2,
        prorrata_definitiva_pct=Decimal("50"),
    )

    assert result.deduccion_provisional == Decimal("0.04")
    assert result.importe == Decimal("-0.01")


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

    result = _regularizar(
        cuotas_soportadas_deducibles=cuotas,
        deducciones_provisionales_practicadas=_deduccion(cuotas, provisional),
        prorrata_definitiva_pct=definitiva,
    )
    assert result.importe == expected_importe
    assert result.direccion is RegularizacionProrrataDireccion.INGRESO


def test_no_regularizacion_when_percentages_coincide() -> None:
    """Equal provisional and definitive percentages leave nothing to regularise."""
    result = _regularizar(
        cuotas_soportadas_deducibles=Decimal("50000.00"),
        deducciones_provisionales_practicadas=_deduccion(Decimal("50000.00"), Decimal("88")),
        prorrata_definitiva_pct=Decimal("88"),
    )
    assert result.importe == Decimal("0.00")
    assert result.direccion is RegularizacionProrrataDireccion.NINGUNA


def test_negative_cuota_is_refused() -> None:
    with pytest.raises(ValidationError):
        _regularizar(
            cuotas_soportadas_deducibles=Decimal("-1"),
            deducciones_provisionales_practicadas=Decimal("0"),
            prorrata_definitiva_pct=Decimal("60"),
        )


def test_out_of_range_percentage_is_refused() -> None:
    for pct in (Decimal("-1"), Decimal("101")):
        with pytest.raises(ValidationError):
            _regularizar(
                cuotas_soportadas_deducibles=Decimal("1000.00"),
                deducciones_provisionales_practicadas=Decimal("0"),
                prorrata_definitiva_pct=pct,
            )


def test_each_partition_applies_its_own_definitive_percentage() -> None:
    """LIVA art. 101.Uno: two sectors regularise separately and the box is their sum.

    Sector A: 150,00 gross deducted at 80 % (120,00), definitive 70 % gives
    105,00. Sector B: 200,00 gross deducted at 30 % (60,00), definitive 40 %
    gives 80,00. Each step is computed independently below.
    """
    deduccion_definitiva = _deduccion(Decimal("150.00"), Decimal("70")) + _deduccion(Decimal("200.00"), Decimal("40"))
    practised = _deduccion(Decimal("150.00"), Decimal("80")) + _deduccion(Decimal("200.00"), Decimal("30"))

    result = compute_regularizacion_prorrata_particionada(
        particiones=(
            RegularizacionProrrataParticion(
                cuotas_soportadas_deducibles=Decimal("150.00"), prorrata_definitiva_pct=Decimal("70")
            ),
            RegularizacionProrrataParticion(
                cuotas_soportadas_deducibles=Decimal("200.00"), prorrata_definitiva_pct=Decimal("40")
            ),
        ),
        deducciones_provisionales_practicadas=practised,
    )

    assert result.deduccion_definitiva == deduccion_definitiva == Decimal("185.00")
    assert result.importe == deduccion_definitiva - practised == Decimal("5.00")
    assert result.direccion is RegularizacionProrrataDireccion.DEDUCCION


def test_no_regularisable_partition_has_a_zero_definitive_deduction() -> None:
    """An especial year whose inputs are all exclusively used leaves nothing for art. 105 to correct."""
    result = compute_regularizacion_prorrata_particionada(
        particiones=(),
        deducciones_provisionales_practicadas=Decimal("0.00"),
    )

    assert result.deduccion_definitiva == Decimal("0")
    assert result.importe == Decimal("0")
    assert result.direccion is RegularizacionProrrataDireccion.NINGUNA
