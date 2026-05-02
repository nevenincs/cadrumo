"""Define the Modelo 100 Anexo E ruleset for 2025 capital gains and losses.

LIRPF arts. 33-39 cover ganancias y pérdidas patrimoniales (capital
gains and losses). The integration split per LIRPF art. 49:

- Held <= 1 year -> base imponible general (Anexo F casilla 0399).
- Held > 1 year  -> base imponible ahorro (Anexo F casilla 0400).

This ruleset verifies only the aggregate saldo (``0405 = ganancias -
pérdidas``). The general/ahorro split is caller-supplied via casillas
0399 and 0400 because the holding-period classification is
per-transacción metadata that lives outside the formula layer: the
caller iterates transmisiones, applies the LIRPF art. 37 FIFO rule on
acciones, computes the per-transaction holding period, and aggregates
into the two integration buckets.

Stable across the 2024, 2025, and 2026 ejercicios — LIRPF arts. 33-39
are unchanged in the consolidated BOE text. Sibling rulesets re-export
the 2025 :data:`CASILLAS` and :data:`CITATIONS` to inherit the same
casilla surface.
"""

from __future__ import annotations

from datetime import date

from .....core.i18n import Translatable
from ..._ruleset import ParameterTable
from .._common import (
    casilla,
    formula,
    ref,
    sub_op,
)
from ._common import cite_lirpf

EFFECTIVE_FROM = date(2025, 1, 1)
"""First day of the ejercicio in which this Anexo E ruleset applies."""

EFFECTIVE_TO = date(2025, 12, 31)
"""Last day of the ejercicio in which this Anexo E ruleset applies."""


def _label(es: str, en: str, hu: str) -> Translatable:
    """Return a :class:`aeat.core.i18n.Translatable` mapping for label texts."""
    return {"es": es, "en": en, "hu": hu}


CITATIONS = (
    cite_lirpf(
        "33",
        "Artículo 33 Ley 35/2006 (IRPF) — concepto de ganancias y "
        "pérdidas patrimoniales: variaciones en el valor del patrimonio "
        "del contribuyente que se pongan de manifiesto con ocasión de "
        "cualquier alteración en su composición, salvo que se califiquen "
        "como rendimientos.",
    ),
    cite_lirpf(
        "37",
        "Artículo 37 Ley 35/2006 (IRPF) — normas específicas de "
        "valoración: regla FIFO para transmisiones de valores cotizados "
        "y participaciones (apartado 2). Soporta el cálculo per-transacción "
        "de la ganancia / pérdida patrimonial.",
    ),
    cite_lirpf(
        "49",
        "Artículo 49 Ley 35/2006 (IRPF) — integración y compensación "
        "de rentas en la base imponible del ahorro: las ganancias y "
        "pérdidas patrimoniales con período de generación superior a un "
        "año se integran en base ahorro; las restantes en base general.",
    ),
)
"""LIRPF citations underpinning the Anexo E saldo neto patrimonial."""


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
            "Pérdidas patrimoniales brutas",
            "Gross capital losses (Anexo E)",
            "Brutto vagyonveszteseg",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0399",
        label=_label(
            "Saldo a integrar en base general (<= 1 año)",
            "Net amount integrating into general base (held <= 1 yr)",
            "Altalanos alapba szamitando egyenleg (<= 1 ev)",
        ),
        computed=False,
        legal_basis=(CITATIONS[2],),
        notes_es=(
            "Caller-computed: net of ganancias - pérdidas con período "
            "de generación <= 1 año. Puede ser negativo (pérdida neta)."
        ),
    ),
    casilla(
        casilla_id="0400",
        label=_label(
            "Saldo a integrar en base ahorro (> 1 año)",
            "Net amount integrating into savings base (held > 1 yr)",
            "Megtakaritasi alapba szamitando egyenleg (> 1 ev)",
        ),
        computed=False,
        legal_basis=(CITATIONS[2],),
        notes_es=(
            "Caller-computed: net of ganancias - pérdidas con período de generación > 1 año. Puede ser negativo."
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
"""Casilla declarations exposed by the Anexo E ruleset."""


FORMULAS = (
    formula(
        casilla_id="0405",
        formula_id="modelo_100.2025.e.saldo_neto_patrimonial",
        body=sub_op(ref("0306"), ref("0307")),
    ),
)
"""Engine formula bindings for the Anexo E computed casillas."""


PARAMETERS = ParameterTable(entries={})
"""Anexo E declares no parametric tables."""


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]
