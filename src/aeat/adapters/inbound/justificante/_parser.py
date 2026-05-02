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

from pathlib import Path

from ....core.logging import get_logger
from ....domain.justificante._errors import JustificanteParseError
from ....domain.justificante._schema import Justificante, JustificanteParserBackend
from ._extract import extract_justificante
from ._parsers import extract_text

_logger = get_logger(__name__)


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
        :exc:`aeat.domain.justificante._errors.JustificanteParseError`: If
            the file is missing, cannot be opened, or does not contain the
            required fields.
        :exc:`aeat.domain.justificante._errors.JustificanteCsvNotFoundError`:
            If the PDF contains no CSV (Código Seguro de Verificación).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise JustificanteParseError(f"justificante PDF not found: {pdf_path}")

    resolved_backend = backend
    if resolved_backend is None:
        # Deferred import: ``aeat.core.config`` imports the public justificante
        # surface for the ``JustificanteParserBackend`` enum, so importing
        # it at module scope would form a cycle.
        from ....core.config import load_settings

        settings = load_settings()
        resolved_backend = JustificanteParserBackend(settings.aeat_justificante_parser_backend.name)

    _logger.debug("parsing justificante %s with backend %s", pdf_path, resolved_backend)
    text = extract_text(pdf_path.resolve(), resolved_backend)
    return extract_justificante(text, pdf_path.resolve())
