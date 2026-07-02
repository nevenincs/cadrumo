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


class TestModulosEngineNoSilentFabrication:
    """no-silent-under-declaration guard: an untabled epígrafe never fabricates a figure."""

    def test_untabled_epigrafe_resolves_to_zero_not_fabricated_figure(self) -> None:
        # A large positive unit count against an activity absent from the
        # bounded first-slice coefficient table must NOT be silently
        # multiplied by a wrong or absent coefficient; the internal
        # reference casilla resolves to zero, and the operator-declared
        # casilla 01 remains the authoritative manual input.
        previo, actividad = _run_modulos_engine(
            "659.4",  # comercio prensa en quioscos — not in the bounded first slice
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
