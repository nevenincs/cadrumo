"""Shared low-level helpers used by every PDF-import family adapter.

Hosts utilities that several inbound parsers (declaracion, borrador,
justificante) consume identically — keeping them here prevents the same
helper being re-implemented in each per-format module.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ....core.hashing import sha256_file as _core_sha256_file
from ....domain.justificante import PdfModeloImportError

_logger = logging.getLogger(__name__)
_INPUT_PDF_SOURCE_LABEL = "<input-pdf>"
_SOURCE_REFERENCE_ROOT = Path(".secure-source")


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of the bytes at ``path``.

    Delegates to the canonical chunked file digest, wrapping the ``OSError``
    raised on an unreadable artefact in the PDF-import error so callers see the
    translated message rather than a raw OS failure.
    """
    try:
        return _core_sha256_file(path)
    except OSError as exc:
        _logger.debug(
            "sha256_file: source=%s failure=%s",
            _INPUT_PDF_SOURCE_LABEL,
            type(exc).__name__,
        )
        raise PdfModeloImportError(
            f"PDF file could not be hashed: {_INPUT_PDF_SOURCE_LABEL}",
            context={"path": _INPUT_PDF_SOURCE_LABEL},
            translated_message="adapters.inbound.pdf.errors.hash_failed",
        ) from None


def source_pdf_reference_path(source_pdf_sha256: str) -> Path:
    """Return the persisted source reference path for a parsed PDF digest.

    The returned value is intentionally not the operator's local filesystem
    path. Parser records can persist it as provenance without disclosing the
    source directory or filename.
    """
    return _SOURCE_REFERENCE_ROOT / f"{source_pdf_sha256}.pdf"


__all__ = ["sha256_file", "source_pdf_reference_path"]
