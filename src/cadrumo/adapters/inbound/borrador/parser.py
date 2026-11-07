"""Public :func:`parse_borrador` entry point for Modelo 100 PDFs.

Reads the PDF's page text once and composes the artefact-kind detector
(:func:`~adapters.inbound.borrador.detect.detect_artefact_kind_from_pages`) with the
observed-value extractor into the single function callers should depend on. The parser
does not infer the tax year from the PDF: every caller names the filing year, and the
pinned support envelope decides whether it is inside what the product claims. The row
grammar does not vary by year, so the year selects no implementation.

Unlike the declaración parser, this adapter does not resolve registry snapshots.
The default parse mode returns observed PDF rows. Registry-profile validation is
available only when the caller supplies a
:class:`~adapters.inbound.borrador.schema.BorradorExtractionProfile`
projection explicitly.
"""

from __future__ import annotations

from pathlib import Path

from ....core.hashing import sha256_hex
from ....core.logging import get_logger
from ....domain.calculations.registry.schema_references import TemporalSupportEnvelope
from ..pdf.page_text_extraction import extract_pages_text_from_bytes
from ..pdf.source_provenance import sha256_file
from .detect import detect_artefact_kind_from_pages
from .errors import BorradorParseError
from .extractors.modelo_100_summary import Modelo100ObservedExtractor
from .parsers.pdfplumber_backend import extract_pages_text
from .schema import (
    ArtefactKind,
    BorradorExtractionProfile,
    BorradorParseMode,
    InboundBorradorObservation,
)

_logger = get_logger(__name__)


def parse_borrador(
    pdf_path: Path | bytes,
    *,
    filing_year: int,
    supported_filing_years: TemporalSupportEnvelope,
    artefact_kind_override: ArtefactKind | None = None,
    extraction_profile: BorradorExtractionProfile | None = None,
    parse_mode: BorradorParseMode = BorradorParseMode.OBSERVED,
) -> InboundBorradorObservation:
    """Parse an observed AEAT Modelo 100 artefact PDF.

    Args:
        pdf_path: Path to the borrador / predeclaración / declaración PDF, or its observed bytes.
        filing_year: The filing year the caller reads this artefact for.
        supported_filing_years: The pinned authority's support envelope; a year outside
            its hard gates is refused before any PDF work.
        artefact_kind_override: Skip auto-detection and force the
            :class:`~adapters.inbound.borrador.schema.ArtefactKind`.
        extraction_profile: Optional caller-supplied registry extraction-profile
            projection. When provided, parsing filters to the profile's target
            casillas and fails when coverage is below the profile minimum.
        parse_mode: ``OBSERVED`` returns observed PDF rows. ``REGISTRY_PROFILE``
            requires ``extraction_profile`` and validates coverage.

    Returns:
        A strict :class:`~adapters.inbound.borrador.schema.InboundBorradorObservation`
        with observed casilla rows extracted.

    Raises:
        BorradorParseError: When ``filing_year`` is outside the support envelope,
            when the PDF has no recognisable VISTA PREVIA / BORRADOR /
            CSV marker and ``artefact_kind_override`` is not supplied, or for other
            parse errors (PDF not found, empty text, missing header fields,
            missing registry profile in ``REGISTRY_PROFILE`` mode, or coverage
            below the supplied profile minimum).
    """
    if not supported_filing_years.admits_coordinate(filing_year):
        raise BorradorParseError(f"filing year {filing_year} is outside the supported filing years")
    if isinstance(pdf_path, bytes):
        return _parse_borrador_bytes(
            pdf_path,
            filing_year=filing_year,
            artefact_kind_override=artefact_kind_override,
            extraction_profile=extraction_profile,
            parse_mode=parse_mode,
        )
    path = Path(pdf_path)
    if parse_mode is BorradorParseMode.REGISTRY_PROFILE and extraction_profile is None:
        raise BorradorParseError("registry-profile parsing requires a registry extraction profile")

    pages: tuple[str, ...] | None = None
    if artefact_kind_override is None:
        pages = extract_pages_text(path)
        artefact_kind = detect_artefact_kind_from_pages(pages)
    else:
        artefact_kind = artefact_kind_override
    _logger.debug("parse_borrador: source=<input-pdf> kind=%s año=%d", artefact_kind, filing_year)

    if pages is None:
        pages = extract_pages_text(path)
    result = Modelo100ObservedExtractor().extract_pages(
        pages,
        artefact_kind,
        source_pdf_sha256=sha256_file(path),
        extraction_profile=extraction_profile,
    )
    _logger.info(
        "parse_borrador: parsed source=<input-pdf> kind=%s año=%d",
        artefact_kind,
        filing_year,
    )
    return result


def _parse_borrador_bytes(
    pdf_bytes: bytes,
    *,
    filing_year: int,
    artefact_kind_override: ArtefactKind | None = None,
    extraction_profile: BorradorExtractionProfile | None = None,
    parse_mode: BorradorParseMode = BorradorParseMode.OBSERVED,
) -> InboundBorradorObservation:
    """Parse one in-memory PDF capture, sharing detection and extraction text."""
    if parse_mode is BorradorParseMode.REGISTRY_PROFILE and extraction_profile is None:
        raise BorradorParseError("registry-profile parsing requires a registry extraction profile")
    pages = extract_pages_text_from_bytes(
        pdf_bytes, error_class=BorradorParseError, pdf_label="PDF", source_label="<input-pdf>"
    )
    artefact_kind = artefact_kind_override or detect_artefact_kind_from_pages(pages)
    _logger.debug("parse_borrador: source=<input-pdf> kind=%s año=%d", artefact_kind, filing_year)
    return Modelo100ObservedExtractor().extract_pages(
        pages,
        artefact_kind,
        source_pdf_sha256=sha256_hex(pdf_bytes),
        extraction_profile=extraction_profile,
    )


__all__ = ["parse_borrador"]
