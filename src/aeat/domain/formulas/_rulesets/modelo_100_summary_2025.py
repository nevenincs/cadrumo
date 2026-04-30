"""Modelo 100 (IRPF / Renta) summary-block ruleset — año 2025 MVP.

Scope: the ~5 top-level derivations every Renta artefact's summary
prints. Full anexo coverage (A-N conditional sections, transitorias,
deducciones autonómicas by comunidad) is tracked for sub-EPIC
#305-F-full.

Derivations:

- ``0595`` (cuota íntegra total) = ``0550`` (general estatal) + ``0551``
  (general autonómica) + ``0560`` (ahorro estatal) + ``0561`` (ahorro
  autonómica).
- ``0630`` (total deducciones) = ``0620`` (estatales) + ``0622``
  (autonómicas).
- ``0698`` (cuota líquida) = ``0595`` - ``0630``, clamped ≥ 0.
- ``0720`` (cuota resultante) = ``0698`` - ``0699`` - ``0700``.
- ``0721`` (resultado a ingresar / a devolver) = ``0720`` (MVP
  equivalence — full ruleset later factors in ingresos / devoluciones
  indebidas from previous autoliquidaciones complementarias).

Parameters: no tax-rate parameters in MVP — the cuota íntegra is taken
as input from the PDF (AEAT's tarifa progresiva applies at the
base-liquidable level, out of summary-block scope).

Citations: Ley 35/2006 (IRPF) — base norma (liquidación is in
LIRPF arts. 62-80); RD 439/2007 (RIRPF) covers retenciones
(arts. 74-101) and pagos fraccionados (arts. 109-112) — NOT
liquidación. Cluster-F-full will back every derivation with a
specific article.
"""

from __future__ import annotations

from datetime import date

from ...modelos import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, Ruleset
from ._common import (
    add_op,
    casilla,
    clamp_pos,
    formula,
    make_citation,
    ref,
    sub_op,
)

_EFFECTIVE_FROM = date(2025, 1, 1)
_EFFECTIVE_TO = date(2025, 12, 31)

_CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "35/2006",
        "Ley 35/2006 IRPF — base normativa del Impuesto sobre la Renta "
        "de las Personas Físicas. Liquidación en los artículos 62-80 "
        "(art. 62 Cuota íntegra estatal; art. 66 tipos del ahorro; "
        "art. 67 Cuota líquida estatal; art. 73 Cuota íntegra "
        "autonómica; art. 77 Cuota líquida autonómica; art. 79 "
        "Cuota diferencial; art. 80 Deducción por doble imposición "
        "internacional).",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
    ),
    make_citation(
        LegalCitationSource.REAL_DECRETO,
        "439/2007",
        "RD 439/2007 Reglamento del IRPF — retenciones "
        "(art. 74-101), pagos fraccionados (art. 109-112). "
        "Wave 73a correction: prior narrative claimed RIRPF "
        "art. 67-77 covered liquidación — wrong; those are "
        "formal/registral obligations. Liquidación is a LIRPF topic.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820",
    ),
)


_CASILLAS = (
    # Cuota íntegra components (four literals → summed).
    casilla(
        casilla_id="0550",
        label={
            "es": "Cuota íntegra general estatal",
            "en": "State general tax liability",
            "hu": "Állami általános adókötelezettség",
        },
        computed=False,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="0551",
        label={
            "es": "Cuota íntegra general autonómica",
            "en": "Autonomous general tax liability",
            "hu": "Autonóm általános adókötelezettség",
        },
        computed=False,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="0560",
        label={
            "es": "Cuota íntegra del ahorro estatal",
            "en": "State savings tax liability",
            "hu": "Állami megtakarítási adókötelezettség",
        },
        computed=False,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="0561",
        label={
            "es": "Cuota íntegra del ahorro autonómica",
            "en": "Autonomous savings tax liability",
            "hu": "Autonóm megtakarítási adókötelezettség",
        },
        computed=False,
        legal_basis=_CITATIONS,
    ),
    # Cuota íntegra total — computed.
    casilla(
        casilla_id="0595",
        label={
            "es": "Cuota íntegra total",
            "en": "Total tax liability (state + autonomous)",
            "hu": "Teljes adókötelezettség (állami + autonóm)",
        },
        computed=True,
        legal_basis=_CITATIONS,
    ),
    # Deducciones — two literals summed.
    casilla(
        casilla_id="0620",
        label={
            "es": "Deducciones estatales",
            "en": "State deductions",
            "hu": "Állami levonások",
        },
        computed=False,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="0622",
        label={
            "es": "Deducciones autonómicas",
            "en": "Autonomous deductions",
            "hu": "Autonóm levonások",
        },
        computed=False,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="0630",
        label={
            "es": "Total deducciones",
            "en": "Total deductions (state + autonomous)",
            "hu": "Összes levonás (állami + autonóm)",
        },
        computed=True,
        legal_basis=_CITATIONS,
    ),
    # Cuota líquida — 0595 - 0630, clamped ≥ 0.
    casilla(
        casilla_id="0698",
        label={
            "es": "Cuota líquida total",
            "en": "Net tax liability (0595 - 0630, clamped ≥ 0)",
            "hu": "Nettó adókötelezettség (0595 - 0630, nem-negatív)",
        },
        computed=True,
        legal_basis=_CITATIONS,
    ),
    # Retenciones / pagos a cuenta.
    casilla(
        casilla_id="0699",
        label={
            "es": "Retenciones e ingresos a cuenta",
            "en": "Withholdings and prepayments",
            "hu": "Levonások és előleg befizetések",
        },
        computed=False,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="0700",
        label={
            "es": "Pagos fraccionados (Modelo 130 / 131)",
            "en": "Fractional payments (Modelo 130 / 131)",
            "hu": "Részletfizetések (130 / 131 modell)",
        },
        computed=False,
        legal_basis=_CITATIONS,
    ),
    # Resultado.
    casilla(
        casilla_id="0720",
        label={
            "es": "Cuota resultante de la autoliquidación",
            "en": "Self-assessment result",
            "hu": "Önbevallás eredménye",
        },
        computed=True,
        legal_basis=_CITATIONS,
    ),
)


_FORMULAS = (
    formula(
        casilla_id="0595",
        formula_id="modelo_100.summary.2025.cuota_integra_total",
        body=add_op(add_op(ref("0550"), ref("0551")), add_op(ref("0560"), ref("0561"))),
    ),
    formula(
        casilla_id="0630",
        formula_id="modelo_100.summary.2025.total_deducciones",
        body=add_op(ref("0620"), ref("0622")),
    ),
    formula(
        casilla_id="0698",
        formula_id="modelo_100.summary.2025.cuota_liquida",
        body=clamp_pos(sub_op(ref("0595"), ref("0630"))),
    ),
    formula(
        casilla_id="0720",
        formula_id="modelo_100.summary.2025.cuota_resultante",
        body=sub_op(sub_op(ref("0698"), ref("0699")), ref("0700")),
    ),
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_100.summary.2025",
    modelo=ModeloCode.MODELO_100,
    # Wave 47: explicit variant="summary" reserves the default slot
    # for the (eventual) full-form modelo_100 ruleset without a
    # registry-overlap conflict.
    variant="summary",
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=ParameterTable(entries={}),
    legal_citations=_CITATIONS,
)
