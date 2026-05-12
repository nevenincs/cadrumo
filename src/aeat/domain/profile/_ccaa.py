"""The closed catalogue of ordinary common-regime Spanish autonomous communities.

Lives in its own module so wizard descriptor construction can reference
the enum without triggering the rest of ``aeat.domain.profile``'s
import-time chain.
"""

from __future__ import annotations

from enum import StrEnum


class CCAA(StrEnum):
    """Ordinary common-regime autonomous communities for residence profile data."""

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
