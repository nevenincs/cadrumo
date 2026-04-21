"""Modelo 390 ruleset covering the full 2025 fiscal year.

Modelo 390 is the IVA annual resumen — the aggregate autoliquidación
that mirrors the four quarterly Modelo 303 filings. The form runs to
~680 casillas but the MVP targets the three algebraic invariants that
bind Apartado 3 (régimen general), Apartado 6 (resultado anual), and
the per-régimen rollup:

- casilla 104 = casilla 100 + casilla 101 (total IVA soportado deducible
  en operaciones interiores = interior + importaciones).
- casilla 105 = casilla 96 - casilla 104 (resultado régimen general =
  total cuotas repercutidas menos total IVA soportado deducible).
- casilla 190 = casilla 105 + casilla 108 + casilla 109 (suma
  resultado = régimen general + simplificado + otros regímenes).

**Scope limitations (wave 40 audit H2):**

This MVP assumes:

- NO regularización de bienes de inversión (casillas 107 / 662). A
  Kent with bienes-inversion adjustments will see a 105 discrepancy
  because the real AEAT formula subtracts those adjustments before
  arriving at 105.
- NO pro-rata adjustment (casillas 102 / 103). AEAT uses these to
  flow into 104 in the full formula; the MVP treats 104 as just
  ``100 + 101``.
- Single-régimen-general autónomos are the target audience.

Full-form support lands in sub-EPIC #305-Modelo-390-full along with
the remaining ~665 casillas, plus the 191/192/193 branching on sign
of 190 (total a ingresar vs. total a devolver).

Legal base: Ley 37/1992 (LIVA), Reglamento IVA (RD 1624/1992), Orden
EHA/3111/2009 (modelo 390 aprobación) modificada anualmente.
"""

from __future__ import annotations

from datetime import date

from ...i18n import Translatable
from ...models import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, Ruleset
from ._common import (
    add_op,
    casilla,
    formula,
    make_citation,
    ref,
    sub_op,
)

_EFFECTIVE_FROM = date(2025, 1, 1)
_EFFECTIVE_TO = date(2025, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


_CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "71",
        "Artículo 71 Ley 37/1992 (IVA) — obligación de presentar la "
        "declaración-resumen anual del IVA (modelo 390) cuando existe "
        "obligación de autoliquidar periódicamente.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
    ),
    make_citation(
        LegalCitationSource.ORDEN_MINISTERIAL,
        "EHA/3111/2009",
        "Orden EHA/3111/2009 — aprobación del modelo 390 y sus diseños "
        "lógicos; modificada anualmente por la correspondiente Orden "
        "del ejercicio.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2009-18554",
    ),
)


def _input(cid: str, label: Translatable) -> tuple:
    return (casilla(casilla_id=cid, label=label, computed=False),)


def _computed(cid: str, label: Translatable) -> tuple:
    return (casilla(casilla_id=cid, label=label, computed=True, legal_basis=_CITATIONS),)


_CASILLAS = (
    *_input("96", _label("Total cuotas repercutidas", "Total output VAT", "Áthárított ÁFA összesen")),
    *_input(
        "100",
        _label(
            "Total IVA soportado deducible operaciones interiores",
            "Total deductible input VAT (domestic)",
            "Levonható ÁFA belföld",
        ),
    ),
    *_input(
        "101",
        _label(
            "Total IVA soportado deducible importaciones",
            "Total deductible input VAT (imports)",
            "Levonható ÁFA import",
        ),
    ),
    *_computed(
        "104",
        _label(
            "Total IVA soportado deducible",
            "Total deductible input VAT",
            "Összes levonható ÁFA",
        ),
    ),
    *_computed(
        "105",
        _label(
            "Resultado régimen general",
            "Result (general regime)",
            "Általános rendszer eredménye",
        ),
    ),
    *_input(
        "108",
        _label(
            "Resultado régimen simplificado",
            "Result (simplified regime)",
            "Egyszerűsített rendszer eredménye",
        ),
    ),
    *_input(
        "109",
        _label(
            "Resultado otros regímenes",
            "Result (other regimes)",
            "Egyéb rendszerek eredménye",
        ),
    ),
    *_computed(
        "190",
        _label("Suma resultado", "Result sum", "Eredmény összege"),
    ),
)


_FORMULAS = (
    formula(
        casilla_id="104",
        formula_id="modelo_390.2025.iva_soportado_total",
        body=add_op(ref("100"), ref("101")),
    ),
    formula(
        casilla_id="105",
        formula_id="modelo_390.2025.resultado_regimen_general",
        body=sub_op(ref("96"), ref("104")),
    ),
    formula(
        casilla_id="190",
        formula_id="modelo_390.2025.suma_resultado",
        body=add_op(ref("105"), ref("108"), ref("109")),
    ),
)


# Modelo 390 is a pure aggregator — every rate applied to the base
# imponible lives in the quarterly 303 ruleset (where `iva.rate_general`,
# `iva.rate_reducido`, etc. are stored). 390 sums pre-computed cuotas
# rather than applying rates, so its ParameterTable is empty by design
# (wave 42 M2 — documented rather than silent).
_PARAMETERS = ParameterTable(entries={})


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_390.2025",
    modelo=ModeloCode.MODELO_390,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
