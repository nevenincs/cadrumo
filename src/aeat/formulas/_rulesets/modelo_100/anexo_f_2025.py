"""Modelo 100 Anexo F — bases imponibles + reducciones + minimos (2025).

Anexo F closes the income side of M100 by:

1. Aggregating per-anexo rendimientos netos into the two base
   imponibles (general LIRPF art. 48; ahorro art. 49).
2. Applying reducciones de la base imponible: planes de pensiones
   (art. 51, cap art. 52 1.500 EUR general + 8.500 EUR contrib.
   empresariales — caller-validated), tributacion conjunta (art. 84).
3. Computing the minimo personal y familiar total (LIRPF arts. 56-61)
   as the sum of its four components, each caller-supplied (the
   per-componente lookup tables 5.550 / 2.400-4.500 / 1.150-1.400 /
   3.000-9.000 + 3.000 EUR depend on caller-known descendiente count,
   ascendiente / discapacidad metadata that lives outside the formula
   layer).
4. Computing the base liquidable general (clamp_pos(BIG - reducciones))
   and base liquidable ahorro (= base imponible ahorro since the
   default reducciones do not absorb at this layer; the cross-over of
   minimo personal happens in Anexo G via the tarifa application).

The base imponible general aggregation pulls casillas from B1 (0022),
B2's contribution to general is zero by design (capital mobiliario =
ahorro), C (0107 + 0085), D normal (0205), D simplificada (0240), D
modulos (0260), E (0399). Base imponible ahorro = B2 (0049) + E (0400).

Stable across 2024 / 2025 / 2026 (LIRPF arts. 47-61 unchanged at BOE
consolidated text consult 2026-02-28; the 2024 amounts of arts. 57-60
remain in force per the year-by-year delta map in the rule-delta
manifest).
"""

from __future__ import annotations

from datetime import date

from ....i18n import Translatable
from ..._ruleset import ParameterTable
from .._common import (
    add_op,
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
        "48",
        "Articulo 48 Ley 35/2006 (IRPF) — base imponible general: "
        "suma algebraica de los rendimientos netos integrables en "
        "base general (trabajo, capital inmobiliario, actividades "
        "economicas, imputaciones de renta) y del saldo positivo de "
        "ganancias y perdidas patrimoniales con periodo de generacion "
        "<= 1 ano.",
    ),
    cite_lirpf(
        "49",
        "Articulo 49 Ley 35/2006 (IRPF) — base imponible del ahorro: "
        "rendimientos del capital mobiliario (art. 25.1, 25.2, 25.3) y "
        "ganancias / perdidas patrimoniales con periodo de generacion "
        "superior a un ano.",
    ),
    cite_lirpf(
        "50",
        "Articulo 50 Ley 35/2006 (IRPF) — base liquidable general y "
        "del ahorro: resultado de minorar la base imponible en las "
        "reducciones aplicables (planes de pensiones, tributacion "
        "conjunta, etc.).",
    ),
    cite_lirpf(
        "51",
        "Articulo 51 Ley 35/2006 (IRPF) — reduccion por aportaciones "
        "y contribuciones a sistemas de prevision social (planes de "
        "pensiones, planes de prevision asegurados, mutualidades de "
        "prevision social, planes de prevision social empresarial).",
    ),
    cite_lirpf(
        "52",
        "Articulo 52 Ley 35/2006 (IRPF) — limite maximo conjunto: "
        "1.500 EUR general + hasta 8.500 EUR adicional via "
        "contribuciones empresariales a sistemas de prevision social.",
    ),
    cite_lirpf(
        "56",
        "Articulo 56 Ley 35/2006 (IRPF) — minimo personal y familiar: "
        "constituye la parte de la base liquidable que, por destinarse "
        "a satisfacer las necesidades basicas personales y familiares "
        "del contribuyente, no se somete a tributacion.",
    ),
    cite_lirpf(
        "57",
        "Articulo 57 Ley 35/2006 (IRPF) — minimo del contribuyente: "
        "5.550 EUR anuales con carácter general; +1.150 EUR si > 65 "
        "anos; +1.400 EUR adicional si > 75.",
    ),
    cite_lirpf(
        "58",
        "Articulo 58 Ley 35/2006 (IRPF) — minimo por descendientes: "
        "2.400 EUR primer descendiente, 2.700 EUR segundo, 4.000 EUR "
        "tercero, 4.500 EUR cuarto y siguientes; bonus +2.800 EUR si "
        "menor de 3 anos. Requisitos: convivencia + rentas del "
        "descendiente <= 8.000 EUR.",
    ),
    cite_lirpf(
        "59",
        "Articulo 59 Ley 35/2006 (IRPF) — minimo por ascendientes: "
        "1.150 EUR si > 65 ano o discapacidad y conviven, rentas "
        "<= 8.000 EUR; +1.400 EUR si > 75.",
    ),
    cite_lirpf(
        "60",
        "Articulo 60 Ley 35/2006 (IRPF) — minimo por discapacidad: "
        "3.000 EUR si grado < 65%; 9.000 EUR si grado >= 65%; +3.000 "
        "EUR adicional por gastos de asistencia (necesita ayuda de "
        "terceras personas, movilidad reducida o grado >= 65%).",
    ),
    cite_lirpf(
        "84",
        "Articulo 84 Ley 35/2006 (IRPF) — reduccion por tributacion "
        "conjunta: 3.400 EUR / 2.150 EUR para unidades familiares "
        "monoparentales (caller computes la reduccion aplicable y la "
        "suministra como casilla 0455).",
    ),
)


CASILLAS = (
    # Inputs — reducciones de la base imponible.
    casilla(
        casilla_id="0445",
        label=_label(
            "Reduccion por aportaciones a sistemas de prevision social",
            "Pension-system contributions reduction (art. 51-52)",
            "Nyugdijrendszer-hozzajarulasi csokkentes",
        ),
        computed=False,
        legal_basis=(CITATIONS[3], CITATIONS[4]),
        notes_es=(
            "Verificado por el llamador: límite general de 1.500 EUR + "
            "hasta 8.500 EUR adicionales vía contribuciones empresariales "
            "a sistemas de previsión social (LIRPF art. 52)."
        ),
    ),
    casilla(
        casilla_id="0455",
        label=_label(
            "Reduccion por tributacion conjunta",
            "Joint-filing reduction (art. 84)",
            "Egyuttes ado-bevallasi csokkentes",
        ),
        computed=False,
        legal_basis=(CITATIONS[10],),
    ),
    # Inputs — minimo personal y familiar componentes.
    casilla(
        casilla_id="0505",
        label=_label(
            "Minimo del contribuyente",
            "Personal exemption (art. 57)",
            "Adoalany szemelyi minimum",
        ),
        computed=False,
        legal_basis=(CITATIONS[6],),
    ),
    casilla(
        casilla_id="0510",
        label=_label(
            "Minimo por descendientes",
            "Dependents exemption (art. 58)",
            "Leszarmazok szerinti minimum",
        ),
        computed=False,
        legal_basis=(CITATIONS[7],),
    ),
    casilla(
        casilla_id="0515",
        label=_label(
            "Minimo por ascendientes",
            "Ascendants exemption (art. 59)",
            "Felmenok szerinti minimum",
        ),
        computed=False,
        legal_basis=(CITATIONS[8],),
    ),
    casilla(
        casilla_id="0520",
        label=_label(
            "Minimo por discapacidad",
            "Disability exemption (art. 60)",
            "Fogyatekossagi minimum",
        ),
        computed=False,
        legal_basis=(CITATIONS[9],),
    ),
    # Computed — bases imponibles y minimo agregado.
    casilla(
        casilla_id="0432",
        label=_label(
            "Base imponible general",
            "General taxable base",
            "Altalanos adoalap",
        ),
        computed=True,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0460",
        label=_label(
            "Base imponible del ahorro",
            "Savings taxable base",
            "Megtakaritasi adoalap",
        ),
        computed=True,
        legal_basis=(CITATIONS[1],),
    ),
    casilla(
        casilla_id="0500",
        label=_label(
            "Minimo personal y familiar total",
            "Personal + family exemption (total)",
            "Szemelyi es csaladi minimum osszesen",
        ),
        computed=True,
        legal_basis=(CITATIONS[5],),
    ),
    casilla(
        casilla_id="0545",
        label=_label(
            "Base liquidable general",
            "General liquidable base",
            "Altalanos likvidalt adoalap",
        ),
        computed=True,
        legal_basis=(CITATIONS[2],),
    ),
    casilla(
        casilla_id="0555",
        label=_label(
            "Base liquidable del ahorro",
            "Savings liquidable base",
            "Megtakaritasi likvidalt adoalap",
        ),
        computed=True,
        legal_basis=(CITATIONS[2],),
    ),
)


# Base imponible general (LIRPF art. 48): sum of B1 0022 + C 0107 +
# C 0085 + D_normal 0205 + D_simplif. 0240 + D_modulos 0260 +
# E 0399 (saldo patrimonial integrable en general).
_BIG_BODY = add_op(
    add_op(
        add_op(ref("0022"), ref("0107")),
        add_op(ref("0085"), ref("0205")),
    ),
    add_op(
        add_op(ref("0240"), ref("0260")),
        ref("0399"),
    ),
)


# Base imponible ahorro (LIRPF art. 49): B2 0049 + E 0400.
_BIA_BODY = add_op(ref("0049"), ref("0400"))


FORMULAS = (
    formula(
        casilla_id="0432",
        formula_id="modelo_100.2025.f.base_imponible_general",
        body=_BIG_BODY,
    ),
    formula(
        casilla_id="0460",
        formula_id="modelo_100.2025.f.base_imponible_ahorro",
        body=_BIA_BODY,
    ),
    formula(
        casilla_id="0500",
        formula_id="modelo_100.2025.f.minimo_personal_familiar_total",
        body=add_op(
            add_op(ref("0505"), ref("0510")),
            add_op(ref("0515"), ref("0520")),
        ),
    ),
    formula(
        casilla_id="0545",
        formula_id="modelo_100.2025.f.base_liquidable_general",
        body=clamp_pos(
            sub_op(
                sub_op(ref("0432"), ref("0445")),
                ref("0455"),
            ),
        ),
    ),
    formula(
        casilla_id="0555",
        formula_id="modelo_100.2025.f.base_liquidable_ahorro",
        body=ref("0460"),
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
