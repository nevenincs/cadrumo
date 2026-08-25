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
from typing import cast

from ...core.errors import CadrumoError


class PdfModeloImportError(CadrumoError):
    """Domain-level root for PDF filing import failures."""


class PdfExtractionCoverageMixin:
    """Shared structured-attribute ``__init__`` for PDF extraction coverage failures.

    Both the justificante and declaración PDF parsers raise a coverage error
    that carries the same four structured attributes describing which target
    fields (field names for justificante, casilla IDs for declaración) could
    not be extracted cleanly. Mixing this in once keeps the attribute shape
    and constructor signature identical across both parser error hierarchies
    instead of each declaring its own copy.

    Attributes:
        missing: Tuple of target identifiers that produced no match in the PDF text.
        malformed: Tuple of target identifiers whose captured value could not be
            coerced to the target type (e.g. an invalid decimal literal).
        ambiguous: Tuple of target identifiers that matched more than one region.
        coverage: Fraction of required targets successfully extracted
            (``Decimal``).  ``None`` when the error is not a coverage failure.
    """

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
        """Initialise the error with optional structured extraction-coverage context.

        Args:
            message: Human-readable error message.
            context: Optional structured context forwarded to the
                :class:`core.errors.CadrumoError` boundary.
            translated_message: Optional locale key rendered at the CLI
                boundary.
            missing: Target identifiers that produced no match in the PDF text.
            malformed: Target identifiers whose captured value could not be coerced.
            ambiguous: Target identifiers that matched more than one region.
            coverage: Fraction of required targets successfully extracted,
                or ``None`` when the error is not a coverage failure.
        """
        # CAST-RATIONALE-PDF-COVERAGE-MRO: cooperative super resolves the CadrumoError initializer in this mixin MRO.
        error_base = cast(  # nosemgrep: no-cast-in-domain-application reason: MRO targets CadrumoError.
            CadrumoError,
            super(),
        )
        error_base.__init__(
            message,
            context=context,
            translated_message=translated_message,
        )
        self.missing: tuple[str, ...] = missing
        self.malformed: tuple[str, ...] = malformed
        self.ambiguous: tuple[str, ...] = ambiguous
        self.coverage: Decimal | None = coverage


class JustificanteError(PdfModeloImportError):
    """Base class for every justificante-related failure."""


class JustificanteParseError(PdfExtractionCoverageMixin, JustificanteError):
    """Raised when a PDF cannot be parsed into a :class:`Justificante`.

    Mirrors :class:`adapters.inbound.declaracion.DeclaracionParseError`'s
    structured-attribute shape (via the shared :class:`PdfExtractionCoverageMixin`)
    so callers can assert on typed attributes rather than parsing the message
    string.
    """


class JustificanteCsvNotFoundError(JustificanteParseError):
    """Raised when a PDF does not contain a Código Seguro de Verificación."""


class JustificanteVerificationError(JustificanteError):
    """Raised when the live CSV verification round-trip fails."""
