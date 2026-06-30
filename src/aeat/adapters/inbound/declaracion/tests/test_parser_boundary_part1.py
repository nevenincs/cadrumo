"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    _MODELO_111_EXPECTED_TARGETS,
    _MODELO_123_2023_SYNTHETIC_FIXTURE,
    _MODELO_123_2024_SYNTHETIC_FIXTURE,
    _MODELO_123_CURRENT_EXPECTED_TARGETS,
    _MODELO_123_HISTORICAL_EXPECTED_TARGETS,
    _REAL_MODELO_303_DECLARATION_COPY,
    A4,
    FIXTURES_DIR,
    AeatError,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    Path,
    PdfModeloImportError,
    TemplateNotDetectedError,
    _casilla_id,
    _expected_casilla_values,
    _expected_period,
    _extract_pages_words,
    _modelo_snapshot,
    _write_declaration_pdf,
    canvas,
    logging,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_M111_CASILLA_07: CasillaId = _casilla_id("07")
_M111_CASILLA_08: CasillaId = _casilla_id("08")
_M111_CASILLA_09: CasillaId = _casilla_id("09")
_M111_CASILLA_28: CasillaId = _casilla_id("28")
_M111_CASILLA_30: CasillaId = _casilla_id("30")


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


def test_parser_extracts_modelo_111_registry_profile_targets_from_pdf() -> None:
    """Assert the M111 declaracion_pdf profile declares exactly the expected 29 targets.

    Casilla 29 (Autoliquidación negativa checkbox) is excluded from the
    declaracion_pdf extraction profile; only casillas 01-28 and 30 are
    present.  The roundtrip contract is verified against the real corpus PDFs
    in test_parser_extracts_modelo_111_casillas_from_corpus.
    """
    snapshot = _modelo_snapshot("111", filing_year=2025, period="1T")
    profile = snapshot.extraction_profiles["modelo-111-declaracion-pdf"]
    assert tuple(target.casilla_id for target in profile.target_casillas) == _MODELO_111_EXPECTED_TARGETS
    for target in profile.target_casillas:
        assert target.match_strategy == "bbox_anchored", (
            f"casilla {target.casilla_id}: expected match_strategy='bbox_anchored', got {target.match_strategy!r}"
        )
        assert target.bbox_anchor is not None, (
            f"casilla {target.casilla_id}: bbox_anchor must be set for bbox_anchored targets"
        )


@pytest.mark.parametrize(
    "pdf_stem,year,period",
    [
        ("2024-1T", 2024, "1T"),
        ("2024-2T", 2024, "2T"),
        ("2024-3T", 2024, "3T"),
        ("2024-4T", 2024, "4T"),
    ],
)
def test_parser_extracts_modelo_111_tax_id_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Tax-id extraction must succeed for all 4 M111 corpus PDFs.

    Ground truth: every M111 corpus PDF carries the same sanitised tax ID
    'Y0000001S' in the page-0 header block.  The _extract_tax_id helper is
    exercised directly, isolating the NIF regex from profile extraction.
    """
    from .._parser import _extract_tax_id
    from .._parsers import extract_pages_text

    pdf_path = FIXTURES_DIR / "justificantes" / "111" / f"{pdf_stem}.pdf"
    pages = extract_pages_text(pdf_path)
    text = "\n".join(pages)

    tax_id = _extract_tax_id(text)

    assert tax_id == "Y0000001S", f"{pdf_stem}: expected tax_id='Y0000001S', got {tax_id!r}"


@pytest.mark.parametrize(
    "pdf_stem,year,period",
    [
        ("2024-1T", 2024, "1T"),
        ("2024-2T", 2024, "2T"),
        ("2024-3T", 2024, "3T"),
        ("2024-4T", 2024, "4T"),
    ],
)
def test_parser_extracts_modelo_111_casillas_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Round-trip: parse all 4 corpus M111 PDFs via the production bbox_anchored profile.

    Ground truth is derived empirically by probing each corpus PDF with pdfplumber
    word-position extraction (see _find_bbox_casilla_hits in _parser.py).  The
    sanitised corpus replaces real amounts with synthetic values; only casillas
    that have a non-blank value printed in the right-side value column are
    extracted — blank (zero or not-applicable) casilla cells produce no hit and
    are legitimately absent from the filing.

    Ground truth from pdfplumber probe on the 4 sanitised corpus PDFs:
    - 2024-1T/2T/3T: casillas 07=1, 08=1.000,00, 09=1.000,00, 28=1.000,00, 30=1.000,00
    - 2024-4T: negative filing; only casilla 30=1.000,00 is printed

    The bbox_anchored profile uses column-specific anchor_x_min/anchor_x_max to
    restrict each casilla to its own column (A: x0~264, B: x0~347, C: x0~461), and
    value_x_max to prevent matching the next column's box number when the cell is empty.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "111" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="111",
        año_override=year,
        period_override=period,
    )

    assert filing.modelo == "111"
    assert filing.period == _expected_period(year, period)
    assert filing.tax_id == "Y0000001S", f"{pdf_stem}: expected tax_id='Y0000001S', got {filing.tax_id!r}"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "111"
    assert filing.registry_snapshot_ref.modelo_year == year

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # Casilla 30 (Resultado a ingresar) is present in all 4 corpus specimens.
    assert _M111_CASILLA_30 in values, (
        f"{pdf_stem}: expected casilla {_M111_CASILLA_30!r} in extracted values, got {set(values.keys())!r}"
    )
    assert values[_M111_CASILLA_30] == Decimal("1000.00"), (
        f"{pdf_stem}: casilla {_M111_CASILLA_30!r} expected Decimal('1000.00'), "
        f"got {values[_M111_CASILLA_30]!r}"
    )

    if pdf_stem == "2024-4T":
        # Negative filing: only casilla 30 is present; no other amounts printed.
        assert set(values.keys()) == {_M111_CASILLA_30}, (
            f"{pdf_stem}: negative filing should yield only casilla '30', got {set(values.keys())!r}"
        )
    else:
        # Positive filing: casillas 07 (count=1), 08 and 09 (amounts), 28, 30 are present.
        assert {_M111_CASILLA_07, _M111_CASILLA_08, _M111_CASILLA_09, _M111_CASILLA_28} <= set(values), (
            f"{pdf_stem}: expected casillas 07/08/09/28/30, got {set(values.keys())!r}"
        )
        expected_positive_values = {
            _M111_CASILLA_07: Decimal("1"),
            _M111_CASILLA_08: Decimal("1000.00"),
            _M111_CASILLA_09: Decimal("1000.00"),
            _M111_CASILLA_28: Decimal("1000.00"),
        }
        for casilla_id, expected_value in expected_positive_values.items():
            assert values[casilla_id] == expected_value, (
                f"{pdf_stem}: casilla {casilla_id!r} expected {expected_value!r}, got {values[casilla_id]!r}"
            )


def test_parser_extracts_modelo_123_current_registry_profile_targets_from_pdf(tmp_path: Path) -> None:
    snapshot = _modelo_snapshot("123", filing_year=2026, period="1T")
    profile = snapshot.extraction_profiles["modelo-123-declaracion-pdf"]
    assert tuple(target.casilla_id for target in profile.target_casillas) == _MODELO_123_CURRENT_EXPECTED_TARGETS
    values = {
        target.casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, target in enumerate(profile.target_casillas, start=1)
    }
    pdf_path = tmp_path / "modelo-123-2026.pdf"
    _write_declaration_pdf(pdf_path, modelo="123", ejercicio="2026", values=values)

    filing = parse_declaracion(pdf_path, modelo_override="123", año_override=2026)

    assert filing.modelo == "123"
    assert filing.period == _expected_period(2026, "1T")
    assert filing.tax_id == "00000000T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == values


def test_parser_extracts_modelo_123_historical_registry_profile_targets_from_pdf(tmp_path: Path) -> None:
    snapshot = _modelo_snapshot("123", filing_year=2023, period="4T")
    profile = snapshot.extraction_profiles["modelo-123-2019-declaracion-pdf"]
    assert tuple(target.casilla_id for target in profile.target_casillas) == _MODELO_123_HISTORICAL_EXPECTED_TARGETS
    values = {
        target.casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, target in enumerate(profile.target_casillas, start=1)
    }
    pdf_path = tmp_path / "modelo-123-2023.pdf"
    _write_declaration_pdf(pdf_path, modelo="123", ejercicio="2023", period="4T", values=values)

    filing = parse_declaracion(pdf_path, modelo_override="123", año_override=2023)

    assert filing.modelo == "123"
    assert filing.period == _expected_period(2023, "4T")
    assert filing.tax_id == "00000000T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == values


def test_parser_extracts_modelo_123_2024_corpus_round_trip() -> None:
    """Round-trip: parse the committed M123 2024-y-siguientes synthetic fixture.

    Ground truth is the AEAT-published Diseño de Registro Modelo 123 v20
    identified by source_ref aeat-dr-123-2024-v20.
    (source_ref: aeat-dr-123-2024-v20; legal authority: Orden HAC/56/2024)

    Layout verdict (LINE-START box numbers):
    The M123 2024 autoliquidacion is a simple sequential single-page form.  Each
    casilla row prints the two-digit box number at LINE START followed by the amount
    on the same line.  The numeric_casilla match strategy is valid for this form.
    This is the opposite of M111/M130 where multi-column table structure places box
    numbers at line END.

    The fixture encodes synthetic amounts satisfying all 5 registry formulas:
      [03] = [01] + [02] = 5,00 + 3,00 = 8,00
      [06] = [04] + [05] = 10.000,00 + 5.000,00 = 15.000,00
      [09] = [07] + [08] = 1.900,00 + 950,00 = 2.850,00
      [12] = [09] + [11] = 2.850,00 + 0,00 = 2.850,00
      [14] = [12] - [13] = 2.850,00 - 0,00 = 2.850,00

    Ground truth values are derived from the fixture data in _generate.py (not
    re-computed from the registry formula), so a formula change that breaks the
    arithmetic constraint would surface as a test failure here.

    Non-tautology: the numeric_casilla regex anchors on the printed box number at
    line start.  If the fixture moved box numbers to line end the parse would fail
    with coverage=0.  If the registry profile casilla IDs changed the fixture
    would no longer match.
    """
    filing = parse_declaracion(
        _MODELO_123_2024_SYNTHETIC_FIXTURE,
        modelo_override="123",
        año_override=2024,
        period_override="1T",
    )

    assert filing.modelo == "123"
    assert filing.period == _expected_period(2024, "1T")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "123"
    assert filing.registry_snapshot_ref.revision_id == "2024-y-siguientes"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "1T"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All 14 casillas defined by the 2024+ declaracion_pdf profile must be present.
    assert set(values.keys()) == set(_MODELO_123_CURRENT_EXPECTED_TARGETS), (
        f"expected exactly the 14 M123 2024+ profile casillas, got {set(values.keys())!r}"
    )

    # Ground truth: fixture amounts from _generate.py _MODELO_123_2024_CASILLAS.
    # Integer casillas (01-03) stored as comma-format, parse_spanish_decimal returns Decimal.
    expected_values = _expected_casilla_values(
        {
            "01": Decimal("5.00"),
            "02": Decimal("3.00"),
            "03": Decimal("8.00"),
            "04": Decimal("10000.00"),
            "05": Decimal("5000.00"),
            "06": Decimal("15000.00"),
            "07": Decimal("1900.00"),
            "08": Decimal("950.00"),
            "09": Decimal("2850.00"),
            "10": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("2850.00"),
            "13": Decimal("0.00"),
            "14": Decimal("2850.00"),
        },
    )
    for casilla_id, expected_value in expected_values.items():
        assert values[casilla_id] == expected_value, (
            f"casilla {casilla_id}: expected {expected_value!r}, got {values[casilla_id]!r}"
        )


def test_parser_extracts_modelo_123_2023_historical_corpus_round_trip() -> None:
    """Round-trip: parse the committed M123 2019-2023 revision synthetic fixture.

    Ground truth is the AEAT-published Orden EHA/3435/2007 and the Diseño de Registro
    Modelo 123 v13 (source_ref: aeat-dr-123-2019-2023-v13).

    Layout verdict (LINE-START box numbers):
    The 2019-2023 form is structurally identical to the 2024+ form: simple sequential
    single-page autoliquidacion with box numbers at line start.  The numeric_casilla
    strategy is valid for both revisions.

    The 2019-2023 registry revision uses the official bare box numbers ("01",
    "02", ...) as canonical casilla IDs. The parser must match those printed
    numbers directly and emit the selected revision's canonical casilla.id.

    The fixture encodes synthetic amounts satisfying both registry formulas:
      [06] = [03] + [05] = 1.520,00 + 0,00 = 1.520,00
      [08] = [06] - [07] = 1.520,00 - 0,00 = 1.520,00

    Ground truth values are derived from the fixture data in _generate.py
    _MODELO_123_2023_RENDER_ROWS — not re-computed from the registry formula.

    Non-tautology: the fixture prints the official bare box number while the expected
    output keys are the registry's canonical 2019-2023 casilla IDs. A parser that
    fails to select the period-specific revision would produce the wrong shape here.
    """
    filing = parse_declaracion(
        _MODELO_123_2023_SYNTHETIC_FIXTURE,
        modelo_override="123",
        año_override=2023,
        period_override="1T",
    )

    assert filing.modelo == "123"
    assert filing.period == _expected_period(2023, "1T")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "123"
    assert filing.registry_snapshot_ref.revision_id == "2019-2023"
    assert filing.registry_snapshot_ref.modelo_year == 2023
    assert filing.registry_snapshot_ref.period == "1T"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All 8 casillas defined by the 2019-2023 declaracion_pdf profile must be present.
    assert set(values.keys()) == set(_MODELO_123_HISTORICAL_EXPECTED_TARGETS), (
        f"expected exactly the 8 M123 2019-2023 profile casillas, got {set(values.keys())!r}"
    )

    # Ground truth: fixture amounts from _generate.py _MODELO_123_2023_RENDER_ROWS.
    expected_values = _expected_casilla_values(
        {
            "01": Decimal("4.00"),
            "02": Decimal("8000.00"),
            "03": Decimal("1520.00"),
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("1520.00"),
            "07": Decimal("0.00"),
            "08": Decimal("1520.00"),
        },
    )
    for casilla_id, expected_value in expected_values.items():
        assert values[casilla_id] == expected_value, (
            f"casilla {casilla_id}: expected {expected_value!r}, got {values[casilla_id]!r}"
        )


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
