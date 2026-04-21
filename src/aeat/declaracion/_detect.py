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
# Real AEAT declaraciones print ``Aprobado por Orden HAC/{number}/{año}`` on
# the footer; when present it pins the template revision precisely. Absent,
# we fall back to a ``{ejercicio}.01`` MVP sentinel — the registry then
# decides whether the sentinel is registered.
_ORDEN_HAC_RE = re.compile(
    r"Orden\s+HAC/\s*(?P<number>\d+)\s*/\s*(?P<año>\d{4})",
    re.IGNORECASE,
)


def detect_template_revision(pdf_path: Path) -> TemplateRevision | None:
    """Peek at the PDF's first page and return a :class:`TemplateRevision`.

    Returns ``None`` if the header does not yield both a modelo and an
    ejercicio. Revision resolution:

    1. If the PDF prints an ``Orden HAC/N/YYYY`` footer, use
       ``"{año}.{MM}"`` where ``MM`` is derived from the order number
       falling in the relevant AEAT publication month window (audit H2).
    2. Else fall back to ``"{ejercicio}.01"``.

    The fallback is deliberately narrow: the registry refuses to resolve
    any revision it has not explicitly registered, so a spurious fallback
    produces a readable ``NoExtractorRegisteredError`` rather than a silent
    mis-extraction.
    """
    pages = extract_pages_text(pdf_path)
    if not pages:
        return None
    head = pages[0][:2000]  # first page header region
    tail = pages[-1][-2000:] if pages else ""

    modelo_match = _HEADER_MODELO_RE.search(head)
    ejercicio_match = _HEADER_EJERCICIO_RE.search(head)
    if modelo_match is None or ejercicio_match is None:
        return None

    modelo = modelo_match.group("modelo")
    ejercicio = ejercicio_match.group("ejercicio")

    orden_match = _ORDEN_HAC_RE.search(head) or _ORDEN_HAC_RE.search(tail)
    if orden_match is not None:
        # Carry the printed Orden HAC number through — registry extractors
        # that register against a specific order number get picked up; the
        # generic "{año}.01" revision is bypassed for post-Orden PDFs.
        revision = f"{orden_match.group('año')}.orden-{orden_match.group('number')}"
    else:
        revision = f"{ejercicio}.01"

    return TemplateRevision(
        modelo=modelo,
        año=int(ejercicio),
        revision=revision,
        detected_from="header",
    )
