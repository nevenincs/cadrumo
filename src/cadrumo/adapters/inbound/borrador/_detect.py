"""Artefact-kind detection for observed Modelo 100 PDFs.

This module classifies the printed text extracted from a Renta borrador,
predeclaración, or declaración PDF into an
:class:`~adapters.inbound.borrador._schema.ArtefactKind`. It is a local
adapter helper: it reads PDF text through
:func:`adapters.inbound.borrador._parsers.extract_pages_text`, applies the
documented marker precedence ladder, and returns the artefact kind consumed by
:func:`~adapters.inbound.borrador.parse_borrador`.
"""

from __future__ import annotations

import re
from pathlib import Path

from .errors import ArtefactNotRecognisedError
from ._parsers import extract_pages_text
from ._schema import ArtefactKind

_VISTA_PREVIA_RE = re.compile(r"\bVISTA\s+PREVIA\b", re.IGNORECASE)
_BORRADOR_RE = re.compile(r"\bBORRADOR\b", re.IGNORECASE)
_CSV_RE = re.compile(r"C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n", re.IGNORECASE)
_INPUT_PDF_SOURCE_LABEL = "<input-pdf>"


def detect_artefact_kind(pdf_path: Path) -> ArtefactKind:
    """Return the detected Modelo 100 artefact kind for ``pdf_path``.

    Precedence when markers overlap is
    :attr:`~adapters.inbound.borrador._schema.ArtefactKind.PREDECLARACION`
    > :attr:`~adapters.inbound.borrador._schema.ArtefactKind.DECLARACION`
    > :attr:`~adapters.inbound.borrador._schema.ArtefactKind.BORRADOR`.
    The *VISTA PREVIA* watermark is the strongest signal of non-binding
    status; the CSV stamp trumps the BORRADOR header because a filed
    declaración always ships with a CSV.

    Args:
        pdf_path: Path to the Modelo 100 PDF to inspect.

    Returns:
        The detected :class:`~adapters.inbound.borrador._schema.ArtefactKind`.

    Raises:
        ArtefactNotRecognisedError: When none of the three markers
            (VISTA PREVIA watermark, BORRADOR header, CSV stamp) match.
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
        f"could not recognise Modelo 100 artefact type in {_INPUT_PDF_SOURCE_LABEL}; "
        "expected one of: VISTA PREVIA watermark, BORRADOR header, CSV stamp",
    )
