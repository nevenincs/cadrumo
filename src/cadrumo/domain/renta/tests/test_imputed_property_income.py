"""Tests for the LIRPF art. 85 imputed property income calculation.

Oracles: the worked example in Manual practico de Renta 2025, Parte 1
(source.pdf.extracted.md lines 31310-31345 for the statement and solution,
31370-31377 for notes (1) and (2)); every other expected value is hand
arithmetic written beside the case. Rates are fixture parameters here because
production code receives them from the registry.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from ..imputed_property_income import (
    BaseOrigen,
    ImputacionCalculada,
    ImputacionNoImputable,
    ImputacionRechazada,
    InmuebleImputable,
    IntervaloExcluyente,
    MotivoNoImputable,
    MotivoRechazo,
    NaturalezaInmueble,
    ParametrosImputacion,
    TipoIntervalo,
    Titularidad,
    calcular_imputacion_inmueble,
)

# Plain fixture year; the production module never names a year.
_Y = 2025

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _parametros(
    year: int = _Y,
    revision_vigor_desde: date | None = None,
    periodo_desde: date | None = None,
) -> ParametrosImputacion:
    return ParametrosImputacion(
        periodo_desde=date(year, 1, 1) if periodo_desde is None else periodo_desde,
        periodo_hasta=date(year, 12, 31),
        porcentaje_general=Decimal(2),
        porcentaje_reducido=Decimal("1.1"),
        porcentaje_base_sin_valor_catastral=Decimal(50),
        periodos_revision_previos=10,
        revision_vigor_desde=revision_vigor_desde,
    )


def _inmueble(
    *,
    titularidad: Titularidad | None = Titularidad.PLENO_DOMINIO,
    porcentaje_propiedad: Decimal | None = Decimal(100),
    porcentaje_usufructo: Decimal | None = None,
    naturaleza: NaturalezaInmueble | None = NaturalezaInmueble.URBANA,
    fecha_adquisicion: date | None = date(_Y - 20, 1, 1),
    fecha_transmision: date | None = None,
    valor_catastral: Decimal | None = Decimal(10000),
    valor_catastral_no_notificado: bool = False,
    revision_colectiva_vigor: date | None = None,
    importe_adquisicion: Decimal | None = None,
    valor_comprobado_administracion: Decimal | None = None,
    intervalos: tuple[IntervaloExcluyente, ...] = (),
    rustico_con_construcciones_no_indispensables: bool = False,
) -> InmuebleImputable:
    return InmuebleImputable(
        titularidad=titularidad,
        porcentaje_propiedad=porcentaje_propiedad,
        porcentaje_usufructo=porcentaje_usufructo,
        naturaleza=naturaleza,
        fecha_adquisicion=fecha_adquisicion,
        fecha_transmision=fecha_transmision,
        valor_catastral=valor_catastral,
        valor_catastral_no_notificado=valor_catastral_no_notificado,
        revision_colectiva_vigor=revision_colectiva_vigor,
        importe_adquisicion=importe_adquisicion,
        valor_comprobado_administracion=valor_comprobado_administracion,
        intervalos=intervalos,
        rustico_con_construcciones_no_indispensables=rustico_con_construcciones_no_indispensables,
    )


def _intervalo(tipo: TipoIntervalo, desde: tuple[int, int], hasta: tuple[int, int] | None) -> IntervaloExcluyente:
    return IntervaloExcluyente(
        tipo,
        date(_Y, *desde),
        None if hasta is None else date(_Y, *hasta),
    )


def _importe(inmueble: InmuebleImputable, parametros: ParametrosImputacion | None = None) -> Decimal:
    resultado = calcular_imputacion_inmueble(inmueble, parametros or _parametros())
    assert isinstance(resultado, ImputacionCalculada), resultado
    return resultado.importe


def test_manual_worked_example_total() -> None:
    # Manual lines 31310-31345: beach apartment, revised 2015, VC 40.800 -> 448,80.
    playa = _inmueble(
        valor_catastral=Decimal(40800),
        revision_colectiva_vigor=date(_Y - 10, 6, 1),
        intervalos=(),
    )
    # Day count in the manual's solution uses the whole year for this property.
    assert _importe(playa) == Decimal("448.80")

    # Manual line 31345: 1,1% s/(50% x 105.000) x 62/365 = 98,10.
    apartamento = _inmueble(
        fecha_adquisicion=date(_Y, 7, 1),
        valor_catastral=None,
        importe_adquisicion=Decimal(105000),
        intervalos=(_intervalo(TipoIntervalo.ARRENDADO, (9, 1), None),),
    )
    resultado = calcular_imputacion_inmueble(apartamento, _parametros())
    assert isinstance(resultado, ImputacionCalculada)
    assert resultado.dias_imputables == 62
    assert resultado.base == Decimal("52500")
    assert resultado.base_origen is BaseOrigen.VALOR_ADQUISICION_O_COMPROBADO
    assert resultado.porcentaje_aplicado == Decimal("1.1")
    assert resultado.importe == Decimal("98.10")

    # Manual total 546,90.
    assert _importe(playa) + resultado.importe == Decimal("546.90")


def test_manual_habitual_home_and_garage_do_not_impute() -> None:
    # Manual: "Vivienda habitual y plaza de garaje: no procede imputacion".
    anual = (_intervalo(TipoIntervalo.VIVIENDA_HABITUAL, (1, 1), None),)
    for valor in (Decimal(34800), Decimal(3900)):
        resultado = calcular_imputacion_inmueble(_inmueble(valor_catastral=valor, intervalos=anual), _parametros())
        assert resultado == ImputacionNoImputable(MotivoNoImputable.SIN_DIAS_A_DISPOSICION)


def test_full_year_general_rate() -> None:
    # 10.000 x 2% = 200,00 over 365/365 days.
    assert _importe(_inmueble()) == Decimal("200.00")


def test_partial_year_ownership_from_acquisition() -> None:
    # Acquired 1 April: 275 days. 200 x 275 / 365 = 150,6849 -> 150,68.
    assert _importe(_inmueble(fecha_adquisicion=date(_Y, 4, 1))) == Decimal("150.68")


def test_transmission_date_is_inclusive() -> None:
    # Sold 30 June: 181 days. 200 x 181 / 365 = 99,1781 -> 99,18.
    assert _importe(_inmueble(fecha_transmision=date(_Y, 6, 30))) == Decimal("99.18")


def test_let_half_year_is_excluded() -> None:
    # Let 1 Jan-30 Jun (181 days) leaves 184. 200 x 184 / 365 = 100,8219 -> 100,82.
    arrendado = (_intervalo(TipoIntervalo.ARRENDADO, (1, 1), (6, 30)),)
    assert _importe(_inmueble(intervalos=arrendado)) == Decimal("100.82")


def test_habitual_home_part_of_year() -> None:
    # Habitual home 1 Jan-31 Mar (90 days) leaves 275 -> 150,68.
    vivienda = (_intervalo(TipoIntervalo.VIVIENDA_HABITUAL, (1, 1), (3, 31)),)
    assert _importe(_inmueble(intervalos=vivienda)) == Decimal("150.68")


def test_overlapping_intervals_do_not_double_subtract() -> None:
    # Let 1 Jan-30 Jun, habitual 1 Apr-30 Sep, activity 1 May-31 May: union 1 Jan-30 Sep
    # = 273 days, leaving 92. 200 x 92 / 365 = 50,4109 -> 50,41 (a naive sum would leave 1).
    intervalos = (
        _intervalo(TipoIntervalo.ARRENDADO, (1, 1), (6, 30)),
        _intervalo(TipoIntervalo.VIVIENDA_HABITUAL, (4, 1), (9, 30)),
        _intervalo(TipoIntervalo.ACTIVIDAD_ECONOMICA, (5, 1), (5, 31)),
    )
    resultado = calcular_imputacion_inmueble(_inmueble(intervalos=intervalos), _parametros())
    assert isinstance(resultado, ImputacionCalculada)
    assert resultado.dias_imputables == 92
    assert resultado.importe == Decimal("50.41")


def test_intervals_outside_ownership_window_are_ignored() -> None:
    # Acquired 1 July; a let interval before that must not reduce the owned days.
    intervalos = (_intervalo(TipoIntervalo.ARRENDADO, (1, 1), (6, 30)),)
    resultado = calcular_imputacion_inmueble(
        _inmueble(fecha_adquisicion=date(_Y, 7, 1), intervalos=intervalos),
        _parametros(),
    )
    assert isinstance(resultado, ImputacionCalculada)
    assert resultado.dias_imputables == 184


def test_leap_year_uses_actual_days() -> None:
    leap = 2024
    inmueble = _inmueble(fecha_adquisicion=date(leap - 20, 1, 1))
    resultado = calcular_imputacion_inmueble(inmueble, _parametros(leap))
    assert isinstance(resultado, ImputacionCalculada)
    assert (resultado.dias_imputables, resultado.dias_periodo) == (366, 366)
    assert resultado.importe == Decimal("200.00")


def test_fifty_percent_coownership() -> None:
    # 200,00 x 50% = 100,00.
    assert _importe(_inmueble(porcentaje_propiedad=Decimal(50))) == Decimal("100.00")


def test_usufruct_imputes_to_usufructuary_with_its_share() -> None:
    usufructuario = _inmueble(
        titularidad=Titularidad.USUFRUCTO,
        porcentaje_propiedad=None,
        porcentaje_usufructo=Decimal(25),
    )
    # 200,00 x 25% = 50,00.
    assert _importe(usufructuario) == Decimal("50.00")


def test_bare_ownership_does_not_impute() -> None:
    nudo = _inmueble(titularidad=Titularidad.NUDA_PROPIEDAD, porcentaje_propiedad=Decimal(100))
    assert calcular_imputacion_inmueble(nudo, _parametros()) == ImputacionNoImputable(MotivoNoImputable.NUDA_PROPIEDAD)


def test_mixed_title_is_refused() -> None:
    mixto = _inmueble(titularidad=Titularidad.PLENO_DOMINIO_Y_USUFRUCTO, porcentaje_usufructo=Decimal(50))
    assert calcular_imputacion_inmueble(mixto, _parametros()) == ImputacionRechazada(
        MotivoRechazo.TITULARIDAD_NO_RESUELTA
    )


def test_revised_value_inside_window_uses_reduced_rate() -> None:
    # 10.000 x 1,1% = 110,00.
    assert _importe(_inmueble(revision_colectiva_vigor=date(_Y - 5, 3, 1))) == Decimal("110.00")
    # Boundary: in force exactly ten periods earlier still qualifies.
    assert _importe(_inmueble(revision_colectiva_vigor=date(_Y - 10, 12, 31))) == Decimal("110.00")


def test_revision_outside_window_or_after_period_uses_general_rate() -> None:
    assert _importe(_inmueble(revision_colectiva_vigor=date(_Y - 11, 12, 31))) == Decimal("200.00")
    assert _importe(_inmueble(revision_colectiva_vigor=date(_Y + 1, 1, 1))) == Decimal("200.00")


def test_caller_supplied_fixed_revision_floor_also_qualifies() -> None:
    vigor = date(_Y - 12, 6, 1)
    inmueble = _inmueble(revision_colectiva_vigor=vigor)
    assert _importe(inmueble, _parametros(revision_vigor_desde=date(_Y - 13, 1, 1))) == Decimal("110.00")
    assert _importe(inmueble, _parametros(revision_vigor_desde=date(_Y - 11, 1, 1))) == Decimal("200.00")


def test_no_cadastral_value_uses_half_of_higher_value() -> None:
    # Higher of 80.000 and 90.000 is 90.000; 50% = 45.000; x 1,1% = 495,00.
    inmueble = _inmueble(
        valor_catastral=None,
        importe_adquisicion=Decimal(80000),
        valor_comprobado_administracion=Decimal(90000),
    )
    resultado = calcular_imputacion_inmueble(inmueble, _parametros())
    assert isinstance(resultado, ImputacionCalculada)
    assert resultado.base == Decimal(45000)
    assert resultado.importe == Decimal("495.00")


def test_unnotified_cadastral_value_falls_back() -> None:
    inmueble = _inmueble(
        valor_catastral_no_notificado=True,
        importe_adquisicion=Decimal(60000),
    )
    # 50% x 60.000 = 30.000 x 1,1% = 330,00 (the stated cadastral value is not used).
    assert _importe(inmueble) == Decimal("330.00")


def test_missing_cadastral_and_acquisition_values_refuse() -> None:
    inmueble = _inmueble(valor_catastral=None)
    assert calcular_imputacion_inmueble(inmueble, _parametros()) == ImputacionRechazada(
        MotivoRechazo.BASE_NO_DETERMINABLE
    )


def test_non_positive_values_refuse() -> None:
    assert calcular_imputacion_inmueble(_inmueble(valor_catastral=Decimal(0)), _parametros()) == ImputacionRechazada(
        MotivoRechazo.VALOR_NO_POSITIVO
    )


def test_rustic_property_is_not_imputable_unless_flagged() -> None:
    rustico = _inmueble(naturaleza=NaturalezaInmueble.RUSTICA)
    assert calcular_imputacion_inmueble(rustico, _parametros()) == ImputacionNoImputable(MotivoNoImputable.RUSTICO)
    construido = replace(rustico, rustico_con_construcciones_no_indispensables=True)
    assert _importe(construido) == Decimal("200.00")


def test_unstated_nature_and_acquisition_date_refuse() -> None:
    sin_naturaleza = _inmueble(naturaleza=None)
    assert calcular_imputacion_inmueble(sin_naturaleza, _parametros()) == ImputacionRechazada(
        MotivoRechazo.NATURALEZA_NO_DECLARADA
    )
    sin_fecha = _inmueble(fecha_adquisicion=None)
    assert calcular_imputacion_inmueble(sin_fecha, _parametros()) == ImputacionRechazada(
        MotivoRechazo.FECHA_ADQUISICION_NO_DECLARADA
    )


def test_unstated_or_invalid_share_refuses() -> None:
    assert calcular_imputacion_inmueble(_inmueble(porcentaje_propiedad=None), _parametros()) == ImputacionRechazada(
        MotivoRechazo.PARTICIPACION_NO_DECLARADA
    )
    assert calcular_imputacion_inmueble(
        _inmueble(porcentaje_propiedad=Decimal(150)), _parametros()
    ) == ImputacionRechazada(MotivoRechazo.PARTICIPACION_FUERA_DE_RANGO)


def test_court_assigned_family_dwelling_and_eviction_intervals() -> None:
    judicial = (_intervalo(TipoIntervalo.VIVIENDA_FAMILIAR_JUDICIAL, (1, 1), None),)
    assert calcular_imputacion_inmueble(_inmueble(intervalos=judicial), _parametros()) == ImputacionNoImputable(
        MotivoNoImputable.SIN_DIAS_A_DISPOSICION
    )
    # Eviction begun 1 Oct: 273 days remain. 200 x 273 / 365 = 149,5890 -> 149,59.
    desahucio = (_intervalo(TipoIntervalo.OCUPACION_ILEGAL_DESAHUCIO, (10, 1), None),)
    assert _importe(_inmueble(intervalos=desahucio)) == Decimal("149.59")


def test_construction_interval_is_excluded() -> None:
    obra = (_intervalo(TipoIntervalo.EN_CONSTRUCCION_O_NO_USABLE, (1, 1), (12, 30)),)
    resultado = calcular_imputacion_inmueble(_inmueble(intervalos=obra), _parametros())
    assert isinstance(resultado, ImputacionCalculada)
    assert resultado.dias_imputables == 1


def test_not_owned_in_period_is_not_imputable() -> None:
    futuro = _inmueble(fecha_adquisicion=date(_Y + 1, 1, 1))
    assert calcular_imputacion_inmueble(futuro, _parametros()) == ImputacionNoImputable(
        MotivoNoImputable.SIN_DIAS_A_DISPOSICION
    )
    vendido = _inmueble(fecha_transmision=date(_Y - 1, 12, 31))
    assert calcular_imputacion_inmueble(vendido, _parametros()) == ImputacionNoImputable(
        MotivoNoImputable.SIN_DIAS_A_DISPOSICION
    )


def test_incoherent_dates_refuse() -> None:
    invertido = (_intervalo(TipoIntervalo.ARRENDADO, (6, 30), (6, 1)),)
    assert calcular_imputacion_inmueble(_inmueble(intervalos=invertido), _parametros()) == ImputacionRechazada(
        MotivoRechazo.INTERVALO_INCOHERENTE
    )
    antes = _inmueble(fecha_transmision=date(_Y - 30, 1, 1))
    assert calcular_imputacion_inmueble(antes, _parametros()) == ImputacionRechazada(
        MotivoRechazo.INTERVALO_INCOHERENTE
    )


def test_inverted_filing_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="periodo_desde"):
        _parametros(periodo_desde=date(_Y + 1, 1, 1))
