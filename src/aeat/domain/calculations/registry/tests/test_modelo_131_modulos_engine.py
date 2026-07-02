"""Modelo 131 estimación-objetiva módulos engine (Fase 1ª + Fase 4ª, phased dataset).

Non-tautological: expected values are transcribed independently from the
bundled Orden HAC/1347/2024 Anexo II coefficient tables
(``corpus/normatives/html/orden-hac-1347-2024.html``), not re-derived from the
registry formula under test. The 5 por ciento reducción general is grounded
in the same Orden's disposición adicional primera.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._formula_runtime import calculate_registry_snapshot
from ._registry_schema_support import _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Rendimiento anual por unidad antes de amortización (Orden HAC/1347/2024
# Anexo II, filing year 2025), independently transcribed for cross-check —
# a discrepancy between these literals and the registry parameter values
# would fail the assertions below, proving the registry table is grounded.
_PELUQUERIA_972_1 = {
    1: Decimal("3161.90"),  # personal asalariado (persona)
    2: Decimal("9649.47"),  # personal no asalariado (persona)
    3: Decimal("94.48"),  # superficie del local (m2)
    4: Decimal("81.88"),  # consumo de energía eléctrica (100 kWh)
}
_AUTOTAXI_721_2 = {
    1: Decimal("1346.27"),  # personal asalariado (persona)
    2: Decimal("7656.89"),  # personal no asalariado (persona)
    3: Decimal("45.08"),  # distancia recorrida (1.000 km)
}
_MERCANCIAS_722 = {
    1: Decimal("2728.59"),  # personal asalariado (persona)
    2: Decimal("10090.99"),  # personal no asalariado (persona)
    3: Decimal("126.21"),  # carga vehículos (tonelada)
}

# Phase 2 next-priority activities (café-bar / restaurante), independently
# transcribed from the bundled Orden HAC/1347/2024 Anexo II
# (corpus/normatives/html/orden-hac-1347-2024.html, lines ~1772-1943) and
# cross-checked byte-identical against the AEAT Manual práctico de Renta 2025,
# Parte 1, Capítulo 8 apéndice (source.pdf.extracted.md lines ~22921-22984).
_RESTAURANTE_DOS_TENEDORES_671_4 = {
    1: Decimal("3709.88"),  # personal asalariado (persona)
    2: Decimal("17434.55"),  # personal no asalariado (persona)
    3: Decimal("201.55"),  # potencia eléctrica (kW contratado)
    4: Decimal("585.77"),  # mesas (mesa)
    5: Decimal("1077.06"),  # máquinas tipo «A»
    6: Decimal("3810.65"),  # máquinas tipo «B»
}
_RESTAURANTE_UN_TENEDOR_671_5 = {
    1: Decimal("3602.80"),  # personal asalariado (persona)
    2: Decimal("16174.82"),  # personal no asalariado (persona)
    3: Decimal("125.97"),  # potencia eléctrica (kW contratado)
    4: Decimal("220.45"),  # mesas (mesa)
    5: Decimal("1077.06"),  # máquinas tipo «A»
    6: Decimal("3810.65"),  # máquinas tipo «B»
}
_CAFETERIAS_672_1 = {
    1: Decimal("1448.68"),  # personal asalariado (persona)
    2: Decimal("13743.56"),  # personal no asalariado (persona)
    3: Decimal("478.69"),  # potencia eléctrica (kW contratado)
    4: Decimal("377.92"),  # mesas (mesa)
    5: Decimal("957.39"),  # máquinas tipo «A»
    6: Decimal("3747.67"),  # máquinas tipo «B»
}

# Phase 2 next-priority activities (comercio al por menor de alimentación),
# independently transcribed from the same bundled Orden Anexo II (lines
# ~837-1148) and cross-checked byte-identical against the AEAT manual
# (source.pdf.extracted.md lines ~22413-22607).
_CARNE_642_1 = {
    1: Decimal("2355.68"),  # personal asalariado (persona)
    2: Decimal("10991.07"),  # personal no asalariado (persona)
    3: Decimal("35.90"),  # superficie local independiente (m2)
    4: Decimal("81.88"),  # superficie local no independiente (m2)
    5: Decimal("39.05"),  # consumo de energía eléctrica (100 kWh)
}
_PAN_PASTELERIA_644_1 = {
    1: Decimal("6248.22"),  # personal asalariado de fabricación (persona)
    2: Decimal("1058.17"),  # resto personal asalariado (persona)
    3: Decimal("14530.89"),  # personal no asalariado (persona)
    4: Decimal("49.13"),  # superficie del local de fabricación (m2)
    5: Decimal("34.01"),  # resto superficie local independiente (m2)
    6: Decimal("125.97"),  # resto superficie local no independiente (m2)
    7: Decimal("629.86"),  # superficie del horno (100 dm2)
}
_ALIMENTACION_647_1 = {
    1: Decimal("1026.67"),  # personal asalariado (persona)
    2: Decimal("10839.90"),  # personal no asalariado (persona)
    3: Decimal("20.15"),  # superficie del local independiente (m2)
    4: Decimal("68.65"),  # superficie del local no independiente (m2)
    5: Decimal("8.81"),  # consumo de energía eléctrica (100 kWh)
}

# Phase 2 activities not previously covered by a dedicated test (backfilled
# per the Phase 2 review's LOW finding), independently transcribed from the
# same bundled Orden Anexo II and cross-checked against the AEAT manual.
_CAFES_ESPECIAL_673_1 = {
    1: Decimal("4056.30"),  # personal asalariado (persona)
    2: Decimal("15538.66"),  # personal no asalariado (persona)
    3: Decimal("321.23"),  # potencia eléctrica (kW contratado)
    4: Decimal("233.04"),  # mesas (mesa)
    5: Decimal("371.62"),  # longitud de barra (metro)
    6: Decimal("957.39"),  # máquinas tipo «A»
    7: Decimal("2903.66"),  # máquinas tipo «B»
}
_OTROS_CAFES_673_2 = {
    1: Decimal("1643.93"),  # personal asalariado (persona)
    2: Decimal("11413.08"),  # personal no asalariado (persona)
    3: Decimal("94.48"),  # potencia eléctrica (kW contratado)
    4: Decimal("119.67"),  # mesas (mesa)
    5: Decimal("163.76"),  # longitud de barra (metro)
    6: Decimal("806.23"),  # máquinas tipo «A»
    7: Decimal("2947.75"),  # máquinas tipo «B»
}
_HUEVOS_AVES_642_5 = {
    1: Decimal("3382.36"),  # personal asalariado (persona)
    2: Decimal("11337.49"),  # personal no asalariado (persona)
    3: Decimal("25.19"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("27.08"),  # superficie local independiente (m2)
    5: Decimal("58.57"),  # superficie local no independiente (m2)
}
_CASQUERIAS_642_6 = {
    1: Decimal("2254.90"),  # personal asalariado (persona)
    2: Decimal("11098.14"),  # personal no asalariado (persona)
    3: Decimal("27.71"),  # superficie local independiente (m2)
    4: Decimal("69.28"),  # superficie local no independiente (m2)
    5: Decimal("35.90"),  # consumo de energía eléctrica (100 kWh)
}
_PESCADOS_643_1 = {
    1: Decimal("3823.25"),  # personal asalariado (persona)
    2: Decimal("13296.36"),  # personal no asalariado (persona)
    3: Decimal("36.53"),  # superficie local independiente (m2)
    4: Decimal("113.37"),  # superficie local no independiente (m2)
    5: Decimal("28.98"),  # consumo de energía eléctrica (100 kWh)
}
_DESPACHOS_PAN_644_2 = {
    1: Decimal("6134.85"),  # personal asalariado de fabricación (persona)
    2: Decimal("1039.27"),  # resto personal asalariado (persona)
    3: Decimal("14266.34"),  # personal no asalariado (persona)
    4: Decimal("48.50"),  # superficie del local de fabricación (m2)
    5: Decimal("33.38"),  # resto superficie local independiente (m2)
    6: Decimal("125.97"),  # resto superficie local no independiente (m2)
    7: Decimal("629.86"),  # superficie del horno (100 dm2)
}
_PASTELERIA_644_3 = {
    1: Decimal("6367.89"),  # personal asalariado de fabricación (persona)
    2: Decimal("1014.08"),  # resto personal asalariado (persona)
    3: Decimal("12912.15"),  # personal no asalariado (persona)
    4: Decimal("43.46"),  # superficie del local de fabricación (m2)
    5: Decimal("34.01"),  # resto superficie local independiente (m2)
    6: Decimal("113.37"),  # resto superficie local no independiente (m2)
    7: Decimal("522.78"),  # superficie del horno (100 dm2)
}
_MASAS_FRITAS_644_6 = {
    1: Decimal("6852.88"),  # personal asalariado de fabricación (persona)
    2: Decimal("2254.90"),  # resto personal asalariado (persona)
    3: Decimal("13214.47"),  # personal no asalariado (persona)
    4: Decimal("27.71"),  # superficie del local de fabricación (m2)
    5: Decimal("21.41"),  # resto superficie local independiente (m2)
    6: Decimal("36.53"),  # resto superficie local no independiente (m2)
}
_AUTOSERVICIO_647_2 = {
    1: Decimal("1788.80"),  # personal asalariado (persona)
    2: Decimal("10827.31"),  # personal no asalariado (persona)
    3: Decimal("23.31"),  # superficie del local (m2)
    4: Decimal("32.75"),  # consumo de energía eléctrica (100 kWh)
}

# Phase 3 next-priority activities (comercio al por menor de textil/calzado/
# mueble/electrodoméstico, hospedaje, reparaciones, transporte urbano),
# independently transcribed from the bundled Orden HAC/1347/2024 Anexo II and
# cross-checked byte-identical against the AEAT Manual práctico de Renta 2025.
_LENCERIA_651_3 = {
    1: Decimal("2198.21"),  # personal asalariado (persona)
    2: Decimal("11998.85"),  # personal no asalariado (persona) — corpus-typo
    # correction: the bundled Orden HTML reads "11.998.85" (period instead of
    # comma); the AEAT Manual Renta 2025 states "11.998,85" unambiguously.
    3: Decimal("47.87"),  # superficie del local (m2)
    4: Decimal("75.58"),  # consumo de energía eléctrica (100 kWh)
}
_TEXTIL_651_1 = {
    1: Decimal("3010.74"),  # personal asalariado (persona)
    2: Decimal("13812.85"),  # personal no asalariado (persona)
    3: Decimal("38.42"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("35.28"),  # superficie del local independiente (m2)
    5: Decimal("107.07"),  # superficie del local no independiente (m2)
}
_MUEBLES_653_1 = {
    1: Decimal("4075.20"),  # personal asalariado (persona)
    2: Decimal("16200.02"),  # personal no asalariado (persona)
    3: Decimal("50.39"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("16.38"),  # superficie del local (m2)
}
_RECAMBIOS_654_2 = {
    1: Decimal("3098.92"),  # personal asalariado (persona)
    2: Decimal("17018.84"),  # personal no asalariado (persona)
    3: Decimal("201.55"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("617.26"),  # potencia fiscal vehículo (CVF)
}
_OPTICA_659_3 = {
    1: Decimal("7174.12"),  # personal asalariado (persona)
    2: Decimal("19273.74"),  # personal no asalariado (persona)
    3: Decimal("119.67"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("1070.76"),  # potencia fiscal vehículo (CVF)
}
_AMBULANTE_ALIMENTACION_663_1 = {
    1: Decimal("1398.29"),  # personal asalariado (persona)
    2: Decimal("13989.21"),  # personal no asalariado (persona)
    3: Decimal("113.37"),  # potencia fiscal vehículo (CVF)
}
_HOSPEDAJE_HOTEL_681 = {
    1: Decimal("6223.02"),  # personal asalariado (persona)
    2: Decimal("20438.98"),  # personal no asalariado (persona)
    3: Decimal("371.62"),  # número de plazas (plaza)
}
_REPARACION_VEHICULOS_691_2 = {
    1: Decimal("4157.08"),  # personal asalariado (persona)
    2: Decimal("17094.42"),  # personal no asalariado (persona)
    3: Decimal("27.08"),  # superficie del local (m2)
}
_TRANSPORTE_URBANO_721_1 = {
    1: Decimal("2981.02"),  # personal asalariado (persona)
    2: Decimal("16016.97"),  # personal no asalariado (persona)
    3: Decimal("121.40"),  # número de asientos (asiento)
}

# Phase 4 next-priority activities (#516): remaining reparaciones,
# engrase/lavado, mudanzas, mensajería, enseñanza, servicios personales, and
# the 659.4/691.9 epígrafe-collision pairs (resolved via the "a"/"b"
# key-namespace suffix convention — see the registry parameter file's Phase 4
# note), independently transcribed from the bundled Orden HAC/1347/2024
# Anexo II and cross-checked byte-identical against the AEAT Manual práctico
# de Renta 2025, Parte 1, Capítulo 8 apéndice.
_PAPELERIA_659_4A = {
    1: Decimal("4648.37"),  # personal asalariado (persona)
    2: Decimal("17176.30"),  # personal no asalariado (persona)
    3: Decimal("57.94"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("30.86"),  # superficie del local (m2)
    5: Decimal("535.38"),  # potencia fiscal vehículo (CVF)
}
_QUIOSCOS_PRENSA_659_4B = {
    1: Decimal("3476.83"),  # personal asalariado (persona)
    2: Decimal("17220.39"),  # personal no asalariado (persona)
    3: Decimal("403.11"),  # consumo de energía eléctrica (100 kWh)
    4: Decimal("844.02"),  # superficie del local (m2)
}
_REPARACION_CALZADO_691_9A = {
    1: Decimal("1845.50"),  # personal asalariado (persona)
    2: Decimal("10014.78"),  # personal no asalariado (persona)
    3: Decimal("125.97"),  # consumo de energía eléctrica (100 kWh)
}
_REPARACION_OTROS_BIENES_691_9B = {
    1: Decimal("4094.10"),  # personal asalariado (persona)
    2: Decimal("16187.42"),  # personal no asalariado (persona)
    3: Decimal("45.35"),  # superficie del local (m2)
}
_ENGRASE_LAVADO_751_5 = {
    1: Decimal("4667.27"),  # personal asalariado (persona)
    2: Decimal("19191.86"),  # personal no asalariado (persona)
    3: Decimal("30.23"),  # superficie del local (m2)
}
_MUDANZAS_757 = {
    1: Decimal("2566.32"),  # personal asalariado (persona)
    2: Decimal("10175.13"),  # personal no asalariado (persona)
    3: Decimal("48.08"),  # carga vehículos (tonelada)
}
_MENSAJERIA_849_5 = {
    1: Decimal("2728.59"),  # personal asalariado (persona)
    2: Decimal("10090.99"),  # personal no asalariado (persona)
    3: Decimal("126.21"),  # carga vehículos (tonelada)
}
_AUTOESCUELA_933_1 = {
    1: Decimal("3067.42"),  # personal asalariado (persona)
    2: Decimal("20596.45"),  # personal no asalariado (persona)
    3: Decimal("774.72"),  # número de vehículos (vehículo)
    4: Decimal("258.24"),  # potencia fiscal vehículo (CVF)
}
_OTRAS_ENSENANZAS_933_9 = {
    1: Decimal("1253.49"),  # personal asalariado (persona)
    2: Decimal("15727.62"),  # personal no asalariado (persona)
    3: Decimal("62.36"),  # superficie del local (m2)
}
_ESCUELAS_DEPORTE_967_2 = {
    1: Decimal("7035.55"),  # personal asalariado (persona)
    2: Decimal("14215.95"),  # personal no asalariado (persona)
    3: Decimal("34.01"),  # superficie del local (m2)
}
_TINTORERIA_971_1 = {
    1: Decimal("4553.90"),  # personal asalariado (persona)
    2: Decimal("16773.19"),  # personal no asalariado (persona)
    3: Decimal("45.98"),  # consumo de energía eléctrica (100 kWh)
}
_INSTITUTOS_BELLEZA_972_2 = {
    1: Decimal("1788.80"),  # personal asalariado (persona)
    2: Decimal("14896.21"),  # personal no asalariado (persona)
    3: Decimal("88.18"),  # superficie del local (m2)
    4: Decimal("55.43"),  # consumo de energía eléctrica (100 kWh)
}
_COPISTERIA_973_3 = {
    1: Decimal("4125.59"),  # personal asalariado (persona)
    2: Decimal("17044.03"),  # personal no asalariado (persona)
    3: Decimal("541.68"),  # potencia eléctrica (KW contratado)
}
_FRUTAS_VERDURAS_641 = {
    1: Decimal("2387.18"),  # personal asalariado (persona)
    2: Decimal("10581.66"),  # personal no asalariado (persona)
    3: Decimal("57.94"),  # superficie local independiente (m2)
    4: Decimal("88.18"),  # superficie local no independiente (m2)
    5: Decimal("1.01"),  # carga elementos de transporte (kilogramo)
}
_QUIOSCOS_SERVICIOS_675 = {
    1: Decimal("2802.88"),  # personal asalariado (persona)
    2: Decimal("14461.60"),  # personal no asalariado (persona)
    3: Decimal("107.07"),  # potencia eléctrica (KW contratado)
    4: Decimal("26.45"),  # superficie del local (m2)
}
_CHOCOLATERIAS_676 = {
    1: Decimal("2418.67"),  # personal asalariado (persona)
    2: Decimal("20016.97"),  # personal no asalariado (persona)
    3: Decimal("541.68"),  # potencia eléctrica (KW contratado)
    4: Decimal("220.45"),  # mesas (mesa)
    5: Decimal("806.23"),  # máquinas tipo «A»
}

_REDUCCION_GENERAL_2025 = Decimal("0.05")


def _run_modulos_engine(
    epigrafe: str | None,
    *,
    modulo_1: Decimal = Decimal("0"),
    modulo_2: Decimal = Decimal("0"),
    modulo_3: Decimal = Decimal("0"),
    modulo_4: Decimal = Decimal("0"),
    modulo_5: Decimal = Decimal("0"),
    modulo_6: Decimal = Decimal("0"),
    modulo_7: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal]:
    snapshot = _committed_snapshot("131", 2025, "1T")
    text_inputs = {"modulos-epigrafe": epigrafe} if epigrafe else {}
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "modulos-1-unidades": modulo_1,
            "modulos-2-unidades": modulo_2,
            "modulos-3-unidades": modulo_3,
            "modulos-4-unidades": modulo_4,
            "modulos-5-unidades": modulo_5,
            "modulos-6-unidades": modulo_6,
            "modulos-7-unidades": modulo_7,
        },
        text_inputs=text_inputs,
        date_context={"filing_period": snapshot.filing_period.end_date},
    )
    values = result.values
    return values["modulos-rendimiento-neto-previo"], values["modulos-rendimiento-neto-actividad"]


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


class TestPeluqueria9721EstimacionObjetiva:
    """Epígrafe IAE 972.1 (Servicios de peluquería de señora y caballero)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 50 m2 local, 30 (100 kWh).
        previo, _actividad = _run_modulos_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("2") * _PELUQUERIA_972_1[1]
            + Decimal("1") * _PELUQUERIA_972_1[2]
            + Decimal("50") * _PELUQUERIA_972_1[3]
            + Decimal("30") * _PELUQUERIA_972_1[4],
        )
        assert previo == expected_previo == Decimal("23153.67")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("21995.99")


class TestAutotaxi7212EstimacionObjetiva:
    """Epígrafe IAE 721.2 (Transporte por autotaxis)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 0 personal asalariado, 1 personal no asalariado (titular), 40 (1.000 km).
        previo, _actividad = _run_modulos_engine(
            "721.2",
            modulo_1=Decimal("0"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = _quantize(Decimal("1") * _AUTOTAXI_721_2[2] + Decimal("40") * _AUTOTAXI_721_2[3])
        assert previo == expected_previo == Decimal("9460.09")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "721.2",
            modulo_1=Decimal("0"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("8987.09")


class TestTransporteMercancias722EstimacionObjetiva:
    """Epígrafe IAE 722 (Transporte de mercancías por carretera)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 0 personal no asalariado, 8 toneladas carga.
        previo, _actividad = _run_modulos_engine(
            "722",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("0"),
            modulo_3=Decimal("8"),
        )
        expected_previo = _quantize(Decimal("1") * _MERCANCIAS_722[1] + Decimal("8") * _MERCANCIAS_722[3])
        assert previo == expected_previo == Decimal("3738.27")


class TestRestauranteDosTenedores6714EstimacionObjetiva:
    """Epígrafe IAE 671.4 (Restaurantes de dos tenedores)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 8 kW potencia
        # eléctrica, 3 mesas, 1 máquina tipo «A».
        previo, _actividad = _run_modulos_engine(
            "671.4",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("8"),
            modulo_4=Decimal("3"),
            modulo_5=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("2") * _RESTAURANTE_DOS_TENEDORES_671_4[1]
            + Decimal("1") * _RESTAURANTE_DOS_TENEDORES_671_4[2]
            + Decimal("8") * _RESTAURANTE_DOS_TENEDORES_671_4[3]
            + Decimal("3") * _RESTAURANTE_DOS_TENEDORES_671_4[4]
            + Decimal("1") * _RESTAURANTE_DOS_TENEDORES_671_4[5],
        )
        assert previo == expected_previo == Decimal("29301.08")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "671.4",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("8"),
            modulo_4=Decimal("3"),
            modulo_5=Decimal("1"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("27836.03")


class TestRestauranteUnTenedor6715EstimacionObjetiva:
    """Epígrafe IAE 671.5 (Restaurantes de un tenedor)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 0 personal no asalariado, 6 kW potencia
        # eléctrica, 4 mesas, 2 máquinas tipo «B».
        previo, _actividad = _run_modulos_engine(
            "671.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("0"),
            modulo_3=Decimal("6"),
            modulo_4=Decimal("4"),
            modulo_6=Decimal("2"),
        )
        expected_previo = _quantize(
            Decimal("1") * _RESTAURANTE_UN_TENEDOR_671_5[1]
            + Decimal("6") * _RESTAURANTE_UN_TENEDOR_671_5[3]
            + Decimal("4") * _RESTAURANTE_UN_TENEDOR_671_5[4]
            + Decimal("2") * _RESTAURANTE_UN_TENEDOR_671_5[6],
        )
        assert previo == expected_previo == Decimal("12861.72")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "671.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("0"),
            modulo_3=Decimal("6"),
            modulo_4=Decimal("4"),
            modulo_6=Decimal("2"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("12218.63")


class TestCafeterias6721EstimacionObjetiva:
    """Epígrafe IAE 672.1, 2 y 3 (Cafeterías)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 3 personal asalariado, 1 personal no asalariado, 10 kW potencia
        # eléctrica.
        previo, _actividad = _run_modulos_engine(
            "672.1",
            modulo_1=Decimal("3"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
        )
        expected_previo = _quantize(
            Decimal("3") * _CAFETERIAS_672_1[1]
            + Decimal("1") * _CAFETERIAS_672_1[2]
            + Decimal("10") * _CAFETERIAS_672_1[3],
        )
        assert previo == expected_previo == Decimal("22876.50")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "672.1",
            modulo_1=Decimal("3"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("21732.68")


class TestComercioCarne6421EstimacionObjetiva:
    """Epígrafe IAE 642.1, 2, 3 y 4 (Comercio al por menor de carne y despojos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 40 m2 superficie
        # local no independiente.
        previo, _actividad = _run_modulos_engine(
            "642.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("40"),
        )
        expected_previo = _quantize(
            Decimal("1") * _CARNE_642_1[1] + Decimal("1") * _CARNE_642_1[2] + Decimal("40") * _CARNE_642_1[4],
        )
        assert previo == expected_previo == Decimal("16621.95")


class TestPanPasteleria6441EstimacionObjetiva:
    """Epígrafe IAE 644.1 (Comercio al por menor de pan, pastelería...) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_uses_all_seven_modulo_slots(self) -> None:
        # 1 personal asalariado de fabricación, 1 resto personal asalariado,
        # 1 personal no asalariado, 30 m2 superficie del local de
        # fabricación, 2 (100 dm2) superficie del horno. This activity has 7
        # signos; a 4-slot engine would silently drop módulo 7 (superficie
        # del horno, 629,86 €/unit) — the exact over-truncation risk the
        # 2026-07-01-modelo-131-eo-modulos-engine-adr Option D rejected.
        previo, _actividad = _run_modulos_engine(
            "644.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("1"),
            modulo_4=Decimal("30"),
            modulo_7=Decimal("2"),
        )
        expected_previo = _quantize(
            Decimal("1") * _PAN_PASTELERIA_644_1[1]
            + Decimal("1") * _PAN_PASTELERIA_644_1[2]
            + Decimal("1") * _PAN_PASTELERIA_644_1[3]
            + Decimal("30") * _PAN_PASTELERIA_644_1[4]
            + Decimal("2") * _PAN_PASTELERIA_644_1[7],
        )
        assert previo == expected_previo == Decimal("24570.90")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "644.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("1"),
            modulo_4=Decimal("30"),
            modulo_7=Decimal("2"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("23342.36")


class TestComercioAlimenticios6471EstimacionObjetiva:
    """Epígrafe IAE 647.1 (Comercio al por menor de alimentación en establecimientos con vendedor)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 40 m2 superficie del local independiente.
        previo, _actividad = _run_modulos_engine(
            "647.1",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = _quantize(Decimal("1") * _ALIMENTACION_647_1[1] + Decimal("40") * _ALIMENTACION_647_1[3])
        assert previo == expected_previo == Decimal("1832.67")


class TestCafesEspecial6731EstimacionObjetiva:
    """Epígrafe IAE 673.1 (Cafés y bares de categoría especial) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 5 metros longitud de barra.
        previo, _actividad = _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("1"),
            modulo_5=Decimal("5"),
        )
        expected_previo = _quantize(
            Decimal("1") * _CAFES_ESPECIAL_673_1[1] + Decimal("5") * _CAFES_ESPECIAL_673_1[5],
        )
        assert previo == expected_previo == Decimal("5914.40")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("1"),
            modulo_5=Decimal("5"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("5618.68")


class TestOtrosCafes6732EstimacionObjetiva:
    """Epígrafe IAE 673.2 (Otros cafés y bares)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 3 mesas.
        previo, _actividad = _run_modulos_engine(
            "673.2",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("3"),
        )
        expected_previo = _quantize(
            Decimal("1") * _OTROS_CAFES_673_2[1]
            + Decimal("1") * _OTROS_CAFES_673_2[2]
            + Decimal("3") * _OTROS_CAFES_673_2[4],
        )
        assert previo == expected_previo == Decimal("13416.02")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "673.2",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("3"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("12745.22")


class TestHuevosAves6425EstimacionObjetiva:
    """Epígrafe IAE 642.5 (Comercio al por menor de huevos, aves, conejos de granja, caza)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 20 m2 superficie local independiente.
        previo, _actividad = _run_modulos_engine(
            "642.5",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _HUEVOS_AVES_642_5[1] + Decimal("20") * _HUEVOS_AVES_642_5[4],
        )
        assert previo == expected_previo == Decimal("3923.96")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "642.5",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("3727.76")


class TestCasquerias6426EstimacionObjetiva:
    """Epígrafe IAE 642.6 (Comercio al por menor en casquerías)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 30 m2 superficie local no independiente.
        previo, _actividad = _run_modulos_engine(
            "642.6",
            modulo_2=Decimal("1"),
            modulo_4=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("1") * _CASQUERIAS_642_6[2] + Decimal("30") * _CASQUERIAS_642_6[4],
        )
        assert previo == expected_previo == Decimal("13176.54")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "642.6",
            modulo_2=Decimal("1"),
            modulo_4=Decimal("30"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("12517.71")


class TestPescados6431EstimacionObjetiva:
    """Epígrafe IAE 643.1 y 2 (Comercio al por menor de pescados)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado.
        previo, _actividad = _run_modulos_engine(
            "643.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _PESCADOS_643_1[1] + Decimal("1") * _PESCADOS_643_1[2],
        )
        assert previo == expected_previo == Decimal("17119.61")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "643.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("16263.63")


class TestDespachosPan6442EstimacionObjetiva:
    """Epígrafe IAE 644.2 (Despachos de pan, panes especiales y bollería) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado de fabricación, 1 personal no asalariado.
        previo, _actividad = _run_modulos_engine(
            "644.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _DESPACHOS_PAN_644_2[1] + Decimal("1") * _DESPACHOS_PAN_644_2[3],
        )
        assert previo == expected_previo == Decimal("20401.19")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "644.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("1"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("19381.13")


class TestPasteleria6443EstimacionObjetiva:
    """Epígrafe IAE 644.3 (Comercio al por menor de pastelería, bollería y confitería) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado de fabricación, 20 m2 superficie del local de fabricación.
        previo, _actividad = _run_modulos_engine(
            "644.3",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _PASTELERIA_644_3[1] + Decimal("20") * _PASTELERIA_644_3[4],
        )
        assert previo == expected_previo == Decimal("7237.09")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "644.3",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("6875.24")


class TestMasasFritas6446EstimacionObjetiva:
    """Epígrafe IAE 644.6 (Comercio al por menor de masas fritas, patatas fritas y similares)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado de fabricación, 1 resto personal asalariado.
        previo, _actividad = _run_modulos_engine(
            "644.6",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _MASAS_FRITAS_644_6[1] + Decimal("1") * _MASAS_FRITAS_644_6[2],
        )
        assert previo == expected_previo == Decimal("9107.78")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "644.6",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("8652.39")


class TestAutoservicio6472EstimacionObjetiva:
    """Epígrafe IAE 647.2 y 3 (Comercio al por menor de alimentación en autoservicio < 400 m2)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 30 m2 superficie del local.
        previo, _actividad = _run_modulos_engine(
            "647.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("1") * _AUTOSERVICIO_647_2[1] + Decimal("30") * _AUTOSERVICIO_647_2[3],
        )
        assert previo == expected_previo == Decimal("2488.10")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "647.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("2363.70")


class TestLenceria6513EstimacionObjetiva:
    """Epígrafe IAE 651.3 y 5 (Comercio al por menor de lencería, corsetería) — corpus-typo correction."""

    def test_fase_1_rendimiento_neto_previo_matches_manual_correction_not_orden_typo(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado. Proves the registry
        # holds the AEAT Manual's "11.998,85" figure, not the bundled Orden
        # HTML's literal typo "11.998.85".
        previo, _actividad = _run_modulos_engine(
            "651.3",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _LENCERIA_651_3[1] + Decimal("1") * _LENCERIA_651_3[2],
        )
        assert previo == expected_previo == Decimal("14197.06")


class TestTextil6511EstimacionObjetiva:
    """Epígrafe IAE 651.1 (Comercio al por menor de productos textiles)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 20 m2 local independiente.
        previo, _actividad = _run_modulos_engine(
            "651.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _TEXTIL_651_1[1] + Decimal("1") * _TEXTIL_651_1[2] + Decimal("20") * _TEXTIL_651_1[4],
        )
        assert previo == expected_previo == Decimal("17529.19")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "651.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("16652.73")


class TestMuebles6531EstimacionObjetiva:
    """Epígrafe IAE 653.1 (Comercio al por menor de muebles)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 30 m2 local.
        previo, _actividad = _run_modulos_engine(
            "653.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("1") * _MUEBLES_653_1[1] + Decimal("1") * _MUEBLES_653_1[2] + Decimal("30") * _MUEBLES_653_1[4],
        )
        assert previo == expected_previo == Decimal("20766.62")


class TestRecambios6542EstimacionObjetiva:
    """Epígrafe IAE 654.2 (Comercio al por menor de accesorios y piezas de recambio para vehículos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 10 CVF potencia fiscal vehículo.
        previo, _actividad = _run_modulos_engine(
            "654.2",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("10"),
        )
        expected_previo = _quantize(
            Decimal("1") * _RECAMBIOS_654_2[1] + Decimal("10") * _RECAMBIOS_654_2[4],
        )
        assert previo == expected_previo == Decimal("9271.52")


class TestOptica6593EstimacionObjetiva:
    """Epígrafe IAE 659.3 (Comercio al por menor de aparatos e instrumentos ópticos y fotográficos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado.
        previo, _actividad = _run_modulos_engine(
            "659.3",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _OPTICA_659_3[1] + Decimal("1") * _OPTICA_659_3[2],
        )
        assert previo == expected_previo == Decimal("26447.86")


class TestAmbulanteAlimentacion6631EstimacionObjetiva:
    """Epígrafe IAE 663.1 (Comercio ambulante de productos alimenticios)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 2 CVF potencia fiscal vehículo.
        previo, _actividad = _run_modulos_engine(
            "663.1",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("2"),
        )
        expected_previo = _quantize(
            Decimal("1") * _AMBULANTE_ALIMENTACION_663_1[1] + Decimal("2") * _AMBULANTE_ALIMENTACION_663_1[3],
        )
        assert previo == expected_previo == Decimal("1625.03")


class TestHospedajeHotel681EstimacionObjetiva:
    """Epígrafe IAE 681 (Servicio de hospedaje en hoteles y moteles de una o dos estrellas)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 20 plazas.
        previo, _actividad = _run_modulos_engine(
            "681",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _HOSPEDAJE_HOTEL_681[1]
            + Decimal("1") * _HOSPEDAJE_HOTEL_681[2]
            + Decimal("20") * _HOSPEDAJE_HOTEL_681[3],
        )
        assert previo == expected_previo == Decimal("34094.40")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "681",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("32389.68")


class TestReparacionVehiculos6912EstimacionObjetiva:
    """Epígrafe IAE 691.2 (Reparación de vehículos automóviles, bicicletas y otros)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 30 m2 superficie del local.
        previo, _actividad = _run_modulos_engine(
            "691.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("1") * _REPARACION_VEHICULOS_691_2[1] + Decimal("30") * _REPARACION_VEHICULOS_691_2[3],
        )
        assert previo == expected_previo == Decimal("4969.48")


class TestTransporteUrbano7211EstimacionObjetiva:
    """Epígrafe IAE 721.1 y 3 (Transporte urbano colectivo y de viajeros por carretera)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 30 asientos.
        previo, _actividad = _run_modulos_engine(
            "721.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("2") * _TRANSPORTE_URBANO_721_1[1]
            + Decimal("1") * _TRANSPORTE_URBANO_721_1[2]
            + Decimal("30") * _TRANSPORTE_URBANO_721_1[3],
        )
        assert previo == expected_previo == Decimal("25621.01")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "721.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("24339.96")


class TestPapeleria6594AEstimacionObjetiva:
    """Epígrafe IAE 659.4a (Comercio al por menor de libros, periódicos, papelería...)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 20 (100 kWh),
        # 15 m2 local, 1 vehículo (CVF).
        previo, _actividad = _run_modulos_engine(
            "659.4a",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
            modulo_4=Decimal("15"),
            modulo_5=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _PAPELERIA_659_4A[1]
            + Decimal("1") * _PAPELERIA_659_4A[2]
            + Decimal("20") * _PAPELERIA_659_4A[3]
            + Decimal("15") * _PAPELERIA_659_4A[4]
            + Decimal("1") * _PAPELERIA_659_4A[5],
        )
        assert previo == expected_previo == Decimal("23981.75")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "659.4a",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
            modulo_4=Decimal("15"),
            modulo_5=Decimal("1"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("22782.66")


class TestQuioscosPrensa6594BEstimacionObjetiva:
    """Epígrafe IAE 659.4b (Comercio al por menor de prensa, revistas y libros en quioscos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 10 (100 kWh), 4 m2 local.
        previo, _actividad = _run_modulos_engine(
            "659.4b",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
            modulo_4=Decimal("4"),
        )
        expected_previo = _quantize(
            Decimal("1") * _QUIOSCOS_PRENSA_659_4B[2]
            + Decimal("10") * _QUIOSCOS_PRENSA_659_4B[3]
            + Decimal("4") * _QUIOSCOS_PRENSA_659_4B[4],
        )
        assert previo == expected_previo == Decimal("24627.57")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "659.4b",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
            modulo_4=Decimal("4"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("23396.19")

    def test_bare_unsuffixed_epigrafe_collision_code_stays_untabled(self) -> None:
        # The bare "659.4" (no "a"/"b" disambiguating suffix) must NOT resolve
        # to either collision activity's coefficients — a lookup on the
        # unsuffixed code would silently misattribute one activity's figures
        # to the other. It stays untabled behind the advisory guard.
        previo, actividad = _run_modulos_engine("659.4", modulo_1=Decimal("1"), modulo_2=Decimal("1"))
        assert previo == Decimal("0")
        assert actividad == Decimal("0")


class TestReparacionCalzado6919AEstimacionObjetiva:
    """Epígrafe IAE 691.9a (Reparación de calzado)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 20 (100 kWh).
        previo, _actividad = _run_modulos_engine(
            "691.9a",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _REPARACION_CALZADO_691_9A[2] + Decimal("20") * _REPARACION_CALZADO_691_9A[3],
        )
        assert previo == expected_previo == Decimal("12534.18")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "691.9a",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("11907.47")


class TestReparacionOtrosBienes6919BEstimacionObjetiva:
    """Epígrafe IAE 691.9b (Reparación de otros bienes de consumo n.c.o.p.)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 25 m2 local.
        previo, _actividad = _run_modulos_engine(
            "691.9b",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("25"),
        )
        expected_previo = _quantize(
            Decimal("1") * _REPARACION_OTROS_BIENES_691_9B[1] + Decimal("25") * _REPARACION_OTROS_BIENES_691_9B[3],
        )
        assert previo == expected_previo == Decimal("5227.85")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "691.9b",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("25"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("4966.46")

    def test_bare_unsuffixed_epigrafe_collision_code_stays_untabled(self) -> None:
        previo, actividad = _run_modulos_engine("691.9", modulo_1=Decimal("1"), modulo_2=Decimal("1"))
        assert previo == Decimal("0")
        assert actividad == Decimal("0")


class TestEngraseLavado7515EstimacionObjetiva:
    """Epígrafe IAE 751.5 (Engrase y lavado de vehículos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 40 m2 local.
        previo, _actividad = _run_modulos_engine(
            "751.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = _quantize(
            Decimal("1") * _ENGRASE_LAVADO_751_5[1]
            + Decimal("1") * _ENGRASE_LAVADO_751_5[2]
            + Decimal("40") * _ENGRASE_LAVADO_751_5[3],
        )
        assert previo == expected_previo == Decimal("25068.33")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "751.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("23814.91")


class TestMudanzas757EstimacionObjetiva:
    """Epígrafe IAE 757 (Servicios de mudanzas)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 15 toneladas carga vehículos.
        previo, _actividad = _run_modulos_engine(
            "757",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("15"),
        )
        expected_previo = _quantize(Decimal("1") * _MUDANZAS_757[2] + Decimal("15") * _MUDANZAS_757[3])
        assert previo == expected_previo == Decimal("10896.33")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "757",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("15"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("10351.51")


class TestMensajeria8495EstimacionObjetiva:
    """Epígrafe IAE 849.5 (Transporte de mensajería y recadería con medios propios)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 3 toneladas carga vehículos.
        previo, _actividad = _run_modulos_engine(
            "849.5",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_previo = _quantize(Decimal("1") * _MENSAJERIA_849_5[1] + Decimal("3") * _MENSAJERIA_849_5[3])
        assert previo == expected_previo == Decimal("3107.22")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "849.5",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("2951.86")


class TestAutoescuela9331EstimacionObjetiva:
    """Epígrafe IAE 933.1 (Enseñanza de conducción de vehículos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 2 vehículos, 4 CVF.
        previo, _actividad = _run_modulos_engine(
            "933.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("2"),
            modulo_4=Decimal("4"),
        )
        expected_previo = _quantize(
            Decimal("1") * _AUTOESCUELA_933_1[1]
            + Decimal("1") * _AUTOESCUELA_933_1[2]
            + Decimal("2") * _AUTOESCUELA_933_1[3]
            + Decimal("4") * _AUTOESCUELA_933_1[4],
        )
        assert previo == expected_previo == Decimal("26246.27")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "933.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("2"),
            modulo_4=Decimal("4"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("24933.96")


class TestOtrasEnsenanzas9339EstimacionObjetiva:
    """Epígrafe IAE 933.9 (Otras actividades de enseñanza: idiomas, corte y confección, etc.)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 40 m2 local.
        previo, _actividad = _run_modulos_engine(
            "933.9",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = _quantize(
            Decimal("1") * _OTRAS_ENSENANZAS_933_9[2] + Decimal("40") * _OTRAS_ENSENANZAS_933_9[3],
        )
        assert previo == expected_previo == Decimal("18222.02")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "933.9",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("17310.92")


class TestEscuelasDeporte9672EstimacionObjetiva:
    """Epígrafe IAE 967.2 (Escuelas y servicios de perfeccionamiento del deporte)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 60 m2 local.
        previo, _actividad = _run_modulos_engine(
            "967.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("60"),
        )
        expected_previo = _quantize(
            Decimal("1") * _ESCUELAS_DEPORTE_967_2[1] + Decimal("60") * _ESCUELAS_DEPORTE_967_2[3],
        )
        assert previo == expected_previo == Decimal("9076.15")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "967.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("60"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("8622.34")


class TestTintoreria9711EstimacionObjetiva:
    """Epígrafe IAE 971.1 (Tinte, limpieza en seco, lavado y planchado)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 30 (100 kWh).
        previo, _actividad = _run_modulos_engine(
            "971.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = _quantize(
            Decimal("1") * _TINTORERIA_971_1[1]
            + Decimal("1") * _TINTORERIA_971_1[2]
            + Decimal("30") * _TINTORERIA_971_1[3],
        )
        assert previo == expected_previo == Decimal("22706.49")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "971.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("21571.17")


class TestInstitutosBelleza9722EstimacionObjetiva:
    """Epígrafe IAE 972.2 (Salones e institutos de belleza)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 40 m2 local, 20 (100 kWh).
        previo, _actividad = _run_modulos_engine(
            "972.2",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
            modulo_4=Decimal("20"),
        )
        expected_previo = _quantize(
            Decimal("1") * _INSTITUTOS_BELLEZA_972_2[2]
            + Decimal("40") * _INSTITUTOS_BELLEZA_972_2[3]
            + Decimal("20") * _INSTITUTOS_BELLEZA_972_2[4],
        )
        assert previo == expected_previo == Decimal("19532.01")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "972.2",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
            modulo_4=Decimal("20"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("18555.41")


class TestCopisteria9733EstimacionObjetiva:
    """Epígrafe IAE 973.3 (Servicios de copias de documentos con máquinas fotocopiadoras)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 3 KW contratado.
        previo, _actividad = _run_modulos_engine(
            "973.3",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_previo = _quantize(Decimal("1") * _COPISTERIA_973_3[2] + Decimal("3") * _COPISTERIA_973_3[3])
        assert previo == expected_previo == Decimal("18669.07")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "973.3",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("17735.62")


class TestFrutasVerduras641EstimacionObjetiva:
    """Epígrafe IAE 641 (Comercio al por menor de frutas, verduras, hortalizas y tubérculos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 30 m2 local
        # independiente, 500 kg carga elementos de transporte.
        previo, _actividad = _run_modulos_engine(
            "641",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
            modulo_5=Decimal("500"),
        )
        expected_previo = _quantize(
            Decimal("1") * _FRUTAS_VERDURAS_641[1]
            + Decimal("1") * _FRUTAS_VERDURAS_641[2]
            + Decimal("30") * _FRUTAS_VERDURAS_641[3]
            + Decimal("500") * _FRUTAS_VERDURAS_641[5],
        )
        assert previo == expected_previo == Decimal("15212.04")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "641",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
            modulo_5=Decimal("500"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("14451.44")


class TestQuioscosServicios675EstimacionObjetiva:
    """Epígrafe IAE 675 (Servicios en quioscos, cajones, barracas u otros locales análogos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 5 KW contratado, 10 m2 local.
        previo, _actividad = _run_modulos_engine(
            "675",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("5"),
            modulo_4=Decimal("10"),
        )
        expected_previo = _quantize(
            Decimal("1") * _QUIOSCOS_SERVICIOS_675[2]
            + Decimal("5") * _QUIOSCOS_SERVICIOS_675[3]
            + Decimal("10") * _QUIOSCOS_SERVICIOS_675[4],
        )
        assert previo == expected_previo == Decimal("15261.45")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "675",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("5"),
            modulo_4=Decimal("10"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("14498.38")


class TestChocolaterias676EstimacionObjetiva:
    """Epígrafe IAE 676 (Servicios en chocolaterías, heladerías y horchaterías)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 3 KW contratado, 5 mesas, 1 máquina tipo A.
        previo, _actividad = _run_modulos_engine(
            "676",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
            modulo_4=Decimal("5"),
            modulo_5=Decimal("1"),
        )
        expected_previo = _quantize(
            Decimal("1") * _CHOCOLATERIAS_676[1]
            + Decimal("3") * _CHOCOLATERIAS_676[3]
            + Decimal("5") * _CHOCOLATERIAS_676[4]
            + Decimal("1") * _CHOCOLATERIAS_676[5],
        )
        assert previo == expected_previo == Decimal("5952.19")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, actividad = _run_modulos_engine(
            "676",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
            modulo_4=Decimal("5"),
            modulo_5=Decimal("1"),
        )
        expected_actividad = _quantize(previo - previo * _REDUCCION_GENERAL_2025)
        assert actividad == expected_actividad == Decimal("5654.58")


class TestModulosEngineNoSilentFabrication:
    """no-silent-under-declaration guard: an untabled epígrafe never fabricates a figure."""

    def test_untabled_epigrafe_resolves_to_zero_not_fabricated_figure(self) -> None:
        # A large positive unit count against an activity absent from the
        # bounded first-slice coefficient table must NOT be silently
        # multiplied by a wrong or absent coefficient; the internal
        # reference casilla resolves to zero, and the operator-declared
        # casilla 01 remains the authoritative manual input.
        previo, actividad = _run_modulos_engine(
            "699.9",  # not an Orden Anexo II epígrafe — remains untabled
            modulo_1=Decimal("5"),
            modulo_2=Decimal("3"),
        )
        assert previo == Decimal("0")
        assert actividad == Decimal("0")

    def test_blank_epigrafe_resolves_to_zero(self) -> None:
        previo, actividad = _run_modulos_engine(None, modulo_1=Decimal("5"))
        assert previo == Decimal("0")
        assert actividad == Decimal("0")

    def test_zero_units_on_tabled_epigrafe_resolves_to_zero(self) -> None:
        # A tabled epígrafe with no units declared (e.g. no activity conducted
        # yet this period) legitimately resolves to zero — not a silent-zero
        # violation, since the antecedent itself is zero.
        previo, actividad = _run_modulos_engine("972.1")
        assert previo == Decimal("0")
        assert actividad == Decimal("0")
