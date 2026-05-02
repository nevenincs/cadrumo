"""Closed enumeration of the 15 ordinary CCAAs and per-CCAA tarifa autonómica brackets.

País Vasco and Navarra are foral regimes (Concierto Económico Ley
12/2002, Convenio Económico Ley 28/1990) and file separate IRPF-
equivalent declarations under their own Norma Foral / Decreto Foral
Legislativo. They are NOT members of :class:`CCAA`.

Ceuta and Melilla are NOT autonomous communities — they are ciudades
autónomas without LIRPF art. 46 bis competence. Their IRPF benefit is
a STATE-level deduction (LIRPF art. 68.4 — 60 % reducción on the
cuota proporcional, per Ley 6/2018) handled in Anexo G, not Anexo Ñ.

This module also publishes the per-CCAA tarifa autonómica general
brackets for all 15 ordinary CCAAs per LIRPF arts. 46 bis + 73-77 and
Ley 22/2009 (cesión de competencias normativas a las CCAA). The
brackets follow the same shape as the estatal tarifas
(``tuple[tuple[from, to | None, rate], ...]``) consumed by the
``progressive_tarifa()`` helper in Anexo G.

Dispatch is two-step: :data:`PER_CCAA_TARIFA_AUTONOMICA_BY_YEAR` covers
the year-dependent CCAAs (Asturias under Ley 3/2025; Canarias under
Ley 5/2024) keyed by ``(CCAA, año)``; everything else falls back to
the stable :data:`PER_CCAA_TARIFA_AUTONOMICA` per-CCAA dict.

Callers compute the autonomic cuota íntegra (casilla 0551) externally
via :func:`compute_cuota_autonomica_general` and supply the result;
the engine verifies the cuota chain via Anexo G's
``0551 + 0561 -> 0595`` aggregation.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class CCAA(StrEnum):
    """Closed enumeration of the 15 in-scope ordinary CCAAs.

    The CCAA where the contribuyente has habitual residence determines
    (a) which tarifa autonómica applies to the base liquidable general
    and ahorro, and (b) which set of deducciones autonómicas may be
    claimed in Anexo Ñ. País Vasco and Navarra are deliberately absent
    as foral regimes are out of scope.
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

# Tarifa autonómica general — Aragón (Decreto Legislativo 1/2005,
# texto refundido, art. 110-1). Stable 2024 / 2025 / 2026.
TARIFA_ARAGON = (
    ("0", "13072.50", "0.095"),
    ("13072.50", "21210.00", "0.12"),
    ("21210.00", "36960.00", "0.15"),
    ("36960.00", "52500.00", "0.185"),
    ("52500.00", "60000.00", "0.205"),
    ("60000.00", "80000.00", "0.23"),
    ("80000.00", "90000.00", "0.24"),
    ("90000.00", "130000.00", "0.25"),
    ("130000.00", None, "0.255"),
)

# Tarifa autonómica general — Principado de Asturias (Decreto Legislativo
# 2/2014, art. 2). YEAR-DEPENDENT: Ley del Principado 3/2025 (BOPA
# 2-12-2025), retroactive 1/1/2025. Tramo 1 10% -> 9%; tramo 4 18.5%
# -> 19.20%; tramo 8 25.5% -> 26%.
TARIFA_ASTURIAS_2024 = (
    ("0", "12450.00", "0.10"),
    ("12450.00", "17707.20", "0.12"),
    ("17707.20", "33007.20", "0.14"),
    ("33007.20", "53407.20", "0.185"),
    ("53407.20", "70000.00", "0.215"),
    ("70000.00", "90000.00", "0.225"),
    ("90000.00", "175000.00", "0.25"),
    ("175000.00", None, "0.255"),
)
TARIFA_ASTURIAS = (  # 2025 + 2026 (post Ley 3/2025).
    ("0", "12450.00", "0.09"),
    ("12450.00", "17707.20", "0.12"),
    ("17707.20", "33007.20", "0.14"),
    ("33007.20", "53407.20", "0.192"),
    ("53407.20", "70000.00", "0.215"),
    ("70000.00", "90000.00", "0.225"),
    ("90000.00", "175000.00", "0.25"),
    ("175000.00", None, "0.26"),
)

# Tarifa autonómica general — Illes Balears (Decreto Legislativo 1/2014,
# art. 1). Stable 2024 / 2025 / 2026.
TARIFA_BALEARES = (
    ("0", "10000.00", "0.09"),
    ("10000.00", "18000.00", "0.1125"),
    ("18000.00", "30000.00", "0.1425"),
    ("30000.00", "48000.00", "0.175"),
    ("48000.00", "70000.00", "0.19"),
    ("70000.00", "90000.00", "0.2175"),
    ("90000.00", "120000.00", "0.2275"),
    ("120000.00", "175000.00", "0.2375"),
    ("175000.00", None, "0.2475"),
)

# Tarifa autonómica general — Canarias (Decreto Legislativo 1/2009,
# art. 18 bis). YEAR-DEPENDENT: Ley 5/2024 (BOC 30-12-2024)
# deflactación 4 % en 4 primeros tramos + 3 % en el quinto, vigente
# 1/1/2025.
TARIFA_CANARIAS_2024 = (
    ("0", "13465.00", "0.09"),
    ("13465.00", "19022.00", "0.115"),
    ("19022.00", "35185.00", "0.14"),
    ("35185.00", "56382.00", "0.185"),
    ("56382.00", "91350.00", "0.235"),
    ("91350.00", "121200.00", "0.25"),
    ("121200.00", None, "0.26"),
)
TARIFA_CANARIAS = (  # 2025 + 2026 (post Ley 5/2024 deflactación).
    ("0", "13748.00", "0.09"),
    ("13748.00", "19422.00", "0.115"),
    ("19422.00", "35924.00", "0.14"),
    ("35924.00", "57566.00", "0.185"),
    ("57566.00", "93268.00", "0.235"),
    ("93268.00", "123745.00", "0.25"),
    ("123745.00", None, "0.26"),
)

# Tarifa autonómica general — Cantabria (Decreto Legislativo 62/2008,
# art. 1). Stable 2024 / 2025 / 2026.
TARIFA_CANTABRIA = (
    ("0", "13000.00", "0.085"),
    ("13000.00", "21000.00", "0.11"),
    ("21000.00", "35200.00", "0.145"),
    ("35200.00", "60000.00", "0.18"),
    ("60000.00", "90000.00", "0.225"),
    ("90000.00", None, "0.245"),
)

# Tarifa autonómica general — Castilla-La Mancha (Ley 8/2013, art. 13
# bis). Stable 2024 / 2025 / 2026.
TARIFA_CASTILLA_LA_MANCHA = (
    ("0", "12450.00", "0.095"),
    ("12450.00", "20200.00", "0.12"),
    ("20200.00", "35200.00", "0.15"),
    ("35200.00", "60000.00", "0.185"),
    ("60000.00", None, "0.225"),
)

# Tarifa autonómica general — Extremadura (Decreto Legislativo 1/2018,
# art. 1). Stable 2024 / 2025 / 2026 (Decreto-ley 2/2023 deflactación
# retroactiva 1-Jan-2023).
TARIFA_EXTREMADURA = (
    ("0", "12450.00", "0.08"),
    ("12450.00", "20200.00", "0.10"),
    ("20200.00", "24200.00", "0.16"),
    ("24200.00", "35200.00", "0.175"),
    ("35200.00", "60000.00", "0.21"),
    ("60000.00", "80200.00", "0.235"),
    ("80200.00", "99200.00", "0.24"),
    ("99200.00", "120200.00", "0.245"),
    ("120200.00", None, "0.25"),
)

# Tarifa autonómica general — Galicia (Decreto Legislativo 1/2011,
# art. 4). Stable 2024 / 2025 / 2026 (post-2022 deflactación).
TARIFA_GALICIA = (
    ("0", "12985.35", "0.09"),
    ("12985.35", "21068.60", "0.1165"),
    ("21068.60", "35200.00", "0.149"),
    ("35200.00", "60000.00", "0.184"),
    ("60000.00", None, "0.225"),
)

# Tarifa autonómica general — Región de Murcia (Decreto Legislativo
# 1/2010, art. 2). Stable 2024 / 2025 / 2026 at retrieval. NOTE: Ley
# 9/2025 introduced auto-deflactación trigger if Murcia IPC YoY > 3%
# in December — bracket boundaries may shift contingently.
TARIFA_MURCIA = (
    ("0", "12450.00", "0.095"),
    ("12450.00", "20200.00", "0.112"),
    ("20200.00", "34000.00", "0.133"),
    ("34000.00", "60000.00", "0.179"),
    ("60000.00", None, "0.225"),
)

# Tarifa autonómica general — La Rioja (Ley 10/2017, art. 31, modif.
# Ley 13/2023 BOR 30-12-2023). Stable 2024 / 2025 / 2026.
TARIFA_LA_RIOJA = (
    ("0", "12450.00", "0.08"),
    ("12450.00", "20200.00", "0.106"),
    ("20200.00", "35200.00", "0.136"),
    ("35200.00", "40000.00", "0.178"),
    ("40000.00", "50000.00", "0.183"),
    ("50000.00", "60000.00", "0.19"),
    ("60000.00", "120000.00", "0.245"),
    ("120000.00", None, "0.27"),
)


# Stable CCAAs (13 of 15): bracket tables identical across 2024/2025/2026.
PER_CCAA_TARIFA_AUTONOMICA: dict[CCAA, tuple[tuple[str, str | None, str], ...]] = {
    CCAA.ANDALUCIA: TARIFA_ANDALUCIA,
    CCAA.ARAGON: TARIFA_ARAGON,
    CCAA.BALEARES: TARIFA_BALEARES,
    CCAA.CANTABRIA: TARIFA_CANTABRIA,
    CCAA.CASTILLA_LA_MANCHA: TARIFA_CASTILLA_LA_MANCHA,
    CCAA.CASTILLA_Y_LEON: TARIFA_CASTILLA_Y_LEON,
    CCAA.CATALUNA: TARIFA_CATALUNA,
    CCAA.COMUNIDAD_VALENCIANA: TARIFA_COMUNIDAD_VALENCIANA,
    CCAA.EXTREMADURA: TARIFA_EXTREMADURA,
    CCAA.GALICIA: TARIFA_GALICIA,
    CCAA.LA_RIOJA: TARIFA_LA_RIOJA,
    CCAA.MADRID: TARIFA_MADRID,
    CCAA.MURCIA: TARIFA_MURCIA,
}

# Year-dependent CCAAs (2 of 15): Asturias (Ley 3/2025) + Canarias (Ley
# 5/2024 deflactación). The (ccaa, año) tuple keys these out so the
# helper consults this dict first and falls back to
# `PER_CCAA_TARIFA_AUTONOMICA` for stable CCAAs.
PER_CCAA_TARIFA_AUTONOMICA_BY_YEAR: dict[tuple[CCAA, int], tuple[tuple[str, str | None, str], ...]] = {
    (CCAA.ASTURIAS, 2024): TARIFA_ASTURIAS_2024,
    (CCAA.ASTURIAS, 2025): TARIFA_ASTURIAS,
    (CCAA.ASTURIAS, 2026): TARIFA_ASTURIAS,
    (CCAA.CANARIAS, 2024): TARIFA_CANARIAS_2024,
    (CCAA.CANARIAS, 2025): TARIFA_CANARIAS,
    (CCAA.CANARIAS, 2026): TARIFA_CANARIAS,
}


def compute_cuota_autonomica_general(blg: Decimal, ccaa: CCAA, año: int = 2025) -> Decimal:
    """Compute the cuota íntegra autonómica general for ``ccaa`` and ``año``.

    Pure-Python progressive-tarifa computation that mirrors the AST
    shape built by the ``progressive_tarifa()`` helper in Anexo G.
    Callers use this to derive casilla 0551 externally before supplying
    it to the engine.

    Dispatch is two-step: the year-dependent table
    :data:`PER_CCAA_TARIFA_AUTONOMICA_BY_YEAR` is consulted first
    (Asturias under Ley 3/2025 retroactive 1/1/2025, Canarias under Ley
    5/2024 deflactación 1/1/2025), then :data:`PER_CCAA_TARIFA_AUTONOMICA`
    serves as fallback for the 13 stable CCAAs. All 15 ordinary CCAAs are
    encoded, so this function does not raise :exc:`KeyError` for any
    in-scope CCAA. País Vasco and Navarra are not members of
    :class:`CCAA` (foral regimes are out of scope).

    Args:
        blg: Base liquidable general expressed as a :class:`~decimal.Decimal`.
        ccaa: Autonomous community of habitual residence.
        año: Filing year. Defaults to ``2025``.

    Returns:
        The cuota íntegra autonómica general, rounded to two decimal
        places using :data:`~decimal.ROUND_HALF_UP`.
    """
    # Two-step lookup: dict.get() defaults are evaluated eagerly, so
    # `PER_CCAA_TARIFA_AUTONOMICA[ccaa]` would raise KeyError for the
    # year-dependent CCAAs (Asturias / Canarias) that are deliberately
    # absent from the stable dict.
    brackets = PER_CCAA_TARIFA_AUTONOMICA_BY_YEAR.get((ccaa, año))
    if brackets is None:
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
    "PER_CCAA_TARIFA_AUTONOMICA_BY_YEAR",
    "compute_cuota_autonomica_general",
]
