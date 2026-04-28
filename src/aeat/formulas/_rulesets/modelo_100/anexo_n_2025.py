"""Modelo 100 Anexo N — deducciones autonomicas (ejercicio 2025).

LIRPF art. 46 bis articulates the cesion de competencias normativas en
materia de IRPF entre el Estado y las Comunidades Autonomas: cada CCAA
puede establecer deducciones aplicables sobre la cuota integra
autonomica (LIRPF art. 73-77). The per-CCAA deduction inventory varies
substantially:

- Andalucia ~16 deducciones; Aragon ~19; Asturias ~27; Illes Balears
  ~26; Canarias ~29; Cantabria ~21; Castilla-La Mancha ~27; Castilla y
  Leon ~18; Cataluna ~13; Comunitat Valenciana ~41; Extremadura ~19;
  Galicia ~25; Madrid ~23; Murcia ~28; La Rioja ~24.

The DSL has no conditional operator, so the per-CCAA deductions are
modeled as **15 caller-supplied aggregate-deduction casillas** — one
per ordinary CCAA. The caller computes the per-deduction sub-totals per
CCAA per the AEAT manual practico tabla y suplementa LIRPF art. 46 bis,
aggregates them into the relevant CCAA casilla, and leaves the other 14
zero. Only ONE CCAA casilla is non-zero in any real filing.

**Casilla numbering rationale (1101-1115)**: the BOE-published M100
casilla space tops out around the 0900s for autonomic deductions; the
1101-1115 range sits ABOVE that range and is project-internal (not
reflected on the AEAT printed form). This avoids collision with any
official BOE casilla. The autonomic-deduction breakdown that AEAT
prints uses per-CCAA per-deduction casilla IDs in the 0700-0900 range
that vary per Comunidad — modeling those exhaustively would require
~336 casillas/year (per the rule-delta reference manifest's per-CCAA
count summary) and is deferred to a follow-up wave; this aggregate
shape is the minimum viable encoding for cross-anexo arithmetic.

The state-level casilla 0622 (deducciones autonomicas total, consumed
by Anexo G via 0630 = 0620 + 0622) is computed here as the sum of all
15 per-CCAA aggregates. Pais Vasco / Navarra are out of scope (foral
regimes, separate Norma Foral / Decreto Foral Legislativo per #424).

Stable structurally across 2024 / 2025 / 2026 — only the per-deduction
amounts and per-CCAA Ley de Presupuestos vary yearly. For 2026 only
Andalucia has published its Ley 8/2025 PGCA 2026 at retrieval
2026-04-27; the other 14 CCAAs use 2025 amounts as the conservative
baseline pending each Comunidad's 2026 publication.
"""

from __future__ import annotations

from datetime import date

from ....i18n import Translatable
from ....models import LegalCitationSource
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
EFFECTIVE_TO = date(2025, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "46-bis",
        "Articulo 46 bis Ley 35/2006 (IRPF) — concepto de la base "
        "liquidable autonomica y cesion de competencias normativas a "
        "las Comunidades Autonomas (en relacion con la Ley 22/2009 de "
        "cesion de tributos): cada CCAA puede establecer deducciones "
        "aplicables sobre la cuota integra autonomica que minoran la "
        "cuota liquida autonomica (art. 77).",
        url=LIRPF_CONSULT_2026_02_28_URL,
        retrieval_date=M100_RETRIEVAL_DATE,
    ),
    make_citation(
        LegalCitationSource.MANUAL_PRACTICO,
        "renta-2025-parte-2",
        "AEAT Manual Practico Renta 2025 — Parte 2 Deducciones "
        "autonomicas: catalogo completo per-CCAA con importes, topes, "
        "y normativas aplicables (Decretos Legislativos / Leyes de "
        "Medidas Fiscales / Leyes de Presupuestos vigentes para el "
        "ejercicio).",
        url="https://sede.agenciatributaria.gob.es/Sede/Ayuda/25Manual/100/deducciones-autonomicas.html",
        retrieval_date=M100_RETRIEVAL_DATE,
    ),
)


_CCAA_LABELS = (
    ("1101", "Andalucia", "Andalusia", "Andaluzia"),
    ("1102", "Aragon", "Aragon", "Aragonia"),
    ("1103", "Principado de Asturias", "Asturias", "Asztur Hercegseg"),
    ("1104", "Illes Balears", "Balearic Islands", "Baleari-szigetek"),
    ("1105", "Canarias", "Canary Islands", "Kanari-szigetek"),
    ("1106", "Cantabria", "Cantabria", "Kantabria"),
    ("1107", "Castilla-La Mancha", "Castile-La Mancha", "Kasztilia-La Mancha"),
    ("1108", "Castilla y Leon", "Castile and Leon", "Kasztilia es Leon"),
    ("1109", "Cataluna", "Catalonia", "Katalonia"),
    ("1110", "Comunitat Valenciana", "Valencian Community", "Valenciai kozosseg"),
    ("1111", "Extremadura", "Extremadura", "Extremadura"),
    ("1112", "Galicia", "Galicia", "Galicia"),
    ("1113", "Comunidad de Madrid", "Madrid Community", "Madridi kozosseg"),
    ("1114", "Region de Murcia", "Murcia Region", "Murcia regio"),
    ("1115", "La Rioja", "La Rioja", "La Rioja"),
)


CASILLAS = (
    *(
        casilla(
            casilla_id=cid,
            label=_label(
                f"Total deducciones autonomicas — {label_es}",
                f"Total autonomic deductions — {label_en}",
                f"Autonom levonasok osszesen — {label_hu}",
            ),
            computed=False,
            legal_basis=(CITATIONS[1],),
            notes_es=(
                f"Caller-aggregate de las deducciones autonomicas vigentes "
                f"para {label_es} en el ejercicio. Solo una de las 15 "
                "casillas (1101-1115) deberia ser no-cero por declaracion, "
                "correspondiente a la CCAA de residencia habitual del "
                "contribuyente. Las restantes permanecen en 0,00."
            ),
        )
        for cid, label_es, label_en, label_hu in _CCAA_LABELS
    ),
    casilla(
        casilla_id="0622",
        label=_label(
            "Total deducciones autonomicas (suma per-CCAA)",
            "Total autonomic deductions (sum across 15 CCAAs)",
            "Osszes autonom levonas (15 CCAA osszege)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0],),
    ),
)


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


PARAMETERS = ParameterTable(entries={})


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]
