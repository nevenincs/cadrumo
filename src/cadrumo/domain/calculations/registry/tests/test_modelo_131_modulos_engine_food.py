"""Modelo 131 módulos engine food and hospitality activity cases.

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
    :mod:`~domain.calculations.registry.tests.test_modelo_131_modulos_engine`
        Core phased dataset that anchors the shared worked-example narrative.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.money import round_to_cents
from ._modelo_131_modulos_engine_support import (
    _AUTOSERVICIO_647_2,
    _CAFES_ESPECIAL_673_1,
    _CASQUERIAS_642_6,
    _DESPACHOS_PAN_644_2,
    _HUEVOS_AVES_642_5,
    _MASAS_FRITAS_644_6,
    _OTROS_CAFES_673_2,
    _PASTELERIA_644_3,
    _PESCADOS_643_1,
    _REDUCCION_GENERAL_2025,
    _expected_minorado,
    _expected_modulos,
    _module_1_coefficient,
    _run_modulos_engine,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class TestCafesEspecial6731EstimacionObjetiva:
    """Epígrafe IAE 673.1 (Cafés y bares de categoría especial) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 5 metros longitud de barra.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("1"),
            modulo_5=Decimal("5"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _CAFES_ESPECIAL_673_1[1] + Decimal("5") * _CAFES_ESPECIAL_673_1[5],
        )
        assert previo == expected_previo == Decimal("5914.40")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("1"),
            modulo_5=Decimal("5"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="673.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("673.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="673.1")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad

    def test_full_manual_worked_example_fases_1_a_4(self) -> None:
        """AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 8, caso práctico.

        Bar de categoría especial (epígrafe 673.1): 3,66 personal asalariado,
        1,00 personal no asalariado, 35,00 kW potencia eléctrica, 8,00 mesas,
        10,00 metros de barra, 0,00 máquinas tipo «A», 1,00 máquina tipo «B»;
        3,00 personas del módulo "personal asalariado" en el ejercicio
        anterior (2024). The Fase 1ª and Fase 2ª figures below are
        transcribed byte-identical from the manual's printed solution — Fase
        1ª rendimiento neto previo 50.111,95; Fase 2ª minoración por
        incentivos al empleo 2.693,38 (coeficiente de minoración 0,664, del
        cual 0,264 por incremento y 0,40 por tramos, sobre el módulo
        "personal asalariado" 4.056,30 euros/unidad). The minoración por
        incentivos a la inversión (6.050,00 euros, an asset-register figure
        this first slice does not model) is NOT applied here, so this test's
        own ``minorado`` (47.418,57) diverges from the manual's printed
        rendimiento neto minorado (41.368,57 = 50.111,95 - 2.693,38 - 6.050);
        the divergence is the documented, legitimate consequence of the
        not-yet-modelled inversión reduction, never a computation error. The
        manual's own Fase 3ª (índice corrector de exceso applied to
        41.368,57, giving rendimiento neto de módulos 44.603,33) does not
        apply against this test's employ-only minorado and is intentionally
        NOT asserted here to avoid re-deriving a "manual" figure the manual
        never printed for this base; Fase 3ª's índice-de-exceso mechanism
        against the tabled cuantía is instead covered structurally by
        ``test_fase_4_rendimiento_neto_actividad_applies_reduccion_general``
        (shared ``_expected_modulos`` helper, cross-checked against the
        Orden's own tabled cuantía/índice constants).
        """
        previo, minorado, _modulos, _actividad = _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("3.66"),
            modulo_2=Decimal("1.00"),
            modulo_3=Decimal("35.00"),
            modulo_4=Decimal("8.00"),
            modulo_5=Decimal("10.00"),
            modulo_6=Decimal("0.00"),
            modulo_7=Decimal("1.00"),
            modulo_1_anterior=Decimal("3.00"),
        )
        assert previo == Decimal("50111.95")
        # Fase 2ª: coeficiente por incremento 0,40 x 0,66 = 0,264; coeficiente
        # por tramos sobre 3,00 unidades restantes = 0,10 + 0,30 = 0,40;
        # coeficiente de minoración 0,264 + 0,40 = 0,664; minoración empleo =
        # 0,664 x 4.056,30 = 2.693,38 (manual, redondeado).
        minoracion_empleo = round_to_cents(previo - minorado)
        assert minoracion_empleo == Decimal("2693.38")
        assert minorado == Decimal("47418.57")

    def test_full_manual_worked_example_incluye_minoracion_inversion(self) -> None:
        """AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 8, caso práctico.

        Same activity and inputs as
        ``test_full_manual_worked_example_fases_1_a_4``, now supplying the
        operator-declared minoración por incentivos a la inversión the
        manual's own libro registro de bienes de inversión yields: mobiliario
        viejo ya amortizado (0), cafetera 9.400 euros amortización pendiente
        1.000 (25% coeficiente máximo topado por el saldo pendiente),
        vitrina térmica 4.000 euros x 25% = 1.000, instalación de aire
        acondicionado 6.600 euros x 25% = 1.650, mesas y sillas nuevas 2.400
        euros amortizadas libremente (elementos nuevos ≤ 601,01 euros/unidad
        y ≤ 3.005,06 euros en conjunto) = 2.400; total minoración por
        incentivos a la inversión = 1.000 + 1.000 + 1.650 + 2.400 = 6.050,00
        euros, transcribed byte-identical from the manual's printed table.
        With this declared amount, this test's rendimiento neto minorado
        (50.111,95 − 2.693,38 − 6.050,00 = 41.368,57) and rendimiento neto de
        módulos (30.586,03 + 1,30 x (41.368,57 − 30.586,03) = 44.603,33) both
        reproduce the manual's own printed Fase 2ª and Fase 3ª figures
        exactly — an independent, non-tautological proof that the engine's
        minoración-por-inversión subtraction and the índice-corrector-de-
        exceso chain compose correctly once the operator supplies the
        amortization figure.
        """
        previo, minorado, modulos, _actividad = _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("3.66"),
            modulo_2=Decimal("1.00"),
            modulo_3=Decimal("35.00"),
            modulo_4=Decimal("8.00"),
            modulo_5=Decimal("10.00"),
            modulo_6=Decimal("0.00"),
            modulo_7=Decimal("1.00"),
            modulo_1_anterior=Decimal("3.00"),
            minoracion_inversion=Decimal("6050.00"),
        )
        assert previo == Decimal("50111.95")
        assert minorado == Decimal("41368.57")
        # Fase 3ª: rendimiento neto minorado 41.368,57 supera la cuantía
        # tabulada 30.586,03; exceso 10.782,54 x índice 1,30 = 14.017,30;
        # rendimiento neto de módulos = 30.586,03 + 14.017,30 = 44.603,33
        # (manual, redondeado).
        assert modulos == Decimal("44603.33")


class TestOtrosCafes6732EstimacionObjetiva:
    """Epígrafe IAE 673.2 (Otros cafés y bares)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 3 mesas.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "673.2",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("3"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _OTROS_CAFES_673_2[1]
            + Decimal("1") * _OTROS_CAFES_673_2[2]
            + Decimal("3") * _OTROS_CAFES_673_2[4],
        )
        assert previo == expected_previo == Decimal("13416.02")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "673.2",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("3"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="673.2",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("673.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="673.2")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestHuevosAves6425EstimacionObjetiva:
    """Epígrafe IAE 642.5 (Comercio al por menor de huevos, aves, conejos de granja, caza)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 20 m2 superficie local independiente.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "642.5",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _HUEVOS_AVES_642_5[1] + Decimal("20") * _HUEVOS_AVES_642_5[4],
        )
        assert previo == expected_previo == Decimal("3923.96")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "642.5",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="642.5",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("642.5"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="642.5")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestCasquerias6426EstimacionObjetiva:
    """Epígrafe IAE 642.6 (Comercio al por menor en casquerías)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal no asalariado, 30 m2 superficie local no independiente.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "642.6",
            modulo_2=Decimal("1"),
            modulo_4=Decimal("30"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _CASQUERIAS_642_6[2] + Decimal("30") * _CASQUERIAS_642_6[4],
        )
        assert previo == expected_previo == Decimal("13176.54")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "642.6",
            modulo_2=Decimal("1"),
            modulo_4=Decimal("30"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="642.6",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("642.6"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="642.6")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestPescados6431EstimacionObjetiva:
    """Epígrafe IAE 643.1 y 2 (Comercio al por menor de pescados)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "643.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _PESCADOS_643_1[1] + Decimal("1") * _PESCADOS_643_1[2],
        )
        assert previo == expected_previo == Decimal("17119.61")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "643.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="643.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("643.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="643.1")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestDespachosPan6442EstimacionObjetiva:
    """Epígrafe IAE 644.2 (Despachos de pan, panes especiales y bollería) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado de fabricación, 1 personal no asalariado.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "644.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("1"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _DESPACHOS_PAN_644_2[1] + Decimal("1") * _DESPACHOS_PAN_644_2[3],
        )
        assert previo == expected_previo == Decimal("20401.19")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "644.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="644.2",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("644.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="644.2")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestPasteleria6443EstimacionObjetiva:
    """Epígrafe IAE 644.3 (Comercio al por menor de pastelería, bollería y confitería) — 7-módulo activity."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado de fabricación, 20 m2 superficie del local de fabricación.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "644.3",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _PASTELERIA_644_3[1] + Decimal("20") * _PASTELERIA_644_3[4],
        )
        assert previo == expected_previo == Decimal("7237.09")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "644.3",
            modulo_1=Decimal("1"),
            modulo_4=Decimal("20"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="644.3",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("644.3"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="644.3")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestMasasFritas6446EstimacionObjetiva:
    """Epígrafe IAE 644.6 (Comercio al por menor de masas fritas, patatas fritas y similares)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado de fabricación, 1 resto personal asalariado.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "644.6",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _MASAS_FRITAS_644_6[1] + Decimal("1") * _MASAS_FRITAS_644_6[2],
        )
        assert previo == expected_previo == Decimal("9107.78")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "644.6",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="644.6",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("644.6"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="644.6")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestAutoservicio6472EstimacionObjetiva:
    """Epígrafe IAE 647.2 y 3 (Comercio al por menor de alimentación en autoservicio < 400 m2)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 30 m2 superficie del local.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "647.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _AUTOSERVICIO_647_2[1] + Decimal("30") * _AUTOSERVICIO_647_2[3],
        )
        assert previo == expected_previo == Decimal("2488.10")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "647.2",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("30"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="647.2",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("647.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="647.2")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad
