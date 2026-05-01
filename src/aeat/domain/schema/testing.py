"""Test-only helpers for :mod:`aeat.domain.schema`.

Public surface: :func:`build_fake_boe_pdf` generates a synthetic
BOE-style annex PDF that matches the line-based pattern library the
:class:`~aeat.domain.schema.BoeOrdenExtractor` consumes. The helper is
imported only by colocated tests and MUST NOT be imported by
production code paths.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def build_fake_boe_pdf(
    path: Path,
    *,
    annex_lines: Sequence[str],
    preamble_lines: Iterable[str] = (),
    same_page_layout: bool = False,
) -> None:
    """Write a synthetic BOE-Orden-shaped PDF to ``path``.

    The first page carries ``preamble_lines`` and an ``ANEXO``
    heading. When ``same_page_layout`` is ``False`` (default), a page
    break separates the heading from the annex body on page 2+; when
    it is ``True``, ``annex_lines`` are laid out on the same page as
    the heading — the layout real BOE Ordenes often use, and the
    regression fixture for the annex-start-page line-loss bug.

    Args:
        path: Destination PDF path.
        annex_lines: Lines that appear after the annex heading; each
            line becomes one ``pdfplumber.extract_text`` line.
        preamble_lines: Optional lines placed before the annex
            heading on page 1.
        same_page_layout: Keep the annex body on the same page as
            the heading instead of breaking to a new page.
    """
    pdf = canvas.Canvas(str(path), pagesize=A4)
    _, page_height = A4
    x = 56.0
    y = page_height - 72.0
    line_step = 14.0

    pdf.setFont("Helvetica", 10)
    for line in preamble_lines:
        pdf.drawString(x, y, line)
        y -= line_step
    pdf.drawString(x, y, "ANEXO I")
    y -= line_step

    if not same_page_layout:
        pdf.showPage()
        pdf.setFont("Helvetica", 10)
        y = page_height - 72.0

    for line in annex_lines:
        if y < 72.0:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = page_height - 72.0
        pdf.drawString(x, y, line)
        y -= line_step
    pdf.showPage()
    pdf.save()
