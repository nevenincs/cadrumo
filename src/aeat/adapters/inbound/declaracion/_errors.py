"""Exception hierarchy for the declaración PDF parser.

Defines the parse-error tree raised by
:mod:`aeat.adapters.inbound.declaracion`. All exceptions descend from
:exc:`aeat.adapters.inbound.pdf._errors.PdfFilingImportError` so callers
can catch the generic PDF-import boundary without needing declaración
specifics.
"""

from __future__ import annotations

from ..pdf._errors import PdfFilingImportError


class DeclaracionParseError(PdfFilingImportError):
    """Raised when a PDF cannot be parsed into a declaración filing.

    Base class for all parse-time errors emitted by
    :func:`aeat.adapters.inbound.declaracion.parse_declaracion`. Concrete
    subclasses (:exc:`NoExtractorRegisteredError`,
    :exc:`TemplateNotDetectedError`) signal recoverable conditions; the
    bare class is raised for low-level failures (PDF unreadable, header
    field missing, etc.).
    """


class NoExtractorRegisteredError(DeclaracionParseError):
    """Raised when extraction reaches the disabled legacy dispatch path.

    The legacy Python extractor registry is intentionally fail-closed.
    Callers must use validated registry snapshots once registry-backed
    declaration extraction is available; supported-triple enumeration is
    no longer authoritative.
    """


class TemplateNotDetectedError(DeclaracionParseError):
    """Raised when the PDF's template revision cannot be auto-detected.

    Emitted by
    :func:`aeat.adapters.inbound.declaracion._detect.detect_template_revision`
    when neither the header nor the footer of the PDF carries enough
    signal to pin a ``(modelo, año, revision)`` triple. Callers may
    recover by passing explicit ``modelo`` / ``año`` overrides to
    :func:`aeat.adapters.inbound.declaracion.parse_declaracion`.
    """
