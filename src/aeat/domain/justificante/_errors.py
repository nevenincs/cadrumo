"""Error hierarchy for the justificante parser (#44, #305)."""

from __future__ import annotations

from ...core.errors import AeatError


class PdfFilingImportError(AeatError):
    """Domain-level root for PDF filing import failures."""


class JustificanteError(PdfFilingImportError):
    """Base class for every justificante-related failure."""


class JustificanteParseError(JustificanteError):
    """Raised when a PDF cannot be parsed into a :class:`Justificante`."""


class JustificanteCsvNotFoundError(JustificanteParseError):
    """Raised when a PDF does not contain a Código Seguro de Verificación."""


class JustificanteVerificationError(JustificanteError):
    """Raised when the live CSV verification round-trip fails."""
