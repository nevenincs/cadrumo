"""Modelo 100 (IRPF annual) declaración extractors.

One base class + three concrete registry entries, one per supported
template revision:

- ``Modelo100V2021LegacyExtractor`` — tax year 2021 column-split layout.
- ``Modelo100V2022ModernExtractor`` — tax year 2022 modern layout.
- ``Modelo100V2023ModernExtractor`` — tax year 2023 modern layout
  (identical rendering shape to 2022; distinct revision so future
  AEAT redesigns land without reshuffling the registry keys).

The base class runs :func:`scan_pages` over the pdfplumber-extracted
text of every page, reduces the hits to strict
:class:`ExtractedCasilla` records, and derives the header fields
(NIF, ejercicio, period) directly from known header-casilla captures.
Modelo 100 is annual so the canonical period is always ``YYYYA``.

Coverage for the MVP corpus:

- 2021: 84 casillas (header + all income + liquidación + resultado)
- 2022: 83 casillas
- 2023: 86 casillas

:class:`ExtractionStatus` resolves to ``UNVERIFIABLE`` because this
MVP declares an empty required-set — casilla coverage varies with the
filer's declared income sources (property rentals, capital gains,
deductions). A stricter required-set lands once sub-EPIC #305 ships a
Modelo 100 schema snapshot per-revision.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from ....pdf._shared import ExtractedCasilla
from ..._errors import DeclaracionParseError
from ..._extractor import DeclaracionExtractor
from ..._schema import (
    DeclaracionFiling,
    ExtractionStatus,
    ExtractionWarning,
    TemplateRevision,
)
from .. import extract_pages_text
from ._scanner import ScannedCasilla, scan_pages


class _Modelo100BaseExtractor(DeclaracionExtractor):
    """Shared driver for all Modelo 100 template revisions.

    Subclasses only pin the ``template_revision`` ClassVar; the scan
    logic is layout-agnostic because ``scan_pages`` runs every pass
    and the overlapping captures are disambiguated by the first-wins
    merge rule.
    """

    template_revision: ClassVar[TemplateRevision]

    def extract(self, pdf_path: Path) -> DeclaracionFiling:
        pages = extract_pages_text(pdf_path)
        scanned = scan_pages(pages)

        by_id: dict[str, ScannedCasilla] = {c.casilla_id: c for c in scanned}

        tax_id = _resolve_tax_id(by_id, pages)
        ejercicio = _resolve_ejercicio(type(self).template_revision, by_id, pages)
        period = f"{ejercicio}A"

        values: list[ExtractedCasilla] = []
        warnings: list[ExtractionWarning] = []
        for capture in scanned:
            confidence = 1.0 if capture.primitive == "tail_cid" else 0.7
            values.append(
                ExtractedCasilla(
                    casilla_id=capture.casilla_id,
                    printed_value=capture.typed_value,
                    source_page=capture.source_page,
                    source_bbox=None,
                    extraction_confidence=confidence,
                )
            )

        return DeclaracionFiling(
            modelo="100",
            period=period,
            ejercicio=ejercicio,
            tax_id=tax_id.upper(),
            template_revision=type(self).template_revision,
            values=tuple(values),
            warnings=tuple(warnings),
            source_pdf_path=pdf_path.resolve(),
            source_pdf_sha256=_sha256_file(pdf_path),
            parsed_at=datetime.now(tz=UTC),
            extraction_status=ExtractionStatus.UNVERIFIABLE,
        )


class Modelo100V2021LegacyExtractor(_Modelo100BaseExtractor):
    """Modelo 100 tax year 2021 — column-split legacy layout."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="100",
        año=2021,
        revision="2021.legacy",
    )


class Modelo100V2022ModernExtractor(_Modelo100BaseExtractor):
    """Modelo 100 tax year 2022 — Renta Web modern layout."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="100",
        año=2022,
        revision="2022.modern",
    )


class Modelo100V2023ModernExtractor(_Modelo100BaseExtractor):
    """Modelo 100 tax year 2023 — Renta Web modern layout (shape parity with 2022)."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="100",
        año=2023,
        revision="2023.modern",
    )


def _resolve_tax_id(by_id: dict[str, ScannedCasilla], pages: tuple[str, ...]) -> str:
    """Return the declarant NIF, with a regex fallback if casilla 01 missed."""
    hit = by_id.get("01")
    if hit is not None and isinstance(hit.typed_value, str):
        return hit.typed_value
    # Fallback: regex the first page for an NIF-shaped token near "NIF".
    import re

    joined = "\n".join(pages[:2])
    match = re.search(r"NIF\s*(?:Presentador)?\s*:?\s*([A-Z0-9]{8,12})", joined, re.IGNORECASE)
    if match is None:
        raise DeclaracionParseError("could not locate NIF in Modelo 100 PDF")
    return match.group(1)


def _resolve_ejercicio(
    template: TemplateRevision,
    by_id: dict[str, ScannedCasilla],
    pages: tuple[str, ...],
) -> str:
    """Return the 4-digit ejercicio string.

    Prefers the explicit printed ``Ejercicio YYYY`` stamp (scanned from
    the pdf text) and falls back to the template-revision's own
    ``año`` when the stamp is absent. Modelo 100 justificantes always
    print the stamp on page 1 or page 2 but we mirror detection's
    two-page header span for robustness.
    """
    import re

    head = "\n".join(pages[: min(2, len(pages))])[:4000]
    match = re.search(r"Ejercicio\s*[:\-]?\s*(\d{4})", head, re.IGNORECASE)
    if match is not None:
        return match.group(1)
    return str(template.año)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = [
    "Modelo100V2021LegacyExtractor",
    "Modelo100V2022ModernExtractor",
    "Modelo100V2023ModernExtractor",
]
