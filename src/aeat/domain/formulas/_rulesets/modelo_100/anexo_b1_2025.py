"""Modelo 100 Anexo B1 — rendimientos del trabajo (ejercicio 2025).

Anexo B1 covers the rendimientos del trabajo block of the RENTA
declaración. The numerical surface is anchored to LIRPF arts. 17-20
(definición, reducción art. 18 30 % rendimientos irregulares, gastos
deducibles art. 19, reducción por obtención de rendimientos del
trabajo art. 20 — modificada por RD-Ley 4/2024).

For ejercicio 2025 the LIRPF art. 20 reducción thresholds are stable
relative to ejercicio 2024 (RD-Ley 4/2024 set them at 14.852 /
17.673,52 / 19.747,50 € with max reducción 7.302 €; no posterior law
modified those values for 2025).

The DSL encodes art. 20 as a two-piece linear function via
``max_op(piece_a, piece_b)``:

- piece_a covers rendimiento <= 17.673,52 with slope 1,75 from
  reducción 7.302 € at 14.852 € down through 2.364,34 € at 17.673,52 €.
- piece_b covers rendimiento >= 17.673,52 with slope 1,14 from
  reducción 2.364,34 € at 17.673,52 € down to ~0 at 19.747,50 €.
- ``max_op`` selects the active piece at any rendimiento level.
- ``clamp_pos`` zeroes out the negative tails so the piecewise
  function reaches 0 above 19.747,50 €.

This module exports ``CASILLAS``, ``FORMULAS`` and ``PARAMETERS`` for
the parent-level aggregator (``modelo_100_2025.py``) to compose into
the public ``RULESET``.
"""

from __future__ import annotations

from datetime import date

from .....core.i18n import Translatable
from ..._ruleset import ParameterTable
from .._common import (
    casilla,
    clamp_pos,
    formula,
    lit,
    max_op,
    min_op,
    mul_op,
    ref,
    sub_op,
)
from ._common import cite_lirpf

EFFECTIVE_FROM = date(2025, 1, 1)
EFFECTIVE_TO = date(2025, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    """Build a multilingual label dict for a casilla in this anexo."""
    return {"es": es, "en": en, "hu": hu}


CITATIONS = (
    cite_lirpf(
        "17",
        "Artículo 17 Ley 35/2006 (IRPF) — definición de rendimientos "
        "íntegros del trabajo: sueldos, salarios, prestaciones por "
        "desempleo, pensiones, retribuciones a administradores, becas y "
        "demás contraprestaciones derivadas del trabajo personal y de "
        "la relación laboral o estatutaria.",
    ),
    cite_lirpf(
        "18",
        "Artículo 18 Ley 35/2006 (IRPF) — porcentajes de reducción "
        "aplicables a determinados rendimientos del trabajo (30% sobre "
        "rendimientos irregulares con período de generación superior a "
        "dos años, con límite cuantitativo de 300.000 €).",
    ),
    cite_lirpf(
        "19",
        "Artículo 19 Ley 35/2006 (IRPF) — gastos deducibles del "
        "rendimiento del trabajo: cotizaciones a la Seguridad Social y "
        "a mutualidades obligatorias, detracciones por derechos pasivos, "
        "cotizaciones a colegios de huérfanos, cuotas satisfechas a "
        "sindicatos y colegios profesionales, gastos de defensa "
        "jurídica, suplemento de 2.000 € por otros gastos, suplemento "
        "por movilidad geográfica.",
    ),
    cite_lirpf(
        "20",
        "Artículo 20 Ley 35/2006 (IRPF) — reducción por obtención de "
        "rendimientos del trabajo. Modificado por Real Decreto-Ley "
        "4/2024 con efectos 1/1/2024: reducción de 7.302 € para "
        "rendimientos netos previos ≤ 14.852 €; tramo decreciente con "
        "pendiente 1,75 hasta 17.673,52 € (donde alcanza 2.364,34 €); "
        "segundo tramo decreciente con pendiente 1,14 hasta 19.747,50 € "
        "(donde alcanza 0); rendimientos > 19.747,50 € no se benefician "
        "de la reducción. Requisito común: otras rentas (excluidas "
        "exentas) ≤ 6.500 €.",
    ),
)


CASILLAS = (
    casilla(
        casilla_id="0001",
        label=_label(
            "Ingresos íntegros rendimientos del trabajo",
            "Gross work income (Anexo B1)",
            "Munkajövedelem bruttó (B1 melléklet)",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
        notes_es=(
            "Suma de sueldos, salarios, pensiones, prestaciones de "
            "desempleo, retribuciones a administradores y demás "
            "rendimientos del trabajo definidos por LIRPF art. 17."
        ),
    ),
    casilla(
        casilla_id="0008",
        label=_label(
            "Gasto deducible cotización Seguridad Social",
            "Social Security contributions (deductible)",
            "Társadalombiztosítási járulék (levonható)",
        ),
        computed=False,
        legal_basis=(CITATIONS[2],),
    ),
    casilla(
        casilla_id="0009",
        label=_label(
            "Otros gastos deducibles del trabajo",
            "Other deductible work expenses",
            "Egyéb levonható munkajövedelem-költségek",
        ),
        computed=False,
        legal_basis=(CITATIONS[2],),
        notes_es=("Cuotas colegiales, sindicatos, defensa jurídica, suplemento 2.000 € art. 19.2 LIRPF."),
    ),
    casilla(
        casilla_id="0010",
        label=_label(
            "Gasto adicional movilidad geográfica",
            "Geographic mobility expense",
            "Földrajzi mobilitási költség",
        ),
        computed=False,
        legal_basis=(CITATIONS[2],),
    ),
    casilla(
        casilla_id="0019",
        label=_label(
            "Reducción art. 18 — rendimientos irregulares",
            "Art. 18 reduction (irregular earnings)",
            "18. cikk csökkentés (rendszertelen jövedelem)",
        ),
        computed=False,
        legal_basis=(CITATIONS[1],),
        notes_es=(
            "Importe ya minorado por el 30% del art. 18.2 sobre la base "
            "irregular, con un límite cuantitativo de 300.000 €."
        ),
    ),
    casilla(
        casilla_id="0020",
        label=_label(
            "Rendimiento neto previo del trabajo",
            "Net work income before art. 20 reduction",
            "Bruttó munkajövedelem az art. 20 csökkentés előtt",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[1], CITATIONS[2]),
    ),
    casilla(
        casilla_id="0021",
        label=_label(
            "Reducción art. 20 rendimientos del trabajo",
            "Art. 20 reduction (work-income obtention)",
            "20. cikk csökkentés (munkajövedelem szerzés)",
        ),
        computed=True,
        legal_basis=(CITATIONS[3],),
    ),
    casilla(
        casilla_id="0022",
        label=_label(
            "Rendimiento neto reducido del trabajo",
            "Net work income (reduced)",
            "Nettó munkajövedelem (csökkentett)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[3]),
    ),
)


# Art. 20 piecewise constants (RD-Ley 4/2024 vigent 2024-2026):
#   piece_a: reducción = clamp_pos(7302 - 1.75 * clamp_pos(rendimiento - 14852))
#   piece_b: reducción = clamp_pos(2364.34 - 1.14 * clamp_pos(rendimiento - 17673.52))
# The active piece at any rendimiento level is max_op(piece_a, piece_b);
# clamp_pos zeroes the negative extrapolation tails. The outer min_op
# caps the reducción at the actual rendimiento previo (0020) — LIRPF
# art. 20 only applies "a los contribuyentes que obtengan rendimientos
# integros del trabajo" with the implicit precondition rendimiento > 0;
# without the cap the engine would emit 7.302 EUR even on a zero filing
# (per the codex code-review M-1 finding).
#
# Verified piecewise:
#   rendimiento = 0       → min(0, max(7302,...)) = 0 (cap protects)
#   rendimiento = 5000    → min(5000, 7302) = 5000 (cap protects)
#   rendimiento = 14852   → min(14852, 7302) = 7302 (piece_a active, uncapped)
#   rendimiento = 17673.52 → 2364.34 (both pieces give 2364.34)
#   rendimiento = 18000   → 1992.15 (piece_b active)
#   rendimiento = 19747.50 → 0 (both pieces give ≤ 0 → clamp_pos = 0)
#   rendimiento ≥ 19747.50 → 0 (both pieces give ≤ 0 → clamp_pos = 0)
_REDUCCION_ART20_BODY = min_op(
    ref("0020"),
    max_op(
        clamp_pos(
            sub_op(
                lit("7302.00"),
                mul_op(
                    lit("1.75"),
                    clamp_pos(sub_op(ref("0020"), lit("14852.00"))),
                ),
            ),
        ),
        clamp_pos(
            sub_op(
                lit("2364.34"),
                mul_op(
                    lit("1.14"),
                    clamp_pos(sub_op(ref("0020"), lit("17673.52"))),
                ),
            ),
        ),
    ),
)


FORMULAS = (
    formula(
        casilla_id="0020",
        formula_id="modelo_100.2025.b1.rendimiento_neto_previo",
        body=clamp_pos(
            sub_op(
                sub_op(
                    sub_op(
                        sub_op(ref("0001"), ref("0008")),
                        ref("0009"),
                    ),
                    ref("0010"),
                ),
                ref("0019"),
            ),
        ),
    ),
    formula(
        casilla_id="0021",
        formula_id="modelo_100.2025.b1.reduccion_art_20",
        body=_REDUCCION_ART20_BODY,
    ),
    formula(
        casilla_id="0022",
        formula_id="modelo_100.2025.b1.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0020"), ref("0021"))),
    ),
)


# Anexo B1 carries no rate-bearing parameters — the art. 20 piecewise
# constants are encoded as Literals directly in the formula body to
# preserve cent-exact precision and keep the BOE-anchored thresholds
# self-documenting alongside the formula.
PARAMETERS = ParameterTable(entries={})


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]
