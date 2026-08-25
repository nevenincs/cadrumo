"""Modelo 100 2025 estimación objetiva agraria — Fase 3ª índices correctores.

Non-tautological: the target rendimiento neto minorado (14.704,42 euros) and
the expected rendimiento neto de módulos (13.233,98 euros) are transcribed
independently from the AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 9
full worked example (Don L.H.I., explotación agrícola-ganadera). The manual
states: "Rendimiento neto de módulos: (14.704,42 x 0,90) = 13.233,98 euros",
applying the índice corrector por utilización de personal asalariado (0,90,
Anexo I instrucción 2.3, letra b) — the único índice aplicable in that
example, the coste de personal asalariado representing between 10% and 20% of
total ingresos.

The test drives the Fase 1ª/2ª chain (a single producto código 12 slot, the
same índice de rendimiento neto 0,37 the Fase 1ª tests already reproduce, plus
an operator-declared amortización) purely to LAND casilla 1539 (rendimiento
neto minorado) on the manual's own externally-sourced figure
(14.704,42 euros); the ingresos and amortización scalars are chosen solely to
reach that target, not asserted as manual-sourced themselves. The índice
corrector value (0,90) and both the minorado and módulos figures ARE
independently AEAT-manual-sourced — the multiplication the Fase 3ª formula
performs is the mechanism under test.

See Also:
    :func:`~domain.calculations.registry._formula_runtime._evaluate_m100_resolve_eo_agraria_indices_correctores`
        Registry runtime evaluator for the sequential Fase 3ª índice cascade.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Public calculation entry point exercised by the worked-example cases.
    :mod:`~domain.calculations.registry.tests.test_modelo_100_eo_agraria_reducciones_fase_4a`
        Fase 4ª/5ª reduction suite that continues from this test's casilla
        1548 result.
    ``src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/formulas/0293-renta-2025-eo-agraria-rendimiento-base.toml``
        Registry-authored Fase 1ª-3ª formula chain under test.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from cadrumo.domain.calculations.registry.snapshot import build_snapshot
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 9, full worked example
# (Don L.H.I., agricultura + ganadería ovina): "Rendimiento neto minorado:
# 14.704,42" euros, "Únicamente resulta aplicable en este caso el índice
# corrector por utilización de personal asalariado ... procede aplicar el
# índice corrector 0,90 ... Rendimiento neto de módulos: (14.704,42 x 0,90) =
# 13.233,98 euros".
_TARGET_MINORADO = Decimal("14704.42")
_INDICE_PERSONAL_ASALARIADO = Decimal("0.90")
_EXPECTED_RENDIMIENTO_NETO_MODULOS = Decimal("13233.98")

# Código 12 (raíces/tubérculos/forrajes/algodón/frutos no cítricos), índice de
# rendimiento neto 0,37 — the same 2025 código the Fase 1ª tests already
# reproduce (Doña M.J.I. worked example). ``ingresos``/``amortizacion`` here
# are chosen solely to land casilla 1539 on Don L.H.I.'s externally-sourced
# 14.704,42 euros target, not claimed as manual-sourced themselves.
_INDICE_RENDIMIENTO_NETO = Decimal("0.37")
_INGRESOS = Decimal("45000.00")
_AMORTIZACION = Decimal("1945.58")

_CASILLA_1521_INGRESOS = validated_casilla_id("1521", surface="test")
_CASILLA_1522_INDICE = validated_casilla_id("1522", surface="test")
_CASILLA_1538_AMORTIZACION = validated_casilla_id("1538", surface="test")
_CASILLA_1539_RENDIMIENTO_NETO_MINORADO = validated_casilla_id("1539", surface="test")
_CASILLA_1548_RENDIMIENTO_NETO_MODULOS = validated_casilla_id("1548", surface="test")

# Fase 3ª índice-corrector input casillas (Anexo I instrucción 2.3, letras a
# to h; índice 9 mejillón en batea is out of scope — see the formula's own
# docstring).
_CASILLA_1540_MEDIOS_AJENOS = validated_casilla_id("1540", surface="test")
_CASILLA_1541_PERSONAL_ASALARIADO = validated_casilla_id("1541", surface="test")
_CASILLA_1542_TIERRAS_ARRENDADAS = validated_casilla_id("1542", surface="test")
_CASILLA_1544_ECOLOGICA = validated_casilla_id("1544", surface="test")
_CASILLA_1545_REGADIO_ELECTRICO = validated_casilla_id("1545", surface="test")
_CASILLA_1546_PEQUENA_EMPRESA = validated_casilla_id("1546", surface="test")
_CASILLA_1547_FORESTAL = validated_casilla_id("1547", surface="test")


def _modelo_100_2025_snapshot():
    modelo, catalogues = _committed_modelo("100")
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="0A")


def _neutral_binding_values() -> dict[str, Decimal]:
    """The minimal neutral binding set every M100 2025 calculate run needs.

    Mirrors the fixture in ``test_modelo_100_eo_agraria_rendimiento_base.py``.
    """
    return {
        # Agricultural activity is económica; the production profile resolver
        # supplies this predicate as 1/0 from taxpayer_type.irpf_income_categories.
        "renta-2025-profile-has-economic-activity": Decimal("1"),
        "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
        "renta-2025-profile-declaration-type": Decimal("1"),
        "renta-2025-profile-marriage-full-year": Decimal("0"),
        "renta-2025-profile-marriage-month-start": Decimal("0"),
        "renta-2025-profile-marriage-month-end": Decimal("0"),
        "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
        "renta-2025-profile-madrid-nacimiento-adopcion-eligible-count": Decimal("0"),
        "renta-2025-profile-unidad-familiar-otros-miembros-base": Decimal("0"),
        "renta-2025-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-2025-profile-minimo-descendientes-autonomico": Decimal("0"),
    }


def _run_calculation(
    *,
    ingresos: Decimal = _INGRESOS,
    indice: Decimal = _INDICE_RENDIMIENTO_NETO,
    amortizacion: Decimal = _AMORTIZACION,
    indices_correctores: Mapping[CasillaId, Decimal] | None = None,
) -> Mapping[CasillaId, Decimal]:
    snapshot = _modelo_100_2025_snapshot()
    revision = snapshot.revision
    inputs: dict[CasillaId, Decimal] = {
        _CASILLA_1521_INGRESOS: ingresos,
        _CASILLA_1522_INDICE: indice,
        _CASILLA_1538_AMORTIZACION: amortizacion,
    }
    inputs.update(indices_correctores or {})
    calculation = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=_neutral_binding_values(),
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values={relation.id: Decimal("0") for relation in revision.relations},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
        date_context={"filing_period": date(2025, 12, 31)},
    )
    return calculation.values


class TestFixtureReachesTheManualsOwnMinorado:
    """Confirm the chosen ingresos/amortización land exactly on Don L.H.I.'s 14.704,42."""

    def test_minorado_matches_manual_worked_example(self) -> None:
        values = _run_calculation()
        assert values[_CASILLA_1539_RENDIMIENTO_NETO_MINORADO] == _TARGET_MINORADO


class TestPersonalAsalariadoIndiceMatchesManualWorkedExample:
    """Fase 3ª: único índice aplicable — personal asalariado 0,90 (letra b)."""

    def test_rendimiento_neto_modulos_matches_manual_worked_example(self) -> None:
        values = _run_calculation(indices_correctores={_CASILLA_1541_PERSONAL_ASALARIADO: _INDICE_PERSONAL_ASALARIADO})
        assert values[_CASILLA_1539_RENDIMIENTO_NETO_MINORADO] == _TARGET_MINORADO
        assert values[_CASILLA_1548_RENDIMIENTO_NETO_MODULOS] == _EXPECTED_RENDIMIENTO_NETO_MODULOS


class TestNoIndiceDeclaredNeverFabricatesAReduction:
    """A blank índice cascade must leave rendimiento neto de módulos unchanged."""

    def test_blank_indices_yield_modulos_equal_to_minorado(self) -> None:
        values = _run_calculation()
        assert values[_CASILLA_1539_RENDIMIENTO_NETO_MINORADO] == _TARGET_MINORADO
        assert values[_CASILLA_1548_RENDIMIENTO_NETO_MODULOS] == _TARGET_MINORADO


class TestSequentialCascadeAppliesEveryDeclaredIndiceInOrder:
    """Each índice applies on the result already rectified by prior índices.

    Orden HAC/1347/2024 Anexo I instrucción 2.3: "sobre el rendimiento neto
    minorado o, en su caso, sobre el rectificado por aplicación de los
    [índices] anteriores" — a sequential cascade, never a simultaneous
    product and never a single-índice pick.
    """

    def test_two_declared_indices_compose_sequentially(self) -> None:
        # Both índices declared: medios de producción ajenos (letra a, 0,75)
        # then personal asalariado (letra b, 0,90) — the Anexo's own letra
        # ordering. The manual states these two are mutually incompatible in
        # practice ("no se aplicará este índice cuando el rendimiento... hubiera
        # sido objeto de reducción por efecto del índice 1"), but the engine's
        # job is to apply whatever the operator declares in the Anexo's letra
        # order; a structural composition test, not a legal-eligibility test.
        values = _run_calculation(
            indices_correctores={
                _CASILLA_1540_MEDIOS_AJENOS: Decimal("0.75"),
                _CASILLA_1541_PERSONAL_ASALARIADO: _INDICE_PERSONAL_ASALARIADO,
            }
        )
        expected = (_TARGET_MINORADO * Decimal("0.75") * _INDICE_PERSONAL_ASALARIADO).quantize(Decimal("0.01"))
        assert values[_CASILLA_1548_RENDIMIENTO_NETO_MODULOS] == expected

    def test_every_letra_slot_applies_when_all_are_declared(self) -> None:
        # Exercises all seven decimal-typed índice casillas (1540-1542,
        # 1544-1547); casilla 1543 (índice 4, piensos, declared ``text`` by
        # the AEAT Diseño de Registros) is covered separately below.
        indices = {
            _CASILLA_1540_MEDIOS_AJENOS: Decimal("0.75"),
            _CASILLA_1541_PERSONAL_ASALARIADO: Decimal("0.90"),
            _CASILLA_1542_TIERRAS_ARRENDADAS: Decimal("0.90"),
            _CASILLA_1544_ECOLOGICA: Decimal("0.95"),
            _CASILLA_1545_REGADIO_ELECTRICO: Decimal("0.75"),
            _CASILLA_1546_PEQUENA_EMPRESA: Decimal("0.90"),
            _CASILLA_1547_FORESTAL: Decimal("0.80"),
        }
        values = _run_calculation(indices_correctores=indices)
        expected = _TARGET_MINORADO
        for indice in indices.values():
            expected = expected * indice
        expected = expected.quantize(Decimal("0.01"))
        assert values[_CASILLA_1548_RENDIMIENTO_NETO_MODULOS] == expected


class TestPiensosIndiceIsTextTypedButStillApplies:
    """Casilla 1543 (índice 4, piensos) is declared field type text, not decimal.

    Unlike the other seven ``P012`` (decimal) índices, casilla 1543 is
    AEAT-declared field type ``X`` (text) — an AEAT Diseño de Registros
    quirk this engine must not let silently disable índice 4.
    """

    def test_text_typed_piensos_indice_applies_via_text_inputs(self) -> None:
        snapshot = _modelo_100_2025_snapshot()
        revision = snapshot.revision
        calculation = calculate_registry_snapshot(
            snapshot,
            inputs={
                _CASILLA_1521_INGRESOS: _INGRESOS,
                _CASILLA_1522_INDICE: _INDICE_RENDIMIENTO_NETO,
                _CASILLA_1538_AMORTIZACION: _AMORTIZACION,
            },
            binding_values=_neutral_binding_values(),
            enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
            relation_values={relation.id: Decimal("0") for relation in revision.relations},
            date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
            date_context={"filing_period": date(2025, 12, 31)},
            text_inputs={"1543": "0.50"},
        )
        assert calculation.values[_CASILLA_1539_RENDIMIENTO_NETO_MINORADO] == _TARGET_MINORADO
        expected = (_TARGET_MINORADO * Decimal("0.50")).quantize(Decimal("0.01"))
        assert calculation.values[_CASILLA_1548_RENDIMIENTO_NETO_MODULOS] == expected

    def test_blank_piensos_text_input_never_fabricates_a_reduction(self) -> None:
        # No text_inputs supplied at all — casilla 1543 must resolve to
        # "índice not applied" (factor of 1), never a crash and never a
        # fabricated reduction, even though its declared type is text.
        values = _run_calculation()
        assert values[_CASILLA_1548_RENDIMIENTO_NETO_MODULOS] == _TARGET_MINORADO


class TestNonPositiveMinoradoNeverReceivesIndicesCorrectores:
    """Negative minorado: "no se aplicarán los índices correctores".

    Per the general estimación-objetiva principle ("si el rendimiento neto
    minorado ... es una cantidad negativa, no se aplicarán los índices
    correctores").
    """

    def test_negative_minorado_yields_modulos_equal_to_minorado(self) -> None:
        # amortización driven above the rendimiento neto previo so casilla
        # 1539 nets negative; the declared índice must NOT apply.
        values = _run_calculation(
            ingresos=Decimal("1000.00"),
            indice=Decimal("0.37"),
            amortizacion=Decimal("5000.00"),
            indices_correctores={_CASILLA_1541_PERSONAL_ASALARIADO: _INDICE_PERSONAL_ASALARIADO},
        )
        minorado = values[_CASILLA_1539_RENDIMIENTO_NETO_MINORADO]
        assert minorado < Decimal("0")
        assert values[_CASILLA_1548_RENDIMIENTO_NETO_MODULOS] == minorado
