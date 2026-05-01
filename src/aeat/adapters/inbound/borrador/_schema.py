"""Strict pydantic v2 records for the Renta / Modelo 100 parser (#305)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..pdf._shared import ExtractedCasilla

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class ArtefactKind(StrEnum):
    """Three Modelo 100 PDF artefact types Kent encounters."""

    BORRADOR = "BORRADOR"
    """Pre-filing draft from Portal Renta; carries casillas, no CSV."""
    PREDECLARACION = "PREDECLARACION"
    """Simulación (Renta Web Open) watermarked VISTA PREVIA; no CSV."""
    DECLARACION = "DECLARACION"
    """Post-filing copy with AEAT CSV stamp."""


class BorradorFiling(BaseModel):
    """Parsed Modelo 100 filing (borrador / predeclaración / declaración).

    Attributes:
        modelo: Always ``"100"`` for this record.
        ejercicio: Four-digit tax year.
        tax_id: NIF / NIE of the filer.
        artefact_kind: Which of the three PDF types was detected.
        values: Tuple of :class:`ExtractedCasilla` records — summary-block
            casillas for the MVP; full anexo coverage lands in #305-F-full.
        source_pdf_path: Absolute path of the parsed PDF.
        source_pdf_sha256: Lowercase hex SHA-256 of source bytes.
        parsed_at: UTC timestamp at parse completion.
        csv: AEAT CSV if the artefact is a DECLARACION; ``None`` for
            borrador / predeclaración.
    """

    model_config = _STRICT_FROZEN

    modelo: Literal["100"] = "100"
    ejercicio: str = Field(min_length=4, max_length=4)
    tax_id: str = Field(min_length=4, max_length=32)
    artefact_kind: ArtefactKind
    values: tuple[ExtractedCasilla, ...]
    source_pdf_path: Path
    source_pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parsed_at: datetime
    csv: str | None = None
    # Per-casilla advisory messages ( audit M2) — e.g.
    # "casilla 0622: value 'unparseable' is not a number".
    warnings: tuple[str, ...] = ()
