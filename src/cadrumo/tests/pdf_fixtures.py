"""Real synthetic PDF bytes shared by evidence-extraction tests."""

from __future__ import annotations


def text_pdf_bytes(lines: tuple[str, ...]) -> bytes:
    """Return real PDF bytes with a text layer drawing each of ``lines``.

    ``invariant=True`` suppresses reportlab's default creation-timestamp
    stamp, so two builds from identical ``lines`` are byte-identical. Without
    it, a caller that stores the same document twice (an idempotent re-store,
    a save/load roundtrip) sees the bytes churn on every call for no reason
    the test intends.
    """
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4, invariant=True)
    y = 760
    for line in lines:
        page.drawString(72, y, line)
        y -= 20
    page.save()
    return buf.getvalue()


def multi_page_text_pdf_bytes(*pages: tuple[str, ...]) -> bytes:
    """Return real PDF bytes with one drawn text page per argument in ``pages``.

    ``invariant=True``: see :func:`text_pdf_bytes`.
    """
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    document = canvas.Canvas(buf, pagesize=A4, invariant=True)
    for lines in pages:
        vertical = 720
        for line in lines:
            document.drawString(72, vertical, line)
            vertical -= 24
        document.showPage()
    document.save()
    return buf.getvalue()
