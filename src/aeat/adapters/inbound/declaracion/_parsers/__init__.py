"""PDF backend implementations for the declaración parser.

:mod:`aeat.adapters.inbound.declaracion._parsers._pdfplumber_backend`
extracts per-page text via pdfplumber and is the default backend.
Additional backends (pypdf AcroForm, OCR) plug in alongside it as
extraction needs grow.
"""

from __future__ import annotations

from ._pdfplumber_backend import extract_pages_text, extract_pages_text_from_bytes

__all__ = ["extract_pages_text", "extract_pages_text_from_bytes"]
