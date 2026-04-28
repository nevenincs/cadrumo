"""Modelo 100 Anexo G — cuotas + tarifas + deducciones estatales (2025).

Anexo G applies the IRPF tarifa progresiva to the base liquidable
general and to the base liquidable del ahorro, both per LIRPF arts. 63
+ 66, accounting for the LIRPF art. 56 mínimo personal y familiar
absorption at the lowest brackets. The autonomic half (LIRPF arts.
73-77) is caller-supplied per-CCAA (cesión de competencias normativas
via Ley 22/2009; the per-CCAA distinct tarifa scales for Madrid /
Cataluña / Andalucía / Comunitat Valenciana / Castilla y León are
encoded as casilla parameter tables in the rule-delta reference
manifest; the 10 remaining CCAAs use the LIRPF DT primera default
unless overridden).

Tarifa estatal general (LIRPF art. 63, stable 2021-2026, vigent for
2025):

  0       - 12.450 EUR  -> 9,50 %
  12.450  - 20.200 EUR  -> 12,00 %
  20.200  - 35.200 EUR  -> 15,00 %
  35.200  - 60.000 EUR  -> 18,50 %
  60.000  - 300.000 EUR -> 22,50 %
  300.000 - inf         -> 24,50 %

Tarifa estatal del ahorro (LIRPF art. 66, post Ley 7/2024 vigent
1/1/2025):

  0       - 6.000 EUR   -> 9,50 %
  6.000   - 50.000 EUR  -> 10,50 %
  50.000  - 200.000 EUR -> 11,50 %
  200.000 - 300.000 EUR -> 13,50 %
  300.000 - inf         -> 15,00 %  (raised from 14,00 % in 2024 by Ley 7/2024)

Encoding: progressive cuota = sum over brackets of
  rate * (clamp_pos(operand - bracket_start) -
           clamp_pos(operand - bracket_end))
which yields the correct progressive tax. The LIRPF art. 56 minimo
absorption applies the same scale to min(BLG, 0500) and subtracts.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....i18n import Translatable
from ..._formula import AddFormula, ClampPositiveFormula, Literal, MulFormula, Operand, SubFormula
from ..._ruleset import ParameterTable
from .._common import (
    add_op,
    casilla,
    clamp_pos,
    formula,
    min_op,
    ref,
    sub_op,
)
from ._common import cite_lirpf

EFFECTIVE_FROM = date(2025, 1, 1)
EFFECTIVE_TO = date(2025, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


# Tarifa estatal general (LIRPF art. 63) — stable 2021-2026.
TARIFA_ESTATAL_GENERAL_2025: tuple[tuple[str, str | None, str], ...] = (
    ("0", "12450.00", "0.095"),
    ("12450.00", "20200.00", "0.12"),
    ("20200.00", "35200.00", "0.15"),
    ("35200.00", "60000.00", "0.185"),
    ("60000.00", "300000.00", "0.225"),
    ("300000.00", None, "0.245"),
)

# Tarifa estatal del ahorro (LIRPF art. 66) — 2025 + 2026 post Ley 7/2024.
TARIFA_ESTATAL_AHORRO_2025: tuple[tuple[str, str | None, str], ...] = (
    ("0", "6000.00", "0.095"),
    ("6000.00", "50000.00", "0.105"),
    ("50000.00", "200000.00", "0.115"),
    ("200000.00", "300000.00", "0.135"),
    ("300000.00", None, "0.15"),
)


def progressive_tarifa(
    operand: Operand,
    brackets: tuple[tuple[str, str | None, str], ...],
) -> Operand:
    """Build the AST for a progressive tax cuota.

    Each bracket contributes ``rate * (portion of operand within
    [from, to])``. Portions: ``clamp_pos(operand - from) -
    clamp_pos(operand - to)`` for bounded brackets;
    ``clamp_pos(operand - from)`` for the open-ended top bracket.
    Returns ``add_op`` over per-bracket contributions.
    """
    parts: list[Operand] = []
    for from_value, to_value, rate in brackets:
        if from_value == "0":
            portion_from: Operand = ClampPositiveFormula(operands=(operand,))
        else:
            portion_from = ClampPositiveFormula(
                operands=(SubFormula(operands=(operand, Literal(value=Decimal(from_value)))),)
            )
        if to_value is not None:
            portion_to: Operand = ClampPositiveFormula(
                operands=(SubFormula(operands=(operand, Literal(value=Decimal(to_value)))),)
            )
            portion: Operand = SubFormula(operands=(portion_from, portion_to))
        else:
            portion = portion_from
        parts.append(MulFormula(operands=(Literal(value=Decimal(rate)), portion)))
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return AddFormula(operands=(parts[0], parts[1]))
    # Fold pair-wise into n-ary AddFormula (min_length=2).
    return AddFormula(operands=tuple(parts))


CITATIONS = (
    cite_lirpf(
        "63",
        "Artículo 63 Ley 35/2006 (IRPF) — escala general estatal "
        "aplicable a la base liquidable general (LIRPF art. 50). "
        "Tramos vigentes desde 1/1/2021 (Ley 11/2020): 0-12450 al "
        "9,5 %; 12450-20200 al 12 %; 20200-35200 al 15 %; "
        "35200-60000 al 18,5 %; 60000-300000 al 22,5 %; "
        ">300000 al 24,5 %.",
    ),
    cite_lirpf(
        "66",
        "Artículo 66 Ley 35/2006 (IRPF) — tipos de gravamen del "
        "ahorro (estatal). Modificado por Ley 7/2024 con efectos "
        "1/1/2025: el ultimo tramo (>300000) sube del 14 % al 15 %; "
        "tramos 0-6000 al 9,5 %; 6000-50000 al 10,5 %; "
        "50000-200000 al 11,5 %; 200000-300000 al 13,5 %; "
        ">300000 al 15 %.",
    ),
    cite_lirpf(
        "67",
        "Artículo 67 Ley 35/2006 (IRPF) — cuota líquida estatal: "
        "resultado de aplicar las deducciones del apartado precedente "
        "(art. 68) a la cantidad estatal de la cuota total previa.",
    ),
    cite_lirpf(
        "68",
        "Artículo 68 Ley 35/2006 (IRPF) — deducciones estatales: "
        "donativos (Ley 49/2002 + apartado 1 art. 68), inversion en "
        "vivienda habitual (regimen transitorio apartado 1 art. "
        "68.1), alquiler vivienda (regimen transitorio apartado 7), "
        "doble imposicion internacional (apartado 9). El apartado 4 "
        "establece la deducción del 60 % por rentas obtenidas en "
        "Ceuta o Melilla (post Ley 6/2018).",
    ),
    cite_lirpf(
        "73",
        "Artículo 73 Ley 35/2006 (IRPF) — cuota íntegra autonómica "
        "general: aplicación de la escala autonómica de cada Comunidad "
        "a la base liquidable general (LIRPF art. 50). La escala es "
        "competencia normativa de cada Comunidad (cesión vía Ley "
        "22/2009).",
    ),
    cite_lirpf(
        "76",
        "Artículo 76 Ley 35/2006 (IRPF) — cuota íntegra autonómica "
        "correspondiente al ahorro: aplicación del tipo del ahorro a "
        "la parte autonómica de la base liquidable del ahorro.",
    ),
    cite_lirpf(
        "77",
        "Artículo 77 Ley 35/2006 (IRPF) — cuota líquida autonómica "
        "total: resultado de aplicar las deducciones autónomicas "
        "(Anexo N) a la suma de las cuotas íntegras autonómicas "
        "general y del ahorro.",
    ),
    cite_lirpf(
        "79",
        "Artículo 79 Ley 35/2006 (IRPF) — cuota diferencial: el "
        "resultado de minorar la cuantia neta total del impuesto en "
        "las retenciones, ingresos a cuenta y pagos fraccionados "
        "ingresados (LIRPF art. 99-101).",
    ),
    cite_lirpf(
        "99",
        "Artículo 99 Ley 35/2006 (IRPF) — obligación de practicar "
        "pagos a cuenta sobre rendimientos del trabajo, capital "
        "mobiliario, capital inmobiliario y actividades economicas. "
        "Las cantidades retenidas e ingresadas a cuenta minoran la "
        "cuota líquida.",
    ),
)


CASILLAS = (
    # Computed — tarifa intermedia.
    casilla(
        casilla_id="0540",
        label=_label(
            "Cuota tarifa estatal general sobre base liquidable",
            "State general tarifa applied to BLG",
            "Allami altalanos tarifa BLG-re alkalmazva",
        ),
        computed=True,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0542",
        label=_label(
            "Cuota tarifa estatal sobre mínimo personal y familiar",
            "State general tarifa applied to mínimo (capped at BLG)",
            "Allami altalanos tarifa szemelyi minimumra (BLG-re korlatozva)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0],),
    ),
    casilla(
        casilla_id="0550",
        label=_label(
            "Cuota integra estatal general",
            "State general gross tax",
            "Allami altalanos brutto ado",
        ),
        computed=True,
        legal_basis=(CITATIONS[0],),
    ),
    # Inputs autonómica general (caller-supplied per-CCAA).
    casilla(
        casilla_id="0551",
        label=_label(
            "Cuota integra autonómica general",
            "Autonomic general gross tax (per-CCAA caller input)",
            "Autonom altalanos brutto ado (CCAA-fuggo, hivo szolgaltatja)",
        ),
        computed=False,
        legal_basis=(CITATIONS[4],),
    ),
    # Computed tarifa ahorro estatal.
    casilla(
        casilla_id="0560",
        label=_label(
            "Cuota integra estatal del ahorro",
            "State savings gross tax",
            "Allami megtakaritasi brutto ado",
        ),
        computed=True,
        legal_basis=(CITATIONS[1],),
    ),
    # Inputs autonómica ahorro (caller-supplied).
    casilla(
        casilla_id="0561",
        label=_label(
            "Cuota integra autonómica del ahorro",
            "Autonomic savings gross tax (per-CCAA caller input)",
            "Autonom megtakaritasi brutto ado (CCAA-fuggo)",
        ),
        computed=False,
        legal_basis=(CITATIONS[5],),
    ),
    # Computed cuota íntegra total.
    casilla(
        casilla_id="0595",
        label=_label(
            "Cuota integra total (estatal + autonómica)",
            "Total gross tax (state + autonomic)",
            "Teljes brutto ado (allami + autonom)",
        ),
        computed=True,
        legal_basis=(CITATIONS[0], CITATIONS[1], CITATIONS[4], CITATIONS[5]),
    ),
    # Deducciones (inputs).
    casilla(
        casilla_id="0612",
        label=_label(
            "Deduccion 60 % rentas Ceuta / Melilla",
            "60 % deduction for Ceuta/Melilla income (LIRPF art. 68.4)",
            "Ceuta/Melilla bevetel 60 %-os levonas",
        ),
        computed=False,
        legal_basis=(CITATIONS[3],),
        notes_es=(
            "Calculado por el consumidor: 60 % sobre la cuota íntegra "
            "proporcional a las rentas obtenidas en Ceuta o Melilla "
            "(tras Ley 6/2018). Tope: la deducción no puede exceder del "
            "60 % de la cuota íntegra total."
        ),
    ),
    casilla(
        casilla_id="0620",
        label=_label(
            "Deducciones estatales total",
            "Total state deductions (donativos / vivienda / etc.)",
            "Allami levonasok osszesen",
        ),
        computed=False,
        legal_basis=(CITATIONS[3],),
    ),
    # NOTE: casilla 0622 (deducciones autónomicas total) is moved to
    # Anexo N — it's computed as the sum of the 15 per-CCAA aggregate-
    # deduction casillas (1101..1115). Anexo G only consumes 0622 via
    # the 0630 formula.
    # Computed deducciones + cuota líquida + cuota diferencial.
    casilla(
        casilla_id="0630",
        label=_label(
            "Total deducciones (estatales + autonómicas)",
            "Total deductions (state + autonomic)",
            "Teljes levonasok",
        ),
        computed=True,
        legal_basis=(CITATIONS[3], CITATIONS[6]),
    ),
    casilla(
        casilla_id="0698",
        label=_label(
            "Cuota liquida total",
            "Total net tax (cuota íntegra - deducciones - Ceuta/Melilla)",
            "Teljes netto ado",
        ),
        computed=True,
        legal_basis=(CITATIONS[2], CITATIONS[6]),
    ),
    casilla(
        casilla_id="0699",
        label=_label(
            "Retenciones e ingresos a cuenta",
            "Withholdings and prepayments (LIRPF arts. 99-101)",
            "Levonasok es eloleg befizetesek",
        ),
        computed=False,
        legal_basis=(CITATIONS[8],),
    ),
    casilla(
        casilla_id="0700",
        label=_label(
            "Pagos fraccionados (Modelos 130 / 131)",
            "Fractional payments (Models 130 / 131)",
            "Reszletfizetesek (130 / 131 modell)",
        ),
        computed=False,
        legal_basis=(CITATIONS[8],),
    ),
    casilla(
        casilla_id="0720",
        label=_label(
            "Cuota diferencial / resultado de la autoliquidacion",
            "Differential cuota / autoliquidation result (art. 79)",
            "Onbevallas eredmenye / kulonbozeti ado (79. cikk)",
        ),
        computed=True,
        legal_basis=(CITATIONS[7],),
    ),
)


_CUOTA_TARIFA_BLG_BODY = progressive_tarifa(ref("0545"), TARIFA_ESTATAL_GENERAL_2025)
_CUOTA_TARIFA_MINIMO_BODY = progressive_tarifa(
    min_op(ref("0500"), ref("0545")),
    TARIFA_ESTATAL_GENERAL_2025,
)
_CUOTA_INTEGRA_AHORRO_BODY = progressive_tarifa(ref("0555"), TARIFA_ESTATAL_AHORRO_2025)


FORMULAS = (
    formula(
        casilla_id="0540",
        formula_id="modelo_100.2025.g.cuota_tarifa_estatal_blg",
        body=_CUOTA_TARIFA_BLG_BODY,
    ),
    formula(
        casilla_id="0542",
        formula_id="modelo_100.2025.g.cuota_tarifa_estatal_minimo",
        body=_CUOTA_TARIFA_MINIMO_BODY,
    ),
    formula(
        casilla_id="0550",
        formula_id="modelo_100.2025.g.cuota_integra_estatal_general",
        body=clamp_pos(sub_op(ref("0540"), ref("0542"))),
    ),
    formula(
        casilla_id="0560",
        formula_id="modelo_100.2025.g.cuota_integra_estatal_ahorro",
        body=_CUOTA_INTEGRA_AHORRO_BODY,
    ),
    formula(
        casilla_id="0595",
        formula_id="modelo_100.2025.g.cuota_integra_total",
        body=add_op(
            add_op(ref("0550"), ref("0551")),
            add_op(ref("0560"), ref("0561")),
        ),
    ),
    formula(
        casilla_id="0630",
        formula_id="modelo_100.2025.g.total_deducciones",
        body=add_op(ref("0620"), ref("0622")),
    ),
    formula(
        casilla_id="0698",
        formula_id="modelo_100.2025.g.cuota_liquida_total",
        body=clamp_pos(
            sub_op(
                sub_op(ref("0595"), ref("0630")),
                ref("0612"),
            ),
        ),
    ),
    formula(
        casilla_id="0720",
        formula_id="modelo_100.2025.g.cuota_diferencial",
        body=sub_op(
            sub_op(ref("0698"), ref("0699")),
            ref("0700"),
        ),
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
    "TARIFA_ESTATAL_AHORRO_2025",
    "TARIFA_ESTATAL_GENERAL_2025",
    "progressive_tarifa",
]
