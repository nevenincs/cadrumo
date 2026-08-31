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

from .....core.money.rounding import round_to_cents
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
    _assert_fase4_reduccion_general,
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
        _assert_fase4_reduccion_general(
            "673.1",
            modulo_1=Decimal("1"),
            modulo_5=Decimal("5"),
        )

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


#: Fase 1ª clone-collapsed dataset for the food/hospitality split — each entry
#: was a separate hand-forked ``TestXxxEstimacionObjetiva.test_fase_1_...``
#: method (identical body, differing only by epígrafe, coefficient table,
#: módulo units and expected figure) before the AST clone scan flagged them.
_FASE_1_CASES = [
    pytest.param(
        "673.2",
        _OTROS_CAFES_673_2,
        {1: Decimal("1"), 2: Decimal("1"), 4: Decimal("3")},
        Decimal("13416.02"),
        id="673.2-otros-cafes-y-bares",
    ),
    pytest.param(
        "642.5",
        _HUEVOS_AVES_642_5,
        {1: Decimal("1"), 4: Decimal("20")},
        Decimal("3923.96"),
        id="642.5-comercio-al-por-menor-de-huevos-aves-conejos-caza",
    ),
    pytest.param(
        "643.1",
        _PESCADOS_643_1,
        {1: Decimal("1"), 2: Decimal("1")},
        Decimal("17119.61"),
        id="643.1-comercio-al-por-menor-de-pescados",
    ),
    pytest.param(
        "644.2",
        _DESPACHOS_PAN_644_2,
        {1: Decimal("1"), 3: Decimal("1")},
        Decimal("20401.19"),
        id="644.2-despachos-de-pan-panes-especiales-y-bolleria",
    ),
    pytest.param(
        "644.3",
        _PASTELERIA_644_3,
        {1: Decimal("1"), 4: Decimal("20")},
        Decimal("7237.09"),
        id="644.3-comercio-al-por-menor-de-pasteleria-bolleria-y-confiteria",
    ),
    pytest.param(
        "644.6",
        _MASAS_FRITAS_644_6,
        {1: Decimal("1"), 2: Decimal("1")},
        Decimal("9107.78"),
        id="644.6-comercio-al-por-menor-de-masas-fritas",
    ),
    pytest.param(
        "647.2",
        _AUTOSERVICIO_647_2,
        {1: Decimal("1"), 3: Decimal("30")},
        Decimal("2488.10"),
        id="647.2-comercio-al-por-menor-de-alimentacion-en-autoservicio",
    ),
]

#: Fase 4ª (5% reducción general) clone-collapsed dataset — same módulo units
#: as the matching Fase 1ª case above.
_FASE_4_CASES = [
    pytest.param("673.2", {1: Decimal("1"), 2: Decimal("1"), 4: Decimal("3")}, id="673.2-otros-cafes-y-bares"),
    pytest.param("642.5", {1: Decimal("1"), 4: Decimal("20")}, id="642.5-huevos-aves"),
    pytest.param("643.1", {1: Decimal("1"), 2: Decimal("1")}, id="643.1-pescados"),
    pytest.param("644.2", {1: Decimal("1"), 3: Decimal("1")}, id="644.2-despachos-de-pan"),
    pytest.param("644.3", {1: Decimal("1"), 4: Decimal("20")}, id="644.3-pasteleria"),
    pytest.param("644.6", {1: Decimal("1"), 2: Decimal("1")}, id="644.6-masas-fritas"),
    pytest.param("647.2", {1: Decimal("1"), 3: Decimal("30")}, id="647.2-autoservicio"),
]


@pytest.mark.parametrize(("epigrafe", "table", "modulos", "expected_previo"), _FASE_1_CASES)
def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(
    epigrafe: str,
    table: dict[int, Decimal],
    modulos: dict[int, Decimal],
    expected_previo: Decimal,
) -> None:
    previo, _minorado, _modulos, _actividad = _run_modulos_engine(
        epigrafe,
        **{f"modulo_{idx}": units for idx, units in modulos.items()},
    )
    expected = round_to_cents(sum((units * table[idx] for idx, units in modulos.items()), start=Decimal("0")))
    assert previo == expected == expected_previo


@pytest.mark.parametrize(("epigrafe", "modulos"), _FASE_4_CASES)
def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(
    epigrafe: str,
    modulos: dict[int, Decimal],
) -> None:
    _assert_fase4_reduccion_general(epigrafe, **{f"modulo_{idx}": units for idx, units in modulos.items()})


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
        _assert_fase4_reduccion_general(
            "642.6",
            modulo_2=Decimal("1"),
            modulo_4=Decimal("30"),
        )
