"""Error hierarchy for the justificante parser.

Defines the typed exceptions raised by :mod:`domain.justificante`
when a PDF filing receipt cannot be parsed, when no Código Seguro de
Verificación is present, or when the live AEAT verification round-trip
fails. Every class derives from :class:`PdfModeloImportError` so PDF
filing import callers can catch the whole domain at once.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.errors.hierarchy import CadrumoError


class PdfModeloImportError(CadrumoError):
    """Domain-level root for PDF filing import failures."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        missing: tuple[str, ...] = (),
        malformed: tuple[str, ...] = (),
        ambiguous: tuple[str, ...] = (),
        coverage: Decimal | None = None,
    ) -> None:
        """Initialise the registered error and its extraction-coverage fields."""
        super().__init__(message, context=context, translated_message=translated_message)
        self._set_extraction_coverage(
            missing=missing,
            malformed=malformed,
            ambiguous=ambiguous,
            coverage=coverage,
        )

    def _set_extraction_coverage(
        self,
        *,
        missing: tuple[str, ...] = (),
        malformed: tuple[str, ...] = (),
        ambiguous: tuple[str, ...] = (),
        coverage: Decimal | None = None,
    ) -> None:
        """Attach the shared extraction-coverage fields to a concrete error."""
        self.missing: tuple[str, ...] = missing
        self.malformed: tuple[str, ...] = malformed
        self.ambiguous: tuple[str, ...] = ambiguous
        self.coverage: Decimal | None = coverage


class JustificanteError(PdfModeloImportError):
    """Base class for every justificante-related failure."""


class JustificanteParseError(JustificanteError):
    """Raised when a PDF cannot be parsed into a :class:`Justificante`.

    Mirrors :class:`adapters.inbound.declaracion.errors.DeclaracionParseError`'s
    structured-attribute shape (via the shared :class:`PdfModeloImportError`)
    so callers can assert on typed attributes rather than parsing the message
    string.
    """


class JustificanteCsvNotFoundError(JustificanteParseError):
    """Raised when a PDF does not contain a Código Seguro de Verificación."""


class JustificanteVerificationError(JustificanteError):
    """Raised when the live CSV verification round-trip fails."""
