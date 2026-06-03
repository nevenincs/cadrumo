"""Shared strict+frozen records consumed across PDF-import modules.

:class:`ExtractedCasilla` is the boundary-crossing record every per-modelo
extractor produces. It pairs a stable casilla identifier with the printed
value the extractor read from the PDF plus provenance (page, bounding box,
confidence) so downstream consumers can classify discrepancies and attach
warnings without re-parsing the PDF.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....domain.calculations.registry import CasillaId


class ExtractedCasilla(BaseModel):
    """One casilla ID + printed value extracted from a filing PDF.

    Attributes:
        casilla_id: Stable casilla identifier (e.g. ``"01"``, ``"071"``).
            Aligned to the canonical :data:`CasillaId` constraint
            (max_length=64, pattern ``[A-Za-z0-9][A-Za-z0-9._:-]*``).
        printed_value: Typed value as printed on the PDF. ``None`` when
            the casilla was located but blank on the page.
        source_page: 1-based page number the value was read from.
        source_bbox: Optional ``(x0, y0, x1, y1)`` bounding box in
            pdfplumber coordinates. Populated by the bbox-anchored
            extraction primitive; ``None`` for label-regex / AcroForm
            extractions where coordinates are not captured.
        extraction_confidence: Float in ``[0.0, 1.0]``. ``1.0`` for
            AcroForm + unambiguous label-regex hits; lower when the
            extractor fell back to bbox-anchored recovery or had to
            disambiguate competing label candidates.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    printed_value: Decimal | int | str | bool | date | None
    source_page: int = Field(ge=1)
    source_bbox: tuple[float, float, float, float] | None = None
    extraction_confidence: float = Field(ge=0.0, le=1.0)
