"""Inbound ``parse_justificante`` entry points.

This thin orchestration layer pairs a text backend selected by
:class:`~domain.justificante.JustificanteParserBackend` with the regex
extractor in :mod:`adapters.inbound.justificante._extract`. The extractor
turns AEAT receipt text into a strict
:class:`~domain.justificante.Justificante`; casilla-complete declaration
PDFs are intentionally out of scope for this adapter.

The filesystem route hashes the PDF before extraction. The bytes route is for
secure-storage or live-capture flows that already hold decrypted bytes and must
avoid plaintext temporary files. Both routes surface structured
:class:`~domain.justificante.JustificanteParseError` attributes for
missing, malformed, ambiguous, and coverage-related failures.
"""

from __future__ import annotations

from pathlib import Path

from ....core.hashing import sha256_hex
from ....core.logging import get_logger
from ....domain.justificante import (
    Justificante,
    JustificanteParseError,
    JustificanteParserBackend,
)
from ._extract import extract_justificante, extract_justificante_from_digest
from ._parsers.text_extraction import extract_text, extract_text_from_bytes

_logger = get_logger(__name__)
_INPUT_PDF_SOURCE_LABEL = "<input-pdf>"


def parse_justificante(
    pdf_path: Path,
    *,
    backend: JustificanteParserBackend | None = None,
) -> Justificante:
    """Parse an AEAT justificante PDF into a strict :class:`Justificante`.

    Use this filesystem entry point when the receipt PDF is already on disk.
    The downstream extractor stores a digest-derived source reference on the
    returned :class:`Justificante`, while parser-boundary failures redact the
    caller-controlled path from user-facing error messages.

    Args:
        pdf_path: Path to the justificante PDF on disk. Must exist and be
            readable.
        backend: Parser backend to use. Defaults to
            :attr:`core.config.Settings.cadrumo_justificante_parser_backend`
            when omitted.

    Returns:
        A fully populated :class:`~domain.justificante.Justificante`
        pydantic v2 record.

    Raises:
        JustificanteParseError: If the file is missing, cannot be opened, or does not
            contain the required fields.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise JustificanteParseError(
            f"justificante PDF not found: {_INPUT_PDF_SOURCE_LABEL}",
            context={"path": _INPUT_PDF_SOURCE_LABEL},
            translated_message="adapters.inbound.justificante.errors.parse_failed",
            missing=("source_pdf",),
        )

    resolved_backend = _resolve_backend(backend)

    _logger.debug("parse_justificante: source=<input-pdf> backend=%s", resolved_backend)
    resolved_pdf_path = pdf_path.resolve()
    try:
        text = extract_text(resolved_pdf_path, resolved_backend)
        return extract_justificante(text, resolved_pdf_path)
    except JustificanteParseError as exc:
        if _mentions_source_path(exc, pdf_path, resolved_pdf_path):
            _logger.debug(
                "parse_justificante: redacted path-bearing %s for source=<input-pdf>",
                type(exc).__name__,
            )
            raise _redacted_parse_error(exc) from exc
        raise


def parse_justificante_bytes(
    pdf_bytes: bytes,
    *,
    backend: JustificanteParserBackend | None = None,
) -> Justificante:
    """Parse an AEAT justificante PDF already loaded from secure storage.

    The PDF bytes are hashed in memory and passed directly to the configured
    backend, so decrypted live-capture content does not need a plaintext
    temporary file.

    Args:
        pdf_bytes: Raw justificante PDF bytes.
        backend: Parser backend to use. Defaults to
            :attr:`core.config.Settings.cadrumo_justificante_parser_backend`
            when omitted.

    Returns:
        The parsed :class:`Justificante` extracted from the PDF bytes.

    Raises:
        JustificanteParseError: If no extractable receipt text or required
            receipt fields can be read.
    """
    resolved_backend = _resolve_backend(backend)
    _logger.debug("parse_justificante_bytes: source=in-memory backend=%s", resolved_backend)
    text = extract_text_from_bytes(pdf_bytes, resolved_backend)
    return extract_justificante_from_digest(
        text,
        source_pdf_sha256=sha256_hex(pdf_bytes),
        source_label="<input-pdf>",
    )


def _resolve_backend(backend: JustificanteParserBackend | None) -> JustificanteParserBackend:
    """Resolve an explicit backend or the configured default backend."""
    if backend is not None:
        return backend
    # Deferred import: ``cadrumo.core.config`` imports the public justificante
    # surface for the ``JustificanteParserBackend`` enum, so importing
    # it at module scope would form a cycle.
    from ....core.config import load_settings

    settings = load_settings()
    return JustificanteParserBackend(settings.cadrumo_justificante_parser_backend.name)


def _mentions_source_path(
    exc: JustificanteParseError,
    original_path: Path,
    resolved_path: Path,
) -> bool:
    """Return whether ``exc`` rendered a caller-controlled filesystem path."""
    message = str(exc)
    candidates = {
        original_path.name,
        str(original_path),
        str(resolved_path),
    }
    return any(candidate and candidate in message for candidate in candidates)


def _redacted_parse_error(exc: JustificanteParseError) -> JustificanteParseError:
    """Return a redacted copy of ``exc`` preserving its structured attributes."""
    return type(exc)(
        f"justificante PDF parse failed: {_INPUT_PDF_SOURCE_LABEL}",
        context={"path": _INPUT_PDF_SOURCE_LABEL},
        translated_message="adapters.inbound.justificante.errors.parse_failed",
        missing=exc.missing,
        malformed=exc.malformed,
        ambiguous=exc.ambiguous,
        coverage=exc.coverage,
    )
