"""Modelo 100 2025 estimación objetiva agraria — Fase 1ª/2ª rendimiento base y minorado.

Non-tautological: the expected figures are transcribed independently from
AEAT Manual práctico de Renta worked examples — not re-derived from the
registry formula under test.

Fase 1ª (rendimiento base producto = ingresos íntegros x índice de
rendimiento neto) is grounded in Orden HAC/1347/2024, Anexo I, instrucción
2.1, cross-checked byte-identical against the bundled consolidated corpus
(``corpus/normatives/html/orden-hac-1347-2024.html``), and the expected
rendimiento neto previo (6.671,10 euros) is transcribed from the Manual
práctico de Renta 2025, Parte 1, Capítulo 9 worked example ("Ejemplo:
Determinación del rendimiento neto previo de la actividad", Doña M.J.I.).

Fase 2ª (rendimiento neto minorado = rendimiento neto previo − amortización
del inmovilizado material e intangible) is grounded in the same Anexo I,
instrucción 2.2. The rendimiento neto previo figure (6.671,10 euros) is the
same 2025 worked example above; the amortización figure (11.185,00 euros) is
independently transcribed from the AEAT Manual práctico de Renta 2022, Parte
1, Capítulo 9 full worked example's own printed "Total amortizaciones" row of
its libro registro de bienes de inversión, proving the subtraction is real,
non-tautological arithmetic against two independently-sourced AEAT figures —
see ``TestRendimientoNetoMinoradoSubtractsAmortizacion``.

See Also:
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Real registry engine used to evaluate the M100 2025 snapshot.
    :func:`~domain.calculations.registry.build_snapshot`
        Snapshot builder that loads the committed Modelo 100 revision under
        test.
    :func:`~domain.calculations.registry.validated_casilla_id`
        Casilla-id constructor used for the 1521/1522/1523/1537/1538/1539
        assertions.
    ``src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/formulas/0293-renta-2025-eo-agraria-rendimiento-base.toml``
        Registry formulas for the Fase 1ª product base, Fase 1ª aggregate, and
        Fase 2ª minorado chain.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.snapshot import build_snapshot

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
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
_CASILLA_1538_AMORTIZACION = validated_casilla_id("1538", surface="test")
_CASILLA_1539_RENDIMIENTO_NETO_MINORADO = validated_casilla_id("1539", surface="test")


def _modelo_100_2025_snapshot():
    modelo, catalogues = _committed_modelo("100")
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="0A")


def _neutral_binding_values() -> dict[str, Decimal]:
    """The minimal neutral binding set every M100 2025 calculate run needs.

    Mirrors the fixture in ``test_ledger_renta_gastos_estimacion_directa_binding.py`` — a
    childless, unmarried, estimación-directa-normal individual filer with no
    prior-year carry, so the chain under test is isolated from unrelated
    axes.
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
    *, ingresos: Decimal, indice: Decimal, amortizacion: Decimal | None = None
) -> Mapping[CasillaId, Decimal]:
    snapshot = _modelo_100_2025_snapshot()
    revision = snapshot.revision
    inputs = {
        _CASILLA_1521_INGRESOS: ingresos,
        _CASILLA_1522_INDICE: indice,
    }
    if amortizacion is not None:
        inputs[_CASILLA_1538_AMORTIZACION] = amortizacion
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


class TestRendimientoNetoMinoradoSubtractsAmortizacion:
    """Fase 2ª: rendimiento neto minorado = rendimiento neto previo − amortización.

    Grounded in Orden HAC/1347/2024, Anexo I, instrucción 2.2 ("El
    rendimiento neto minorado se obtiene deduciendo del anterior las
    cantidades que, en concepto de amortización del inmovilizado material e
    intangible correspondan a la depreciación efectiva..."). The rendimiento
    neto previo figure (6.671,10 euros) is the same AEAT Manual práctico de
    Renta 2025, Parte 1, Capítulo 9 worked example (Doña M.J.I., código 12)
    the Fase 1ª tests above reproduce; the amortización figure (11.185,00
    euros) is independently transcribed from the AEAT Manual práctico de
    Renta 2022, Parte 1, Capítulo 9 full worked example's own printed "Total
    amortizaciones" row of its libro registro de bienes de inversión ("Nave
    almacén y establo" 1.800 + "Remolque" 0 + "Máquina abonadora" 300 +
    "Instalación de riego" 625 + "Tractor y accesorios" 7.200 + "Útiles de
    labranza" 1.260 = 11.185). Combining a 2025 previo figure with a 2022
    amortización figure proves the subtraction is real, non-tautological
    arithmetic against two independently-sourced AEAT figures — not a claim
    that this exact combination appears together in either manual.
    """

    def test_previo_minus_independently_transcribed_amortizacion(self) -> None:
        values = _run_calculation(
            ingresos=_INGRESOS,
            indice=_INDICE,
            amortizacion=Decimal("11185.00"),
        )
        assert values[_CASILLA_1537_RENDIMIENTO_NETO_PREVIO] == _EXPECTED_RENDIMIENTO_NETO_PREVIO
        # 6.671,10 (2025 manual previo) − 11.185,00 (2022 manual's own
        # printed "Total amortizaciones") = −4.513,90 — the instrucción 2.2
        # text does not floor the minorado at zero (unlike a floored
        # reduction elsewhere in the chain), so a negative minorado is the
        # correct, ungrounded-in-a-floor arithmetic result here.
        assert values[_CASILLA_1539_RENDIMIENTO_NETO_MINORADO] == Decimal("-4513.90")

    def test_blank_amortizacion_never_fabricates_a_reduction(self) -> None:
        # An operator who has not yet declared their amortización figure
        # (this engine models no per-element asset register) must see
        # rendimiento neto minorado equal rendimiento neto previo exactly —
        # never a fabricated depreciation the engine has no basis to derive.
        values = _run_calculation(ingresos=_INGRESOS, indice=_INDICE)
        assert values[_CASILLA_1539_RENDIMIENTO_NETO_MINORADO] == _EXPECTED_RENDIMIENTO_NETO_PREVIO

    def test_declared_amortizacion_reduces_minorado_below_previo(self) -> None:
        values = _run_calculation(
            ingresos=_INGRESOS,
            indice=_INDICE,
            amortizacion=Decimal("1500.00"),
        )
        assert values[_CASILLA_1537_RENDIMIENTO_NETO_PREVIO] == _EXPECTED_RENDIMIENTO_NETO_PREVIO
        assert values[_CASILLA_1539_RENDIMIENTO_NETO_MINORADO] == _EXPECTED_RENDIMIENTO_NETO_PREVIO - Decimal("1500.00")
