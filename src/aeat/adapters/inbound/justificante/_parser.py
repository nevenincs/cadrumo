"""Inbound :func:`parse_justificante` entry point.

Thin orchestration layer that pairs a parser backend
(:class:`aeat.domain.justificante._schema.JustificanteParserBackend`) with
the regex extractor in :mod:`aeat.adapters.inbound.justificante._extract` to
turn a justificante PDF on disk into a strict :class:`Justificante` record.
The default backend is read from
:attr:`aeat.core.config.Settings.aeat_justificante_parser_backend` when the
caller does not supply one.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ....core.logging import get_logger
from ....domain.justificante._errors import JustificanteParseError
from ....domain.justificante._schema import Justificante, JustificanteParserBackend
from ._extract import extract_justificante, extract_justificante_from_digest
from ._parsers import extract_text, extract_text_from_bytes

_logger = get_logger(__name__)
_INPUT_PDF_SOURCE_LABEL = "<input-pdf>"


def parse_justificante(
    pdf_path: Path,
    *,
    backend: JustificanteParserBackend | None = None,
) -> Justificante:
    """Parse an AEAT justificante PDF into a strict :class:`Justificante`.

    Args:
        pdf_path: Path to the justificante PDF on disk. Must exist and be
            readable.
        backend: Parser backend to use. Defaults to
            :attr:`aeat.core.config.Settings.aeat_justificante_parser_backend`
            when omitted.

    Returns:
        A fully populated :class:`aeat.domain.justificante._schema.Justificante`
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

    Returns:
        The parsed :class:`Justificante` extracted from the PDF bytes.
    """
    resolved_backend = _resolve_backend(backend)
    _logger.debug("parse_justificante_bytes: source=in-memory backend=%s", resolved_backend)
    text = extract_text_from_bytes(pdf_bytes, resolved_backend)
    return extract_justificante_from_digest(
        text,
        source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        source_label="<input-pdf>",
    )


def _resolve_backend(backend: JustificanteParserBackend | None) -> JustificanteParserBackend:
    if backend is not None:
        return backend
    # Deferred import: ``aeat.core.config`` imports the public justificante
    # surface for the ``JustificanteParserBackend`` enum, so importing
    # it at module scope would form a cycle.
    from ....core.config import load_settings

    settings = load_settings()
    return JustificanteParserBackend(settings.aeat_justificante_parser_backend.name)


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
