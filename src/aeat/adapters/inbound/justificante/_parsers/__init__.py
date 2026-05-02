"""Private parser backends for the inbound justificante adapter.

Callers outside :mod:`aeat.adapters.inbound.justificante` must never import
from here. Backends expose a common :func:`extract_text` entry point that
returns the raw concatenated text of a justificante PDF; all field-level
extraction happens in :mod:`aeat.adapters.inbound.justificante._extract`.

The dispatch is keyed on :class:`aeat.domain.justificante._schema.JustificanteParserBackend`
so adding a new backend is a matter of branching on the enum value and
importing the corresponding ``extract_text_*`` helper.
"""

from __future__ import annotations

from pathlib import Path

from .....domain.justificante._errors import JustificanteParseError
from .....domain.justificante._schema import JustificanteParserBackend


def extract_text(pdf_path: Path, backend: JustificanteParserBackend) -> str:
    """Extract concatenated text from ``pdf_path`` using ``backend``.

    Args:
        pdf_path: Absolute path to the PDF to read.
        backend: Which backend to dispatch to.

    Returns:
        The concatenated text of every page in the PDF, joined by newlines.

    Raises:
        :exc:`aeat.domain.justificante._errors.JustificanteParseError`: If
            ``backend`` is not yet implemented or the underlying library
            fails to open the PDF.
    """
    backend_value = backend.value if hasattr(backend, "value") else str(backend)
    normalized_backend = backend_value.lower()
    if normalized_backend == JustificanteParserBackend.PDFPLUMBER.value.lower():
        from ._pdfplumber_backend import extract_text_pdfplumber

        return extract_text_pdfplumber(pdf_path)
    if normalized_backend == JustificanteParserBackend.PYMUPDF.value.lower():
        raise JustificanteParseError("PYMUPDF backend is not implemented yet; use PDFPLUMBER (the default).")
    raise JustificanteParseError(f"unknown parser backend: {backend!r}")
