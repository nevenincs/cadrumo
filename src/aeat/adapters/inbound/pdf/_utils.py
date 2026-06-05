"""Shared low-level helpers used by every PDF-import family adapter.

Hosts utilities that several inbound parsers (declaracion, borrador,
justificante) consume identically — keeping them here prevents the same
helper being re-implemented in each per-format module.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from ....domain.justificante import PdfModeloImportError

_logger = logging.getLogger(__name__)
_HASH_CHUNK_SIZE = 65536
_INPUT_PDF_SOURCE_LABEL = "<input-pdf>"
_SOURCE_REFERENCE_ROOT = Path(".secure-source")


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of the bytes at ``path``.

    Reads in 64 KiB chunks so PDFs larger than process memory still hash
    cleanly. Use this instead of inline ``hashlib.sha256(path.read_bytes())``
    when you need a stable digest of an on-disk artefact.
    """
    digest = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(_HASH_CHUNK_SIZE), b""):
                digest.update(chunk)
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
    return digest.hexdigest()


def source_pdf_reference_path(source_pdf_sha256: str) -> Path:
    """Return the persisted source reference path for a parsed PDF digest.

    The returned value is intentionally not the operator's local filesystem
    path. Parser records can persist it as provenance without disclosing the
    source directory or filename.
    """
    return _SOURCE_REFERENCE_ROOT / f"{source_pdf_sha256}.pdf"


__all__ = ["sha256_file", "source_pdf_reference_path"]
