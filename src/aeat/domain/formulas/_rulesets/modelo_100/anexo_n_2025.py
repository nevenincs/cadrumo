"""Define the Modelo 100 Anexo N ruleset for 2025 deducciones autonómicas.

LIRPF art. 46 bis articulates the cesión de competencias normativas en
materia de IRPF between the Estado and the Comunidades Autónomas: each
CCAA may establish deductions applicable to the cuota íntegra
autonómica (LIRPF arts. 73-77). The per-CCAA deduction inventory
varies substantially:

- Andalucía ~16, Aragón ~19, Asturias ~27, Illes Balears ~26, Canarias
  ~29, Cantabria ~21, Castilla-La Mancha ~27, Castilla y León ~18,
  Cataluña ~13, Comunitat Valenciana ~41, Extremadura ~19, Galicia
  ~25, Madrid ~23, Murcia ~28, La Rioja ~24.

The DSL has no conditional operator, so the per-CCAA deductions are
modelled as fifteen caller-supplied aggregate-deduction casillas — one
per ordinary CCAA. The caller computes the per-deduction sub-totals
following the AEAT manual práctico tabla complementing LIRPF art. 46
bis, aggregates them into the relevant CCAA casilla, and leaves the
other fourteen at zero. Only one CCAA casilla is non-zero in any real
filing.

**Casilla numbering rationale (1101-1115)**: the BOE-published M100
casilla space tops out around the 0900s for autonomic deductions; the
1101-1115 range sits above that range and is project-internal (not
reflected on the AEAT printed form), which avoids collision with any
official BOE casilla. The per-CCAA per-deduction casilla IDs that AEAT
prints sit in the 0700-0900 range and vary per Comunidad — modelling
them exhaustively would require ~336 casillas per year, so this
aggregate shape is the minimum viable encoding for cross-anexo
arithmetic.

The state-level casilla 0622 (deducciones autonómicas total, consumed
by :mod:`aeat.domain.formulas._rulesets.modelo_100.anexo_g_2025` via
``0630 = 0620 + 0622``) is computed here as the sum of all fifteen
per-CCAA aggregates. País Vasco and Navarra are out of scope (foral
regimes use separate Norma Foral / Decreto Foral Legislativo
rulesets).

Stable structurally across the 2024, 2025, and 2026 ejercicios — only
the per-deduction amounts and per-CCAA Ley de Presupuestos vary
yearly. For 2026 only Andalucía has published its Ley 8/2025 PGCA
2026; the other fourteen CCAAs use 2025 amounts as the conservative
baseline pending each Comunidad's 2026 publication.
"""

from __future__ import annotations

from datetime import date

from .....core.i18n import Translatable
from ....modelos import LegalCitationSource
from ..._ruleset import ParameterTable
from .._common import (
    add_op,
    casilla,
    formula,
    make_citation,
    ref,
)
from ._common import LIRPF_CONSULT_2026_02_28_URL, M100_RETRIEVAL_DATE

EFFECTIVE_FROM = date(2025, 1, 1)
"""First day of the ejercicio in which this Anexo N ruleset applies."""

EFFECTIVE_TO = date(2025, 12, 31)
"""Last day of the ejercicio in which this Anexo N ruleset applies."""


def _label(es: str, en: str, hu: str) -> Translatable:
    """Return a :class:`aeat.core.i18n.Translatable` mapping for label texts."""
    return {"es": es, "en": en, "hu": hu}


CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "46-bis",
        "Artículo 46 bis Ley 35/2006 (IRPF) — concepto de la base "
        "liquidable autonómica y cesión de competencias normativas a "
        "las Comunidades Autónomas (en relación con la Ley 22/2009 de "
        "cesión de tributos): cada CCAA puede establecer deducciones "
        "aplicables sobre la cuota íntegra autonómica que minoran la "
        "cuota líquida autonómica (art. 77).",
        url=LIRPF_CONSULT_2026_02_28_URL,
        retrieval_date=M100_RETRIEVAL_DATE,
    ),
    make_citation(
        LegalCitationSource.MANUAL_PRACTICO,
        "renta-2025-parte-2",
        "AEAT Manual Práctico Renta 2025 — Parte 2 Deducciones "
        "autonómicas: catálogo completo per-CCAA con importes, topes, "
        "y normativas aplicables (Decretos Legislativos / Leyes de "
        "Medidas Fiscales / Leyes de Presupuestos vigentes para el "
        "ejercicio).",
        url="https://sede.agenciatributaria.gob.es/Sede/Ayuda/25Manual/100/deducciones-autonomicas.html",
        retrieval_date=M100_RETRIEVAL_DATE,
    ),
)
"""Citations underpinning the Anexo N deducciones autonómicas surface."""


_CCAA_LABELS = (
    ("1101", "Andalucía", "Andalusia", "Andaluzia"),
    ("1102", "Aragón", "Aragon", "Aragonia"),
    ("1103", "Principado de Asturias", "Asturias", "Asztur Hercegseg"),
    ("1104", "Illes Balears", "Balearic Islands", "Baleari-szigetek"),
    ("1105", "Canarias", "Canary Islands", "Kanari-szigetek"),
    ("1106", "Cantabria", "Cantabria", "Kantabria"),
    ("1107", "Castilla-La Mancha", "Castile-La Mancha", "Kasztilia-La Mancha"),
    ("1108", "Castilla y León", "Castile and Leon", "Kasztilia es Leon"),
    ("1109", "Cataluña", "Catalonia", "Katalonia"),
    ("1110", "Comunitat Valenciana", "Valencian Community", "Valenciai kozosseg"),
    ("1111", "Extremadura", "Extremadura", "Extremadura"),
    ("1112", "Galicia", "Galicia", "Galicia"),
    ("1113", "Comunidad de Madrid", "Madrid Community", "Madridi kozosseg"),
    ("1114", "Región de Murcia", "Murcia Region", "Murcia regio"),
    ("1115", "La Rioja", "La Rioja", "La Rioja"),
)


CASILLAS = (
    *(
        casilla(
            casilla_id=cid,
            label=_label(
                f"Total deducciones autonómicas — {label_es}",
                f"Total autonomic deductions — {label_en}",
                f"Autonom levonasok osszesen — {label_hu}",
            ),
            computed=False,
            legal_basis=(CITATIONS[1],),
            notes_es=(
                f"Sumatorio agregado por el consumidor de las deducciones "
                f"autonómicas vigentes para {label_es} en el ejercicio. "
                "Solo una de las 15 casillas (1101-1115) debería ser "
                "distinta de cero por declaración, correspondiente a la "
                "CCAA de residencia habitual del contribuyente. Las "
                "restantes permanecen en 0,00."
            ),
        )
        for cid, label_es, label_en, label_hu in _CCAA_LABELS
    ),
    casilla(
        casilla_id="0622",
        label=_label(
            "Total deducciones autonómicas (suma per-CCAA)",
            "Total autonomic deductions (sum across 15 CCAAs)",
            "Osszes autonom levonas (15 CCAA osszege)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0],),
    ),
)
"""Casilla declarations exposed by the Anexo N ruleset.

Includes one input casilla per CCAA (1101-1115) and the computed
state-level aggregate :data:`casilla 0622`.
"""


# 0622 = add_op over 15 per-CCAA aggregate-deduction casillas. Folded
# into pair-wise add_op nesting since add_op is variadic with min_length=2.
_CCAA_REFS = tuple(ref(cid) for cid, *_ in _CCAA_LABELS)
_TOTAL_AUTONOMICAS_BODY = add_op(*_CCAA_REFS)


FORMULAS = (
    formula(
        casilla_id="0622",
        formula_id="modelo_100.2025.n.total_deducciones_autonomicas",
        body=_TOTAL_AUTONOMICAS_BODY,
    ),
)
"""Engine formula bindings for the 2025 Anexo N computed casillas."""


PARAMETERS = ParameterTable(entries={})
"""Anexo N declares no parametric tables."""


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]
