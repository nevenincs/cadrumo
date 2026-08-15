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


def multi_page_text_pdf_bytes(*pages: tuple[str, ...]) -> bytes:
    """Return real PDF bytes with one drawn text page per argument in ``pages``."""
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    document = canvas.Canvas(buf, pagesize=A4)
    for lines in pages:
        vertical = 720
        for line in lines:
            document.drawString(72, vertical, line)
            vertical -= 24
        document.showPage()
    document.save()
    return buf.getvalue()
