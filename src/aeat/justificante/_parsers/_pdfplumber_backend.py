"""pdfplumber-backed text extraction for justificante PDFs."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from ...logging import get_logger
from .._errors import JustificanteParseError

_logger = get_logger(__name__)


def extract_text_pdfplumber(pdf_path: Path) -> str:
    """Return the concatenated text of ``pdf_path`` using pdfplumber.

    Args:
        pdf_path: Path to the PDF to open.

    Returns:
        A single string with every page's ``extract_text`` result joined by
        newlines. Empty pages are skipped.

    Raises:
        JustificanteParseError: If pdfplumber cannot open the PDF.
    """
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            chunks: list[str] = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    chunks.append(text)
            return "\n".join(chunks)
    except JustificanteParseError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _logger.warning("pdfplumber failed to open %s: %s", pdf_path, exc)
        raise JustificanteParseError(f"pdfplumber failed to open {pdf_path}: {exc}") from exc
