"""pdfplumber-backed text extraction for justificante PDFs.

Implements the :data:`aeat.domain.justificante._schema.JustificanteParserBackend.PDFPLUMBER`
branch of the parser dispatch in
:mod:`aeat.adapters.inbound.justificante._parsers`. Concatenates the
``page.extract_text()`` output of every non-empty page; layout-sensitive
parsing is left to the regex extractor downstream.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pdfplumber

from .....core.logging import get_logger
from .....domain.justificante._errors import JustificanteParseError

_logger = get_logger(__name__)


@contextmanager
def _suppress_pdfminer_debug_logging() -> Iterator[None]:
    logger = logging.getLogger("pdfminer")
    previous_level = logger.level
    if previous_level == logging.NOTSET or previous_level < logging.WARNING:
        logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(previous_level)


def extract_text_pdfplumber(pdf_path: Path) -> str:
    """Return the concatenated text of ``pdf_path`` using pdfplumber.

    Args:
        pdf_path: Path to the PDF to open.

    Returns:
        A single string with every page's ``extract_text`` result joined by
        newlines. Empty pages are skipped.

    Raises:
        :exc:`aeat.domain.justificante._errors.JustificanteParseError`: If
            pdfplumber cannot open the PDF.
    """
    try:
        with _suppress_pdfminer_debug_logging(), pdfplumber.open(str(pdf_path)) as pdf:
            chunks: list[str] = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    chunks.append(text)
            return "\n".join(chunks)
    except JustificanteParseError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _logger.error("pdfplumber failed to open %s", pdf_path, exc_info=True)
        raise JustificanteParseError(f"pdfplumber failed to open {pdf_path}: {exc}") from exc
