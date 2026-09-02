"""Modelo 100 2025 estimación objetiva agraria — Fase 4ª/5ª reducciones.

Non-tautological: the target rendimiento neto de módulos (13.233,98 euros),
the 5 por 100 reducción general (661,70 euros), and the resulting
rendimiento neto de la actividad (12.572,28 euros) are transcribed
independently from the AEAT Manual práctico de Renta 2025, Parte 1,
Capítulo 9 full worked example (Don L.H.I., explotación agrícola-ganadera),
continuing exactly where
``test_modelo_100_eo_agraria_indices_correctores.py`` leaves off (Fase 3ª
lands casilla 1548 on 13.233,98 euros there). The manual states: "Reducción
de carácter general: 5% s/13.233,98 = 661,70 euros" and, because Don L.H.I.
has neither gastos extraordinarios nor derecho a la reducción por
agricultores jóvenes, "el rendimiento neto de la actividad es el siguiente:
13.233,98 – 661,70 = 12.572,28 euros". The manual's own Fase 5ª for this
example also has zero irregularidad ("Al no computarse ningún tipo de
rendimiento con período de generación superior a dos años... no procede
aplicar reducción alguna por este concepto"), reproduced by
``TestReduccionIrregularidadMatchesManualWorkedExample``.

The reducción agricultores jóvenes (25 por 100, LIRPF DA-6ª / instrucción 3
del Anexo I Orden HAC/1347/2024) has no applied worked example in the
bundled 2025 manual (Don L.H.I. explicitly does not qualify), so its
mechanism is exercised structurally: the externally-sourced 25 por 100 rate
applied to the externally-sourced post-general-reducción base (casilla
1550), gated by the AJ eligibility casilla — the same composition-testing
convention ``test_two_declared_indices_compose_sequentially`` already uses
in the sibling Fase 3ª suite for the índices correctores cascade. The Fase
5ª art. 32.1 irregularidad reducción (30 por 100, capped at 300.000 euros
anuales) has no POSITIVE applied worked example in the bundled 2025 manual
either (every agraria caso práctico in Capítulo 9 declares zero
rendimientos irregulares), so its mechanism — the 30 por 100 rate and the
300.000 euros cap, both grounded in LIRPF art. 32.1 — is exercised
structurally in ``TestReduccionIrregularidadAppliesThirtyPercentCappedAt300000``,
the same pattern.

See Also:
    :func:`~domain.calculations.registry.build_snapshot`
        Registry snapshot builder used to load the 2025 Modelo 100 revision.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Public calculation entry point exercised by the Fase 4ª/5ª cases.
    :mod:`~domain.calculations.registry.tests.test_modelo_100_eo_agraria_indices_correctores`
        Fase 3ª índice-corrector suite whose casilla 1548 result this test
        continues from.
    ``src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/formulas/0294-renta-2025-eo-agraria-reducciones-fase-4a.toml``
        Registry-authored Fase 4ª formula chain under test.
    ``src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/formulas/0295-renta-2025-eo-agraria-reduccion-irregularidad.toml``
        Registry-authored Fase 5ª irregularidad reduction chain under test.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources.bundled_data import bundled_path
from .....tests.registry_snapshot import build_snapshot
from ..formula_runtime import calculate_registry_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 9, full worked
# example (Don L.H.I., agricultura + ganadería ovina de carne):
# "Rendimiento neto de módulos: (14.704,42 x 0,90) = 13.233,98 euros" (Fase
# 3ª, reproduced by test_modelo_100_eo_agraria_indices_correctores.py);
# "Reducción de carácter general: 5% s/13.233,98 = 661,70 euros"; "Al no
# existir gastos extraordinarios por circunstancias excepcionales ni
# derecho a la reducción por agricultores jóvenes, el rendimiento neto de
# la actividad es el siguiente: 13.233,98 – 661,70 = 12.572,28 euros";
# Fase 5ª "no procede aplicar reducción alguna" so "Rendimiento neto
# reducido de la actividad = Rendimiento neto de la actividad (12.572,28
# euros)" — the manual's own casilla 1555 terminal figure for this example.
_TARGET_MINORADO = Decimal("14704.42")
_INDICE_PERSONAL_ASALARIADO = Decimal("0.90")
_EXPECTED_RENDIMIENTO_NETO_MODULOS = Decimal("13233.98")
_EXPECTED_REDUCCION_GENERAL = Decimal("661.70")
_EXPECTED_RENDIMIENTO_NETO_ACTIVIDAD = Decimal("12572.28")

# Código 12 (raíces/tubérculos/forrajes/algodón/frutos no cítricos), índice
# de rendimiento neto 0,37 — the same Fase 1ª/2ª fixture the sibling Fase 3ª
# suite uses to land casilla 1539 on Don L.H.I.'s externally-sourced
# 14.704,42 euros target.
_INDICE_RENDIMIENTO_NETO = Decimal("0.37")
_INGRESOS = Decimal("45000.00")
_AMORTIZACION = Decimal("1945.58")

_CASILLA_1521_INGRESOS = validated_casilla_id("1521", surface="test")
_CASILLA_1522_INDICE = validated_casilla_id("1522", surface="test")
_CASILLA_1538_AMORTIZACION = validated_casilla_id("1538", surface="test")
_CASILLA_1539_RENDIMIENTO_NETO_MINORADO = validated_casilla_id("1539", surface="test")
_CASILLA_1541_PERSONAL_ASALARIADO = validated_casilla_id("1541", surface="test")
_CASILLA_1548_RENDIMIENTO_NETO_MODULOS = validated_casilla_id("1548", surface="test")
_CASILLA_1549_REDUCCION_GENERAL = validated_casilla_id("1549", surface="test")
_CASILLA_1550_DIFERENCIA = validated_casilla_id("1550", surface="test")
_CASILLA_1551_REDUCCION_JOVENES = validated_casilla_id("1551", surface="test")
_CASILLA_1552_GASTOS_EXTRAORDINARIOS = validated_casilla_id("1552", surface="test")
_CASILLA_1554_REDUCCION_IRREGULARIDAD = validated_casilla_id("1554", surface="test")
_CASILLA_1555_RENDIMIENTO_NETO_REDUCIDO = validated_casilla_id("1555", surface="test")
_CASILLA_AJ_JOVENES_FLAG = validated_casilla_id("AJ", surface="test")
_CASILLA_REDUCCION_IRREGULARIDAD_BASE = validated_casilla_id("eo-agraria-reduccion-irregularidad-base", surface="test")


def _modelo_100_2025_snapshot():
    modelo, catalogues = _committed_modelo("100")
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="0A")


def _neutral_binding_values() -> dict[str, Decimal]:
    """The minimal neutral binding set every M100 2025 calculate run needs.

    Mirrors the fixture in ``test_modelo_100_eo_agraria_indices_correctores.py``.
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
    indice_personal_asalariado: Decimal | None = _INDICE_PERSONAL_ASALARIADO,
    agricultor_joven: Decimal = Decimal("0"),
    gastos_extraordinarios: Decimal = Decimal("0"),
    reduccion_irregularidad_base: Decimal = Decimal("0"),
) -> Mapping[CasillaId, Decimal]:
    snapshot = _modelo_100_2025_snapshot()
    revision = snapshot.revision
    inputs: dict[CasillaId, Decimal] = {
        _CASILLA_1521_INGRESOS: ingresos,
        _CASILLA_1522_INDICE: indice,
        _CASILLA_1538_AMORTIZACION: amortizacion,
        _CASILLA_AJ_JOVENES_FLAG: agricultor_joven,
        _CASILLA_1552_GASTOS_EXTRAORDINARIOS: gastos_extraordinarios,
        _CASILLA_REDUCCION_IRREGULARIDAD_BASE: reduccion_irregularidad_base,
    }
    if indice_personal_asalariado is not None:
        inputs[_CASILLA_1541_PERSONAL_ASALARIADO] = indice_personal_asalariado
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


class TestReduccionGeneralMatchesManualWorkedExample:
    """Fase 4ª apartado 1: reducción de carácter general, 5 por 100."""

    def test_reduccion_general_matches_manual_worked_example(self) -> None:
        values = _run_calculation()
        assert values[_CASILLA_1548_RENDIMIENTO_NETO_MODULOS] == _EXPECTED_RENDIMIENTO_NETO_MODULOS
        assert values[_CASILLA_1549_REDUCCION_GENERAL] == _EXPECTED_REDUCCION_GENERAL
        assert values[_CASILLA_1550_DIFERENCIA] == _EXPECTED_RENDIMIENTO_NETO_ACTIVIDAD


class TestRendimientoNetoReducidoMatchesManualWorkedExample:
    """Fase 4ª/5ª terminal: rendimiento neto reducido (casilla 1555).

    Don L.H.I. has neither gastos extraordinarios nor derecho a la
    reducción por agricultores jóvenes, and no rendimientos irregulares
    (Fase 5ª): the manual states the rendimiento neto reducido de la
    actividad equals the rendimiento neto de la actividad, 12.572,28 euros.
    """

    def test_rendimiento_neto_reducido_matches_manual_worked_example(self) -> None:
        values = _run_calculation()
        assert values[_CASILLA_1551_REDUCCION_JOVENES] == Decimal("0")
        assert values[_CASILLA_1555_RENDIMIENTO_NETO_REDUCIDO] == _EXPECTED_RENDIMIENTO_NETO_ACTIVIDAD


class TestReduccionGeneralNeverFabricatedWhenModulosIsNonPositive:
    """The reducción general only applies "sólo si el importe... es > 0"."""

    def test_zero_modulos_yields_no_reduccion_general(self) -> None:
        values = _run_calculation(
            ingresos=Decimal("1000.00"),
            indice=Decimal("0.37"),
            amortizacion=Decimal("5000.00"),
            indice_personal_asalariado=None,
        )
        modulos = values[_CASILLA_1548_RENDIMIENTO_NETO_MODULOS]
        assert modulos <= Decimal("0")
        assert values[_CASILLA_1549_REDUCCION_GENERAL] == Decimal("0")
        assert values[_CASILLA_1550_DIFERENCIA] == modulos


class TestReduccionJovenesAppliesOnlyWhenEligibilityFlagIsDeclared:
    """Fase 4ª apartado 2: reducción agricultores jóvenes, 25 por 100.

    No applied worked example exists in the bundled 2025 manual (Don
    L.H.I. explicitly does not qualify), so the mechanism is exercised
    structurally: the externally-sourced 25 por 100 rate is applied to the
    externally-sourced post-reducción-general base (casilla 1550, itself
    Don L.H.I.'s manual-sourced 12.572,28 euros), gated by the AJ
    eligibility casilla.
    """

    def test_declared_eligibility_applies_twenty_five_percent_on_1550(self) -> None:
        values = _run_calculation(agricultor_joven=Decimal("1"))
        base = _EXPECTED_RENDIMIENTO_NETO_ACTIVIDAD
        expected_reduccion_jovenes = (base * Decimal("25") / Decimal("100")).quantize(Decimal("0.01"))
        assert values[_CASILLA_1550_DIFERENCIA] == base
        assert values[_CASILLA_1551_REDUCCION_JOVENES] == expected_reduccion_jovenes
        expected_1555 = base - expected_reduccion_jovenes
        assert values[_CASILLA_1555_RENDIMIENTO_NETO_REDUCIDO] == expected_1555

    def test_blank_eligibility_flag_never_fabricates_a_reduccion_jovenes(self) -> None:
        values = _run_calculation(agricultor_joven=Decimal("0"))
        assert values[_CASILLA_1551_REDUCCION_JOVENES] == Decimal("0")


class TestGastosExtraordinariosRemainsAManualDeduction:
    """Fase 4ª apartado 3 (gastos extraordinarios) stays an operator-declared
    amount; casilla 1555 subtracts whatever is declared, never fabricating a
    value when it is blank.
    """

    def test_declared_gastos_extraordinarios_reduce_1555(self) -> None:
        gastos = Decimal("100.00")
        values = _run_calculation(gastos_extraordinarios=gastos)
        assert values[_CASILLA_1555_RENDIMIENTO_NETO_REDUCIDO] == _EXPECTED_RENDIMIENTO_NETO_ACTIVIDAD - gastos


class TestReduccionIrregularidadMatchesManualWorkedExample:
    """Fase 5ª: reducción por irregularidad (casilla 1554, art. 32.1 LIRPF).

    Don L.H.I. has no rendimientos con período de generación superior a dos
    años ni obtenidos de forma notoriamente irregular: the manual states "no
    procede aplicar reducción alguna por este concepto" and "Rendimiento
    neto reducido de la actividad = Rendimiento neto de la actividad
    (12.572,28 euros)" — casilla 1554 stays zero and 1555 equals the Fase 4ª
    terminal figure, reproduced exactly.
    """

    def test_blank_base_yields_zero_reduccion_irregularidad(self) -> None:
        values = _run_calculation()
        assert values[_CASILLA_1554_REDUCCION_IRREGULARIDAD] == Decimal("0")
        assert values[_CASILLA_1555_RENDIMIENTO_NETO_REDUCIDO] == _EXPECTED_RENDIMIENTO_NETO_ACTIVIDAD


class TestReduccionIrregularidadAppliesThirtyPercentCappedAt300000:
    """Fase 5ª mechanism: 30 por 100 sobre min(base declarada, 300.000 euros).

    No agraria caso práctico in the bundled 2025 manual declares a positive
    rendimiento irregular (every worked example in Capítulo 9 states "no
    procede aplicar reducción alguna"), so the mechanism is exercised
    structurally — the same composition-testing convention the sibling
    reducción agricultores jóvenes test above already uses. LIRPF art. 32.1:
    "se reducirán en un 30 por ciento" and "no podrá superar el importe de
    300.000 euros anuales".
    """

    def test_declared_base_under_cap_applies_thirty_percent(self) -> None:
        base = Decimal("1000.00")
        values = _run_calculation(reduccion_irregularidad_base=base)
        expected_reduccion = (base * Decimal("30") / Decimal("100")).quantize(Decimal("0.01"))
        assert values[_CASILLA_1554_REDUCCION_IRREGULARIDAD] == expected_reduccion
        assert (
            values[_CASILLA_1555_RENDIMIENTO_NETO_REDUCIDO] == _EXPECTED_RENDIMIENTO_NETO_ACTIVIDAD - expected_reduccion
        )

    def test_declared_base_over_cap_is_capped_at_300000_before_the_thirty_percent(self) -> None:
        base = Decimal("350000.00")
        values = _run_calculation(reduccion_irregularidad_base=base)
        expected_reduccion = (Decimal("300000") * Decimal("30") / Decimal("100")).quantize(Decimal("0.01"))
        assert values[_CASILLA_1554_REDUCCION_IRREGULARIDAD] == expected_reduccion
        assert values[_CASILLA_1554_REDUCCION_IRREGULARIDAD] == Decimal("90000.00")

    def test_zero_declared_base_never_fabricates_a_reduccion(self) -> None:
        values = _run_calculation(reduccion_irregularidad_base=Decimal("0"))
        assert values[_CASILLA_1554_REDUCCION_IRREGULARIDAD] == Decimal("0")
