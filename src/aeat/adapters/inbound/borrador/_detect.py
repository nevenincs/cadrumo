"""Artefact-kind detection for Modelo 100 PDFs (#305 cluster F)."""

from __future__ import annotations

import re
from pathlib import Path

from ._errors import ArtefactNotRecognisedError
from ._parsers import extract_pages_text
from ._schema import ArtefactKind

_VISTA_PREVIA_RE = re.compile(r"\bVISTA\s+PREVIA\b", re.IGNORECASE)
_BORRADOR_RE = re.compile(r"\bBORRADOR\b", re.IGNORECASE)
_CSV_RE = re.compile(r"C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n", re.IGNORECASE)


def detect_artefact_kind(pdf_path: Path) -> ArtefactKind:
    """Return the detected Modelo 100 artefact kind.

    Precedence when markers overlap: PREDECLARACION > DECLARACION >
    BORRADOR. The *VISTA PREVIA* watermark is the strongest signal of
    non-binding status; CSV stamp trumps BORRADOR header since a filed
    declaración always ships with a CSV.

    Raises:
        ArtefactNotRecognisedError: When none of the three markers matches.
    """
    pages = extract_pages_text(pdf_path)
    text = "\n".join(pages)

    if _VISTA_PREVIA_RE.search(text):
        return ArtefactKind.PREDECLARACION
    if _CSV_RE.search(text):
        return ArtefactKind.DECLARACION
    if _BORRADOR_RE.search(text):
        return ArtefactKind.BORRADOR

    raise ArtefactNotRecognisedError(
        f"could not recognise Modelo 100 artefact type in {pdf_path}; "
        "expected one of: VISTA PREVIA watermark, BORRADOR header, CSV stamp"
    )
