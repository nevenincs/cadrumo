"""Error hierarchy for the justificante parser.

Defines the typed exceptions raised by :mod:`aeat.domain.justificante`
when a PDF filing receipt cannot be parsed, when no Código Seguro de
Verificación is present, or when the live AEAT verification round-trip
fails. Every class derives from :class:`PdfModeloImportError` so PDF
filing import callers can catch the whole domain at once.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.errors import AeatError


class PdfModeloImportError(AeatError):
    """Domain-level root for PDF filing import failures."""


class JustificanteError(PdfModeloImportError):
    """Base class for every justificante-related failure."""


class JustificanteParseError(JustificanteError):
    """Raised when a PDF cannot be parsed into a :class:`Justificante`.

    Mirrors :class:`aeat.adapters.inbound.declaracion._errors.DeclaracionParseError`'s
    structured-attribute shape so callers can assert on typed attributes rather than
    parsing the message string.

    When the error originates from a field-extraction failure the following
    structured attributes are populated:

    Attributes:
        missing: Tuple of field names that produced no match in the PDF text.
        malformed: Tuple of field names whose captured value could not be coerced
            to the target type (e.g. an invalid decimal literal).
        ambiguous: Tuple of field names that matched more than one region.
        coverage: Fraction of required fields successfully extracted
            (``Decimal``).  ``None`` when the error is not a coverage failure.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: str | None = None,
        missing: tuple[str, ...] = (),
        malformed: tuple[str, ...] = (),
        ambiguous: tuple[str, ...] = (),
        coverage: Decimal | None = None,
    ) -> None:
        """Initialise the error with optional structured field-extraction context.

        Args:
            message: Human-readable error message.
            context: Optional structured context forwarded to the
                :class:`~aeat.core.errors.AeatError` boundary.
            suggestion: Optional copy-paste recovery hint forwarded to
                :class:`~aeat.core.errors.AeatError`.
            translated_message: Optional locale key rendered at the CLI
                boundary.
            missing: Field names that produced no match in the PDF text.
            malformed: Field names whose captured value could not be coerced.
            ambiguous: Field names that matched more than one region.
            coverage: Fraction of required fields successfully extracted,
                or ``None`` when the error is not a coverage failure.
        """
        super().__init__(
            message,
            context=context,
            suggestion=suggestion,
            translated_message=translated_message,
        )
        self.missing: tuple[str, ...] = missing
        self.malformed: tuple[str, ...] = malformed
        self.ambiguous: tuple[str, ...] = ambiguous
        self.coverage: Decimal | None = coverage


class JustificanteCsvNotFoundError(JustificanteParseError):
    """Raised when a PDF does not contain a Código Seguro de Verificación."""


class JustificanteVerificationError(JustificanteError):
    """Raised when the live CSV verification round-trip fails."""
