"""Error hierarchy for the borrador parser.

Specialises :class:`aeat.adapters.inbound.pdf._errors.PdfFilingImportError`
with Modelo 100 specific exceptions raised by
:func:`aeat.adapters.inbound.borrador.parse_borrador` and the helpers in
:mod:`aeat.adapters.inbound.borrador._detect`.
"""

from __future__ import annotations

from ..pdf._errors import PdfFilingImportError


class BorradorParseError(PdfFilingImportError):
    """Raised when a Modelo 100 PDF cannot be parsed into a :class:`~aeat.adapters.inbound.borrador._schema.BorradorFiling`.

    Base class for every domain-specific failure raised by the borrador
    pipeline. Subclasses (e.g. :class:`ArtefactNotRecognisedError`)
    refine the failure mode.
    """


class ArtefactNotRecognisedError(BorradorParseError):
    """Raised when the PDF does not match any known Modelo 100 artefact shape.

    Surfaced by :func:`aeat.adapters.inbound.borrador._detect.detect_artefact_kind`
    when none of the BORRADOR / VISTA PREVIA / CSV markers can be located.
    """
