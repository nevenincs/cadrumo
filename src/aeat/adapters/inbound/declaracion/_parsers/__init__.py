"""PDF backend implementations for the declaración parser.

``_pdfplumber_backend.py`` extracts per-page text via pdfplumber, the
default backend. Additional backends (pypdf AcroForm, OCR) land in
later phases.
"""

from __future__ import annotations

from ._pdfplumber_backend import extract_pages_text

__all__ = ["extract_pages_text"]
