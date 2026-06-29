"""Strict pydantic v2 schema for parsed AEAT justificantes.

The :class:`Justificante` record is the boundary-crossing type consumed
by downstream subpackages (the submission engine and the status
reader). It is *frozen* and *strict* so callers can rely on
deterministic field types, and so mutating it after parse requires an
explicit :meth:`pydantic.BaseModel.model_copy`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, Field, ValidationInfo, field_validator

from ...core import STRICT_FROZEN_CONFIG, Period, PeriodError


class JustificanteParserBackend(StrEnum):
    """Closed set of supported parser backends.

    Attributes:
        PDFPLUMBER: Fidelity-first default backend.
    """

    PDFPLUMBER = "PDFPLUMBER"


class Justificante(BaseModel):
    """Parsed AEAT *justificante de presentación* receipt.

    A ``Justificante`` represents a single successful filing receipt produced
    by AEAT after a modelo has been submitted. Every field is either pulled
    verbatim from the PDF body or derived deterministically from the source
    file (``source_pdf_sha256``, ``parsed_at``).

    Attributes:
        csv: Código Seguro de Verificación — the short AEAT-assigned hash
            used to verify the document on the Sede electrónica.
        modelo: String ID of the modelo the receipt belongs to. References
            the modelo catalogue in :mod:`aeat.domain.modelos`.
        period: Typed filing period resolved from the AEAT period token
            printed on the receipt and ``ejercicio``.
        ejercicio: Four-digit tax year as printed on the receipt, when
            present. ``None`` for receipts that omit the label.
        presentation_id: AEAT's internal ``Número de justificante`` if
            present on the receipt; ``None`` when the modelo does not print
            a separate presentation ID.
        presented_at: Timestamp AEAT stamped on the receipt at submission.
        tax_id: NIF/NIE of the taxpayer who filed (the *autónomo* owner).
        total_a_ingresar: Amount to be paid in, if the receipt includes one.
        total_a_devolver: Amount to be refunded, if the receipt includes one.
        verification_url: AEAT URL printed on the receipt where the CSV can
            be re-verified against the Sede electrónica.
        source_pdf_path: Privacy-preserving source reference derived from
            the source PDF digest.
        source_pdf_sha256: Lowercase hex sha-256 of the source PDF bytes.
        parsed_at: UTC wall-clock time the parse finished.
    """

    model_config = STRICT_FROZEN_CONFIG

    csv: str = Field(..., min_length=4, max_length=64)
    modelo: str = Field(..., min_length=1, max_length=16)
    ejercicio: str | None = Field(default=None, max_length=8)
    period: Period
    presentation_id: str | None = Field(default=None, max_length=64)
    presented_at: datetime
    tax_id: str = Field(..., min_length=4, max_length=32)
    total_a_ingresar: Decimal | None = None
    total_a_devolver: Decimal | None = None
    verification_url: AnyHttpUrl
    source_pdf_path: Path
    source_pdf_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    parsed_at: datetime

    @field_validator("period", mode="before")
    @classmethod
    def _coerce_printed_period(cls, raw_period: object, info: ValidationInfo) -> object:
        ejercicio = info.data.get("ejercicio")
        if not isinstance(raw_period, str):
            return raw_period
        if not isinstance(ejercicio, str) or not ejercicio.isdigit():
            return raw_period

        try:
            return Period.from_year_and_code(int(ejercicio), raw_period)
        except PeriodError:
            return raw_period
