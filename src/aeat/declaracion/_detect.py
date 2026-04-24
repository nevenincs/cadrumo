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
       ``"{año}.orden-{N}"`` (audit H2).
    2. Else, if the detected modelo has a modelo-specific revision rule
       (currently only Modelo 100 — IRPF annual), apply it.
    3. Else fall back to ``"{ejercicio}.01"``.

    Modelo 100 (IRPF) does not carry an ``Orden HAC`` stamp on the
    justificante PDF and publishes a stable per-year layout that we
    identify by ejercicio. We mint ``"2021.legacy"`` for the 2021
    column-split layout and ``"{ejercicio}.modern"`` for 2022 onwards;
    the extractor registry binds exactly one class per revision.

    The fallback is deliberately narrow: the registry refuses to resolve
    any revision it has not explicitly registered, so a spurious fallback
    produces a readable ``NoExtractorRegisteredError`` rather than a silent
    mis-extraction.

    The ``Ejercicio`` stamp is searched across the first two pages of
    the header cluster — some Modelo 100 pre-2022 justificantes print
    the ``INFORMACIÓN DE LA PRESENTACIÓN`` cover page without the
    ``Ejercicio YYYY`` line, deferring that marker to page 2.
    """
    pages = extract_pages_text(pdf_path)
    if not pages:
        return None
    # Union of pages 1-2 header region — 2021 legacy Modelo 100 PDFs print
    # the ``Ejercicio YYYY`` stamp on page 2, not page 1.
    head_span = "\n".join(pages[: min(2, len(pages))])[:4000]
    tail = pages[-1][-2000:]

    modelo_match = _HEADER_MODELO_RE.search(head_span)
    ejercicio_match = _HEADER_EJERCICIO_RE.search(head_span)
    if modelo_match is None or ejercicio_match is None:
        return None

    modelo = modelo_match.group("modelo")
    ejercicio = ejercicio_match.group("ejercicio")

    orden_match = _ORDEN_HAC_RE.search(head_span) or _ORDEN_HAC_RE.search(tail)
    if orden_match is not None:
        revision = f"{orden_match.group('año')}.orden-{orden_match.group('number')}"
    elif modelo == "100":
        revision = _modelo_100_revision(int(ejercicio))
    else:
        revision = f"{ejercicio}.01"

    return TemplateRevision(
        modelo=modelo,
        año=int(ejercicio),
        revision=revision,
        detected_from="header",
    )


def _modelo_100_revision(año: int) -> str:
    """Map a Modelo 100 ejercicio to its layout-revision tag.

    Modelo 100 rendered its justificante in a 2-column header layout
    through tax year 2021 (``VALUE label VALUE2 label2``). The 2022
    Renta Web redesign inverted the shape to the modern ``label VALUE CID``
    line-oriented form used today. The revision tag drives extractor
    dispatch; see the 2021/2022+ extractors under
    ``src/aeat/declaracion/_parsers/modelo_100/``.
    """
    if año <= 2021:
        return "2021.legacy"
    return f"{año}.modern"
