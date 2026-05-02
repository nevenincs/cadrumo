"""Modelo 100 Anexo D — estimación directa normal (actividades económicas, ejercicio 2025).

Estimación directa normal applies to actividades económicas IRPF
whose cifra de negocios is over 600.000 € (RIRPF art. 28) — full P&L
per LIS principles. Inventario per LIS art. 17 (FIFO, PMP, coste
medio; LIFO forbidden); amortizaciones per LIS art. 12 (lineal table)
plus libertad de amortización art. 102 (PYMES) and DA 18ª LIS via Ley
31/2022 plus DA 59ª LIRPF via RD-Ley 4/2024 (vehículos eléctricos).

Aggregation chain on M100:

- ``0140`` — ingresos de explotación (input).
- ``0150`` — compras y consumos del ejercicio (input).
- ``0155`` — variación de existencias (input — ``final - initial`` per
  the caller's :class:`._inventario.InventoryRecord`; positive =
  increase = revenue contribution).
- ``0165`` — gastos de personal (input).
- ``0170`` — servicios exteriores, tributos and otros gastos (input).
- ``0173`` — amortización del inmovilizado (input — caller computes
  per LIS art. 12 lineal table or libertad amortización).
- ``0180`` — provisiones y deterioros (input — LIS arts. 13-14).
- ``0190`` (total gastos computables, computed) =
  ``0150 + 0165 + 0170 + 0173 + 0180 - 0155``. Variación de
  existencias negativa — i.e. existencias finales menores que
  iniciales — incrementa gastos; positiva incrementa ingresos.
  ``0155`` is signed (positive when stock grew), so it is subtracted
  from gastos to net out.
- ``0195`` (rendimiento neto previo E.D. normal, computed) =
  ``clamp_pos(0140 - 0190)``.
- ``0200`` — reducciones LIRPF art. 32 (input — start of activity,
  irregularidad rendimientos).
- ``0205`` (rendimiento neto reducido E.D. normal, computed) =
  ``clamp_pos(0195 - 0200)``.

Stable across 2024, 2025 and 2026 (LIRPF arts. 27-32 and LIS arts.
12-14 plus 17 unchanged at the BOE consolidated-text consult of
2026-02-28).
"""

from __future__ import annotations

from datetime import date

from .....core.i18n import Translatable
from ..._ruleset import ParameterTable
from .._common import (
    add_op,
    casilla,
    clamp_pos,
    formula,
    ref,
    sub_op,
)
from ._common import cite_lirpf, cite_lis, cite_rirpf

EFFECTIVE_FROM = date(2025, 1, 1)
EFFECTIVE_TO = date(2025, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    """Build a multilingual label dict for a casilla in this anexo."""
    return {"es": es, "en": en, "hu": hu}


CITATIONS = (
    cite_lirpf(
        "27",
        "Artículo 27 Ley 35/2006 (IRPF) — define rendimiento de "
        "actividad económica como aquel derivado de la ordenación por "
        "cuenta propia de los medios de producción y de los recursos "
        "humanos, con la finalidad de intervenir en la producción o "
        "distribución de bienes o servicios.",
    ),
    cite_lirpf(
        "28",
        "Artículo 28 Ley 35/2006 (IRPF) — rendimiento neto en "
        "estimación directa: con carácter general el rendimiento neto "
        "de la actividad económica se determina por la diferencia "
        "entre la totalidad de los ingresos íntegros y los gastos "
        "deducibles, aplicando las normas del Impuesto sobre Sociedades.",
    ),
    cite_lirpf(
        "32",
        "Artículo 32 Ley 35/2006 (IRPF) — reducciones aplicables al "
        "rendimiento neto de actividades económicas: 30 % por "
        "rendimientos irregulares (período de generación > 2 años o "
        "calificados como notoriamente irregulares), reducción 20 % "
        "para autónomos noveles en el primer ejercicio de actividad y "
        "el siguiente, hasta 100.000 € de base.",
    ),
    cite_lis(
        "12",
        "Artículo 12 Ley 27/2014 (LIS) — correcciones de valor: "
        "amortizaciones. Tabla lineal aplicable en estimación directa "
        "normal del IRPF (33 categorías de activos con coeficiente "
        "máximo y período máximo). Libertad de amortización en LIS "
        "art. 12.3 (I+D, vehículos eléctricos via DA 18ª LIS) y art. "
        "102 (PYMES). DA 59ª LIRPF via RD-Ley 4/2024 amplía libertad "
        "de amortización a infraestructura de recarga.",
    ),
    cite_lis(
        "13",
        "Artículo 13 Ley 27/2014 (LIS) — pérdida por deterioro de "
        "valor de elementos patrimoniales: régimen restrictivo a "
        "créditos comerciales y existencias.",
    ),
    cite_lis(
        "17",
        "Artículo 17 Ley 27/2014 (LIS) — reglas de valoración de "
        "existencias: coste de adquisición o producción; admisible "
        "precio medio o coste medio ponderado y FIFO; LIFO no "
        "admisible para fines fiscales.",
    ),
    cite_rirpf(
        "28",
        "Artículo 28 RD 439/2007 (Reglamento del IRPF) — modalidades "
        "del método de estimación directa: normal aplicable cuando la "
        "cifra neta de negocios del conjunto de actividades supera "
        "los 600.000 € en el año anterior.",
    ),
)


CASILLAS = (
    casilla(
        casilla_id="0140",
        label=_label(
            "Ingresos de explotación",
            "Operating income (E.D. normal)",
            "Üzemi bevétel (E.D. normál)",
        ),
        computed=False,
        legal_basis=(CITATIONS[0], CITATIONS[1]),
    ),
    casilla(
        casilla_id="0150",
        label=_label(
            "Compras y consumos del ejercicio",
            "Purchases and consumption (E.D. normal)",
            "Beszerzés és felhasználás",
        ),
        computed=False,
        legal_basis=(CITATIONS[1], CITATIONS[5]),
    ),
    casilla(
        casilla_id="0155",
        label=_label(
            "Variación de existencias",
            "Inventory variation (final - initial)",
            "Keszletvaltozas (zaro - nyito)",
        ),
        computed=False,
        legal_basis=(CITATIONS[5],),
        notes_es=(
            "Calculado por el consumidor a partir de `InventoryRecord` "
            "según LIS art. 17. Con signo: positivo = existencias finales "
            "> iniciales = contribución a ingresos; negativo = existencias "
            "finales < iniciales = contribución a gastos."
        ),
    ),
    casilla(
        casilla_id="0165",
        label=_label(
            "Gastos de personal",
            "Personnel expenses",
            "Személyi költségek",
        ),
        computed=False,
        legal_basis=(CITATIONS[1],),
    ),
    casilla(
        casilla_id="0170",
        label=_label(
            "Servicios exteriores, tributos y otros",
            "External services, taxes, other",
            "Külső szolgáltatások, adók, egyéb",
        ),
        computed=False,
        legal_basis=(CITATIONS[1],),
    ),
    casilla(
        casilla_id="0173",
        label=_label(
            "Amortización del inmovilizado",
            "Tangible/intangible amortization",
            "Befektetett eszközök amortizációja",
        ),
        computed=False,
        legal_basis=(CITATIONS[3],),
        notes_es=(
            "Calculado por el consumidor según la tabla LIS art. 12 lineal "
            "(33 filas) o el régimen de libertad de amortización (LIS art. "
            "102 PYMES, DA 18ª LIS, DA 59ª LIRPF tras RD-Ley 4/2024)."
        ),
    ),
    casilla(
        casilla_id="0180",
        label=_label(
            "Provisiones y deterioros",
            "Provisions and impairments",
            "Tartalékok és értékvesztés",
        ),
        computed=False,
        legal_basis=(CITATIONS[4],),
    ),
    casilla(
        casilla_id="0190",
        label=_label(
            "Total gastos computables E.D. normal",
            "Total deductible expenses (E.D. normal)",
            "Összes levonható költség (E.D. normál)",
        ),
        computed=True,
        legal_basis=(CITATIONS[1], CITATIONS[3], CITATIONS[4]),
    ),
    casilla(
        casilla_id="0195",
        label=_label(
            "Rendimiento neto previo E.D. normal",
            "Net business income before art. 32 reduction",
            "Bruttó vállalkozási jövedelem 32. cikk csökkentés előtt",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[1]),
    ),
    casilla(
        casilla_id="0200",
        label=_label(
            "Reducción LIRPF art. 32",
            "Art. 32 reduction (irregular / startup)",
            "32. cikk csökkentés (rendszertelen / induló)",
        ),
        computed=False,
        legal_basis=(CITATIONS[2],),
    ),
    casilla(
        casilla_id="0205",
        label=_label(
            "Rendimiento neto reducido E.D. normal",
            "Net business income (reduced, E.D. normal)",
            "Nettó vállalkozási jövedelem (csökkentett, normál)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[1], CITATIONS[2]),
    ),
)


# 0190 = sum(gastos directos) - variación existencias positiva.
# Positive 0155 (final > initial) means stock grew — that build-up
# is NOT a current-period gasto, so we subtract it from total gastos.
# Negative 0155 (final < initial) means stock was consumed — caller
# enters it as a positive gasto contribution via 0150 (compras y
# consumos), so 0155 negative is added back via the same sub_op
# (subtracting a negative = adding).
_TOTAL_GASTOS_BODY = sub_op(
    add_op(
        add_op(ref("0150"), ref("0165")),
        add_op(
            ref("0170"),
            add_op(ref("0173"), ref("0180")),
        ),
    ),
    ref("0155"),
)


FORMULAS = (
    formula(
        casilla_id="0190",
        formula_id="modelo_100.2025.d_normal.total_gastos",
        body=_TOTAL_GASTOS_BODY,
    ),
    formula(
        casilla_id="0195",
        formula_id="modelo_100.2025.d_normal.rendimiento_neto_previo",
        body=clamp_pos(sub_op(ref("0140"), ref("0190"))),
    ),
    formula(
        casilla_id="0205",
        formula_id="modelo_100.2025.d_normal.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0195"), ref("0200"))),
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
