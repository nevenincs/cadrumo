"""Hand-curated handbook and volume identifiers for :mod:`aeat.domain.manuals`.

Identifiers are closed enums so extraction pipelines cannot create
rogue volumes.
"""

from __future__ import annotations

from enum import StrEnum


class ManualId(StrEnum):
    """Authoritative handbook identifiers."""

    RENTA = "renta"
    IVA = "iva"
    SOCIEDADES = "sociedades"


class ManualPart(StrEnum):
    """Volume identifiers for multi-part handbooks."""

    SINGLE = "single"
    PARTE_1 = "part1"
    PARTE_2_DEDUCCIONES_AUTONOMICAS = "part2-deducciones-autonomicas"
    PARTE_3 = "part3"
