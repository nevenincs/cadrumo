"""Public :func:`parse_borrador` entry point for Modelo 100 PDFs.

Composes the artefact-kind detector
(:func:`aeat.adapters.inbound.borrador._detect.detect_artefact_kind`)
with the per-año extractor registry
(:mod:`aeat.adapters.inbound.borrador._extractors`) into the single
function callers should depend on.
"""

from __future__ import annotations

from pathlib import Path

from ....core.logging import get_logger
from ._detect import detect_artefact_kind
from ._errors import BorradorParseError
from ._extractors import get_extractor
from ._schema import (
    ArtefactKind,
    BorradorExtractionProfile,
    BorradorObservation,
    BorradorParseMode,
)

_logger = get_logger(__name__)


def parse_borrador(
    pdf_path: Path,
    *,
    artefact_kind_override: ArtefactKind | None = None,
    año_override: int | None = None,
    extraction_profile: BorradorExtractionProfile | None = None,
    parse_mode: BorradorParseMode = BorradorParseMode.OBSERVED,
) -> BorradorObservation:
    """Parse an AEAT Modelo 100 artefact PDF.

    Args:
        pdf_path: Path to the borrador / predeclaración / declaración PDF.
        artefact_kind_override: Skip auto-detection and force the kind.
        año_override: Skip auto-detection of the tax year and force it.
        extraction_profile: Optional registry extraction profile. When
            provided, parsing filters to the profile's target casillas and
            fails when coverage is below the registry minimum.
        parse_mode: ``OBSERVED`` returns observed PDF rows. ``REGISTRY_PROFILE``
            requires ``extraction_profile`` and validates coverage.

    Returns:
        A strict :class:`~aeat.adapters.inbound.borrador._schema.BorradorObservation`
        with observed casilla rows extracted.

    Raises:
        BorradorParseError: When the PDF has no recognisable VISTA PREVIA / BORRADOR /
            CSV marker and ``artefact_kind_override`` is not supplied, or for other
            parse errors (PDF not found, empty text, missing header fields).
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
