"""Modelo 100 2025 estimación objetiva agraria — Fase 1ª rendimiento base producto.

Non-tautological: the expected figure is transcribed independently from the
AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 9 worked example
("Ejemplo: Determinación del rendimiento neto previo de la actividad", Doña
M.J.I.) — not re-derived from the registry formula under test. The mechanism
(rendimiento base producto = ingresos íntegros x índice de rendimiento neto)
is grounded in Orden HAC/1347/2024, Anexo I, instrucción 2.1, cross-checked
byte-identical against the bundled consolidated corpus
(``corpus/normatives/html/orden-hac-1347-2024.html``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .. import CasillaId, build_snapshot, calculate_registry_snapshot, validated_casilla_id
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 9 (Rendimientos de
# actividades económicas en estimación objetiva (II), actividades agrícolas,
# ganaderas y forestales), worked example: Doña M.J.I., explotación agrícola
# de manzanas (frutos no cítricos → código 12, "Raíces (excepto remolacha
# azucarera), tubérculos, forrajes, algodón, frutos no cítricos y otros
# productos agrícolas no comprendidos expresamente en otros números").
_INGRESOS = Decimal("18030.00")
_INDICE = Decimal("0.37")
_EXPECTED_RENDIMIENTO_NETO_PREVIO = Decimal("6671.10")

_CASILLA_1521_INGRESOS = validated_casilla_id("1521", surface="test")
_CASILLA_1522_INDICE = validated_casilla_id("1522", surface="test")
_CASILLA_1523_RENDIMIENTO_BASE = validated_casilla_id("1523", surface="test")
_CASILLA_1537_RENDIMIENTO_NETO_PREVIO = validated_casilla_id("1537", surface="test")


def _modelo_100_2025_snapshot():
    modelo, catalogues = _committed_modelo("100")
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="0A")


def _neutral_binding_values() -> dict[str, Decimal]:
    """The minimal neutral binding set every M100 2025 calculate run needs.

    Mirrors the fixture in ``test_ledger_renta_expense_binding.py`` — a
    childless, unmarried, estimación-directa-normal individual filer with no
    prior-year carry, so the chain under test is isolated from unrelated
    axes.
    """
    return {
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


def _run_calculation(*, ingresos: Decimal, indice: Decimal) -> Mapping[CasillaId, Decimal]:
    snapshot = _modelo_100_2025_snapshot()
    revision = snapshot.revision
    calculation = calculate_registry_snapshot(
        snapshot,
        inputs={
            _CASILLA_1521_INGRESOS: ingresos,
            _CASILLA_1522_INDICE: indice,
        },
        binding_values=_neutral_binding_values(),
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values={relation.id: Decimal("0") for relation in revision.relations},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
        date_context={"filing_period": date(2025, 12, 31)},
    )
    return calculation.values


class TestRaicesTuberculosFrutosNoCitricosManualWorkedExample:
    """Código 12 (raíces/tubérculos/forrajes/algodón/frutos no cítricos)."""

    def test_rendimiento_base_producto_matches_manual_worked_example(self) -> None:
        values = _run_calculation(ingresos=_INGRESOS, indice=_INDICE)
        assert values[_CASILLA_1523_RENDIMIENTO_BASE] == _EXPECTED_RENDIMIENTO_NETO_PREVIO

    def test_rendimiento_neto_previo_sums_the_single_populated_producto(self) -> None:
        # Only one producto código is populated (the taxpayer's declared
        # actividad, casilla 1486); every other producto's ingresos/índice
        # stay blank (zero), so the Fase 1ª aggregate equals that single
        # producto's rendimiento base — never double-counted, never
        # silently dropped.
        values = _run_calculation(ingresos=_INGRESOS, indice=_INDICE)
        assert values[_CASILLA_1537_RENDIMIENTO_NETO_PREVIO] == _EXPECTED_RENDIMIENTO_NETO_PREVIO


class TestZeroCoverageIsNeverFabricated:
    """A blank ingresos/índice pair must resolve to zero, never a fabricated figure."""

    def test_no_declared_activity_yields_zero_rendimiento(self) -> None:
        values = _run_calculation(ingresos=Decimal("0"), indice=Decimal("0"))
        assert values[_CASILLA_1523_RENDIMIENTO_BASE] == Decimal("0")
        assert values[_CASILLA_1537_RENDIMIENTO_NETO_PREVIO] == Decimal("0")

    def test_ingresos_without_declared_indice_yields_zero_not_a_fabricated_figure(self) -> None:
        # The índice is an operator-declared field (the AEAT form itself asks
        # the filer to transcribe it from the Anexo I código table); a
        # populated ingresos with no índice must multiply to zero, never
        # invent a coefficient the operator did not supply.
        values = _run_calculation(ingresos=Decimal("18030.00"), indice=Decimal("0"))
        assert values[_CASILLA_1523_RENDIMIENTO_BASE] == Decimal("0")
