"""Error hierarchy for the borrador parser (EPIC #305 cluster F)."""

from __future__ import annotations

from ..pdf._errors import PdfFilingImportError


class BorradorParseError(PdfFilingImportError):
    """Raised when a Modelo 100 PDF cannot be parsed into a :class:`BorradorFiling`."""


class ArtefactNotRecognisedError(BorradorParseError):
    """Raised when the PDF does not match any known Modelo 100 artefact shape."""
