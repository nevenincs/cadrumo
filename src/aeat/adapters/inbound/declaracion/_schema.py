"""Strict pydantic v2 records for the declaración parser.

Defines the boundary types every extractor produces — the
:class:`TemplateRevision` triple that identifies an AEAT template
revision, the :class:`ExtractionWarning` advisory record, the
:class:`ExtractionStatus` coverage verdict, and the top-level
:class:`DeclaracionFiling` aggregate. All models are frozen and
``extra="forbid"`` so accidental field drift surfaces at validation
time.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..pdf._shared import ExtractedCasilla

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class ExtractionStatus(StrEnum):
    """Completion level of an extraction run.

    Attributes:
        COMPLETE: Every required casilla (per schema) was resolved AND
            the extractor had a non-empty required set. A COMPLETE
            filing with ``values=()`` is an invariant violation and MUST
            NOT occur.
        PARTIAL: At least 50% of required casillas resolved; remainder
            recorded as :class:`ExtractionWarning`.
        FAILED: Fewer than 50% of required casillas resolved.
        UNVERIFIABLE: The extractor recognised the document (NIF /
            ejercicio / período captured) but exposes no casilla-level
            data — either because the scope is header-only pending a
            text-value primitive (e.g. Modelos 036, 037, 232, 369, 720,
            840), or because the required set was empty by construction.
            Downstream consumers MUST NOT treat ``UNVERIFIABLE`` as a
            successful verification; tax-law calculations based on zero
            values are meaningless.
    """

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNVERIFIABLE = "UNVERIFIABLE"


class TemplateRevision(BaseModel):
    """Detected or caller-resolved declaration template identity.

    Identifies modelo, ejercicio, and revision tag discovered during
    detection. It is resolved against validated registry snapshots for
    casilla-complete extraction coverage.

    Attributes:
        modelo: Stable modelo identifier (``"130"``, ``"303"``, ...).
        año: Tax year as a four-digit integer (2000-2099).
        revision: Intra-año revision tag (``"2025.01"``,
            ``"2024.orden-819"``, ...).
        detected_from: How this triple was resolved — ``"header"`` /
            ``"footer"`` / ``"filename"`` for auto-detection, or
            ``"explicit_override"`` for caller-supplied values.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    año: int = Field(ge=2000, le=2099)
    revision: str = Field(min_length=1, max_length=32)
    detected_from: Literal["header", "footer", "filename", "explicit_override"] = "header"


class ExtractionWarning(BaseModel):
    """One advisory emitted during extraction.

    Captures non-fatal extraction conditions (casilla missing, label
    ambiguous, value unparseable, bbox fallback used, ...). Surfaces in
    :attr:`DeclaracionFiling.warnings`.

    Attributes:
        casilla_id: The affected casilla identifier, or ``None`` when
            the warning is global (not tied to a specific casilla).
        code: Short stable identifier for the warning class
            (``"casilla-not-found"``, ``"value-unparseable"``,
            ``"ambiguous-label"``, ...).
        message: str human-readable description.
        primitive_attempted: Which extraction primitive produced the
            warning — ``"acroform"`` / ``"label_regex"`` / ``"bbox"`` /
            ``"ocr"`` / ``"merged"``.
    """

    model_config = _STRICT_FROZEN

    casilla_id: str | None
    code: str = Field(min_length=1)
    message: str
    primitive_attempted: Literal["acroform", "label_regex", "bbox", "ocr", "merged"]


class DeclaracionFiling(BaseModel):
    """Parsed casilla-complete declaración PDF.

    Attributes:
        modelo: Stable modelo identifier (``"130"``, ``"303"``, …).
        period: Canonical period (``"2026Q1"`` / ``"2026-01"`` / ``"2026A"``).
        ejercicio: Four-digit tax year as printed on the receipt.
        tax_id: NIF / NIE of the filer (as printed).
        template_revision: Which AEAT template the PDF matches.
        values: Tuple of :class:`ExtractedCasilla` records, one per
            resolved casilla. Order follows the schema's casilla ordering.
        warnings: Tuple of advisories — unresolved casillas, ambiguous
            labels, bbox fallbacks, etc.
        source_pdf_path: Absolute path of the source PDF.
        source_pdf_sha256: Lowercase hex SHA-256 of the source PDF bytes.
        parsed_at: UTC timestamp at parse completion.
        extraction_status: Coverage verdict — COMPLETE / PARTIAL / FAILED.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    ejercicio: str = Field(min_length=4, max_length=4)
    tax_id: str = Field(min_length=4, max_length=32)
    template_revision: TemplateRevision
    values: tuple[ExtractedCasilla, ...]
    warnings: tuple[ExtractionWarning, ...] = ()
    source_pdf_path: Path
    source_pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parsed_at: datetime
    extraction_status: ExtractionStatus
