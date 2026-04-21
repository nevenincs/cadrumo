"""Modelo 202 ruleset covering the full 2025 fiscal year.

Modelo 202 is the IS / IRNR-EP instalment filing — 1P / 2P / 3P
(April, October, December). MVP covers the liquidación block that
Kent's filing must satisfy on every period:

- casilla 18 = casilla 16 x (casilla 17 / 100) (cuota integra = base
  x tipo, under modalidad art. 40.3 LIS — running current-year base).
  AEAT prints casilla 17 as the whole-percent value (``17,00`` ⇒ 17%);
  the ``/ 100`` normalisation happens in the formula so the ruleset
  can be applied directly to raw PDF-extracted values without
  pre-processing (wave 33 H1 fix).
- casilla 32 = 18 - 27 - 28 - 30 (resultado — cuota integra menos
  bonificaciones, retenciones e ingresos a cuenta, pagos fraccionados
  anteriores).
- casilla 34 = max(32, 33) (cantidad a ingresar — el mayor entre el
  resultado y el mínimo a ingresar art. 40.3 LIS párr. 2).

Modalidad art. 40.2 (prior-year cuota) uses a different formula chain
and lands in sub-EPIC #305-Modelo-202-full.

Legal base: Orden HFP/227/2017 (BOE-A-2017-2778); refreshed by
HFP/312/2023 and HAC/262/2025 (BOE-A-2025-5407) — the 2025 Orden
introduced the micropyme / pyme rate boxes relevant to casilla 17.
"""

from __future__ import annotations

from datetime import date

from ...i18n import Translatable
from ...models import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, Ruleset
from ._common import (
    casilla,
    formula,
    make_citation,
    max_op,
    percent_from_whole,
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
        "40",
        "Artículo 40 Ley 27/2014 (LIS) — pagos fraccionados del "
        "Impuesto sobre Sociedades; modalidad 40.2 (sobre cuota "
        "íntegra del último período declarado) y 40.3 (sobre la base "
        "imponible del período corriente con el tipo del 17%, ajustado "
        "por las disposiciones transitorias).",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328",
    ),
    make_citation(
        LegalCitationSource.ORDEN_MINISTERIAL,
        "HFP/227/2017",
        "Orden HFP/227/2017 (BOE-A-2017-2778) — aprobación del modelo 202 y sus diseños de registro.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2017-2778",
    ),
    make_citation(
        LegalCitationSource.ORDEN_MINISTERIAL,
        "HAC/262/2025",
        "Orden HAC/262/2025 (BOE-A-2025-5407) — actualización de los "
        "modelos 202 y 222 para ejercicio 2025; introduce las casillas "
        "de los tipos reducidos para microempresas (17%) y pequeñas "
        "empresas (20-21%).",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2025-5407",
    ),
)


_CASILLAS = (
    casilla(
        casilla_id="16",
        label=_label("Base del pago fraccionado", "Instalment base", "Részletfizetés alapja"),
        computed=False,
    ),
    casilla(
        casilla_id="17",
        label=_label("Tipo de gravamen aplicable", "Applicable rate", "Alkalmazandó kulcs"),
        computed=False,
    ),
    casilla(
        casilla_id="18",
        label=_label("Cuota integra", "Gross tax amount", "Bruttó adóösszeg"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="27",
        label=_label("Bonificaciones", "Rebates", "Kedvezmények"),
        computed=False,
    ),
    casilla(
        casilla_id="28",
        label=_label(
            "Retenciones e ingresos a cuenta",
            "Withholdings and payments on account",
            "Levonások és előlegek",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="30",
        label=_label(
            "Pagos fraccionados anteriores del ejercicio",
            "Prior instalments of the period",
            "Korábbi részletek az időszakból",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="32",
        label=_label("Resultado", "Net result", "Nettó eredmény"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="33",
        label=_label("Minimo a ingresar", "Minimum payable", "Minimális fizetendő"),
        computed=False,
    ),
    casilla(
        casilla_id="34",
        label=_label("Cantidad a ingresar", "Amount payable", "Fizetendő összeg"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
)


_FORMULAS = (
    formula(
        casilla_id="18",
        formula_id="modelo_202.2025.cuota_integra",
        # Normalise casilla 17 from whole-percent (17,00) to fraction (0,17).
        body=percent_from_whole(ref("17"), ref("16")),
    ),
    formula(
        casilla_id="32",
        formula_id="modelo_202.2025.resultado",
        body=sub_op(
            sub_op(sub_op(ref("18"), ref("27")), ref("28")),
            ref("30"),
        ),
    ),
    formula(
        casilla_id="34",
        formula_id="modelo_202.2025.cantidad_a_ingresar",
        body=max_op(ref("32"), ref("33")),
    ),
)


_PARAMETERS = ParameterTable(entries={})


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_202.2025",
    modelo=ModeloCode.MODELO_202,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
