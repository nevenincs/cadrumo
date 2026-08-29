"""Strict pydantic v2 schema for parsed AEAT justificantes.

The :class:`Justificante` record is the boundary-crossing type consumed
by downstream subpackages (the submission engine and the status
reader). It is *frozen* and *strict* so callers can rely on
deterministic field types, and so mutating it after parse requires an
explicit :meth:`pydantic.BaseModel.model_copy`.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, Field, ValidationInfo, field_validator

from ...core import STRICT_FROZEN_CONFIG, Period, PeriodError
from ...core.identity import AeatCsv, AeatPresentationId, ContentDigest, SubjectTaxId, same_tax_identifier
from ...core.time import UtcInstant


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
            the modelo catalogue in :mod:`domain.modelos`.
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

    csv: AeatCsv
    modelo: str = Field(..., min_length=1, max_length=16)
    ejercicio: str | None = Field(default=None, max_length=8)
    period: Period
    presentation_id: AeatPresentationId | None = None
    presented_at: UtcInstant
    tax_id: SubjectTaxId
    total_a_ingresar: Decimal | None = None
    total_a_devolver: Decimal | None = None
    verification_url: AnyHttpUrl
    source_pdf_path: Path
    source_pdf_sha256: ContentDigest
    parsed_at: UtcInstant

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

    def matches_filing_target(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        tax_id: str | None = None,
    ) -> bool:
        """Return whether this receipt belongs to one filing target.

        ``tax_id`` is an optional refinement for receipt sources that do not
        expose that axis.

        Verifying that the receipt is the one AEAT issued for a filing is the
        caller's job, and it is a :attr:`csv` comparison against a csv the
        caller obtained from somewhere other than this PDF. This predicate
        deliberately offers no parameter for that axis: the only receipt
        identifier printed beside the csv is
        :attr:`presentation_id`, AEAT's *Número de justificante*, and the
        values callers actually hold are register-issued expediente ids from
        *Consultar declaraciones presentadas* — a different AEAT namespace that
        never appears on a receipt body, so no caller could populate such a
        parameter correctly.
        """
        return (
            self.modelo.strip() == modelo.strip()
            and str(self.ejercicio or "").strip() == str(filing_year)
            and self.period == period
            and (tax_id is None or same_tax_identifier(self.tax_id, tax_id))
        )
