"""Modelo 390 ruleset covering the full 2024 fiscal year.

Modelo 390 is the *declaración-resumen anual del IVA*. A taxpayer who
files four quarterly Modelo 303 autoliquidaciones during the year files
exactly one Modelo 390 with período code ``0A`` after year-end. The
form summarises the full-year IVA position, the régimen-by-régimen
result split, the regularización por bienes de inversión adjustment,
and the cuota anual a ingresar / a devolver.

The full BOE template runs to roughly 680 fields. The scoped surface
encoded here covers the kent-relevant régimen-general result chain:

- Apartado 1 datos estadísticos: casillas ``01`` (régimen general 1T
  base), ``04`` (régimen general 1T cuota). Held as user-supplied
  inputs to satisfy the extractor surface; not part of the algebraic
  chain.
- Apartado 3 régimen general anual: casillas ``95`` (total bases
  imponibles), ``96`` (total cuotas repercutidas), ``100`` (total IVA
  soportado deducible interior), ``101`` (total IVA soportado
  deducible importaciones), ``104`` (= 100 + 101), ``105`` (= 96 -
  104).
- Apartados 4-5 otros regímenes: casillas ``108`` (resultado régimen
  simplificado), ``109`` (resultado otros regímenes).
- Apartado 6 resultado anual: casilla ``190`` (= 105 + 108 + 109),
  ``191`` (= 190 - 662), ``192`` (= clamp_pos(191)), ``193`` (=
  clamp_pos(0 - 191)).
- Apartado 7 regularización: casilla ``662`` (regularización por
  bienes de inversión, user-supplied annual adjustment).

Annual cumulation strategy. Modelo 390 is structurally an annual
aggregator of four quarterly Modelo 303 filings. The cumulated
casillas (``95``, ``96``, ``100``, ``101``, ``108``, ``109``, ``662``)
remain user-supplied; only the algebraic relationships among them are
encoded as formulas. Cumulation correctness is asserted at the test
level, not in the formula DSL. This mirrors the Modelo 180 annual
IRPF retention summary pattern. See
``.vault/adr/2026-04-27-modelo-390-calc-verify-adr.md`` for the full
discussion of the alternatives considered.

The 2024 module owns the shared casilla and citation tuples; the
2025 and 2026 siblings re-import them and declare year-scoped
``ParameterTable`` entries plus year-stamped formula identifiers.

Out of scope (tracked under the IVA complexity sub-EPIC ``#345``):

- Per-rate-bucket detail of Apartado 3 (4 / 10 / 21 percent bases and
  cuotas decomposition).
- Deeper prorrata derivation (LIVA arts. 102-106).
- Multi-year bienes-inversión regularización window modelling (LIVA
  arts. 107-110); ``662`` stays a single user-supplied annual figure.
- 2026 small-enterprise franquicia regime (Directiva (UE) 2020/285)
  and 2026 onwards Spanish transposition.
- Foral regimes (País Vasco / Navarra) under EPIC ``#424``.
- Canarias IGIC and Ceuta / Melilla IPSI regional deviations.

Legal base. LIVA arts. 90 and 91 fix the 21 / 10 / 4 percent rate
buckets. LIVA arts. 92-100 ground the IVA soportado deducible
framework (interior + importaciones + intracomunitarias). LIVA arts.
107-110 ground the regularización por bienes de inversión. LIVA art.
164 grounds the autoliquidación and resumen-anual obligation. RIVA
art. 71 (especially the resumen-anual obligation in art. 71.7)
anchors the autoliquidación cycle. Orden EHA/3111/2009 approves the
form; subsequent Órdenes HAC amend non-substantive form metadata
annually without touching the algebraic chain encoded here.
"""

from __future__ import annotations

from datetime import date

from ...i18n import Translatable
from ...models import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, Ruleset
from ._common import (
    add_op,
    casilla,
    clamp_pos,
    formula,
    lit,
    make_citation,
    ref,
    sub_op,
)

_EFFECTIVE_FROM = date(2024, 1, 1)
_EFFECTIVE_TO = date(2024, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


_CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "90",
        "Ley 37/1992 IVA, artículo 90.Uno. Establece el tipo impositivo "
        "general del 21 % aplicable a las operaciones sujetas no incluidas "
        "en los tipos reducidos del artículo 91. Modelo 390 reúne las "
        "cuotas devengadas a este tipo en la casilla 96.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "91",
        "Ley 37/1992 IVA, artículo 91. Establece los tipos reducidos del "
        "10 % (apartado Uno) y del 4 % (apartado Dos). Modelo 390 reúne "
        "las cuotas devengadas a estos tipos en la casilla 96.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "92",
        "Ley 37/1992 IVA, artículo 92. Reconoce el derecho a la deducción "
        "del IVA soportado en operaciones gravadas. Modelo 390 reúne el "
        "IVA soportado deducible interior en la casilla 100 y el "
        "soportado en importaciones en la casilla 101; la casilla 104 los "
        "totaliza.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "102",
        "Ley 37/1992 IVA, artículo 102. Establece la regla de prorrata "
        "para sujetos pasivos con operaciones que originan el derecho a "
        "deducción y operaciones que no lo originan. Modelo 390 supone "
        "que el contribuyente ha aplicado la prorrata correspondiente "
        "antes de cumplimentar el IVA soportado deducible.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "107",
        "Ley 37/1992 IVA, artículo 107. Regula la regularización de las "
        "deducciones por adquisición de bienes de inversión. Modelo 390 "
        "recoge el ajuste anual en la casilla 662, que se traslada a la "
        "cuota resultante anual de la casilla 191.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "164",
        "Ley 37/1992 IVA, artículo 164. Establece la obligación general "
        "de presentar las declaraciones-liquidaciones e ingresar el "
        "importe del impuesto resultante. La declaración-resumen anual "
        "del IVA (modelo 390) materializa esta obligación a nivel anual.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.REGLAMENTO,
        "71.7",
        "Artículo 71.7 RD 1624/1992 (Reglamento IVA, RIVA). Obligación de "
        "presentar la declaración-resumen anual del IVA (modelo 390) "
        "junto con la autoliquidación del último período del ejercicio.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28925",
    ),
    make_citation(
        LegalCitationSource.ORDEN_MINISTERIAL,
        "EHA/3111/2009",
        "Orden EHA/3111/2009, de 5 de noviembre. Aprueba el modelo 390 "
        "y sus diseños lógicos; modificada anualmente por sucesivas "
        "Órdenes HAC para adaptar metadatos de formato sin alterar la "
        "cadena algebraica codificada en este ruleset.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2009-18472",
    ),
)


# Citation slices — keep in sync with the order in `_CITATIONS`.
_CIT_RATES = _CITATIONS[0:2]  # LIVA arts. 90, 91
_CIT_DEDUCCION = _CITATIONS[2:4]  # LIVA arts. 92, 102
_CIT_REGULARIZACION = _CITATIONS[4:5]  # LIVA art. 107
_CIT_AUTOLIQUIDACION = _CITATIONS[5:6]  # LIVA art. 164
_CIT_RESUMEN_OBLIGATION = _CITATIONS[6:8]  # RIVA art. 71.7 + Orden EHA/3111/2009


_CASILLAS = (
    # ── Apartado 1 — datos estadísticos Q1 (statistical reproduction) ──
    casilla(
        casilla_id="01",
        label=_label(
            "Régimen general 1T base",
            "General regime Q1 base",
            "Általános rendszer 1T alap",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="04",
        label=_label(
            "Régimen general 1T cuota",
            "General regime Q1 quota",
            "Általános rendszer 1T összeg",
        ),
        computed=False,
    ),
    # ── Apartado 3 — régimen general anual ───────────────────────────
    casilla(
        casilla_id="95",
        label=_label(
            "Total bases imponibles",
            "Total taxable bases",
            "Összes adóalap",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="96",
        label=_label(
            "Total cuotas repercutidas",
            "Total output VAT",
            "Áthárított ÁFA összesen",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="100",
        label=_label(
            "Total IVA soportado deducible operaciones interiores",
            "Total deductible input VAT (domestic)",
            "Levonható ÁFA belföld",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="101",
        label=_label(
            "Total IVA soportado deducible importaciones",
            "Total deductible input VAT (imports)",
            "Levonható ÁFA import",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="104",
        label=_label(
            "Total IVA soportado deducible",
            "Total deductible input VAT",
            "Összes levonható ÁFA",
        ),
        computed=True,
        legal_basis=_CIT_DEDUCCION,
    ),
    casilla(
        casilla_id="105",
        label=_label(
            "Resultado régimen general",
            "Result (general regime)",
            "Általános rendszer eredménye",
        ),
        computed=True,
        legal_basis=_CIT_RATES + _CIT_AUTOLIQUIDACION,
    ),
    # ── Apartados 4-5 — otros regímenes ──────────────────────────────
    casilla(
        casilla_id="108",
        label=_label(
            "Resultado régimen simplificado",
            "Result (simplified regime)",
            "Egyszerűsített rendszer eredménye",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="109",
        label=_label(
            "Resultado otros regímenes",
            "Result (other regimes)",
            "Egyéb rendszerek eredménye",
        ),
        computed=False,
    ),
    # ── Apartado 6 — resultado anual ─────────────────────────────────
    casilla(
        casilla_id="190",
        label=_label(
            "Suma resultado",
            "Result sum",
            "Eredmény összege",
        ),
        computed=True,
        legal_basis=_CIT_AUTOLIQUIDACION,
    ),
    casilla(
        casilla_id="191",
        label=_label(
            "Cuota resultante anual",
            "Annual result quota",
            "Éves eredmény-összeg",
        ),
        computed=True,
        legal_basis=_CIT_REGULARIZACION + _CIT_AUTOLIQUIDACION,
    ),
    casilla(
        casilla_id="192",
        label=_label(
            "Total a ingresar",
            "Total payable",
            "Fizetendő összeg",
        ),
        computed=True,
        legal_basis=_CIT_AUTOLIQUIDACION,
    ),
    casilla(
        casilla_id="193",
        label=_label(
            "Total a devolver",
            "Total refundable",
            "Visszatérítendő összeg",
        ),
        computed=True,
        legal_basis=_CIT_AUTOLIQUIDACION,
    ),
    # ── Apartado 7 — regularización bienes de inversión ──────────────
    casilla(
        casilla_id="662",
        label=_label(
            "Regularización bienes de inversión",
            "Capital-goods regularisation",
            "Tárgyi eszközök szabályozása",
        ),
        computed=False,
    ),
)


_FORMULAS_2024 = (
    formula(
        casilla_id="104",
        formula_id="modelo_390.2024.iva_soportado_total",
        body=add_op(ref("100"), ref("101")),
    ),
    formula(
        casilla_id="105",
        formula_id="modelo_390.2024.resultado_regimen_general",
        body=sub_op(ref("96"), ref("104")),
    ),
    formula(
        casilla_id="190",
        formula_id="modelo_390.2024.suma_resultado",
        body=add_op(ref("105"), ref("108"), ref("109")),
    ),
    formula(
        casilla_id="191",
        formula_id="modelo_390.2024.cuota_resultante_anual",
        body=sub_op(ref("190"), ref("662")),
    ),
    formula(
        casilla_id="192",
        formula_id="modelo_390.2024.total_a_ingresar",
        body=clamp_pos(ref("191")),
    ),
    formula(
        casilla_id="193",
        formula_id="modelo_390.2024.total_a_devolver",
        body=clamp_pos(sub_op(lit("0"), ref("191"))),
    ),
)


# Modelo 390 sums pre-computed cuotas rather than applying rates, so
# its ParameterTable is empty by design — every IVA rate lives in the
# upstream Modelo 303 quarterly ruleset.
_PARAMETERS = ParameterTable(entries={})


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_390.2024",
    modelo=ModeloCode.MODELO_390,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS_2024,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
