"""Error hierarchy for the declaración parser (EPIC #305)."""

from __future__ import annotations

from ..pdf._errors import PdfFilingImportError


class DeclaracionParseError(PdfFilingImportError):
    """Raised when a PDF cannot be parsed into a :class:`DeclaracionFiling`."""


class NoExtractorRegisteredError(DeclaracionParseError):
    """Raised when no concrete extractor exists for the detected template."""


class TemplateNotDetectedError(DeclaracionParseError):
    """Raised when :func:`detect_template_revision` cannot identify the PDF."""
