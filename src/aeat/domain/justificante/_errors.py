"""Error hierarchy for the justificante parser (#44, #305).

All errors inherit from :class:`aeat._pdf_import.PdfFilingImportError` —
the shared root for every PDF-import module — which in turn inherits
:class:`aeat.errors.AeatError`. Callers catching either level continue
to work unchanged.
"""

from __future__ import annotations

from ...adapters.inbound.pdf._errors import PdfFilingImportError


class JustificanteError(PdfFilingImportError):
    """Base class for every justificante-related failure."""


class JustificanteParseError(JustificanteError):
    """Raised when a PDF cannot be parsed into a :class:`Justificante`."""


class JustificanteCsvNotFoundError(JustificanteParseError):
    """Raised when a PDF does not contain a Código Seguro de Verificación."""


class JustificanteVerificationError(JustificanteError):
    """Raised when the live CSV verification round-trip fails."""
