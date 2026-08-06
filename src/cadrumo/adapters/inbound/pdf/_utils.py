"""Shared low-level helpers used by every PDF-import family adapter.

Declaracion, borrador, and justificante parsers all need the same two
provenance operations: hash the source bytes for integrity and derive a
persistable source reference that does not expose the operator's local
filename. Keeping those helpers here prevents per-format drift in the
secure-storage boundary.
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
    raised on an unreadable artefact in the shared PDF-import error so callers
    see the translated message rather than a raw OS failure. Error messages and
    logs use ``<input-pdf>`` instead of the concrete path to avoid leaking
    source filenames through diagnostics.
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

    The returned value is ``.secure-source/<sha256>.pdf`` rather than the
    operator's local filesystem path. Parser records can persist it as
    provenance without disclosing the source directory or filename, while the
    companion digest remains the integrity coordinate for the original bytes.
    """
    return _SOURCE_REFERENCE_ROOT / f"{source_pdf_sha256}.pdf"


__all__ = ["sha256_file", "source_pdf_reference_path"]
