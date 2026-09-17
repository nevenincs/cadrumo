"""Exception hierarchy for the declaración PDF parser.

Defines the parse-error tree raised by
:mod:`adapters.inbound.declaracion`. All exceptions descend from
:class:`~domain.justificante.errors.PdfModeloImportError` so callers can catch
the generic PDF-import boundary without needing declaración specifics.

Coverage failures carry structured ``missing`` / ``malformed`` / ``ambiguous``
/ ``coverage`` attributes mirroring the registry extraction profile contract;
callers should inspect those fields rather than parsing localized messages.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ....domain.justificante.errors import PdfExtractionCoverageMixin, PdfModeloImportError


class DeclaracionParseError(PdfExtractionCoverageMixin, PdfModeloImportError):
    """Raised when a PDF cannot be parsed into a declaración filing.

    Base class for all parse-time errors emitted by
    :func:`adapters.inbound.declaracion.parser.parse_declaracion`.
    :class:`TemplateNotDetectedError` signals a recoverable template
    detection failure; the bare class is raised for low-level failures
    (PDF unreadable, header field missing, missing registry coverage,
    etc.).

    The structured ``missing`` / ``malformed`` / ``ambiguous`` / ``coverage``
    extraction-coverage attributes (casilla IDs here, mirroring
    :class:`~domain.justificante.errors.JustificanteParseError`'s field names) come
    from the shared :class:`~domain.justificante.errors.PdfExtractionCoverageMixin`
    so callers can assert on them without parsing the message string.
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
        """Initialise the registered error and its extraction-coverage fields."""
        super().__init__(message, context=context, translated_message=translated_message)
        self._set_extraction_coverage(
            missing=missing,
            malformed=malformed,
            ambiguous=ambiguous,
            coverage=coverage,
        )


class TemplateNotDetectedError(DeclaracionParseError):
    """Raised when the PDF's template revision cannot be auto-detected.

    Emitted by
    :func:`~adapters.inbound.declaracion._detect.detect_template_revision`
    when neither the header nor the footer of the PDF carries enough signal to
    pin a ``(modelo, año, revision)`` triple. Callers may recover by passing
    explicit ``modelo`` / ``año`` overrides to
    :func:`~adapters.inbound.declaracion.parser.parse_declaracion`.
    """
