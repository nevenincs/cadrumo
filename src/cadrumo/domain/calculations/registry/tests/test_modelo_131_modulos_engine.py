"""Modelo 131 estimación-objetiva módulos engine (Fases 1ª-4ª, phased dataset).

Non-tautological: expected values are transcribed independently from the
bundled Orden HAC/1347/2024 Anexo II coefficient tables
(``corpus/normatives/html/orden-hac-1347-2024.html``), not re-derived from the
registry formula under test. Fase 2ª's minoración por incentivos al empleo
(the coeficiente por incremento + coeficiente por tramos mechanism) is
cross-checked byte-identical against the AEAT Manual práctico de Renta 2025
full worked example (epígrafe 673.1, Capítulo 8) — see
``TestCafesEspecial6731EstimacionObjetiva.test_full_manual_worked_example_fases_1_a_4``.
Fase 2ª's minoración por incentivos a la inversión is an operator-declared
euro amount (this engine does not model a per-element libro registro de
bienes de inversión); its subtraction is cross-checked against the same
manual worked example's printed 6.050,00 euros figure — see
``test_full_manual_worked_example_incluye_minoracion_inversion``. Fase 3ª's
índice corrector de exceso is grounded in the same Orden's tabled
cuantía/índice constants via the shared ``_expected_modulos`` helper (an
independent reproduction, not a re-derivation of the formula under test's own
intermediate output). The 5 por ciento reducción general (Fase 4ª) is grounded
in the same Orden's disposición adicional primera.

See Also:
    :mod:`~domain.calculations.registry.tests._modelo_131_modulos_engine_support`
        Shared independent coefficient tables and oracle arithmetic.
    :mod:`~domain.calculations.registry._formula_runtime_m131`
        Extracted M131 módulos formula evaluators exercised here.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Registry runtime entry point used to calculate the committed snapshot.
    :class:`~domain.calculations.registry.ParameterDefinition`
        Registry-authored módulo coefficient and índice tables under test.
    :mod:`~domain.calculations.registry.tests.test_modelo_131_modulos_engine_food`
        Split food and hospitality activity coverage using the same helpers.
    :mod:`~domain.calculations.registry.tests.test_modelo_131_modulos_engine_retail_services`
        Split retail, repair, transport, and service activity coverage.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.money import round_to_cents
from .._formula_runtime import calculate_registry_snapshot
from ._modelo_131_modulos_engine_support import (
    _ALIMENTACION_647_1,
    _AUTOTAXI_721_2,
    _CAFETERIAS_672_1,
    _CARNE_642_1,
    _MERCANCIAS_722,
    _PAN_PASTELERIA_644_1,
    _PELUQUERIA_972_1,
    _REDUCCION_GENERAL_2025,
    _RESTAURANTE_DOS_TENEDORES_671_4,
    _RESTAURANTE_UN_TENEDOR_671_5,
    _expected_minorado,
    _expected_modulos,
    _expected_modulos_generales,
    _module_1_coefficient,
    _run_modulos_engine,
)
from ._registry_schema_support import _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class TestPeluqueria9721EstimacionObjetiva:
    """Epígrafe IAE 972.1 (Servicios de peluquería de señora y caballero)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 50 m2 local, 30 (100 kWh).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_previo = round_to_cents(
            Decimal("2") * _PELUQUERIA_972_1[1]
            + Decimal("1") * _PELUQUERIA_972_1[2]
            + Decimal("50") * _PELUQUERIA_972_1[3]
            + Decimal("30") * _PELUQUERIA_972_1[4],
        )
        assert previo == expected_previo == Decimal("23153.67")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="972.1",
            modulo_1=Decimal("2"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("972.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="972.1")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestAutotaxi7212EstimacionObjetiva:
    """Epígrafe IAE 721.2 (Transporte por autotaxis)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 0 personal asalariado, 1 personal no asalariado (titular), 40 (1.000 km).
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "721.2",
            modulo_1=Decimal("0"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = round_to_cents(Decimal("1") * _AUTOTAXI_721_2[2] + Decimal("40") * _AUTOTAXI_721_2[3])
        assert previo == expected_previo == Decimal("9460.09")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "721.2",
            modulo_1=Decimal("0"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="721.2",
            modulo_1=Decimal("0"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("721.2"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="721.2")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestTransporteMercancias722EstimacionObjetiva:
    """Epígrafe IAE 722 (Transporte de mercancías por carretera)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 0 personal no asalariado, 8 toneladas carga.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "722",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("0"),
            modulo_3=Decimal("8"),
        )
        expected_previo = round_to_cents(Decimal("1") * _MERCANCIAS_722[1] + Decimal("8") * _MERCANCIAS_722[3])
        assert previo == expected_previo == Decimal("3738.27")


class TestRestauranteDosTenedores6714EstimacionObjetiva:
    """Epígrafe IAE 671.4 (Restaurantes de dos tenedores)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 8 kW potencia
        # eléctrica, 3 mesas, 1 máquina tipo «A».
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "671.4",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("8"),
            modulo_4=Decimal("3"),
            modulo_5=Decimal("1"),
        )
        expected_previo = round_to_cents(
            Decimal("2") * _RESTAURANTE_DOS_TENEDORES_671_4[1]
            + Decimal("1") * _RESTAURANTE_DOS_TENEDORES_671_4[2]
            + Decimal("8") * _RESTAURANTE_DOS_TENEDORES_671_4[3]
            + Decimal("3") * _RESTAURANTE_DOS_TENEDORES_671_4[4]
            + Decimal("1") * _RESTAURANTE_DOS_TENEDORES_671_4[5],
        )
        assert previo == expected_previo == Decimal("29301.08")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "671.4",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("8"),
            modulo_4=Decimal("3"),
            modulo_5=Decimal("1"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="671.4",
            modulo_1=Decimal("2"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("671.4"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="671.4")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestRestauranteUnTenedor6715EstimacionObjetiva:
    """Epígrafe IAE 671.5 (Restaurantes de un tenedor)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 0 personal no asalariado, 6 kW potencia
        # eléctrica, 4 mesas, 2 máquinas tipo «B».
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "671.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("0"),
            modulo_3=Decimal("6"),
            modulo_4=Decimal("4"),
            modulo_6=Decimal("2"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _RESTAURANTE_UN_TENEDOR_671_5[1]
            + Decimal("6") * _RESTAURANTE_UN_TENEDOR_671_5[3]
            + Decimal("4") * _RESTAURANTE_UN_TENEDOR_671_5[4]
            + Decimal("2") * _RESTAURANTE_UN_TENEDOR_671_5[6],
        )
        assert previo == expected_previo == Decimal("12861.72")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "671.5",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("0"),
            modulo_3=Decimal("6"),
            modulo_4=Decimal("4"),
            modulo_6=Decimal("2"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="671.5",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("671.5"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="671.5")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestCafeterias6721EstimacionObjetiva:
    """Epígrafe IAE 672.1, 2 y 3 (Cafeterías)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 3 personal asalariado, 1 personal no asalariado, 10 kW potencia
        # eléctrica.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "672.1",
            modulo_1=Decimal("3"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
        )
        expected_previo = round_to_cents(
            Decimal("3") * _CAFETERIAS_672_1[1]
            + Decimal("1") * _CAFETERIAS_672_1[2]
            + Decimal("10") * _CAFETERIAS_672_1[3],
        )
        assert previo == expected_previo == Decimal("22876.50")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "672.1",
            modulo_1=Decimal("3"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("10"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="672.1",
            modulo_1=Decimal("3"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("672.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="672.1")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestComercioCarne6421EstimacionObjetiva:
    """Epígrafe IAE 642.1, 2, 3 y 4 (Comercio al por menor de carne y despojos)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 1 personal no asalariado, 40 m2 superficie
        # local no independiente.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "642.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_4=Decimal("40"),
        )
        expected_previo = round_to_cents(
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
        # del horno, 629,86 €/unit), so the engine supports all 7 módulo
        # slots rather than capping at 4.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "644.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("1"),
            modulo_4=Decimal("30"),
            modulo_7=Decimal("2"),
        )
        expected_previo = round_to_cents(
            Decimal("1") * _PAN_PASTELERIA_644_1[1]
            + Decimal("1") * _PAN_PASTELERIA_644_1[2]
            + Decimal("1") * _PAN_PASTELERIA_644_1[3]
            + Decimal("30") * _PAN_PASTELERIA_644_1[4]
            + Decimal("2") * _PAN_PASTELERIA_644_1[7],
        )
        assert previo == expected_previo == Decimal("24570.90")

    def test_fase_4_rendimiento_neto_actividad_applies_reduccion_general(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "644.1",
            modulo_1=Decimal("1"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("1"),
            modulo_4=Decimal("30"),
            modulo_7=Decimal("2"),
        )
        expected_minorado = _expected_minorado(
            previo,
            epigrafe="644.1",
            modulo_1=Decimal("1"),
            modulo_1_anterior=Decimal("0"),
            modulo_1_coefficient=_module_1_coefficient("644.1"),
        )
        expected_modulos = _expected_modulos(minorado, epigrafe="644.1")
        expected_actividad = round_to_cents(modulos - modulos * _REDUCCION_GENERAL_2025)
        assert minorado == expected_minorado
        assert modulos == expected_modulos
        assert actividad == expected_actividad


class TestComercioAlimenticios6471EstimacionObjetiva:
    """Epígrafe IAE 647.1 (Comercio al por menor de alimentación en establecimientos con vendedor)."""

    def test_fase_1_rendimiento_neto_previo_matches_orden_coefficients(self) -> None:
        # 1 personal asalariado, 40 m2 superficie del local independiente.
        previo, _minorado, _modulos, _actividad = _run_modulos_engine(
            "647.1",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = round_to_cents(Decimal("1") * _ALIMENTACION_647_1[1] + Decimal("40") * _ALIMENTACION_647_1[3])
        assert previo == expected_previo == Decimal("1832.67")


class TestModulosEngineNoSilentFabrication:
    """no-silent-under-declaration guard: an untabled epígrafe never fabricates a figure."""

    def test_untabled_epigrafe_resolves_to_zero_not_fabricated_figure(self) -> None:
        # A large positive unit count against an activity absent from the
        # bounded first-slice coefficient table must NOT be silently
        # multiplied by a wrong or absent coefficient; the internal
        # reference casilla resolves to zero, and the operator-declared
        # casilla 01 remains the authoritative manual input.
        previo, minorado, modulos, actividad = _run_modulos_engine(
            "699.9",  # not an Orden Anexo II epígrafe — remains untabled
            modulo_1=Decimal("5"),
            modulo_2=Decimal("3"),
        )
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")

    def test_blank_epigrafe_resolves_to_zero(self) -> None:
        previo, minorado, modulos, actividad = _run_modulos_engine(None, modulo_1=Decimal("5"))
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")

    def test_zero_units_on_tabled_epigrafe_resolves_to_zero(self) -> None:
        # A tabled epígrafe with no units declared (e.g. no activity conducted
        # yet this period) legitimately resolves to zero — not a silent-zero
        # violation, since the antecedent itself is zero.
        previo, minorado, modulos, actividad = _run_modulos_engine("972.1")
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")


class TestModulosIndicesCorrectoresGenerales:
    """Fase 3ª índices correctores generales cascade (b.1, b.2, b.3, b.4).

    Grounded in Orden HAC/1347/2024 Anexo II, instrucción 2.3 (bundled
    ``orden-hac-1347-2024.html`` corpus) and cross-checked against the AEAT
    Manual práctico de Renta 2025, Parte 1, Capítulo 8 (same índice values
    and the same three incompatibilidades quoted verbatim). Uses the same
    673.1 base as ``TestCafesEspecial6731EstimacionObjetiva``'s full manual
    worked example so the b.1/b.2/b.4 additions can be verified against a
    figure (Fase 1ª/2ª) already independently proven correct.
    """

    def _run_673_1(self, **kwargs: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        return _run_modulos_engine(
            "673.1",
            modulo_1=Decimal("3.66"),
            modulo_2=Decimal("1.00"),
            modulo_3=Decimal("35.00"),
            modulo_4=Decimal("8.00"),
            modulo_5=Decimal("10.00"),
            modulo_7=Decimal("1.00"),
            modulo_1_anterior=Decimal("3.00"),
            minoracion_inversion=Decimal("6050.00"),
            **kwargs,
        )

    def test_no_indices_generales_declared_matches_b3_only_baseline(self) -> None:
        """No b.1/b.2/b.4 declared reproduces the pre-existing b.3-only manual figure exactly."""
        _previo, minorado, modulos, _actividad = self._run_673_1()
        assert minorado == Decimal("41368.57")
        assert modulos == Decimal("44603.33")
        expected = _expected_modulos_generales(minorado, epigrafe="673.1")
        assert modulos == expected

    def test_pequena_dimension_applies_multiplicatively_and_excludes_indice_exceso(self) -> None:
        """b.1 (0,80) applies to minorado; b.3 (índice de exceso) is then excluded outright."""
        _previo, minorado, modulos, _actividad = self._run_673_1(
            indice_pequena_dimension=Decimal("0.80"),
        )
        expected = _expected_modulos_generales(minorado, epigrafe="673.1", pequena_dimension=Decimal("0.80"))
        assert modulos == expected == Decimal("33094.86")
        # Confirms b.3 was skipped: a naive product with the manual's own
        # índice-exceso figure would be far higher than the plain 0,80 product.
        assert modulos == round_to_cents(minorado * Decimal("0.80"))

    def test_pequena_dimension_ignored_for_autotaxi_especial_epigrafe(self) -> None:
        """b.1 is IGNORED (never applied) for an epígrafe carrying a documented índice especial (721.2)."""
        previo, minorado, modulos, _actividad = _run_modulos_engine(
            "721.2",
            modulo_2=Decimal("1"),
            modulo_3=Decimal("900"),
            indice_pequena_dimension=Decimal("0.80"),
        )
        expected_previo = round_to_cents(Decimal("1") * _AUTOTAXI_721_2[2] + Decimal("900") * _AUTOTAXI_721_2[3])
        assert previo == expected_previo
        # b.1 ignored -> b.3 índice de exceso still applies to the plain minorado.
        expected = _expected_modulos_generales(minorado, epigrafe="721.2", pequena_dimension=Decimal("0.80"))
        assert modulos == expected == _expected_modulos(minorado, epigrafe="721.2")

    def test_pequena_dimension_ignored_for_mercancias_especial_epigrafe(self) -> None:
        """b.1 is IGNORED (never applied) for an epígrafe carrying a documented índice especial (722)."""
        _previo, minorado, modulos, _actividad = _run_modulos_engine(
            "722",
            modulo_1=Decimal("1"),
            modulo_3=Decimal("800"),
            indice_pequena_dimension=Decimal("0.75"),
        )
        expected = _expected_modulos_generales(minorado, epigrafe="722", pequena_dimension=Decimal("0.75"))
        assert modulos == expected == _expected_modulos(minorado, epigrafe="722")

    def test_temporada_applies_multiplicatively_before_indice_exceso(self) -> None:
        """b.2 (temporada) applies to minorado before b.3 evaluates the (adjusted) excess."""
        _previo, minorado, modulos, _actividad = self._run_673_1(indice_temporada=Decimal("1.50"))
        expected = _expected_modulos_generales(minorado, epigrafe="673.1", temporada=Decimal("1.50"))
        assert modulos == expected

    def test_inicio_actividad_applies_when_temporada_absent(self) -> None:
        """b.4 (inicio de nuevas actividades) applies when temporada is not declared."""
        _previo, minorado, modulos, _actividad = self._run_673_1(indice_inicio_actividad=Decimal("0.80"))
        expected = _expected_modulos_generales(minorado, epigrafe="673.1", inicio_actividad=Decimal("0.80"))
        assert modulos == expected

    def test_inicio_actividad_after_exceso_regression_b1347_2024_orden_order(self) -> None:
        """b.4 MUST be applied AFTER b.3 (exceso), never before — regression for the reversed-order defect.

        Orden HAC/1347/2024 Anexo II, instrucción 2.3: "Los índices
        correctores se aplicarán según el orden que aparecen enumerados a
        continuación ... sobre el rendimiento neto minorado o, en su caso,
        sobre el rectificado por aplicación de los mismos" — the literal
        enumeration is b.1, b.2, b.3 (exceso), b.4 (inicio de nuevas
        actividades). b.3's exceso threshold is a non-linear piecewise
        function (identity below the tabled cuantía; ``cuantía + índice ×
        exceso`` above), so grouping b.4 with b.2 ahead of b.3 (rather than
        strictly sequencing b.1 -> b.2 -> b.3 -> b.4) yields a materially
        different figure. This test uses the 673.1 Cafés y bares de categoría
        especial base from the AEAT Manual práctico de Renta 2025 worked
        example (Capítulo 8) — rendimiento neto minorado 41.368,57, cuantía de
        exceso 30.586,03, índice de exceso 1,30 — with b.4 = 0,80 (primer año
        de ejercicio de la actividad) declared alone (no b.2 temporada):

        * Law-correct (b.3 THEN b.4): 30.586,03 + 1,30 × (41.368,57 -
          30.586,03) = 44.603,33; 44.603,33 × 0,80 = 35.682,67 (money-2
          rounded at the formula's output stage).
        * Defect (b.4 THEN b.3, the reversed order this test guards against):
          41.368,57 × 0,80 = 33.094,856 (below the 30.586,03 cuantía, so b.3
          never fires) = 33.847,50 once erroneously re-run through b.3's
          formula on the already-b.4-adjusted figure — a distinct, wrong
          result this test would have passed under the reversed order.
        """
        _previo, minorado, modulos, _actividad = self._run_673_1(indice_inicio_actividad=Decimal("0.80"))
        assert minorado == Decimal("41368.57")
        expected = _expected_modulos_generales(minorado, epigrafe="673.1", inicio_actividad=Decimal("0.80"))
        assert expected == Decimal("35682.67")
        assert modulos == expected
        # The reversed (defective) order would have produced 33.847,50 —
        # confirm the engine does NOT reproduce that figure.
        assert modulos != Decimal("33847.50")

    def test_temporada_and_inicio_actividad_declared_together_temporada_wins(self) -> None:
        """b.2 and b.4 are mutually exclusive; temporada (enumeration order) wins, inicio is ignored."""
        _previo, minorado, modulos_both, _actividad = self._run_673_1(
            indice_temporada=Decimal("1.50"),
            indice_inicio_actividad=Decimal("0.80"),
        )
        _previo2, minorado2, modulos_temporada_only, _actividad2 = self._run_673_1(
            indice_temporada=Decimal("1.50"),
        )
        assert minorado == minorado2
        assert modulos_both == modulos_temporada_only
        expected = _expected_modulos_generales(minorado, epigrafe="673.1", temporada=Decimal("1.50"))
        assert modulos_both == expected

    def test_blank_indices_generales_never_fabricate_a_factor(self) -> None:
        """A blank/zero b.1/b.2/b.4 input never fabricates a factor (baseline unchanged)."""
        _previo, minorado, modulos, _actividad = self._run_673_1(
            indice_pequena_dimension=Decimal("0"),
            indice_temporada=Decimal("0"),
            indice_inicio_actividad=Decimal("0"),
        )
        assert modulos == _expected_modulos(minorado, epigrafe="673.1") == Decimal("44603.33")

    def test_non_positive_minorado_never_receives_indices_generales(self) -> None:
        """A non-positive rendimiento neto minorado skips the whole cascade (mirrors the b.3-only guard)."""
        _previo, minorado, modulos, _actividad = _run_modulos_engine(
            "972.1",
            indice_pequena_dimension=Decimal("0.80"),
            indice_temporada=Decimal("1.50"),
        )
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")


class TestModulosIndicesGeneralesAdvisoryFlags:
    """The pequeña-dimensión-ignorado and temporada/inicio-conflicto advisory-support flags."""

    def test_pequena_dimension_ignorado_flag_fires_on_especial_epigrafe(self) -> None:
        snapshot = _committed_snapshot("131", 2025, "1T")
        assert snapshot.filing_period is not None
        result = calculate_registry_snapshot(
            snapshot,
            inputs={
                "modulos-2-unidades": Decimal("1"),
                "modulos-3-unidades": Decimal("900"),
                "modulos-indice-pequena-dimension": Decimal("0.80"),
            },
            text_inputs={"modulos-epigrafe": "721.2"},
            date_context={"filing_period": snapshot.filing_period.end_date},
        )
        assert result.values["modulos-pequena-dimension-ignorado-flag"] == Decimal("1")

    def test_pequena_dimension_ignorado_flag_stays_zero_on_ordinary_epigrafe(self) -> None:
        snapshot = _committed_snapshot("131", 2025, "1T")
        assert snapshot.filing_period is not None
        result = calculate_registry_snapshot(
            snapshot,
            inputs={
                "modulos-1-unidades": Decimal("2"),
                "modulos-indice-pequena-dimension": Decimal("0.80"),
            },
            text_inputs={"modulos-epigrafe": "972.1"},
            date_context={"filing_period": snapshot.filing_period.end_date},
        )
        assert result.values["modulos-pequena-dimension-ignorado-flag"] == Decimal("0")

    def test_pequena_dimension_ignorado_flag_stays_zero_when_not_declared(self) -> None:
        snapshot = _committed_snapshot("131", 2025, "1T")
        assert snapshot.filing_period is not None
        result = calculate_registry_snapshot(
            snapshot,
            inputs={"modulos-2-unidades": Decimal("1"), "modulos-3-unidades": Decimal("900")},
            text_inputs={"modulos-epigrafe": "721.2"},
            date_context={"filing_period": snapshot.filing_period.end_date},
        )
        assert result.values["modulos-pequena-dimension-ignorado-flag"] == Decimal("0")

    def test_temporada_inicio_conflicto_flag_fires_when_both_declared(self) -> None:
        snapshot = _committed_snapshot("131", 2025, "1T")
        assert snapshot.filing_period is not None
        result = calculate_registry_snapshot(
            snapshot,
            inputs={
                "modulos-1-unidades": Decimal("1"),
                "modulos-indice-temporada": Decimal("1.50"),
                "modulos-indice-inicio-actividad": Decimal("0.80"),
            },
            text_inputs={"modulos-epigrafe": "673.1"},
            date_context={"filing_period": snapshot.filing_period.end_date},
        )
        assert result.values["modulos-temporada-inicio-actividad-conflicto-flag"] == Decimal("1")

    def test_temporada_inicio_conflicto_flag_stays_zero_when_only_one_declared(self) -> None:
        snapshot = _committed_snapshot("131", 2025, "1T")
        assert snapshot.filing_period is not None
        result = calculate_registry_snapshot(
            snapshot,
            inputs={"modulos-1-unidades": Decimal("1"), "modulos-indice-temporada": Decimal("1.50")},
            text_inputs={"modulos-epigrafe": "673.1"},
            date_context={"filing_period": snapshot.filing_period.end_date},
        )
        assert result.values["modulos-temporada-inicio-actividad-conflicto-flag"] == Decimal("0")
