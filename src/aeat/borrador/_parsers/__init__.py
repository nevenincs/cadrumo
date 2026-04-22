"""PDF backend implementations for the borrador parser."""

from __future__ import annotations

from ._pdfplumber_backend import extract_pages_text

__all__ = ["extract_pages_text"]
