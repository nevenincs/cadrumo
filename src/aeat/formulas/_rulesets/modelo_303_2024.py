"""Modelo 303 ruleset covering the full 2024 fiscal year (#183).

Codifies the régimen general arithmetic of the autoliquidación
trimestral de IVA: IVA devengado on operaciones interiores
(casillas 01-09), IVA deducible (casillas 28-45) and the
resultado de la liquidación (casillas 64-71). Out-of-scope for
this wave (per the wave-2 ADR
``2026-04-17-modelo-303-formulas-adr.md``):

- Régimen simplificado, REAGP, REBU, recargo de equivalencia
  (casillas 46-63).
- Casillas 10-12 (Ley 7/2024 transitional rates for alimentación
  básica, electricidad, gas).
- Cross-quarter accumulation of casilla 67; caller-maintained
  pool, identical pattern to Modelo 130 casilla 05.
- Foral attribution; casilla 65 defaults to 100.

The 2024 and 2025 rulesets are mechanically identical because
LIVA arts. 90 / 91 régimen general rates were not amended
between the two years (see the wave-2 research doc
``2026-04-17-modelo-303-casilla-rules-research.md`` §"Mid-year
rule changes"). The shared casilla and citation tuples live in
this module; the 2025 sibling re-imports them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...models import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from ._common import (
    add_op,
    casilla,
    div_op,
    formula,
    lit,
    make_citation,
    param,
    percent,
    ref,
    sub_op,
)

_EFFECTIVE_FROM = date(2024, 1, 1)
_EFFECTIVE_TO = date(2024, 12, 31)


_CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "90",
        "Ley 37/1992 IVA, artículo 90.Uno. Establece el tipo impositivo "
        "general del 21 % aplicable a las operaciones sujetas no incluidas "
        "en los tipos reducidos del artículo 91.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "91",
        "Ley 37/1992 IVA, artículo 91. Establece los tipos reducidos del "
        "10 % (apartado Uno) y del 4 % (apartado Dos) aplicables a las "
        "operaciones interiores enumeradas, así como las exenciones y "
        "particularidades aplicables a cada categoría de bienes y "
        "servicios.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "92",
        "Ley 37/1992 IVA, artículo 92. Reconoce el derecho a la deducción "
        "del IVA soportado en las operaciones gravadas que el sujeto "
        "pasivo realiza en el ejercicio de su actividad empresarial o "
        "profesional, sujeto a los requisitos de los artículos 93 a 100.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "164",
        "Ley 37/1992 IVA, artículo 164. Establece la obligación general "
        "de los sujetos pasivos de presentar las declaraciones-"
        "liquidaciones correspondientes e ingresar el importe del "
        "impuesto resultante.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.REAL_DECRETO,
        "71",
        "Real Decreto 1624/1992, artículo 71. Establece el periodo de "
        "liquidación trimestral del IVA para los empresarios y "
        "profesionales cuyo volumen de operaciones no exceda los "
        "límites establecidos.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28925",
    ),
)


_CASILLAS = (
    # ── IVA devengado — régimen general operaciones interiores ──────
    casilla(
        casilla_id="01",
        label={
            "es": "Base imponible al 4 %",
            "en": "Taxable base at the super-reduced 4 % rate",
            "hu": "Adóalap szuper-kedvezményes 4 %-os kulcson",
        },
        computed=False,
        legal_basis=_CITATIONS[1:2],
        notes_es="Base imponible de las entregas y prestaciones interiores "
        "gravadas al tipo súper-reducido del 4 % (Art. 91.Dos).",
    ),
    casilla(
        casilla_id="02",
        label={
            "es": "Tipo 4 %",
            "en": "Rate 4 %",
            "hu": "Kulcs 4 %",
        },
        computed=True,
        legal_basis=_CITATIONS[1:2],
        notes_es="Tipo impositivo súper-reducido (constante).",
    ),
    casilla(
        casilla_id="03",
        label={
            "es": "Cuota devengada al 4 %",
            "en": "Output VAT at 4 % (01 x 0.04)",
            "hu": "Fizetendő ÁFA 4 %-on (01 x 0.04)",
        },
        computed=True,
        legal_basis=_CITATIONS[1:2],
    ),
    casilla(
        casilla_id="04",
        label={
            "es": "Base imponible al 10 %",
            "en": "Taxable base at the reduced 10 % rate",
            "hu": "Adóalap kedvezményes 10 %-os kulcson",
        },
        computed=False,
        legal_basis=_CITATIONS[1:2],
    ),
    casilla(
        casilla_id="05",
        label={
            "es": "Tipo 10 %",
            "en": "Rate 10 %",
            "hu": "Kulcs 10 %",
        },
        computed=True,
        legal_basis=_CITATIONS[1:2],
        notes_es="Tipo impositivo reducido (constante).",
    ),
    casilla(
        casilla_id="06",
        label={
            "es": "Cuota devengada al 10 %",
            "en": "Output VAT at 10 % (04 x 0.10)",
            "hu": "Fizetendő ÁFA 10 %-on (04 x 0.10)",
        },
        computed=True,
        legal_basis=_CITATIONS[1:2],
    ),
    casilla(
        casilla_id="07",
        label={
            "es": "Base imponible al 21 %",
            "en": "Taxable base at the general 21 % rate",
            "hu": "Adóalap általános 21 %-os kulcson",
        },
        computed=False,
        legal_basis=_CITATIONS[0:1],
    ),
    casilla(
        casilla_id="08",
        label={
            "es": "Tipo 21 %",
            "en": "Rate 21 %",
            "hu": "Kulcs 21 %",
        },
        computed=True,
        legal_basis=_CITATIONS[0:1],
        notes_es="Tipo impositivo general (constante).",
    ),
    casilla(
        casilla_id="09",
        label={
            "es": "Cuota devengada al 21 %",
            "en": "Output VAT at 21 % (07 x 0.21)",
            "hu": "Fizetendő ÁFA 21 %-on (07 x 0.21)",
        },
        computed=True,
        legal_basis=_CITATIONS[0:1],
    ),
    # ── IVA deducible — bases y cuotas ───────────────────────────────
    casilla(
        casilla_id="28",
        label={
            "es": "Base — operaciones interiores corrientes",
            "en": "Base — domestic current operations",
            "hu": "Adóalap — belföldi folyó ügyletek",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
        notes_es="Base imponible total del IVA soportado deducible en operaciones interiores corrientes.",
    ),
    casilla(
        casilla_id="29",
        label={
            "es": "Cuota deducible — operaciones interiores corrientes",
            "en": "Deductible VAT — domestic current operations",
            "hu": "Levonható ÁFA — belföldi folyó ügyletek",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="30",
        label={
            "es": "Base — operaciones interiores bienes de inversión",
            "en": "Base — domestic capital goods",
            "hu": "Adóalap — belföldi tárgyi eszközök",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="31",
        label={
            "es": "Cuota deducible — bienes de inversión",
            "en": "Deductible VAT — capital goods",
            "hu": "Levonható ÁFA — tárgyi eszközök",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="32",
        label={
            "es": "Base — importaciones bienes corrientes",
            "en": "Base — current-good imports",
            "hu": "Adóalap — folyó termékimport",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="33",
        label={
            "es": "Cuota deducible — importaciones corrientes",
            "en": "Deductible VAT — current-good imports",
            "hu": "Levonható ÁFA — folyó termékimport",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="34",
        label={
            "es": "Base — importaciones bienes de inversión",
            "en": "Base — capital-good imports",
            "hu": "Adóalap — tárgyieszköz-import",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="35",
        label={
            "es": "Cuota deducible — importaciones de inversión",
            "en": "Deductible VAT — capital-good imports",
            "hu": "Levonható ÁFA — tárgyieszköz-import",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="36",
        label={
            "es": "Base — adquisiciones intracomunitarias corrientes",
            "en": "Base — intra-community current acquisitions",
            "hu": "Adóalap — közösségi folyó beszerzések",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="37",
        label={
            "es": "Cuota deducible — adquisiciones intracomunitarias corrientes",
            "en": "Deductible VAT — intra-community current acquisitions",
            "hu": "Levonható ÁFA — közösségi folyó beszerzések",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="38",
        label={
            "es": "Base — adquisiciones intracomunitarias de inversión",
            "en": "Base — intra-community capital acquisitions",
            "hu": "Adóalap — közösségi tárgyieszköz-beszerzések",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="39",
        label={
            "es": "Cuota deducible — adquisiciones intracomunitarias inversión",
            "en": "Deductible VAT — intra-community capital acquisitions",
            "hu": "Levonható ÁFA — közösségi tárgyieszköz-beszerzések",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="40",
        label={
            "es": "Rectificación de deducciones",
            "en": "Rectification of deductions",
            "hu": "Levonási helyesbítés",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
        notes_es="Importe signado: positivo cuando aumenta la deducción, negativo cuando la minora.",
    ),
    casilla(
        casilla_id="41",
        label={
            "es": "Compensaciones régimen especial A.G.P.",
            "en": "REAGP compensations",
            "hu": "REAGP-kompenzációk",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="42",
        label={
            "es": "Regularización bienes de inversión",
            "en": "Capital-goods regularisation",
            "hu": "Tárgyi eszközök szabályozása",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="43",
        label={
            "es": "Regularización por aplicación del porcentaje definitivo de prorrata",
            "en": "Definitive prorata regularisation",
            "hu": "Végleges prorata-szabályozás",
        },
        computed=False,
        legal_basis=_CITATIONS[2:3],
        notes_es="Importe ya calculado por el contribuyente; el motor no deriva el porcentaje en este wave.",
    ),
    casilla(
        casilla_id="44",
        label={
            "es": "Total a deducir",
            "en": "Total deductible (Σ deductibles + adjustments)",
            "hu": "Összes levonható (Σ levonások + helyesbítések)",
        },
        computed=True,
        legal_basis=_CITATIONS[2:3],
    ),
    casilla(
        casilla_id="45",
        label={
            "es": "Resultado régimen general",
            "en": "Régimen general result ((03+06+09) - 44)",
            "hu": "Régimen general eredmény ((03+06+09) - 44)",
        },
        computed=True,
        legal_basis=_CITATIONS[2:3],
    ),
    # ── Resultado de la liquidación ──────────────────────────────────
    casilla(
        casilla_id="64",
        label={
            "es": "Suma de resultados",
            "en": "Sum of partial results (= 45 in v1)",
            "hu": "Részeredmények összege (= 45 v1-ben)",
        },
        computed=True,
        legal_basis=_CITATIONS[3:4],
    ),
    casilla(
        casilla_id="65",
        label={
            "es": "% atribuible al Estado",
            "en": "% attributable to the State (default 100)",
            "hu": "Az állam részesedése (alapértelmezetten 100)",
        },
        computed=False,
        legal_basis=_CITATIONS[3:4],
        notes_es="Default 100 para contribuyentes sin atribución foral. "
        "Foral (País Vasco / Navarra) queda fuera de este wave.",
    ),
    casilla(
        casilla_id="66",
        label={
            "es": "Atribuible al Estado",
            "en": "Attributable to the State (64 x 65 ÷ 100)",
            "hu": "Államnak juttatott rész (64 x 65 ÷ 100)",
        },
        computed=True,
        legal_basis=_CITATIONS[3:4],
    ),
    casilla(
        casilla_id="67",
        label={
            "es": "Cuotas a compensar de períodos anteriores",
            "en": "Carry-over compensation from prior periods",
            "hu": "Korábbi időszakok kompenzálandó tételei",
        },
        computed=False,
        legal_basis=_CITATIONS[3:4],
        notes_es="Acumulador cross-quarter. El motor no deriva 67 "
        "dentro de una sola liquidación; el llamador mantiene la "
        "suma de cuotas a compensar de trimestres anteriores.",
    ),
    casilla(
        casilla_id="69",
        label={
            "es": "Resultado",
            "en": "Result (66 - 67)",
            "hu": "Eredmény (66 - 67)",
        },
        computed=True,
        legal_basis=_CITATIONS[3:4],
    ),
    casilla(
        casilla_id="71",
        label={
            "es": "Resultado de la autoliquidación",
            "en": "Self-assessment result (= 69 in v1)",
            "hu": "Önadózás eredménye (= 69 v1-ben)",
        },
        computed=True,
        legal_basis=_CITATIONS[3:4],
    ),
)


# Casillas 64 and 71 are pass-through casillas in v1 (they equal 45
# and 69 respectively). The wave-1 engine's :class:`AddFormula`
# requires ``min_length=2`` operands; we add ``Literal("0")`` as the
# second operand to keep the formula DSL within its declared
# arity. The terminal :class:`RoundFormula` quantises to 2 dp and
# the value is semantically equivalent to ``ref("45")`` /
# ``ref("69")`` for monetary purposes.
_FORMULAS_2024 = (
    formula(
        casilla_id="02",
        formula_id="modelo_303.2024.tipo_superreducido",
        body=lit(4),
    ),
    formula(
        casilla_id="03",
        formula_id="modelo_303.2024.cuota_superreducido",
        body=percent(param("iva.rate_superreducido"), ref("01")),
    ),
    formula(
        casilla_id="05",
        formula_id="modelo_303.2024.tipo_reducido",
        body=lit(10),
    ),
    formula(
        casilla_id="06",
        formula_id="modelo_303.2024.cuota_reducido",
        body=percent(param("iva.rate_reducido"), ref("04")),
    ),
    formula(
        casilla_id="08",
        formula_id="modelo_303.2024.tipo_general",
        body=lit(21),
    ),
    formula(
        casilla_id="09",
        formula_id="modelo_303.2024.cuota_general",
        body=percent(param("iva.rate_general"), ref("07")),
    ),
    formula(
        casilla_id="44",
        formula_id="modelo_303.2024.total_deducible",
        body=add_op(
            ref("29"),
            ref("31"),
            ref("33"),
            ref("35"),
            ref("37"),
            ref("39"),
            ref("40"),
            ref("41"),
            ref("42"),
            ref("43"),
        ),
    ),
    formula(
        casilla_id="45",
        formula_id="modelo_303.2024.resultado_regimen_general",
        body=sub_op(add_op(ref("03"), ref("06"), ref("09")), ref("44")),
    ),
    formula(
        casilla_id="64",
        formula_id="modelo_303.2024.suma_resultados",
        body=add_op(ref("45"), lit("0")),
    ),
    formula(
        casilla_id="66",
        formula_id="modelo_303.2024.atribuible_estado",
        body=div_op(percent(ref("65"), ref("64")), lit("100")),
    ),
    formula(
        casilla_id="69",
        formula_id="modelo_303.2024.resultado",
        body=sub_op(ref("66"), ref("67")),
    ),
    formula(
        casilla_id="71",
        formula_id="modelo_303.2024.resultado_autoliquidacion",
        body=add_op(ref("69"), lit("0")),
    ),
)


_PARAMETERS_2024 = ParameterTable(
    entries={
        "iva.rate_general": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.21"),
            ),
        ),
        "iva.rate_reducido": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.10"),
            ),
        ),
        "iva.rate_superreducido": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.04"),
            ),
        ),
    }
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_303.2024",
    modelo=ModeloCode.MODELO_303,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS_2024,
    parameters=_PARAMETERS_2024,
    legal_citations=_CITATIONS,
)
