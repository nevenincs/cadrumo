"""Template-revision detection for declaración PDFs.

AEAT prints the form code + año + period in a header / footer stamp.
``detect_template_revision`` peeks at the first page text; returns
``None`` on ambiguity so the caller can fall back to explicit
``--modelo --año`` flags. Detection resolves template identity only; the
revision tag selects the registry ``declaracion_pdf`` extraction profile
for the matched modelo and ejercicio.

The detector returns :class:`~adapters.inbound.declaracion.TemplateRevision`
records; it does not load
:class:`~domain.calculations.registry.RegistrySnapshot` data or choose an
extraction profile. Registry validation happens in
:func:`~adapters.inbound.declaracion.parse_declaracion`.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..pdf.label_regex import EJERCICIO_LABEL, MODELO_LABEL
from ._parsers._pdfplumber_backend import extract_pages_text
from ._schema import TemplateRevision

# AEAT renders the header stamp in the sede UI language the filer used, so both
# labels accept the Spanish and English wording. Both searches are bounded to
# the page-1/2 header span below, which keeps the English "Form" alternative
# from matching ordinary prose elsewhere in the document.
_HEADER_MODELO_RE = re.compile(rf"{MODELO_LABEL}\s*[:\-]?\s*(?P<modelo>\d{{3}}[A-Z]?)", re.IGNORECASE)
_HEADER_EJERCICIO_RE = re.compile(rf"{EJERCICIO_LABEL}\s*[:\-]?\s*(?P<ejercicio>\d{{4}})", re.IGNORECASE)
# Real AEAT declaraciones print ``Aprobado por Orden HAC/{number}/{año}`` on
# the footer; when present it pins the template revision precisely. Absent,
# we fall back to a ``{ejercicio}.01`` sentinel.
_ORDEN_HAC_RE = re.compile(
    r"Orden\s+HAC/\s*(?P<number>\d+)\s*/\s*(?P<año>\d{4})",
    re.IGNORECASE,
)


def detect_template_revision(pdf_path: Path) -> TemplateRevision | None:
    """Peek at the PDF's first page and return a :class:`TemplateRevision`.

    Returns ``None`` if the header does not yield both a modelo and an
    ejercicio. Revision resolution:

    1. If the PDF prints an ``Orden HAC/N/YYYY`` footer, use
       ``"{año}.orden-{N}"``.
    2. Else fall back to ``"{ejercicio}.01"``.

    The fallback is deliberately narrow: the registry must refuse any
    revision it has not explicitly registered.

    The ``Ejercicio`` stamp is searched across the first two pages of
    the header cluster — some Modelo 100 pre-2022 justificantes print
    the ``INFORMACIÓN DE LA PRESENTACIÓN`` cover page without the
    ``Ejercicio YYYY`` line, deferring that marker to page 2.
    """
    return detect_template_revision_from_pages(extract_pages_text(pdf_path))


def detect_template_revision_from_pages(pages: tuple[str, ...]) -> TemplateRevision | None:
    """Return a :class:`TemplateRevision` from already-extracted PDF page text.

    Args:
        pages: Per-page text extracted from a declaración PDF.

    Returns:
        The detected :class:`TemplateRevision`, or ``None`` when the header
        pages do not carry enough modelo/year signal.
    """
    if not pages:
        return None
    # Union of pages 1-2 header region: some Modelo 100 PDFs print
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
    else:
        revision = f"{ejercicio}.01"

    return TemplateRevision(
        modelo=modelo,
        año=int(ejercicio),
        revision=revision,
        detected_from="header",
    )
