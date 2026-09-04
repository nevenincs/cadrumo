"""LIVA art-110 single ("única") disposal regularización compute.

Expected values are derived term by term from the art. 110.Uno ordinal procedure
read verbatim from the bundled consolidated LIVA corpus
(``corpus/normatives/html/ley-37-1992-art-110.html``): a disposal during the
regularisation window triggers ONE regularización for every remaining window
year, imputing 100% usage (regla 1.ª, entrega sujeta y no exenta) or 0% usage
(regla 2.ª, entrega exenta o no sujeta) for that whole remaining span, applying
the same art-109 deducción-efectuada-menos-imputada ÷ divisor quotient but
multiplied by the count of remaining years. Regla 1.ª additionally caps the
resulting additional deduction at the cuota devengada on the disposal itself
("no será deducible la diferencia ... y el importe de la cuota devengada por la
entrega del bien"). Arithmetic below is worked by hand from the statute's
ordinals, never by re-running the function under test.

See Also:
    :func:`~domain.bienes_inversion.compute_regularizacion_transmision`
        Pure art. 110 single-disposal compute under test.
    :class:`~domain.bienes_inversion.RegularizacionTransmisionResult`
        Result payload carrying capped and uncapped amounts plus direction.
    :func:`~domain.bienes_inversion.compute_registro_transmisiones`
        Register-wide projection that folds disposal computes into casilla 43.
    :func:`~application.calculations.build_bienes_inversion_transmision_advisory`
        Application diagnostic that surfaces art. 110 projected values.
        Governing capital-goods regularización design.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.schema_base import ThresholdComparison
from ..register import (
    BienInversionDisposalRegime,
    BienInversionKind,
    BienInversionValidationError,
    RegularizacionDireccion,
    compute_regularizacion_transmision,
)
from ..regularizacion_parameters import (
    BienesInversionParameterProvenance,
    BienesInversionRegularizacionParameters,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: An explicit bundle, supplied rather than resolved: these are unit tests of the
#: art-109/110 PROCEDURE, and the procedure is what they prove. Whether the
#: figures below are the ones the law states is a separate question, answered
#: against the registry itself by the modelo 303 parameter gates. Supplying them
#: here as inputs keeps a legal value out of this file's assertions.
_PARAMS = BienesInversionRegularizacionParameters(
    ventana_anos_mueble=4,
    ventana_anos_inmueble=9,
    divisor_mueble=Decimal("5"),
    divisor_inmueble=Decimal("10"),
    umbral_puntos=Decimal("10"),
    umbral_comparison=ThresholdComparison.EXCLUSIVE,
    provenance=BienesInversionParameterProvenance(
        modelo_id="303",
        revision_id="2025",
        parameter_ids=(
            "m303-bien-inversion-ventana-anos-mueble",
            "m303-bien-inversion-ventana-anos-inmueble",
            "m303-bien-inversion-divisor-mueble",
            "m303-bien-inversion-divisor-inmueble",
            "m303-bien-inversion-regularizacion-umbral-puntos",
        ),
        resolved_on=date(2025, 6, 1),
    ),
)


def test_regla_primera_sujeta_no_exenta_imputes_full_usage_for_remaining_years() -> None:
    """Regla 1.ª: disposal deemed 100%-deductible use for every remaining year.

    Mueble acquired with cuota soportada 10.000,00 €, initial prorrata 60 %,
    disposed of with 3 window years remaining (divisor 5).

    deducción efectuada (año adquisición) = 10.000 × 60 % = 6.000,00.
    deducción imputada (regla 1.ª, 100 %) = 10.000 × 100 % = 10.000,00.
    diferencia = 6.000,00 − 10.000,00 = −4.000,00.
    × 3 años restantes = −12.000,00 ÷ 5 (mueble) = −2.400,00 → deducción
    complementaria (additional deduction), uncapped (no cuota devengada supplied).
    """
    result = compute_regularizacion_transmision(
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        anos_restantes=3,
        kind=BienInversionKind.MUEBLE,
        regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA,
        parameters=_PARAMS,
    )
    assert result.anos_restantes == 3
    assert result.divisor == Decimal("5")
    assert result.importe_sin_limite == Decimal("-2400.00")
    assert result.importe == Decimal("-2400.00")
    assert result.direccion is RegularizacionDireccion.DEDUCCION
    assert result.capped is False


def test_regla_primera_caps_additional_deduction_at_cuota_devengada() -> None:
    """The regla-1.ª additional deduction never exceeds the disposal's own cuota devengada.

    Same inputs as above (uncapped quotient −2.400,00 €), but the disposal's own
    cuota devengada is only 1.500,00 €. Art. 110.Uno: "no será deducible la
    diferencia ... y el importe de la cuota devengada" caps the additional
    deduction's magnitude at that figure.
    """
    result = compute_regularizacion_transmision(
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        anos_restantes=3,
        kind=BienInversionKind.MUEBLE,
        regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA,
        cuota_devengada_entrega=Decimal("1500.00"),
        parameters=_PARAMS,
    )
    assert result.importe_sin_limite == Decimal("-2400.00")
    assert result.importe == Decimal("-1500.00")
    assert result.direccion is RegularizacionDireccion.DEDUCCION
    assert result.capped is True


def test_regla_primera_cap_does_not_bind_when_devengada_exceeds_quotient() -> None:
    """A cuota devengada larger than the uncapped quotient never triggers the cap."""
    result = compute_regularizacion_transmision(
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        anos_restantes=3,
        kind=BienInversionKind.MUEBLE,
        regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA,
        cuota_devengada_entrega=Decimal("5000.00"),
        parameters=_PARAMS,
    )
    assert result.importe == Decimal("-2400.00")
    assert result.capped is False


def test_regla_segunda_exenta_o_no_sujeta_imputes_zero_usage_for_remaining_years() -> None:
    """Regla 2.ª: disposal deemed 0%-deductible use for every remaining year.

    Inmueble acquired with cuota soportada 31.500,00 €, initial prorrata 65 %,
    disposed of with 4 window years remaining (divisor 10).

    deducción efectuada = 31.500 × 65 % = 20.475,00.
    deducción imputada (regla 2.ª, 0 %) = 0,00.
    diferencia = 20.475,00 − 0,00 = 20.475,00.
    × 4 años restantes = 81.900,00 ÷ 10 (inmueble) = 8.190,00 → ingreso
    complementario (repayment). Regla 2.ª is never capped.
    """
    result = compute_regularizacion_transmision(
        cuota_soportada=Decimal("31500.00"),
        prorrata_inicial_pct=Decimal("65"),
        anos_restantes=4,
        kind=BienInversionKind.INMUEBLE,
        regime=BienInversionDisposalRegime.EXENTA_O_NO_SUJETA,
        parameters=_PARAMS,
    )
    assert result.anos_restantes == 4
    assert result.divisor == Decimal("10")
    assert result.importe_sin_limite == Decimal("8190.00")
    assert result.importe == Decimal("8190.00")
    assert result.direccion is RegularizacionDireccion.INGRESO
    assert result.capped is False


def test_regla_segunda_cap_never_applies_even_when_devengada_supplied() -> None:
    """Supplying a cuota devengada under regla 2.ª has no effect (no cap there)."""
    result = compute_regularizacion_transmision(
        cuota_soportada=Decimal("31500.00"),
        prorrata_inicial_pct=Decimal("65"),
        anos_restantes=4,
        kind=BienInversionKind.INMUEBLE,
        regime=BienInversionDisposalRegime.EXENTA_O_NO_SUJETA,
        cuota_devengada_entrega=Decimal("1.00"),
        parameters=_PARAMS,
    )
    assert result.importe == Decimal("8190.00")
    assert result.capped is False


def test_no_diferencia_de_puntos_gate_a_disposal_always_regularises() -> None:
    """Unlike art-109, art-110 has no over-10-point gate: any disposal computes.

    Acquisition-year percentage 90 %; a regla-1.ª disposal imputes 100 % — only a
    10-point difference, which would NOT clear the art-107/109 gate — yet the
    art-110 single regularización still fires (a disposal, not a percentage
    drift, is what triggers it).
    """
    result = compute_regularizacion_transmision(
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=Decimal("90"),
        anos_restantes=1,
        kind=BienInversionKind.MUEBLE,
        regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA,
        parameters=_PARAMS,
    )
    # efectuada = 4500,00; imputada = 5000,00; diff = -500,00; x1 / 5 = -100,00
    assert result.importe == Decimal("-100.00")
    assert result.direccion is RegularizacionDireccion.DEDUCCION


def test_non_positive_cuota_is_refused() -> None:
    """A non-positive cuota soportada is an instructive refusal, not a silent zero."""
    with pytest.raises(BienInversionValidationError, match="cuota_soportada"):
        compute_regularizacion_transmision(
            parameters=_PARAMS,
            cuota_soportada=Decimal("0"),
            prorrata_inicial_pct=Decimal("70"),
            anos_restantes=1,
            kind=BienInversionKind.MUEBLE,
            regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA,
        )


def test_out_of_range_percentage_is_refused() -> None:
    """A percentage outside 0-100 is refused."""
    with pytest.raises(BienInversionValidationError, match="prorrata_inicial_pct"):
        compute_regularizacion_transmision(
            parameters=_PARAMS,
            cuota_soportada=Decimal("1000"),
            prorrata_inicial_pct=Decimal("120"),
            anos_restantes=1,
            kind=BienInversionKind.MUEBLE,
            regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA,
        )


def test_non_positive_anos_restantes_is_refused() -> None:
    """A disposal outside the regularisation window has nothing left to regularise."""
    with pytest.raises(BienInversionValidationError, match="anos_restantes"):
        compute_regularizacion_transmision(
            parameters=_PARAMS,
            cuota_soportada=Decimal("1000"),
            prorrata_inicial_pct=Decimal("70"),
            anos_restantes=0,
            kind=BienInversionKind.MUEBLE,
            regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA,
        )


def test_negative_cuota_devengada_entrega_is_refused() -> None:
    """A negative cuota devengada is a structural error, not a silent clamp."""
    with pytest.raises(BienInversionValidationError, match="cuota_devengada_entrega"):
        compute_regularizacion_transmision(
            parameters=_PARAMS,
            cuota_soportada=Decimal("1000"),
            prorrata_inicial_pct=Decimal("70"),
            anos_restantes=1,
            kind=BienInversionKind.MUEBLE,
            regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA,
            cuota_devengada_entrega=Decimal("-1"),
        )
