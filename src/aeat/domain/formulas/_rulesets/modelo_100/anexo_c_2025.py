"""Modelo 100 Anexo C — rendimientos del capital inmobiliario (ejercicio 2025).

Anexo C covers arrendamientos urbanos and imputación de rentas
inmobiliarias per LIRPF arts. 22-24 + 85.

The aggregation chain on M100:

- ``0106`` (rendimiento neto previo capital inmobiliario) =
  ``clamp_pos(0061 - 0066 - 0072)`` where:
    - ``0061`` = ingresos íntegros arrendamiento (caller-summed across fincas)
    - ``0066`` = gastos deducibles (financiación, IBI, comunidad, reparación)
    - ``0072`` = amortización 3 % de la construcción (LIRPF art. 23.1)
- ``0107`` (rendimiento neto reducido capital inmobiliario) =
  ``clamp_pos(0106 - 0078)`` where ``0078`` is the LIRPF art. 23.2
  reducción at the applicable tier (50 % default / 60 % rehabilitación
  reciente / 70 % zona tensionada inquilino joven / 90 % zona
  tensionada con reducción >= 5 %), caller-supplied since the tier
  selection depends on contract metadata (date of contract, zone,
  inquilino age, reducción versus prior contract).

Imputación de rentas inmobiliarias (LIRPF art. 85, casilla 0085) is a
parallel income category — caller computes 1,1 % / 2 % del valor
catastral and supplies the resulting amount; it does NOT feed into
0106 or 0107 (it lands in base imponible general directly via Anexo F).

Stable across 2024 / 2025 / 2026 — Ley 12/2023 set the tiered
reducción art. 23.2 with effects on contracts celebrados desde
26/5/2023; the framework is unchanged at BOE consolidated text consult
2026-02-28.
"""

from __future__ import annotations

from datetime import date

from .....core.i18n import Translatable
from ..._ruleset import ParameterTable
from .._common import (
    casilla,
    clamp_pos,
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
        "22",
        "Artículo 22 Ley 35/2006 (IRPF) — definición de rendimientos "
        "íntegros del capital inmobiliario, incluyendo rendimientos "
        "derivados del arrendamiento o cesión de inmuebles urbanos.",
    ),
    cite_lirpf(
        "23",
        "Artículo 23 Ley 35/2006 (IRPF) — gastos deducibles "
        "(art. 23.1: financiación, conservación, tributos, "
        "amortización al 3 % del coste de adquisición o del valor "
        "catastral de la construcción) y reducciones (art. 23.2 "
        "modificado por Ley 12/2023, BOE-A-2023-12203, con efectos "
        "sobre contratos celebrados desde 26/5/2023): tramos 50 % por "
        "defecto, 60 % vivienda rehabilitada en los 2 años anteriores, "
        "70 % primer alquiler en zona tensionada a inquilino 18-35 ó a "
        "Administración Pública, 90 % zona tensionada con reducción "
        ">= 5 % sobre la renta inicial del contrato anterior.",
    ),
    cite_lirpf(
        "24",
        "Artículo 24 Ley 35/2006 (IRPF) — rendimiento mínimo "
        "computable por arrendamiento entre cónyuges, ascendientes y "
        "descendientes (mínimo igual al valor de la imputación de "
        "rentas inmobiliarias del art. 85).",
    ),
    cite_lirpf(
        "85",
        "Artículo 85 Ley 35/2006 (IRPF) — imputación de rentas "
        "inmobiliarias: 2 % del valor catastral; 1,1 % si el valor "
        "catastral fue revisado en los 10 períodos impositivos "
        "anteriores; 1,1 % sobre el 50 % del mayor de valor "
        "administrativo o de adquisición si el inmueble carece de "
        "valor catastral.",
    ),
)


CASILLAS = (
    casilla(
        casilla_id="0061",
        label=_label(
            "Ingresos íntegros arrendamiento inmuebles",
            "Gross rental income (urban properties)",
            "Bruttó bérleti díj bevétel",
        ),
        computed=False,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0066",
        label=_label(
            "Gastos deducibles arrendamiento",
            "Deductible rental expenses",
            "Levonható bérleti költségek",
        ),
        computed=False,
        legal_basis=(CITATIONS[1],),
        notes_es=(
            "Suma de financiación, IBI, comunidad, reparación y "
            "conservación, seguros, suministros, gestión y otros gastos "
            "deducibles per LIRPF art. 23.1."
        ),
    ),
    casilla(
        casilla_id="0072",
        label=_label(
            "Amortización 3 % construcción",
            "Building amortization (3 %)",
            "Építmény-amortizáció (3 %)",
        ),
        computed=False,
        legal_basis=(CITATIONS[1],),
        notes_es=(
            "3 % sobre el mayor del coste de adquisición o del valor "
            "catastral de la construcción (LIRPF art. 23.1, párr. f)."
        ),
    ),
    casilla(
        casilla_id="0078",
        label=_label(
            "Reducción art. 23.2 — tramos 50/60/70/90 %",
            "Art. 23.2 reduction (50/60/70/90 % tiered)",
            "23.2 cikk csökkentés (50/60/70/90 % többszintű)",
        ),
        computed=False,
        legal_basis=(CITATIONS[1],),
        notes_es=(
            "El consumidor calcula el tramo aplicable según los metadatos "
            "del contrato: por defecto 50 %, vivienda rehabilitada en los "
            "2 años anteriores 60 %, primer alquiler en zona tensionada a "
            "inquilino joven o Administración Pública 70 %, zona tensionada "
            "con reducción >= 5 % sobre la renta inicial del contrato "
            "anterior 90 %. Se aplica sobre el rendimiento neto positivo "
            "declarado (0106 antes de la reducción)."
        ),
    ),
    casilla(
        casilla_id="0085",
        label=_label(
            "Imputación rentas inmobiliarias",
            "Imputed real-estate income (art. 85)",
            "Ingatlan-betudott jövedelem (85. cikk)",
        ),
        computed=False,
        legal_basis=(CITATIONS[3],),
        notes_es=(
            "El consumidor calcula 1,1 % o 2 % del valor catastral por "
            "cada inmueble no afecto. No alimenta las casillas 0106 / "
            "0107 — es una línea de ingresos paralela consumida por el "
            "Anexo F."
        ),
    ),
    casilla(
        casilla_id="0106",
        label=_label(
            "Rendimiento neto previo capital inmobiliario",
            "Net real-estate income before art. 23.2 reduction",
            "Bruttó ingatlanjövedelem 23.2 csökkentés előtt",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[1]),
    ),
    casilla(
        casilla_id="0107",
        label=_label(
            "Rendimiento neto reducido capital inmobiliario",
            "Net real-estate income (reduced)",
            "Nettó ingatlanjövedelem (csökkentett)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[1]),
    ),
)


FORMULAS = (
    formula(
        casilla_id="0106",
        formula_id="modelo_100.2025.c.rendimiento_neto_previo",
        body=clamp_pos(
            sub_op(
                sub_op(ref("0061"), ref("0066")),
                ref("0072"),
            ),
        ),
    ),
    formula(
        casilla_id="0107",
        formula_id="modelo_100.2025.c.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0106"), ref("0078"))),
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
