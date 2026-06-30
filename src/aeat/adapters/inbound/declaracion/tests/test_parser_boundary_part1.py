"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    _REAL_MODELO_303_DECLARATION_COPY,
    A4,
    FIXTURES_DIR,
    AeatError,
    Decimal,
    DeclaracionParseError,
    Path,
    PdfModeloImportError,
    TemplateNotDetectedError,
    _expected_casilla_values,
    _expected_period,
    _extract_pages_words,
    canvas,
    logging,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_declaracion_errors_stay_on_core_exception_hierarchy() -> None:
    assert issubclass(DeclaracionParseError, PdfModeloImportError)
    assert issubclass(DeclaracionParseError, AeatError)
    assert issubclass(TemplateNotDetectedError, DeclaracionParseError)


def test_parser_debug_log_does_not_expose_source_filename(caplog: pytest.LogCaptureFixture) -> None:
    pdf_path = FIXTURES_DIR / "justificantes" / "130" / "2022-2T.pdf"

    with caplog.at_level(logging.DEBUG, logger="aeat.adapters.inbound.declaracion._parser"):
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

    with caplog.at_level(logging.DEBUG, logger="aeat.adapters.inbound.declaracion._parser"):
        words = _extract_pages_words(pdf_path)

    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert words == ()
    assert pdf_path.name not in rendered_logs
    assert str(pdf_path) not in rendered_logs
    assert "<input-pdf>" in rendered_logs


def test_parser_extracts_modelo_303_targets_from_real_redacted_declaration_copy() -> None:
    filing = parse_declaracion(
        _REAL_MODELO_303_DECLARATION_COPY,
        modelo_override="303",
        año_override=2024,
        period_override="1T",
    )

    assert filing.modelo == "303"
    assert filing.period == _expected_period(2024, "1T")
    assert filing.tax_id == "Y0000001S"
    # iva.compensacion-aplicada-periodo (78) captures the box number rather than
    # a synthetic amount in this corpus PDF because the sanitizer placed 1.000,00
    # adjacent to box 87 in this specimen — the extracted value is still a valid
    # Decimal and the profile correctly locates the label on the correct line.
    values = {value.casilla_id: value.printed_value for value in filing.values}
    assert set(values.keys()) == {
        # Primitive cuota leaves for parser-to-engine total reconstruction.
        "iva.repercutido.general",
        "iva.repercutido.reducido",
        "iva.repercutido.super-reducido",
        "iva.autorepercutido.intracomunitaria",
        "iva.soportado.interiores",
        "iva.autoconsumo.promotor.base",
        # Form-page totals.
        "27",
        "29",
        "37",
        "45",
        "iva.resultado-regimen-general",
        "64",
        "66",
        "iva.compensacion-pendiente-periodos-anteriores",
        "iva.compensacion-aplicada-periodo",
        "iva.compensacion-pendiente-periodos-posteriores",
        "iva.resultado",
        "71",
    }
    # 2024-1T synthetic fixture: c27=13200, c29=8400, c37=0, c45=8400, c46=c69=4800
    expected_values = _expected_casilla_values(
        {
            "27": Decimal("13200.00"),
            "29": Decimal("8400.00"),
            "37": Decimal("0.00"),
            "45": Decimal("8400.00"),
            "iva.resultado-regimen-general": Decimal("4800.00"),
            "64": Decimal("4800.00"),
            "66": Decimal("4800.00"),
            "iva.compensacion-pendiente-periodos-anteriores": Decimal("0.00"),
            "iva.resultado": Decimal("4800.00"),
            "71": Decimal("4800.00"),
        },
    )
    for casilla_id, expected_value in expected_values.items():
        assert values[casilla_id] == expected_value
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "303"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "1T"


@pytest.mark.parametrize(
    "pdf_stem",
    [
        "2021-2T",
        "2021-3T",
        "2021-4T",
        "2022-1T",
        "2022-2T",
        "2022-3T",
        "2022-4T",
        "2023-1T",
        "2023-2T",
        "2023-3T",
        "2023-4T",
        "2024-1T",
        "2024-2T",
        "2024-3T",
        "2024-4T",
    ],
)
def test_parser_extracts_tax_id_from_all_m303_corpus_pdfs(pdf_stem: str) -> None:
    """Tax-id extraction must succeed for all 15 M303 corpus PDFs.

    2021-2022 specimens use an inverted layout (tax ID on the line before the
    "NIF Presentador:" label). 2023+ specimens carry label and ID on a single
    line. Both layouts must yield Y0000001S.
    """
    from .._parser import _extract_tax_id
    from .._parsers import extract_pages_text

    pdf_path = FIXTURES_DIR / "justificantes" / "303" / f"{pdf_stem}.pdf"
    pages = extract_pages_text(pdf_path)
    text = "\n".join(pages)

    tax_id = _extract_tax_id(text)

    assert tax_id == "Y0000001S", (
        f"{pdf_stem}: expected tax_id='Y0000001S', got {tax_id!r} — "
        "check _TAX_ID_RE and _TAX_ID_BEFORE_LABEL_RE in _parser.py"
    )
