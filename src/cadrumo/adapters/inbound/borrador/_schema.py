"""Strict pydantic v2 records for the Renta / Modelo 100 parser.

Defines the inbound data shapes that the borrador pipeline produces. These
records are observed-data contracts; registry authority stays with callers that
project a profile into :class:`BorradorExtractionProfile`.

- :class:`ArtefactKind` — three Modelo 100 PDF flavours.
- :class:`BorradorParseMode` — observed rows versus caller-supplied
  registry-profile validation.
- :class:`BorradorExtractionProfile` — lightweight protocol projected by the
  caller from registry metadata when completeness checks are required.
- :class:`InboundBorradorObservation` — parsed observed record with printed
  casillas, source provenance and per-casilla advisory warnings.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from ....core.casilla_id import CasillaId
from ....core.identity import AeatCsv, ContentDigest
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
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
    """Parser authority mode requested by the caller.

    Attributes:
        OBSERVED: Return the casilla rows printed in the PDF without minimum
            coverage enforcement.
        REGISTRY_PROFILE: Require a caller-supplied
            :class:`BorradorExtractionProfile`, filter to its target casillas,
            and enforce its minimum coverage without consulting a registry
            snapshot inside the adapter.
    """

    OBSERVED = "observed"
    REGISTRY_PROFILE = "registry_profile"


class BorradorExtractionTarget(Protocol):
    """Per-target descriptor surface the parser reads from a profile.

    This protocol is intentionally narrow so callers can project registry
    targets without making the inbound adapter depend on registry internals.
    Only the stable casilla identifier is needed by the observed-value filter.
    """

    @property
    def casilla_id(self) -> CasillaId: ...


class BorradorExtractionProfile(Protocol):
    """Registry extraction-profile surface consumed by the parser.

    The parser consumes this structural protocol only when
    :class:`BorradorParseMode.REGISTRY_PROFILE` is requested. It is supplied by
    the caller; the inbound adapter does not look up
    :class:`~domain.calculations.registry.RegistrySnapshot` data itself.
    """

    @property
    def id(self) -> str: ...

    @property
    def target_casillas(self) -> tuple[BorradorExtractionTarget, ...]: ...

    @property
    def min_coverage(self) -> Decimal: ...


class InboundBorradorObservation(BaseModel):
    """Observed Modelo 100 PDF data.

    Strict, frozen pydantic record produced by
    :func:`adapters.inbound.borrador.parse_borrador`.

    Attributes:
        modelo: Always ``"100"`` for this record.
        ejercicio: Four-digit tax year.
        tax_id: NIF / NIE of the filer.
        artefact_kind: Which of the three PDF types was detected.
        values: Tuple of
            :class:`~adapters.inbound.pdf.ExtractedCasilla` records
            observed in the PDF.
        registry_extraction_profile_id: Registry extraction profile applied
            to this parse, when the caller requested coverage validation.
        extraction_coverage: Observed target-casilla coverage when a
            registry extraction profile was supplied.
        source_pdf_path: Privacy-preserving ``.secure-source/<sha256>.pdf``
            reference derived from the parsed PDF digest.
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
    source_pdf_sha256: ContentDigest
    parsed_at: datetime
    csv: AeatCsv | None = None
    warnings: tuple[str, ...] = ()
