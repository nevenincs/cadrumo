"""Real synthetic PDF bytes shared by evidence-extraction tests."""

from __future__ import annotations


def text_pdf_bytes(lines: tuple[str, ...]) -> bytes:
    """Return real PDF bytes with a text layer drawing each of ``lines``."""
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4)
    y = 760
    for line in lines:
        page.drawString(72, y, line)
        y -= 20
    page.save()
    return buf.getvalue()
