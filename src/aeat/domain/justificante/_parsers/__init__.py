"""Private parser backends for the justificante subpackage.

Callers outside ``aeat.domain.justificante`` must never import from here — the
public surface lives at :mod:`aeat.domain.justificante`. Backends expose a common
:func:`extract_text` function that returns the raw concatenated text of a
justificante PDF; all field extraction happens in
:mod:`aeat.domain.justificante._extract`.
"""

from __future__ import annotations

from pathlib import Path

from .._errors import JustificanteParseError
from .._schema import JustificanteParserBackend


def extract_text(pdf_path: Path, backend: JustificanteParserBackend) -> str:
    """Extract concatenated text from ``pdf_path`` using ``backend``.

    Args:
        pdf_path: Absolute path to the PDF to read.
        backend: Which backend to dispatch to.

    Returns:
        The concatenated text of every page in the PDF, joined by newlines.

    Raises:
        JustificanteParseError: If ``backend`` is not yet implemented or the
            underlying library fails to open the PDF.
    """
    if backend is JustificanteParserBackend.PDFPLUMBER:
        from ._pdfplumber_backend import extract_text_pdfplumber

        return extract_text_pdfplumber(pdf_path)
    if backend is JustificanteParserBackend.PYMUPDF:
        raise JustificanteParseError("PYMUPDF backend is not implemented yet; use PDFPLUMBER (the default).")
    raise JustificanteParseError(f"unknown parser backend: {backend!r}")
