"""Closed enumeration of the 15 ordinary autonomous communities + per-CCAA tarifa autonómica brackets.

País Vasco and Navarra are foral regimes (Concierto Económico Ley
12/2002, Convenio Económico Ley 28/1990) and file separate IRPF-
equivalent declarations under their own Norma Foral / Decreto Foral
Legislativo. They are NOT members of this enum.

Ceuta and Melilla are NOT autonomous communities — they are ciudades
autónomas without LIRPF art. 46 bis competence. Their IRPF benefit is a
STATE-level deduction (LIRPF art. 68.4 — 60 % reducción on the cuota
proporcional, post Ley 6/2018) handled in Anexo G, not Anexo Ñ.

This module also publishes the **per-CCAA tarifa autonómica general
brackets** for the 5 highest-population CCAAs (Madrid, Cataluña,
Andalucía, Comunitat Valenciana, Castilla y León) per LIRPF arts.
46 bis + 73-77 + Ley 22/2009 (cesión de competencias normativas a las
CCAA). The brackets follow the same shape as the estatal tarifas
(`tuple[tuple[from, to | None, rate], ...]`) consumed by
``progressive_tarifa()`` in Anexo G.

Caller computes the autonomic cuota íntegra (casilla 0551) externally
via ``compute_cuota_autonomica_general(blg, ccaa, año)`` and supplies
the result; the engine verifies the cuota chain via Anexo G's
0551 + 0561 -> 0595 aggregation. The 10 remaining CCAAs (Aragón,
Asturias, Baleares, Canarias, Cantabria, Castilla-La Mancha,
Extremadura, Galicia, Murcia, La Rioja) use their own per-CCAA Decreto
Legislativo / Ley de Presupuestos tarifa scales not yet encoded here
(deferred follow-up — caller computes externally pending each CCAA's
publication).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class CCAA(StrEnum):
    """Closed enumeration of the 15 in-scope ordinary CCAAs.

    The CCAA where Kent has habitual residence determines (a) which
    tarifa autonómica applies to his base liquidable general / ahorro,
    and (b) which set of deducciones autonómicas he can claim in
    Anexo Ñ. País Vasco and Navarra are deliberately absent (foral
    regimes — out of scope per `#424`).
    """

    ANDALUCIA = "andalucia"
    ARAGON = "aragon"
    ASTURIAS = "asturias"
    BALEARES = "baleares"
    CANARIAS = "canarias"
    CANTABRIA = "cantabria"
    CASTILLA_LA_MANCHA = "castilla_la_mancha"
    CASTILLA_Y_LEON = "castilla_y_leon"
    CATALUNA = "cataluna"
    COMUNIDAD_VALENCIANA = "comunidad_valenciana"
    EXTREMADURA = "extremadura"
    GALICIA = "galicia"
    LA_RIOJA = "la_rioja"
    MADRID = "madrid"
    MURCIA = "murcia"


# Tarifa autonómica general — Comunidad de Madrid (Decreto Legislativo
# 1/2010 modificado por Ley 5/2024 deflactación).
# Stable 2024 / 2025 / 2026. Source: research doc §6.3.1.
TARIFA_MADRID = (
    ("0", "13362.22", "0.085"),
    ("13362.22", "19004.63", "0.107"),
    ("19004.63", "35425.68", "0.128"),
    ("35425.68", "57320.40", "0.174"),
    ("57320.40", None, "0.205"),
)

# Tarifa autonómica general — Cataluña (Llei 5/2020 + actualizaciones
# presupuestarias). Stable 2024 / 2025 / 2026. Source: research doc §6.3.2.
TARIFA_CATALUNA = (
    ("0", "12450.00", "0.105"),
    ("12450.00", "17707.20", "0.12"),
    ("17707.20", "21000.00", "0.14"),
    ("21000.00", "33007.20", "0.15"),
    ("33007.20", "53407.20", "0.188"),
    ("53407.20", "90000.00", "0.215"),
    ("90000.00", "120000.00", "0.235"),
    ("120000.00", "175000.00", "0.245"),
    ("175000.00", None, "0.255"),
)

# Tarifa autonómica general — Andalucía (Decreto Legislativo 1/2018
# modificado). Stable 2024 / 2025 / 2026. Source: research doc §6.3.3.
TARIFA_ANDALUCIA = (
    ("0", "13000.00", "0.095"),
    ("13000.00", "21100.00", "0.12"),
    ("21100.00", "35200.00", "0.15"),
    ("35200.00", "60000.00", "0.185"),
    ("60000.00", None, "0.225"),
)

# Tarifa autonómica general — Comunitat Valenciana (Ley 13/1997
# modificada anualmente). Stable 2024 / 2025 / 2026. Source: research
# doc §6.3.4.
TARIFA_COMUNIDAD_VALENCIANA = (
    ("0", "12000.00", "0.09"),
    ("12000.00", "22000.00", "0.12"),
    ("22000.00", "32000.00", "0.15"),
    ("32000.00", "42000.00", "0.175"),
    ("42000.00", "52000.00", "0.20"),
    ("52000.00", "65000.00", "0.225"),
    ("65000.00", "72000.00", "0.25"),
    ("72000.00", "100000.00", "0.265"),
    ("100000.00", "150000.00", "0.275"),
    ("150000.00", "200000.00", "0.285"),
    ("200000.00", None, "0.295"),
)

# Tarifa autonómica general — Castilla y León (Decreto Legislativo
# 1/2013). Stable 2024 / 2025 / 2026. Source: research doc §6.3.5.
TARIFA_CASTILLA_Y_LEON = (
    ("0", "12450.00", "0.09"),
    ("12450.00", "20200.00", "0.12"),
    ("20200.00", "35200.00", "0.14"),
    ("35200.00", "60000.00", "0.185"),
    ("60000.00", None, "0.215"),
)


# Per-CCAA tarifa lookup. Only the 5 highest-population CCAAs are
# encoded here; the 10 remaining CCAAs follow their own per-CCAA texto
# refundido / Ley de Presupuestos that is not yet first-class in the
# codebase (caller computes externally pending follow-up per-CCAA
# encoding wave).
PER_CCAA_TARIFA_AUTONOMICA: dict[CCAA, tuple[tuple[str, str | None, str], ...]] = {
    CCAA.MADRID: TARIFA_MADRID,
    CCAA.CATALUNA: TARIFA_CATALUNA,
    CCAA.ANDALUCIA: TARIFA_ANDALUCIA,
    CCAA.COMUNIDAD_VALENCIANA: TARIFA_COMUNIDAD_VALENCIANA,
    CCAA.CASTILLA_Y_LEON: TARIFA_CASTILLA_Y_LEON,
}


def compute_cuota_autonomica_general(blg: Decimal, ccaa: CCAA) -> Decimal:
    """Compute the cuota íntegra autonómica general for `ccaa` at base
    liquidable general `blg`.

    Pure-Python progressive-tarifa computation that mirrors the AST shape
    built by ``progressive_tarifa()`` in Anexo G. Caller uses this to
    derive casilla 0551 externally before supplying it to the engine.

    For the 10 CCAAs not in `PER_CCAA_TARIFA_AUTONOMICA` (Aragón,
    Asturias, Baleares, Canarias, Cantabria, Castilla-La Mancha,
    Extremadura, Galicia, Murcia, La Rioja) the function raises
    `KeyError` — caller is expected to compute externally per each
    CCAA's vigent Decreto Legislativo / Ley de Presupuestos. Once those
    CCAAs' tarifas land in this module, the dispatch widens
    transparently.
    """
    brackets = PER_CCAA_TARIFA_AUTONOMICA[ccaa]
    cuota = Decimal("0.00")
    for from_value, to_value, rate in brackets:
        from_d = Decimal(from_value)
        rate_d = Decimal(rate)
        portion_from = max(Decimal("0"), blg - from_d)
        if to_value is not None:
            portion_to = max(Decimal("0"), blg - Decimal(to_value))
            portion = portion_from - portion_to
        else:
            portion = portion_from
        cuota += rate_d * portion
    return cuota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


__all__ = [
    "CCAA",
    "PER_CCAA_TARIFA_AUTONOMICA",
    "TARIFA_ANDALUCIA",
    "TARIFA_CASTILLA_Y_LEON",
    "TARIFA_CATALUNA",
    "TARIFA_COMUNIDAD_VALENCIANA",
    "TARIFA_MADRID",
    "compute_cuota_autonomica_general",
]
