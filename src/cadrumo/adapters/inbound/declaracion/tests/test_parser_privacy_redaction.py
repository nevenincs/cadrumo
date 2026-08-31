"""Declaracion parser privacy redaction tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    A4,
    FIXTURES_DIR,
    Path,
    TemplateNotDetectedError,
    _extract_pages_words,
    canvas,
    logging,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_parser_debug_log_does_not_expose_source_filename(caplog: pytest.LogCaptureFixture) -> None:
    pdf_path = FIXTURES_DIR / "justificantes" / "130" / "2022-2T.pdf"

    with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.inbound.declaracion.parser"):
        parse_declaracion(pdf_path, modelo_override="130", año_override=2022, period_override="2T")

    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert pdf_path.name not in rendered_logs
    assert "source=<input-pdf>" in rendered_logs


def test_template_not_detected_context_does_not_expose_source_filename(tmp_path: Path) -> None:
    pdf_path = tmp_path / "12345678Z-private-declaracion.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=A4)
    pdf.drawString(50, 750, "PDF text without declaration template markers")
    pdf.save()

    with pytest.raises(TemplateNotDetectedError) as excinfo:
        parse_declaracion(pdf_path)

    assert excinfo.value.context is not None
    assert excinfo.value.context.get("path") == "<input-pdf>"


def test_word_extraction_debug_log_does_not_expose_source_filename(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    pdf_path = tmp_path / "12345678Z-private-words.pdf"
    pdf_path.write_text("not a PDF", encoding="utf-8")

    with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.inbound.declaracion.parser"):
        words = _extract_pages_words(pdf_path)

    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert words == ()
    assert pdf_path.name not in rendered_logs
    assert str(pdf_path) not in rendered_logs
    assert "<input-pdf>" in rendered_logs
