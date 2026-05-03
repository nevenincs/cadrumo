"""Modelo 130 ruleset covering the full 2024 fiscal year.

The formulas below encode the AEAT Instrucciones Modelo 130 and the
reglamentary text of Real Decreto 439/2007 article 110 for tax year
2024. Mid-year rule changes are absent across 2024 → 2025; the 2025
ruleset is therefore structurally identical and re-imports this module's
casilla and citation tuples.

Casillas that depend on prior-quarter state (``05`` pagos fraccionados
anteriores, ``15`` arrastre de negativos) are user-input — the caller
maintains the cross-quarter pool.

The module also exposes :func:`compute_casilla_13_minoracion`, a helper
that resolves the RIRPF art. 110.3.c sliding-scale step function so the
caller can pre-compute the casilla-13 input before invoking the engine.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....core.errors import EvaluationError
from ...modelos import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from ._common import (
    Bracket,
    add_op,
    casilla,
    clamp_pos,
    formula,
    lit,
    make_citation,
    max_op,
    param,
    percent,
    ref,
    sub_op,
)

_EFFECTIVE_FROM = date(2024, 1, 1)
_EFFECTIVE_TO = date(2024, 12, 31)

_CITATIONS = (
    make_citation(
        LegalCitationSource.REAL_DECRETO,
        "110",
        "Importe del fraccionamiento — art. 110 del Reglamento del IRPF "
        "(RD 439/2007). Establece los tipos del 20% (actividades en estimación "
        "directa distintas de las agrícolas, ganaderas, forestales y pesqueras) "
        "y 2% (actividades agrícolas, ganaderas, forestales y pesqueras), "
        "las minoraciones aplicables y la regla del arrastre de negativos.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "99",
        "Ley 35/2006 IRPF, artículo 99. Establece la obligación general de "
        "practicar pagos a cuenta del IRPF, entre ellos los pagos fraccionados.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
    ),
)


_CASILLAS = (
    casilla(
        casilla_id="01",
        label={
            "es": "Ingresos",
            "en": "Cumulative gross income (Apartado I)",
            "hu": "Halmozott bruttó bevétel (I. szakasz)",
        },
        computed=False,
        legal_basis=_CITATIONS[:1],
        notes_es="Totalidad de los ingresos íntegros fiscalmente computables "
        "del conjunto de las actividades. Acumulado hasta el cierre del "
        "trimestre.",
    ),
    casilla(
        casilla_id="02",
        label={
            "es": "Gastos",
            "en": "Cumulative deductible expenses (Apartado I)",
            "hu": "Halmozott levonható költségek (I. szakasz)",
        },
        computed=False,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="03",
        label={
            "es": "Rendimiento neto",
            "en": "Net return (01 - 02)",
            "hu": "Nettó eredmény (01 - 02)",
        },
        computed=True,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="04",
        label={
            "es": "Importe del pago fraccionado (20%)",
            "en": "Fractional payment (20% of 03, clamped ≥ 0)",
            "hu": "Részletfizetés összege (03 x 20%, nem-negatív)",
        },
        computed=True,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="05",
        label={
            "es": "Pagos fraccionados anteriores (Apartado I)",
            "en": "Prior-quarter fractional payments (caller-maintained)",
            "hu": "Korábbi részletfizetések (hívó fél tartja karban)",
        },
        computed=False,
        legal_basis=_CITATIONS[:1],
        notes_es="Acumulador cross-quarter. El motor no deriva 05 dentro de "
        "una sola liquidación; el llamador mantiene la suma de cas. 07 "
        "positivas y cas. 16 de trimestres anteriores.",
    ),
    casilla(
        casilla_id="06",
        label={
            "es": "Retenciones e ingresos a cuenta (Apartado I)",
            "en": "YTD withholdings (Apartado I)",
            "hu": "Éves halmozott levonások (I. szakasz)",
        },
        computed=False,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="07",
        label={
            "es": "Resultado parcial Apartado I",
            "en": "Partial Apartado I result (04 - 05 - 06)",
            "hu": "I. szakasz részösszeg (04 - 05 - 06)",
        },
        computed=True,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="08",
        label={
            "es": "Volumen de ingresos del trimestre (Apartado II)",
            "en": "Quarterly income volume (Apartado II, per-quarter not YTD)",
            "hu": "Negyedéves bevétel (II. szakasz, nem halmozott)",
        },
        computed=False,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="09",
        label={
            "es": "Importe del pago fraccionado (2%)",
            "en": "Fractional payment (2% of 08)",
            "hu": "Részletfizetés összege (08 x 2%)",
        },
        computed=True,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="10",
        label={
            "es": "Retenciones e ingresos a cuenta (Apartado II)",
            "en": "Quarterly withholdings (Apartado II)",
            "hu": "Negyedéves levonások (II. szakasz)",
        },
        computed=False,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="11",
        label={
            "es": "Resultado parcial Apartado II",
            "en": "Partial Apartado II result (09 - 10)",
            "hu": "II. szakasz részösszeg (09 - 10)",
        },
        computed=True,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="12",
        label={
            "es": "Suma de resultados parciales (nunca negativa)",
            "en": "Sum of Apartados I + II, clamped ≥ 0",
            "hu": "Részösszegek összege, nem-negatív",
        },
        computed=True,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="13",
        label={
            "es": "Minoración por rendimientos netos ≤ 12.000 € (art. 110.3.c)",
            "en": "Low-income minoration (art. 110.3.c step function)",
            "hu": "Alacsony jövedelmi csökkentés (110.3.c szakasz)",
        },
        computed=False,
        legal_basis=_CITATIONS[:1],
        notes_es="El contribuyente introduce el importe directamente o usa el "
        "ayudante compute_casilla_13_minoracion con el rendimiento neto del "
        "ejercicio anterior. La escala 100/75/50/25 €.",
    ),
    casilla(
        casilla_id="14",
        label={
            "es": "Neto tras minoración",
            "en": "Net after minoration (12 - 13, signed)",
            "hu": "Csökkentés utáni nettó (12 - 13, előjeles)",
        },
        computed=True,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="15",
        label={
            "es": "Arrastre de negativos (trimestres anteriores)",
            "en": "Carry-forward of prior-quarter negatives (caller-maintained)",
            "hu": "Korábbi negatívok átvitele (hívó fél tartja karban)",
        },
        computed=False,
        legal_basis=_CITATIONS[:1],
        notes_es="El motor no impone el tope 15 ≤ 14 en este ciclo; queda "
        "a cargo del llamador para la orquestación inter-trimestral.",
    ),
    casilla(
        casilla_id="16",
        label={
            "es": "Deducción por inversión en vivienda habitual",
            "en": "Primary-residence deduction (2% capped at 660.14 €)",
            "hu": "Lakásvásárlási levonás (2%, 660,14 € felső határ)",
        },
        computed=False,
        legal_basis=_CITATIONS[:1],
        notes_es="Aportada por el llamador bajo su propio gating (elegibilidad, apartados mutuamente excluyentes).",
    ),
    casilla(
        casilla_id="17",
        label={
            "es": "Diferencia",
            "en": "Difference (14 - 15 - 16, signed)",
            "hu": "Különbség (14 - 15 - 16, előjeles)",
        },
        computed=True,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="18",
        label={
            "es": "Resultado a ingresar de autoliquidaciones anteriores (complementaria)",
            "en": "Amount paid in earlier complementarias for the same quarter",
            "hu": "Korábbi kiegészítő bevallásban befizetett összeg",
        },
        computed=False,
        legal_basis=_CITATIONS[:1],
    ),
    casilla(
        casilla_id="19",
        label={
            "es": "Resultado final",
            "en": "Final result (17 - 18, signed)",
            "hu": "Végeredmény (17 - 18, előjeles)",
        },
        computed=True,
        legal_basis=_CITATIONS[:1],
    ),
)


_FORMULAS = (
    formula(
        casilla_id="03",
        formula_id="modelo_130.2024.rendimiento_neto",
        body=sub_op(ref("01"), ref("02")),
    ),
    formula(
        casilla_id="04",
        formula_id="modelo_130.2024.pago_fraccionado",
        body=clamp_pos(percent(param("irpf.trimestral_rate"), ref("03"))),
    ),
    formula(
        casilla_id="07",
        formula_id="modelo_130.2024.resultado_apartado_i",
        body=sub_op(sub_op(ref("04"), ref("05")), ref("06")),
    ),
    formula(
        casilla_id="09",
        formula_id="modelo_130.2024.pago_fraccionado_agraria",
        body=percent(param("agraria.trimestral_rate"), ref("08")),
    ),
    formula(
        casilla_id="11",
        formula_id="modelo_130.2024.resultado_apartado_ii",
        body=sub_op(ref("09"), ref("10")),
    ),
    formula(
        casilla_id="12",
        formula_id="modelo_130.2024.suma_parciales",
        body=max_op(lit("0"), add_op(ref("07"), ref("11"))),
    ),
    formula(
        casilla_id="14",
        formula_id="modelo_130.2024.neto_tras_minoracion",
        body=sub_op(ref("12"), ref("13")),
    ),
    formula(
        casilla_id="17",
        formula_id="modelo_130.2024.diferencia",
        body=sub_op(sub_op(ref("14"), ref("15")), ref("16")),
    ),
    formula(
        casilla_id="19",
        formula_id="modelo_130.2024.resultado_final",
        body=sub_op(ref("17"), ref("18")),
    ),
)


_PARAMETERS = ParameterTable(
    entries={
        "irpf.trimestral_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.20"),
            ),
        ),
        "agraria.trimestral_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.02"),
            ),
        ),
    }
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_130.2024",
    modelo=ModeloCode.MODELO_130,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)


# -- Casilla 13 minoración helper ---------------------------------------


_CASILLA_13_BRACKETS: tuple[Bracket, ...] = (
    Bracket(upper_inclusive=Decimal("9000.00"), value=Decimal("100")),
    Bracket(upper_inclusive=Decimal("10000.00"), value=Decimal("75")),
    Bracket(upper_inclusive=Decimal("11000.00"), value=Decimal("50")),
    Bracket(upper_inclusive=Decimal("12000.00"), value=Decimal("25")),
    Bracket(upper_inclusive=None, value=Decimal("0")),
)


def compute_casilla_13_minoracion(previous_year_rendimiento_neto: Decimal) -> Decimal:
    """Return the casilla-13 minoración for the supplied previous-year RN.

    Implements the sliding-scale step function from RIRPF art. 110.3.c. The
    caller passes the result as the ``13`` user-input to
    :meth:`aeat.domain.formulas.Engine.derive`.

    Args:
        previous_year_rendimiento_neto: Net income (rendimiento neto) of the
            preceding fiscal year, used as the bracket-lookup key.

    Returns:
        The applicable minoración amount in euros, drawn from
        :data:`_CASILLA_13_BRACKETS` (100, 75, 50, 25, or 0).

    Raises:
        TypeError: If ``previous_year_rendimiento_neto`` is not a
            :class:`decimal.Decimal`.
        RuntimeError: If the bracket table is exhausted without a match
            (indicates an inconsistent :data:`_CASILLA_13_BRACKETS`).
    """
    if not isinstance(previous_year_rendimiento_neto, Decimal):
        raise TypeError("previous_year_rendimiento_neto must be a Decimal")
    probe = previous_year_rendimiento_neto
    for step in _CASILLA_13_BRACKETS:
        if step.upper_inclusive is None or probe <= step.upper_inclusive:
            return step.value
    raise EvaluationError("casilla 13 brackets exhausted without match")
