"""Error hierarchy for the borrador parser.

Specialises :class:`aeat.domain.justificante.PdfModeloImportError`
with Modelo 100 specific exceptions raised by
:func:`aeat.adapters.inbound.borrador.parse_borrador` and the helpers in
:mod:`aeat.adapters.inbound.borrador._detect`.
"""

from __future__ import annotations

from decimal import Decimal

from ....domain.justificante import PdfModeloImportError


class BorradorParseError(PdfModeloImportError):
    """Raised when a Modelo 100 PDF cannot be parsed into a filing record.

    Base class for every domain-specific failure raised by the borrador
    pipeline. Subclasses (e.g. :class:`ArtefactNotRecognisedError`)
    refine the failure mode.

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
        """Initialise with an optional human-readable message and structured coverage fields.

        Args:
            message: Optional human-readable description of the failure.
            missing: Casilla IDs that produced no hit in the PDF.
            malformed: Casilla IDs whose captured value could not be parsed.
            ambiguous: Casilla IDs that matched more than one region.
            coverage: Fraction of target casillas successfully extracted.
        """
        super().__init__(message)
        self.missing: tuple[str, ...] = missing
        self.malformed: tuple[str, ...] = malformed
        self.ambiguous: tuple[str, ...] = ambiguous
        self.coverage: Decimal | None = coverage


class ArtefactNotRecognisedError(BorradorParseError):
    """Raised when the PDF does not match any known Modelo 100 artefact shape.

    Surfaced by :func:`aeat.adapters.inbound.borrador._detect.detect_artefact_kind`
    when none of the BORRADOR / VISTA PREVIA / CSV markers can be located.
    """
