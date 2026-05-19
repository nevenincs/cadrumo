"""Error hierarchy for the justificante parser.

Defines the typed exceptions raised by :mod:`aeat.domain.justificante`
when a PDF filing receipt cannot be parsed, when no Código Seguro de
Verificación is present, or when the live AEAT verification round-trip
fails. Every class derives from :class:`PdfModeloImportError` so PDF
filing import callers can catch the whole domain at once.
"""

from __future__ import annotations

from ...core.errors import AeatError


class PdfModeloImportError(AeatError):
    """Domain-level root for PDF filing import failures."""


class JustificanteError(PdfModeloImportError):
    """Base class for every justificante-related failure."""


class JustificanteParseError(JustificanteError):
    """Raised when a PDF cannot be parsed into a :class:`Justificante`."""


class JustificanteCsvNotFoundError(JustificanteParseError):
    """Raised when a PDF does not contain a Código Seguro de Verificación."""


class JustificanteVerificationError(JustificanteError):
    """Raised when the live CSV verification round-trip fails."""
