"""Closed enumeration of the 15 ordinary autonomous communities.

País Vasco and Navarra are foral regimes (Concierto Económico Ley
12/2002, Convenio Económico Ley 28/1990) and file separate IRPF-
equivalent declarations under their own Norma Foral / Decreto Foral
Legislativo. They are NOT members of this enum.

Ceuta and Melilla are NOT autonomous communities — they are ciudades
autónomas without LIRPF art. 46 bis competence. Their IRPF benefit is a
STATE-level deduction (LIRPF art. 68.4 — 60% reducción on the cuota
proporcional, post Ley 6/2018) handled in Anexo G, not Anexo Ñ.
"""

from __future__ import annotations

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


__all__ = ["CCAA"]
