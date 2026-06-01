"""PDF backend implementations for the borrador parser.

Re-exports ``extract_pages_text`` from the active backend
implementation. Today the only backend is the pdfplumber-based
``_pdfplumber_backend``.
"""

from __future__ import annotations

from ._pdfplumber_backend import extract_pages_text

__all__ = ["extract_pages_text"]
