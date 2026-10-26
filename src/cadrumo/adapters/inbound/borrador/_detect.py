"""Artefact-kind detection for observed Modelo 100 PDFs.

This module classifies the printed text extracted from a Renta borrador,
predeclaración, or declaración PDF into an
:class:`~adapters.inbound.borrador.schema.ArtefactKind`. It is a local
adapter helper: it receives the page text
:func:`~adapters.inbound.borrador.parser.parse_borrador` has already read, applies the
documented marker precedence ladder, and returns the artefact kind the parser
hands to the extractor.
"""

from __future__ import annotations

import re

from ..pdf.redaction import INPUT_PDF_SOURCE_LABEL as _INPUT_PDF_SOURCE_LABEL
from .errors import ArtefactNotRecognisedError
from .schema import ArtefactKind

_VISTA_PREVIA_RE = re.compile(r"\bVISTA\s+PREVIA\b", re.IGNORECASE)
_BORRADOR_RE = re.compile(r"\bBORRADOR\b", re.IGNORECASE)
_CSV_RE = re.compile(r"C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n", re.IGNORECASE)


def detect_artefact_kind_from_pages(pages: tuple[str, ...]) -> ArtefactKind:
    """Return the detected Modelo 100 artefact kind for extracted page text.

    Precedence when markers overlap is
    :attr:`~adapters.inbound.borrador.schema.ArtefactKind.PREDECLARACION`
    > :attr:`~adapters.inbound.borrador.schema.ArtefactKind.DECLARACION`
    > :attr:`~adapters.inbound.borrador.schema.ArtefactKind.BORRADOR`.
    The *VISTA PREVIA* watermark is the strongest signal of non-binding
    status; the CSV stamp trumps the BORRADOR header because a filed
    declaración always ships with a CSV.

    Raises:
        ArtefactNotRecognisedError: When none of the three markers
            (VISTA PREVIA watermark, BORRADOR header, CSV stamp) match.
    """
    text = "\n".join(pages)

    if _VISTA_PREVIA_RE.search(text):
        return ArtefactKind.PREDECLARACION
    if _CSV_RE.search(text):
        return ArtefactKind.DECLARACION
    if _BORRADOR_RE.search(text):
        return ArtefactKind.BORRADOR

    raise ArtefactNotRecognisedError(
        f"could not recognise Modelo 100 artefact type in {_INPUT_PDF_SOURCE_LABEL}; "
        "expected one of: VISTA PREVIA watermark, BORRADOR header, CSV stamp",
    )
