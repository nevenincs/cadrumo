"""Public :func:`parse_borrador` entry point for Modelo 100 PDFs.

Composes the artefact-kind detector
(:func:`~adapters.inbound.borrador._detect.detect_artefact_kind`) with the
per-año extractor registry (:mod:`adapters.inbound.borrador._extractors`)
into the single function callers should depend on. The parser does not infer
the tax year from the PDF today; callers that need a non-default year must pass
``año_override`` explicitly.

Unlike the declaración parser, this adapter does not resolve registry snapshots.
The default parse mode returns observed PDF rows. Registry-profile validation is
available only when the caller supplies a
:class:`~adapters.inbound.borrador.schema.BorradorExtractionProfile`
projection explicitly.
"""

from __future__ import annotations

from pathlib import Path

from ....core.logging import get_logger
from ._detect import detect_artefact_kind
from ._extractors.selection import get_extractor
from .schema import (
    ArtefactKind,
    BorradorExtractionProfile,
    BorradorParseMode,
    InboundBorradorObservation,
)
from .errors import BorradorParseError

_logger = get_logger(__name__)


def parse_borrador(
    pdf_path: Path,
    *,
    artefact_kind_override: ArtefactKind | None = None,
    año_override: int | None = None,
    extraction_profile: BorradorExtractionProfile | None = None,
    parse_mode: BorradorParseMode = BorradorParseMode.OBSERVED,
) -> InboundBorradorObservation:
    """Parse an observed AEAT Modelo 100 artefact PDF.

    Args:
        pdf_path: Path to the borrador / predeclaración / declaración PDF.
        artefact_kind_override: Skip auto-detection and force the
            :class:`~adapters.inbound.borrador.schema.ArtefactKind`.
        año_override: Select the year-keyed extractor explicitly. When omitted,
            the parser uses the current default extractor year (``2025``).
        extraction_profile: Optional caller-supplied registry extraction-profile
            projection. When provided, parsing filters to the profile's target
            casillas and fails when coverage is below the profile minimum.
        parse_mode: ``OBSERVED`` returns observed PDF rows. ``REGISTRY_PROFILE``
            requires ``extraction_profile`` and validates coverage.

    Returns:
        A strict :class:`~adapters.inbound.borrador.schema.InboundBorradorObservation`
        with observed casilla rows extracted.

    Raises:
        BorradorParseError: When the PDF has no recognisable VISTA PREVIA / BORRADOR /
            CSV marker and ``artefact_kind_override`` is not supplied, or for other
            parse errors (PDF not found, empty text, missing header fields,
            missing registry profile in ``REGISTRY_PROFILE`` mode, or coverage
            below the supplied profile minimum).
    """
    path = Path(pdf_path)
    if parse_mode is BorradorParseMode.REGISTRY_PROFILE and extraction_profile is None:
        raise BorradorParseError("registry-profile parsing requires a registry extraction profile")

    artefact_kind = artefact_kind_override or detect_artefact_kind(path)
    año = año_override or 2025
    _logger.debug("parse_borrador: source=<input-pdf> kind=%s año=%d", artefact_kind, año)

    extractor = get_extractor(año)
    result = extractor.extract(path, artefact_kind, extraction_profile=extraction_profile)
    _logger.info(
        "parse_borrador: parsed source=<input-pdf> kind=%s año=%d",
        artefact_kind,
        año,
    )
    return result


__all__ = ["parse_borrador"]
