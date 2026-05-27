"""Exception hierarchy for the declaración PDF parser.

Defines the parse-error tree raised by
:mod:`aeat.adapters.inbound.declaracion`. All exceptions descend from
:exc:`aeat.adapters.inbound.pdf._errors.PdfModeloImportError` so callers
can catch the generic PDF-import boundary without needing declaración
specifics.
"""

from __future__ import annotations

from decimal import Decimal

from ..pdf._errors import PdfModeloImportError


class DeclaracionParseError(PdfModeloImportError):
    """Raised when a PDF cannot be parsed into a declaración filing.

    Base class for all parse-time errors emitted by
    :func:`aeat.adapters.inbound.declaracion.parse_declaracion`.
    :exc:`TemplateNotDetectedError` signals a recoverable template
    detection failure; the bare class is raised for low-level failures
    (PDF unreadable, header field missing, missing registry coverage,
    etc.).

    When the error originates from an extraction-coverage failure the
    following structured attributes are populated so callers can assert
    on them without parsing the message string:

    Attributes:
        missing: Tuple of casilla IDs that produced no hit in the PDF.
        malformed: Tuple of casilla IDs whose captured value could not
            be parsed as a valid decimal or text token.
        ambiguous: Tuple of casilla IDs that matched more than one
            region in the PDF.
        coverage: Fraction of target casillas successfully extracted
            (``Decimal``).  ``None`` when the error is not an
            extraction-coverage failure.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        missing: tuple[str, ...] = (),
        malformed: tuple[str, ...] = (),
        ambiguous: tuple[str, ...] = (),
        coverage: Decimal | None = None,
    ) -> None:
        super().__init__(message)
        self.missing: tuple[str, ...] = missing
        self.malformed: tuple[str, ...] = malformed
        self.ambiguous: tuple[str, ...] = ambiguous
        self.coverage: Decimal | None = coverage


class TemplateNotDetectedError(DeclaracionParseError):
    """Raised when the PDF's template revision cannot be auto-detected.

    Emitted by
    :func:`aeat.adapters.inbound.declaracion._detect.detect_template_revision`
    when neither the header nor the footer of the PDF carries enough
    signal to pin a ``(modelo, año, revision)`` triple. Callers may
    recover by passing explicit ``modelo`` / ``año`` overrides to
    :func:`aeat.adapters.inbound.declaracion.parse_declaracion`.
    """
