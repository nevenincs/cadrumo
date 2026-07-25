"""Modelo 131 módulos engine retail, repair, transport, and service activity cases.

See Also:
    :mod:`~domain.calculations.registry.tests._modelo_131_modulos_engine_support`
        Shared independent coefficient tables and oracle arithmetic.
    :mod:`~domain.calculations.registry._formula_runtime_m131`
        Extracted M131 módulos formula evaluators exercised here.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Registry runtime entry point reached through ``_run_modulos_engine``.
    :class:`~domain.calculations.registry.ParameterDefinition`
        Registry-authored coefficient and índice tables cross-checked by these
        cases.
    :mod:`~domain.calculations.registry.tests.test_modelo_131_modulos_engine_food`
        Sibling food and hospitality activity split using the same helper
        oracle.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.money import round_to_cents
from ._modelo_131_modulos_engine_support import (
    _AMBULANTE_ALIMENTACION_663_1,
    _AUTOESCUELA_933_1,
    _CHOCOLATERIAS_676,
    _COPISTERIA_973_3,
    _ENGRASE_LAVADO_751_5,
    _ESCUELAS_DEPORTE_967_2,
    _FRUTAS_VERDURAS_641,
    _HOSPEDAJE_HOTEL_681,
    _INSTITUTOS_BELLEZA_972_2,
    _LENCERIA_651_3,
    _MENSAJERIA_849_5,
    _MUDANZAS_757,
    _MUEBLES_653_1,
    _OPTICA_659_3,
    _OTRAS_ENSENANZAS_933_9,
    _PAPELERIA_659_4A,
    _QUIOSCOS_PRENSA_659_4B,
    _QUIOSCOS_SERVICIOS_675,
    _RECAMBIOS_654_2,
    _REDUCCION_GENERAL_2025,
    _REPARACION_CALZADO_691_9A,
    _REPARACION_OTROS_BIENES_691_9B,
    _REPARACION_VEHICULOS_691_2,
    _TEXTIL_651_1,
    _TINTORERIA_971_1,
    _TRANSPORTE_URBANO_721_1,
    _expected_minorado,
    _expected_modulos,
    _module_1_coefficient,
    _run_modulos_engine,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class TestLenceria6513EstimacionObjetiva:
    """Epígrafe IAE 651.3 y 5 (Comercio al por menor de lencería, corsetería) — corpus-typo correction."""

    def test_fase_1_rendimiento_neto_previo_matches_manual_correction_not_orden_typo(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado. Proves the registry
        # holds the AEAT Manual's "11.998,85" figure, not the bundled Orden
        # HTML's literal typo "11.998.85".
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "651.3",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _LENCERIA_651_3[1] + Decimal("1") * _LENCERIA_651_3[2],
        )
        assert previo == expected_previo == Decimal("14197.06")


class TestTextil6511EstimacionObjetiva:
    """Epígrafe IAE 651.1 (Comercio al por menor de productos textiles)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 20 m2 local independiente.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "651.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _TEXTIL_651_1[1] + Decimal("1") * _TEXTIL_651_1[2] + Decimal("20") * _TEXTIL_651_1[4],
        )
        assert previo == expected_previo == Decimal("17529.19")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "651.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="651.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("651.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="651.1")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestMuebles6531EstimacionObjetiva:
    """Epígrafe IAE 653.1 (Comercio al por menor de muebles)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 30 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "653.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("30"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _MUEBLES_653_1[1] + Decimal("1") * _MUEBLES_653_1[2] + Decimal("30") * _MUEBLES_653_1[4],
        )
        assert previo == expected_previo == Decimal("20766.62")


class TestRecambios6542EstimacionObjetiva:
    """Epígrafe IAE 654.2 (Comercio al por menor de accesorios y piezas de recambio para vehículos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 10 CVF potencia fiscal vehículo.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "654.2",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("10"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _RECAMBIOS_654_2[1] + Decimal("10") * _RECAMBIOS_654_2[4],
        )
        assert previo == expected_previo == Decimal("9271.52")


class TestOptica6593EstimacionObjetiva:
    """Epígrafe IAE 659.3 (Comercio al por menor de aparatos e instrumentos ópticos y fotográficos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "659.3",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _OPTICA_659_3[1] + Decimal("1") * _OPTICA_659_3[2],
        )
        assert previo == expected_previo == Decimal("26447.86")


class TestAmbulanteAlimentacion6631EstimacionObjetiva:
    """Epígrafe IAE 663.1 (Comercio ambulante de productos alimenticios)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 2 CVF potencia fiscal vehículo.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "663.1",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("2"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _AMBULANTE_ALIMENTACION_663_1[1] + Decimal("2") * _AMBULANTE_ALIMENTACION_663_1[3],
        )
        assert previo == expected_previo == Decimal("1625.03")


class TestHospedajeHotel681EstimacionObjetiva:
    """Epígrafe IAE 681 (Servicio de hospedaje en hoteles y moteles de una o dos estrellas)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 20 plazas.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "681",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _HOSPEDAJE_HOTEL_681[1]
            + Decimal("1") * _HOSPEDAJE_HOTEL_681[2]
            + Decimal("20") * _HOSPEDAJE_HOTEL_681[3],
        )
        assert previo == expected_previo == Decimal("34094.40")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "681",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="681",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("681"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="681")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestReparacionVehiculos6912EstimacionObjetiva:
    """Epígrafe IAE 691.2 (Reparación de vehículos automóviles, bicicletas y otros)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 30 m2 superficie del local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "691.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _REPARACION_VEHICULOS_691_2[1] + Decimal("30") * _REPARACION_VEHICULOS_691_2[3],
        )
        assert previo == expected_previo == Decimal("4969.48")


class TestTransporteUrbano7211EstimacionObjetiva:
    """Epígrafe IAE 721.1 y 3 (Transporte urbano colectivo y de viajeros por carretera)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 30 asientos.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "721.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = round_to_cents(
            Decimal("2") * _TRANSPORTE_URBANO_721_1[1]
            + Decimal("1") * _TRANSPORTE_URBANO_721_1[2]
            + Decimal("30") * _TRANSPORTE_URBANO_721_1[3],
        )
        assert previo == expected_previo == Decimal("25621.01")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "721.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="721.1",
            modulo_1=Decimal("2"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("721.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="721.1")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestPapeleria6594AEstimacionObjetiva:
    """Epígrafe IAE 659.4a (Comercio al por menor de libros, periódicos, papelería...)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 20 (100 kWh),
        # 15 m2 local, 1 vehículo (CVF).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "659.4a",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
            modulo_4=Decimal("15"),
            modulo_5=Decimal("1"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _PAPELERIA_659_4A[1]
            + Decimal("1") * _PAPELERIA_659_4A[2]
            + Decimal("20") * _PAPELERIA_659_4A[3]
            + Decimal("15") * _PAPELERIA_659_4A[4]
            + Decimal("1") * _PAPELERIA_659_4A[5],
        )
        assert previo == expected_previo == Decimal("23981.75")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "659.4a",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
            modulo_4=Decimal("15"),
            modulo_5=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="659.4a",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("659.4a"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="659.4a")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestQuioscosPrensa6594BEstimacionObjetiva:
    """Epígrafe IAE 659.4b (Comercio al por menor de prensa, revistas y libros en quioscos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 10 (100 kWh), 4 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "659.4b",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
            modulo_4=Decimal("4"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _QUIOSCOS_PRENSA_659_4B[2]
            + Decimal("10") * _QUIOSCOS_PRENSA_659_4B[3]
            + Decimal("4") * _QUIOSCOS_PRENSA_659_4B[4],
        )
        assert previo == expected_previo == Decimal("24627.57")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "659.4b",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
            modulo_4=Decimal("4"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="659.4b",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("659.4b"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="659.4b")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad

    def test_bare_unsuffixed_epigrafe_collision_code_stays_untabled(self) -> None:
        # The bare "659.4" (no "a"/"b" disambiguating suffix) must NOT resolve
        # to either collision activity's coefficients — a lookup on the
        # unsuffixed code would silently misattribute one activity's figures
        # to the other. It stays untabled behind the advisory guard.
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "659.4", modulo_1=Decimal("1"), modulo_2=Decimal("1")
        )
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")


class TestReparacionCalzado6919AEstimacionObjetiva:
    """Epígrafe IAE 691.9a (Reparación de calzado)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 20 (100 kWh).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "691.9a",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _REPARACION_CALZADO_691_9A[2] + Decimal("20") * _REPARACION_CALZADO_691_9A[3],
        )
        assert previo == expected_previo == Decimal("12534.18")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "691.9a",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="691.9a",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("691.9a"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="691.9a")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestReparacionOtrosBienes6919BEstimacionObjetiva:
    """Epígrafe IAE 691.9b (Reparación de otros bienes de consumo n.c.o.p.)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 25 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "691.9b",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("25"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _REPARACION_OTROS_BIENES_691_9B[1] + Decimal("25") * _REPARACION_OTROS_BIENES_691_9B[3],
        )
        assert previo == expected_previo == Decimal("5227.85")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "691.9b",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("25"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="691.9b",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("691.9b"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="691.9b")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad

    def test_bare_unsuffixed_epigrafe_collision_code_stays_untabled(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "691.9", modulo_1=Decimal("1"), modulo_2=Decimal("1")
        )
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")


class TestEngraseLavado7515EstimacionObjetiva:
    """Epígrafe IAE 751.5 (Engrase y lavado de vehículos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 40 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "751.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _ENGRASE_LAVADO_751_5[1]
            + Decimal("1") * _ENGRASE_LAVADO_751_5[2]
            + Decimal("40") * _ENGRASE_LAVADO_751_5[3],
        )
        assert previo == expected_previo == Decimal("25068.33")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "751.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="751.5",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("751.5"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="751.5")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestMudanzas757EstimacionObjetiva:
    """Epígrafe IAE 757 (Servicios de mudanzas)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 15 toneladas carga vehículos.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "757",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("15"),
        )
        expected_previo = round_to_cents(Decimal("1") * _MUDANZAS_757[2] + Decimal("15") * _MUDANZAS_757[3])
        assert previo == expected_previo == Decimal("10896.33")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "757",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("15"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="757",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("757"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="757")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestMensajeria8495EstimacionObjetiva:
    """Epígrafe IAE 849.5 (Transporte de mensajería y recadería con medios propios)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 3 toneladas carga vehículos.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "849.5",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_previo = round_to_cents(Decimal("1") * _MENSAJERIA_849_5[1] + Decimal("3") * _MENSAJERIA_849_5[3])
        assert previo == expected_previo == Decimal("3107.22")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "849.5",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="849.5",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("849.5"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="849.5")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestAutoescuela9331EstimacionObjetiva:
    """Epígrafe IAE 933.1 (Enseñanza de conducción de vehículos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 2 vehículos, 4 CVF.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "933.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("2"),
            modulo_4=Decimal("4"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _AUTOESCUELA_933_1[1]
            + Decimal("1") * _AUTOESCUELA_933_1[2]
            + Decimal("2") * _AUTOESCUELA_933_1[3]
            + Decimal("4") * _AUTOESCUELA_933_1[4],
        )
        assert previo == expected_previo == Decimal("26246.27")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "933.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("2"),
            modulo_4=Decimal("4"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="933.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("933.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="933.1")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestOtrasEnsenanzas9339EstimacionObjetiva:
    """Epígrafe IAE 933.9 (Otras actividades de enseñanza: idiomas, corte y confección, etc.)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 40 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "933.9",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _OTRAS_ENSENANZAS_933_9[2] + Decimal("40") * _OTRAS_ENSENANZAS_933_9[3],
        )
        assert previo == expected_previo == Decimal("18222.02")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "933.9",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="933.9",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("933.9"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="933.9")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestEscuelasDeporte9672EstimacionObjetiva:
    """Epígrafe IAE 967.2 (Escuelas y servicios de perfeccionamiento del deporte)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 60 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "967.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("60"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _ESCUELAS_DEPORTE_967_2[1] + Decimal("60") * _ESCUELAS_DEPORTE_967_2[3],
        )
        assert previo == expected_previo == Decimal("9076.15")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "967.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("60"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="967.2",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("967.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="967.2")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestTintoreria9711EstimacionObjetiva:
    """Epígrafe IAE 971.1 (Tinte, limpieza en seco, lavado y planchado)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 30 (100 kWh).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "971.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _TINTORERIA_971_1[1]
            + Decimal("1") * _TINTORERIA_971_1[2]
            + Decimal("30") * _TINTORERIA_971_1[3],
        )
        assert previo == expected_previo == Decimal("22706.49")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "971.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="971.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("971.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="971.1")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestInstitutosBelleza9722EstimacionObjetiva:
    """Epígrafe IAE 972.2 (Salones e institutos de belleza)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 40 m2 local, 20 (100 kWh).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "972.2",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
            modulo_4=Decimal("20"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _INSTITUTOS_BELLEZA_972_2[2]
            + Decimal("40") * _INSTITUTOS_BELLEZA_972_2[3]
            + Decimal("20") * _INSTITUTOS_BELLEZA_972_2[4],
        )
        assert previo == expected_previo == Decimal("19532.01")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "972.2",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
            modulo_4=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="972.2",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("972.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="972.2")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestCopisteria9733EstimacionObjetiva:
    """Epígrafe IAE 973.3 (Servicios de copias de documentos con máquinas fotocopiadoras)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 3 KW contratado.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "973.3",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_previo = round_to_cents(Decimal("1") * _COPISTERIA_973_3[2] + Decimal("3") * _COPISTERIA_973_3[3])
        assert previo == expected_previo == Decimal("18669.07")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "973.3",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("3"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="973.3",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("973.3"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="973.3")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestFrutasVerduras641EstimacionObjetiva:
    """Epígrafe IAE 641 (Comercio al por menor de frutas, verduras, hortalizas y tubérculos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 30 m2 local
        # independiente, 500 kg carga elementos de transporte.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "641",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
            modulo_5=Decimal("500"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _FRUTAS_VERDURAS_641[1]
            + Decimal("1") * _FRUTAS_VERDURAS_641[2]
            + Decimal("30") * _FRUTAS_VERDURAS_641[3]
            + Decimal("500") * _FRUTAS_VERDURAS_641[5],
        )
        assert previo == expected_previo == Decimal("15212.04")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "641",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("30"),
            modulo_5=Decimal("500"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="641",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("641"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="641")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestQuioscosServicios675EstimacionObjetiva:
    """Epígrafe IAE 675 (Servicios en quioscos, cajones, barracas u otros locales análogos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 5 KW contratado, 10 m2 local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "675",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("5"),
            modulo_4=Decimal("10"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _QUIOSCOS_SERVICIOS_675[2]
            + Decimal("5") * _QUIOSCOS_SERVICIOS_675[3]
            + Decimal("10") * _QUIOSCOS_SERVICIOS_675[4],
        )
        assert previo == expected_previo == Decimal("15261.45")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "675",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("5"),
            modulo_4=Decimal("10"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="675",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("675"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="675")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestChocolaterias676EstimacionObjetiva:
    """Epígrafe IAE 676 (Servicios en chocolaterías, heladerías y horchaterías)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 3 KW contratado, 5 mesas, 1 máquina tipo A.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "676",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
            modulo_4=Decimal("5"),
            modulo_5=Decimal("1"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _CHOCOLATERIAS_676[1]
            + Decimal("3") * _CHOCOLATERIAS_676[3]
            + Decimal("5") * _CHOCOLATERIAS_676[4]
            + Decimal("1") * _CHOCOLATERIAS_676[5],
        )
        assert previo == expected_previo == Decimal("5952.19")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "676",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("3"),
            modulo_4=Decimal("5"),
            modulo_5=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="676",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("676"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="676")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad
