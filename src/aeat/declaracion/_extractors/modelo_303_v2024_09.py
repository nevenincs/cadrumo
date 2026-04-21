"""Modelo 303 v2024.09 extractor — post-HAC/819/2024 renumbering.

Orden HAC/819/2024 (published 2024-08-05) renumbered several Modelo
303 casillas and introduced new tipos impositivos (autoliquidación
rectificativa). Filings from period 2024-09 onward use this layout.

The casilla-ID set is a superset of the v2025 set plus the historical
literals the HAC/819 order retained. This MVP covers the same 33
casillas as v2025; drift between v2024.09 and v2025 (if any) is
captured by the separate ``revision`` key.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo303V2024Orden819Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 303 post-HAC/819/2024 (tax year 2024)."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="303",
        año=2024,
        revision="2024.orden-819",
    )
    # Same 33 casillas as v2025 — HAC/819 added tipos impositivos but did
    # not repackage the liquidación block. A phase-3 audit against real
    # anchors will widen this if needed.
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "28",
        "29",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
        "36",
        "37",
        "38",
        "39",
        "40",
        "41",
        "42",
        "43",
        "44",
        "45",
        "64",
        "65",
        "66",
        "67",
        "69",
        "71",
    )


__all__ = ["Modelo303V2024Orden819Extractor"]
