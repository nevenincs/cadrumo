"""Strict pydantic v2 records for the Renta / Modelo 100 parser.

Defines the inbound data shapes that the borrador pipeline produces:

- :class:`ArtefactKind` — three Modelo 100 PDF flavours.
- :class:`BorradorObservation` — parsed observed record with printed
  casillas, source provenance and per-casilla advisory warnings.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core import Modelo
from ....domain.calculations.registry import CasillaId
from ..pdf._shared import ExtractedCasilla


class ArtefactKind(StrEnum):
    """The three Modelo 100 PDF artefact types the operator encounters.

    Attributes:
        BORRADOR: Pre-filing draft from Portal Renta; carries casillas
            but no CSV.
        PREDECLARACION: Simulación (Renta Web Open) watermarked
            ``VISTA PREVIA``; carries no CSV.
        DECLARACION: Post-filing copy with an AEAT CSV stamp.
    """

    BORRADOR = "BORRADOR"
    PREDECLARACION = "PREDECLARACION"
    DECLARACION = "DECLARACION"


class BorradorParseMode(StrEnum):
    """Parser authority mode requested by the caller."""

    OBSERVED = "observed"
    REGISTRY_PROFILE = "registry_profile"


class BorradorExtractionTarget(Protocol):
    """Per-target descriptor surface the parser reads from a profile."""

    @property
    def casilla_id(self) -> CasillaId: ...


class BorradorExtractionProfile(Protocol):
    """Registry extraction-profile surface consumed by the parser."""

    @property
    def id(self) -> str: ...

    @property
    def target_casillas(self) -> tuple[BorradorExtractionTarget, ...]: ...

    @property
    def min_coverage(self) -> Decimal: ...


class BorradorObservation(BaseModel):
    """Observed Modelo 100 PDF data.

    Strict, frozen pydantic record produced by
    :func:`aeat.adapters.inbound.borrador.parse_borrador`.

    Attributes:
        modelo: Always ``"100"`` for this record.
        ejercicio: Four-digit tax year.
        tax_id: NIF / NIE of the filer.
        artefact_kind: Which of the three PDF types was detected.
        values: Tuple of
            :class:`~aeat.adapters.inbound.pdf._shared.ExtractedCasilla`
            records observed in the PDF.
        registry_extraction_profile_id: Registry extraction profile applied
            to this parse, when the caller requested coverage validation.
        extraction_coverage: Observed target-casilla coverage when a
            registry extraction profile was supplied.
        source_pdf_path: Privacy-preserving source reference derived from
            the parsed PDF digest.
        source_pdf_sha256: Lowercase hex SHA-256 of source bytes.
        parsed_at: UTC timestamp at parse completion.
        csv: AEAT CSV if the artefact is a ``DECLARACION``; ``None`` for
            borrador / predeclaración.
        warnings: Per-casilla advisory messages emitted by the extractor
            (for example ``"casilla 0622: value 'unparseable' is not a
            number"``).
    """

    model_config = _STRICT_FROZEN

    modelo: Literal[Modelo.M100] = Modelo.M100
    ejercicio: str = Field(min_length=4, max_length=4)
    tax_id: str = Field(min_length=4, max_length=32)
    artefact_kind: ArtefactKind
    values: tuple[ExtractedCasilla, ...]
    registry_extraction_profile_id: str | None = None
    extraction_coverage: Decimal | None = None
    source_pdf_path: Path
    source_pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parsed_at: datetime
    csv: str | None = None
    warnings: tuple[str, ...] = ()
