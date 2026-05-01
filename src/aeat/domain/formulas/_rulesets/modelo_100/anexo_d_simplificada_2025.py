"""Modelo 100 Anexo D — E.D. simplificada (actividades económicas, ejercicio 2025).

Estimación directa simplificada applies when cifra de negocios <=
600.000 € and the contribuyente has not opted out of the régimen
(RIRPF art. 28). The defining characteristic vs E.D. normal is the
**5 % gastos de difícil justificación cap** of RIRPF art. 30:

    gastos_dificil_justif = min( 5% * rendimiento_neto_previo,  2.000 EUR )

Aggregation chain on M100:

- ``0210`` — ingresos de explotación (input)
- ``0215`` — gastos generales deducibles (input — incluye gastos de
  personal, servicios exteriores, tributos, amortización per tabla
  simplificada — se imputan al casillero único 0215 en este régimen
  para mantener la simplicidad operativa de la estimación
  simplificada)
- ``0220`` (rendimiento neto antes del 5 % difícil justificación,
  computed) = ``clamp_pos(0210 - 0215)``
- ``0225`` (gastos difícil justificación, computed) =
  ``min( 0.05 * 0220, 2000.00 )``
- ``0230`` (rendimiento neto previo E.D. simplificada, computed) =
  ``clamp_pos(0220 - 0225)``
- ``0235`` — reducciones LIRPF art. 32 (input — irregularidad,
  startup)
- ``0240`` (rendimiento neto reducido E.D. simplificada, computed) =
  ``clamp_pos(0230 - 0235)``

RIRPF art. 30 has been stable since the modificación of 2018 (the
2.000 € cap was introduced then); BOE consolidated-text consult
2026-02-28 confirms no posterior modification. Stable across 2024 /
2025 / 2026.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .....core.i18n import Translatable
from ..._formula import Literal, MinFormula, MulFormula
from ..._ruleset import ParameterTable
from .._common import (
    casilla,
    clamp_pos,
    formula,
    lit,
    ref,
    sub_op,
)
from ._common import cite_lirpf, cite_rirpf

EFFECTIVE_FROM = date(2025, 1, 1)
EFFECTIVE_TO = date(2025, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


CITATIONS = (
    cite_lirpf(
        "28",
        "Artículo 28 Ley 35/2006 (IRPF) — rendimiento neto en "
        "estimación directa simplificada: diferencia entre la "
        "totalidad de los ingresos íntegros y los gastos deducibles, "
        "con las particularidades del Reglamento.",
    ),
    cite_lirpf(
        "32",
        "Artículo 32 Ley 35/2006 (IRPF) — reducciones aplicables al "
        "rendimiento neto: 30 % rendimientos irregulares; reducción "
        "20 % autónomos noveles primer ejercicio + siguiente.",
    ),
    cite_rirpf(
        "30",
        "Artículo 30 RD 439/2007 (Reglamento del IRPF) — estimación "
        "directa simplificada: el conjunto de las provisiones "
        "deducibles y los gastos de difícil justificación se "
        "cuantificará aplicando el porcentaje del 5 % sobre el "
        "rendimiento neto positivo, excluido este concepto, sin que "
        "pueda exceder de 2.000 € anuales.",
    ),
    cite_rirpf(
        "28",
        "Artículo 28 RD 439/2007 (Reglamento del IRPF) — la "
        "modalidad simplificada es aplicable cuando la cifra neta de "
        "negocios del conjunto de actividades del año anterior <= "
        "600.000 € y no se ha renunciado a esta modalidad.",
    ),
)


CASILLAS = (
    casilla(
        casilla_id="0210",
        label=_label(
            "Ingresos de explotación E.D. simplificada",
            "Operating income (E.D. simplificada)",
            "Üzemi bevétel (E.D. egyszerűsített)",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0215",
        label=_label(
            "Gastos generales deducibles E.D. simplificada",
            "Deductible general expenses (E.D. simplificada)",
            "Általános levonható költségek (egyszerűsített)",
        ),
        computed=False,
        legal_basis=(CITATIONS[0], CITATIONS[2]),
        notes_es=(
            "Engloba gastos de personal, servicios exteriores, "
            "tributos, amortización per la tabla simplificada del "
            "Anexo de la Orden de 27/3/1998. Excluye los gastos de "
            "difícil justificación (computados aparte en 0225 al 5 %)."
        ),
    ),
    casilla(
        casilla_id="0220",
        label=_label(
            "Rendimiento neto antes del 5 % difícil justificación",
            "Net income before 5 % unjustified-expenses cap",
            "Bruttó jövedelem 5 % nehezen igazolható költség előtt",
        ),
        computed=True,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0225",
        label=_label(
            "Gastos de difícil justificación (5 % límite 2.000 €)",
            "Unjustified expenses (5 % capped at 2.000 €)",
            "Nehezen igazolható költségek (5 %, 2.000 € felső)",
        ),
        computed=True,
        legal_basis=(CITATIONS[2],),
    ),
    casilla(
        casilla_id="0230",
        label=_label(
            "Rendimiento neto previo E.D. simplificada",
            "Net business income before art. 32 reduction (simpl.)",
            "Bruttó vállalkozási jövedelem 32. cikk előtt (egyszerűsített)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[2]),
    ),
    casilla(
        casilla_id="0235",
        label=_label(
            "Reducción LIRPF art. 32 — E.D. simplificada",
            "Art. 32 reduction (E.D. simplificada)",
            "32. cikk csökkentés (egyszerűsített)",
        ),
        computed=False,
        legal_basis=(CITATIONS[1],),
    ),
    casilla(
        casilla_id="0240",
        label=_label(
            "Rendimiento neto reducido E.D. simplificada",
            "Net business income (reduced, simpl.)",
            "Nettó vállalkozási jövedelem (csökkentett, egyszerűsített)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[1], CITATIONS[2]),
    ),
)


# RIRPF art. 30 5 % cap at 2.000 €:
#   gastos_dificil = min( 0.05 * rendimiento_neto_previo, 2000 )
# encoded directly via MinFormula(MulFormula(literal, ref), literal).
# The MulFormula is constructed manually because the _common.percent
# helper expects the rate as the first operand and base as second; the
# arithmetic is identical (0.05 * 0220) but bypassing percent keeps
# the AST shape minimal — one mul + one min vs one percent + one min.
_GASTOS_DIFICIL_BODY = MinFormula(
    operands=(
        MulFormula(operands=(Literal(value=Decimal("0.05")), ref("0220"))),
        lit("2000.00"),
    ),
)


FORMULAS = (
    formula(
        casilla_id="0220",
        formula_id="modelo_100.2025.d_simplificada.rendimiento_neto_pre_cap",
        body=clamp_pos(sub_op(ref("0210"), ref("0215"))),
    ),
    formula(
        casilla_id="0225",
        formula_id="modelo_100.2025.d_simplificada.gastos_dificil_justificacion",
        body=_GASTOS_DIFICIL_BODY,
    ),
    formula(
        casilla_id="0230",
        formula_id="modelo_100.2025.d_simplificada.rendimiento_neto_previo",
        body=clamp_pos(sub_op(ref("0220"), ref("0225"))),
    ),
    formula(
        casilla_id="0240",
        formula_id="modelo_100.2025.d_simplificada.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0230"), ref("0235"))),
    ),
)


PARAMETERS = ParameterTable(entries={})


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]
