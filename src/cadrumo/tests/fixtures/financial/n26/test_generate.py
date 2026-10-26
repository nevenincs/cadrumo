"""Smoke tests for the N26 savings-statement PDF fixture generator.

`main()` mutates committed in-tree fixture bytes, so the smoke tests
exercise the importable surface (`_Fixture` dataclass + `_FIXTURES`
catalogue + `_draw_page` rendering) on a fresh ReportLab canvas
without touching the committed PDFs.
"""

from __future__ import annotations

import io

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ._generate import (
    _FIXTURES,
    _draw_page,
    _Fixture,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_fixture_catalogue_is_non_empty_and_frozen() -> None:
    """Generator carries at least one fixture; each is the immutable
    `_Fixture` dataclass."""

    assert len(_FIXTURES) > 0
    for fixture in _FIXTURES:
        assert isinstance(fixture, _Fixture)
        assert fixture.filename.endswith(".pdf")
        assert fixture.title
        assert fixture.pages


def test_draw_page_renders_lines_onto_canvas_without_error() -> None:
    """The rendering path runs end-to-end on a fresh canvas with a
    sample line set; emits valid PDF bytes."""

    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=A4)
    sample_lines = ("Header line", "Body line 1", "Body line 2")

    _draw_page(pdf_canvas, sample_lines)
    pdf_canvas.showPage()
    pdf_canvas.save()

    pdf_bytes = buffer.getvalue()
    assert pdf_bytes.startswith(b"%PDF"), "rendered bytes are not a PDF"
    assert len(pdf_bytes) > 500, "rendered PDF suspiciously small"
