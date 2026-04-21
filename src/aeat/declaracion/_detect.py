"""Template-revision detection for declaración PDFs.

AEAT prints the form code + año + period in a header / footer stamp.
``detect_template_revision`` peeks at the first page text; returns
``None`` on ambiguity so the caller can fall back to explicit
``--modelo --año`` flags.
"""

from __future__ import annotations

import re
from pathlib import Path

from ._parsers import extract_pages_text
from ._schema import TemplateRevision

_HEADER_MODELO_RE = re.compile(r"Modelo\s*[:\-]?\s*(?P<modelo>\d{3}[A-Z]?)", re.IGNORECASE)
_HEADER_EJERCICIO_RE = re.compile(r"Ejercicio\s*[:\-]?\s*(?P<ejercicio>\d{4})", re.IGNORECASE)


def detect_template_revision(pdf_path: Path) -> TemplateRevision | None:
    """Peek at the PDF's first page and return a :class:`TemplateRevision`.

    Returns ``None`` if the header does not yield both a modelo and an
    ejercicio. The revision defaults to ``"{ejercicio}.01"`` — AEAT's
    usual intra-año revision marker; cluster-F / cluster-D MVP
    extractors register against it.
    """
    pages = extract_pages_text(pdf_path)
    if not pages:
        return None
    head = pages[0][:2000]  # first page header region

    modelo_match = _HEADER_MODELO_RE.search(head)
    ejercicio_match = _HEADER_EJERCICIO_RE.search(head)
    if modelo_match is None or ejercicio_match is None:
        return None

    return TemplateRevision(
        modelo=modelo_match.group("modelo"),
        año=int(ejercicio_match.group("ejercicio")),
        revision=f"{ejercicio_match.group('ejercicio')}.01",
        detected_from="header",
    )
