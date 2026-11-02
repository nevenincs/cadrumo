"""Error hierarchy for the Modelo 100 borrador parser.

The hierarchy specialises
:class:`~domain.justificante.errors.PdfModeloImportError` with Modelo 100
exceptions raised by :func:`adapters.inbound.borrador.parser.parse_borrador`,
the artefact detector, and coverage validation. It is an inbound parse-error
boundary; callers should inspect the structured attributes on
:class:`BorradorParseError` rather than parsing rendered messages.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from ....domain.justificante.errors import PdfModeloImportError


class BorradorRefusalReason(StrEnum):
    """Typed reason a borrador was refused for what it prints, not for how it parses.

    Attributes:
        JOINT_DECLARATION: The document names a second declarant or a joint
            filing, so its figures are not one taxpayer's.
        CONFLICTING_DUPLICATE_ROW: One casilla is printed more than once with
            different values, so no single value can be taken as printed.
    """

    JOINT_DECLARATION = "joint_declaration"
    CONFLICTING_DUPLICATE_ROW = "conflicting_duplicate_row"


class BorradorParseError(PdfModeloImportError):
    """Raised when a Modelo 100 PDF cannot be parsed into an observation record.

    Base class for every borrador-specific failure raised by the inbound
    parser. Subclasses, such as :class:`ArtefactNotRecognisedError`, refine the
    failure mode while preserving the
    :class:`~domain.justificante.errors.PdfModeloImportError` import-family
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
        reason: :class:`BorradorRefusalReason` when the document was refused
            for what it prints; ``None`` otherwise.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        missing: tuple[str, ...] = (),
        malformed: tuple[str, ...] = (),
        ambiguous: tuple[str, ...] = (),
        coverage: Decimal | None = None,
        reason: BorradorRefusalReason | None = None,
    ) -> None:
        """Initialise with an optional message and structured coverage fields.

        Args:
            message: Optional human-readable description of the failure.
            missing: Casilla IDs that produced no hit in the PDF.
            malformed: Casilla IDs whose captured value could not be parsed.
            ambiguous: Casilla IDs that matched more than one region.
            coverage: Fraction of target casillas successfully extracted.
            reason: Typed refusal reason when the document is refused for its
                printed content.
        """
        super().__init__(message)
        self.missing: tuple[str, ...] = missing
        self.malformed: tuple[str, ...] = malformed
        self.ambiguous: tuple[str, ...] = ambiguous
        self.coverage: Decimal | None = coverage
        self.reason: BorradorRefusalReason | None = reason


class ArtefactNotRecognisedError(BorradorParseError):
    """Raised when the PDF does not match any known Modelo 100 artefact shape.

    Surfaced by
    :func:`~adapters.inbound.borrador._detect.detect_artefact_kind_from_pages` when
    none of the BORRADOR / VISTA PREVIA / CSV markers can be located.
    """
