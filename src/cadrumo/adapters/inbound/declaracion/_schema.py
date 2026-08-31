"""Strict pydantic v2 records for the declaración parser.

Defines the boundary types every extractor produces — the
:class:`TemplateRevision` triple that identifies an AEAT template
revision, the :class:`ExtractionWarning` advisory record, and the
top-level :class:`InboundDeclaracionObservation` aggregate. All models are
frozen and ``extra="forbid"`` so accidental field drift surfaces at
validation time.

These records carry observations, not calculation authority. The parser stamps
current observations with a
:class:`~domain.calculations.registry.RegistrySnapshotRef` so downstream
flows can re-resolve the registry coordinate that supplied the extraction
profile.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from ....core.casilla_id import CasillaId
from ....core.filing_year import FilingYear
from ....core.identity import ContentDigest
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.period import Period, PeriodError
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ..pdf.extracted_casilla import ExtractedCasilla


class TemplateRevision(BaseModel):
    """Detected or caller-resolved declaration template identity.

    Identifies modelo, ejercicio, and revision tag discovered during detection.
    :class:`~domain.calculations.registry.RegistrySnapshot` instances
    decide whether that template is usable for extraction and verification.

    Attributes:
        modelo: Stable modelo identifier.
        año: Tax year as a four-digit integer (2000-2099).
        revision: Intra-año revision tag (``"2025.01"``,
            ``"2024.orden-819"``, ...).
        detected_from: How this triple was resolved — ``"header"`` /
            ``"footer"`` / ``"filename"`` for auto-detection, or
            ``"explicit_override"`` for caller-supplied values.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    año: FilingYear
    revision: str = Field(min_length=1, max_length=32)
    detected_from: Literal["header", "footer", "filename", "explicit_override"] = "header"


class ExtractionWarning(BaseModel):
    """One advisory emitted during extraction.

    Captures non-fatal extraction conditions (casilla missing, label
    ambiguous, value unparseable, bbox fallback used, ...). Surfaces in
    :attr:`InboundDeclaracionObservation.warnings`.

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

    casilla_id: CasillaId | None
    code: str = Field(min_length=1)
    message: str
    primitive_attempted: Literal["acroform", "label_regex", "bbox", "ocr", "merged"]


class InboundDeclaracionObservation(BaseModel):
    """Observed values parsed from a declaración PDF.

    Attributes:
        modelo: Stable modelo identifier.
        period: Typed filing period resolved from the printed AEAT token
            and ``ejercicio``.
        ejercicio: Four-digit tax year as printed on the receipt.
        tax_id: NIF / NIE of the filer (as printed).
        template_revision: Which AEAT template the PDF matches.
        registry_snapshot_ref: Four-axis registry coordinate that supplied the
            extraction profile.
        values: Tuple of observed :class:`ExtractedCasilla` records.
        warnings: Tuple of advisories — unresolved casillas, ambiguous
            labels, bbox fallbacks, etc.
        extraction_profile_id: Registry ``declaracion_pdf`` extraction profile
            id that supplied ``values``.
        extraction_profile_provisional: Stamped from the selected profile's
            ``provisional_pending_specimen`` flag. ``True`` means no real AEAT
            specimen has confirmed this modelo's printed layout, so the
            ``bbox_anchored`` anchor positions are unverified guesses;
            downstream consumers MUST disclose this to the operator rather
            than presenting the extracted values as confirmed.
        source_pdf_path: Privacy-preserving source reference derived from
            the source PDF digest.
        source_pdf_sha256: Lowercase hex SHA-256 of the source PDF bytes.
        parsed_at: UTC timestamp at parse completion.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: str = Field(min_length=4, max_length=4)
    period: Period = Field()
    tax_id: str = Field(min_length=4, max_length=32)
    template_revision: TemplateRevision
    registry_snapshot_ref: RegistrySnapshotRef
    """Four-axis registry coordinate captured at parse time.

    Populated by the parser from the active ``RegistrySnapshot`` so a
    persisted observation can be re-resolved against the live registry
    catalogue with a single
    :meth:`ValidatedRegistryAuthority.snapshot` call. Current observations
    always carry the ref so downstream checks can detect silent AEAT template
    drift on subsequent registry releases.
    """
    values: tuple[ExtractedCasilla, ...]
    warnings: tuple[ExtractionWarning, ...] = ()
    extraction_profile_id: str = Field(min_length=1, max_length=128)
    extraction_profile_provisional: bool = False
    source_pdf_path: Path
    source_pdf_sha256: ContentDigest
    parsed_at: datetime

    @field_validator("period", mode="before")
    @classmethod
    def _coerce_filing_period(cls, raw_period: object, info: ValidationInfo) -> object:
        ejercicio = info.data.get("ejercicio")
        if not isinstance(raw_period, str):
            return raw_period
        if not isinstance(ejercicio, str) or not ejercicio.isdigit():
            return raw_period

        period_code = "0A" if raw_period == ejercicio else raw_period
        try:
            return Period.from_year_and_code(int(ejercicio), period_code)
        except PeriodError:
            return raw_period
