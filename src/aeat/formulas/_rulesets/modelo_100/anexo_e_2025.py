"""Modelo 100 Anexo E — ganancias y perdidas patrimoniales (ejercicio 2025).

LIRPF arts. 33-39 cover ganancias y perdidas patrimoniales (capital
gains and losses). The integration split per LIRPF art. 49:

- Held <= 1 year -> base imponible general (Anexo F casilla 0399).
- Held > 1 year   -> base imponible ahorro (Anexo F casilla 0400).

This ruleset verifies the aggregate saldo (0405 = ganancias - perdidas).
The general/ahorro split is caller-supplied via 0399 + 0400 since the
holding-period classification is per-transaccion metadata that lives
outside the formula layer (caller iterates transmisiones, applies
LIRPF art. 37 FIFO regla on acciones, computes the per-transaction
holding period, and aggregates into the two integration buckets).

Stable across 2024 / 2025 / 2026 (LIRPF arts. 33-39 unchanged at BOE
consolidated text consult 2026-02-28).
"""

from __future__ import annotations

from datetime import date

from ....i18n import Translatable
from ..._ruleset import ParameterTable
from .._common import (
    casilla,
    formula,
    ref,
    sub_op,
)
from ._common import cite_lirpf

EFFECTIVE_FROM = date(2025, 1, 1)
EFFECTIVE_TO = date(2025, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


CITATIONS = (
    cite_lirpf(
        "33",
        "Articulo 33 Ley 35/2006 (IRPF) — concepto de ganancias y "
        "perdidas patrimoniales: variaciones en el valor del patrimonio "
        "del contribuyente que se pongan de manifiesto con ocasion de "
        "cualquier alteracion en su composicion, salvo que se califiquen "
        "como rendimientos.",
    ),
    cite_lirpf(
        "37",
        "Articulo 37 Ley 35/2006 (IRPF) — normas especificas de "
        "valoracion: regla FIFO para transmisiones de valores cotizados "
        "y participaciones (apartado 2). Soporta el calculo per-transaccion "
        "de la ganancia / perdida patrimonial.",
    ),
    cite_lirpf(
        "49",
        "Articulo 49 Ley 35/2006 (IRPF) — integracion y compensacion "
        "de rentas en la base imponible del ahorro: las ganancias y "
        "perdidas patrimoniales con periodo de generacion superior a un "
        "ano se integran en base ahorro; las restantes en base general.",
    ),
)


CASILLAS = (
    casilla(
        casilla_id="0306",
        label=_label(
            "Ganancias patrimoniales brutas",
            "Gross capital gains (Anexo E)",
            "Brutto vagyongyarapodas",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0307",
        label=_label(
            "Perdidas patrimoniales brutas",
            "Gross capital losses (Anexo E)",
            "Brutto vagyonveszteseg",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0399",
        label=_label(
            "Saldo a integrar en base general (<= 1 ano)",
            "Net amount integrating into general base (held <= 1 yr)",
            "Altalanos alapba szamitando egyenleg (<= 1 ev)",
        ),
        computed=False,
        legal_basis=(CITATIONS[2],),
        notes_es=(
            "Caller-computed: net of ganancias - perdidas con periodo "
            "de generacion <= 1 ano. Puede ser negativo (perdida neta)."
        ),
    ),
    casilla(
        casilla_id="0400",
        label=_label(
            "Saldo a integrar en base ahorro (> 1 ano)",
            "Net amount integrating into savings base (held > 1 yr)",
            "Megtakaritasi alapba szamitando egyenleg (> 1 ev)",
        ),
        computed=False,
        legal_basis=(CITATIONS[2],),
        notes_es=(
            "Caller-computed: net of ganancias - perdidas con periodo de generacion > 1 ano. Puede ser negativo."
        ),
    ),
    casilla(
        casilla_id="0405",
        label=_label(
            "Saldo neto patrimonial total",
            "Total net capital gain/loss",
            "Teljes netto vagyon vagy veszteseg",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[1]),
    ),
)


FORMULAS = (
    formula(
        casilla_id="0405",
        formula_id="modelo_100.2025.e.saldo_neto_patrimonial",
        body=sub_op(ref("0306"), ref("0307")),
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
