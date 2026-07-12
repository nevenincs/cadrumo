"""Error hierarchy for the Modelo 100 borrador parser.

The hierarchy specialises
:class:`~domain.justificante.PdfModeloImportError` with Modelo 100
exceptions raised by :func:`adapters.inbound.borrador.parse_borrador`,
the artefact detector, and coverage validation. It is an inbound parse-error
boundary; callers should inspect the structured attributes on
:class:`BorradorParseError` rather than parsing rendered messages.
"""

from __future__ import annotations

from decimal import Decimal

from ....domain.justificante import PdfModeloImportError


class BorradorParseError(PdfModeloImportError):
    """Raised when a Modelo 100 PDF cannot be parsed into an observation record.

    Base class for every borrador-specific failure raised by the inbound
    parser. Subclasses, such as :class:`ArtefactNotRecognisedError`, refine the
    failure mode while preserving the
    :class:`~domain.justificante.PdfModeloImportError` import-family
    contract.

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
        """Initialise with an optional message and structured coverage fields.

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

    Surfaced by
    :func:`~adapters.inbound.borrador._detect.detect_artefact_kind` when
    none of the BORRADOR / VISTA PREVIA / CSV markers can be located.
    """
