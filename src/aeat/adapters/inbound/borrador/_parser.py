"""Public ``parse_borrador`` entry point for Modelo 100 PDFs (#305)."""

from __future__ import annotations

from pathlib import Path

from ._detect import detect_artefact_kind
from ._extractors import get_extractor
from ._schema import ArtefactKind, BorradorFiling


def parse_borrador(
    pdf_path: Path,
    *,
    artefact_kind_override: ArtefactKind | None = None,
    año_override: int | None = None,
) -> BorradorFiling:
    """Parse an AEAT Modelo 100 artefact PDF.

    Args:
        pdf_path: Path to the borrador / predeclaración / declaración PDF.
        artefact_kind_override: Skip auto-detection and force the kind.
        año_override: Skip auto-detection of the tax year and force it.

    Returns:
        A strict :class:`BorradorFiling` with the summary-block casillas
        extracted.

    Raises:
        ArtefactNotRecognisedError: When the PDF has no recognisable
            VISTA PREVIA / BORRADOR / CSV marker and no override is
            supplied.
        BorradorParseError: Base class for other parse errors (PDF not
            found, empty text, missing header fields).
    """
    path = Path(pdf_path)

    artefact_kind = artefact_kind_override or detect_artefact_kind(path)

    extractor = get_extractor(año_override or 2025)  # MVP supports 2025 only
    return extractor.extract(path, artefact_kind)


__all__ = ["parse_borrador"]
