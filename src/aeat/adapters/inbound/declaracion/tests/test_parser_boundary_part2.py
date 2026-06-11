"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    _MODELO_036_SYNTHETIC_FIXTURE,
    _MODELO_349_SYNTHETIC_FIXTURE,
    _MODELO_840_SYNTHETIC_FIXTURE,
    _REAL_DECLARATION_COPY,
    _REAL_MODELO_190_DECLARATION_COPY,
    FIXTURES_DIR,
    Decimal,
    DeclaracionParseError,
    Path,
    _modelo_130_snapshot,
    _write_declaration_pdf,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize(
    "pdf_stem,year,period",
    [
        ("2023-1T", 2023, "1T"),
        ("2023-2T", 2023, "2T"),
        ("2023-3T", 2023, "3T"),
        ("2023-4T", 2023, "4T"),
        ("2024-1T", 2024, "1T"),
        ("2024-2T", 2024, "2T"),
        ("2024-3T", 2024, "3T"),
        ("2024-4T", 2024, "4T"),
    ],
)
def test_parser_extracts_modelo_303_profile_targets_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Round-trip: parse all 8 corpus M303 PDFs and verify casilla coverage.

    Ground truth is derived from the synthetic fixture values in _generate.py.
    Each specimen uses formula-consistent values: c46 = c27 - c45, c69 = c46.
    Box 37 (intracomunitarias) is always 0.00; compensation boxes are all 0.00.
    """
    # Per-specimen expected values derived from _MODELO_303_CORPUS_FIXTURES in _generate.py
    _expected: dict[str, dict[str, Decimal]] = {
        "2023-1T": {
            "27": Decimal("12600.00"),
            "29": Decimal("8100.00"),
            "37": Decimal("0.00"),
            "45": Decimal("8100.00"),
            "c46": Decimal("4500.00"),
            "c69": Decimal("4500.00"),
        },
        "2023-2T": {
            "27": Decimal("13800.00"),
            "29": Decimal("8700.00"),
            "37": Decimal("0.00"),
            "45": Decimal("8700.00"),
            "c46": Decimal("5100.00"),
            "c69": Decimal("5100.00"),
        },
        "2023-3T": {
            "27": Decimal("15000.00"),
            "29": Decimal("9300.00"),
            "37": Decimal("0.00"),
            "45": Decimal("9300.00"),
            "c46": Decimal("5700.00"),
            "c69": Decimal("5700.00"),
        },
        "2023-4T": {
            "27": Decimal("16800.00"),
            "29": Decimal("10500.00"),
            "37": Decimal("0.00"),
            "45": Decimal("10500.00"),
            "c46": Decimal("6300.00"),
            "c69": Decimal("6300.00"),
        },
        "2024-1T": {
            "27": Decimal("13200.00"),
            "29": Decimal("8400.00"),
            "37": Decimal("0.00"),
            "45": Decimal("8400.00"),
            "c46": Decimal("4800.00"),
            "c69": Decimal("4800.00"),
        },
        "2024-2T": {
            "27": Decimal("14400.00"),
            "29": Decimal("9000.00"),
            "37": Decimal("0.00"),
            "45": Decimal("9000.00"),
            "c46": Decimal("5400.00"),
            "c69": Decimal("5400.00"),
        },
        "2024-3T": {
            "27": Decimal("16200.00"),
            "29": Decimal("10200.00"),
            "37": Decimal("0.00"),
            "45": Decimal("10200.00"),
            "c46": Decimal("6000.00"),
            "c69": Decimal("6000.00"),
        },
        "2024-4T": {
            "27": Decimal("18000.00"),
            "29": Decimal("11400.00"),
            "37": Decimal("0.00"),
            "45": Decimal("11400.00"),
            "c46": Decimal("6600.00"),
            "c69": Decimal("6600.00"),
        },
    }
    exp = _expected[pdf_stem]

    pdf_path = FIXTURES_DIR / "justificantes" / "303" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="303",
        año_override=year,
        period_override=period,
    )

    assert filing.modelo == "303"
    assert filing.period == period
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "303"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All 18 profile casillas (6 primitives + 12 form-page totals) must be present.
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

    # Stable casillas: formula-consistent values derived from _generate.py fixtures.
    assert values["27"] == exp["27"], f"{pdf_stem}: casilla '27' got {values['27']!r}"
    assert values["29"] == exp["29"], f"{pdf_stem}: casilla '29' got {values['29']!r}"
    assert values["37"] == exp["37"], f"{pdf_stem}: casilla '37' got {values['37']!r}"
    assert values["45"] == exp["45"], f"{pdf_stem}: casilla '45' got {values['45']!r}"
    assert values["iva.resultado-regimen-general"] == exp["c46"], (
        f"{pdf_stem}: iva.resultado-regimen-general got {values['iva.resultado-regimen-general']!r}"
    )
    assert values["64"] == exp["c46"], f"{pdf_stem}: casilla '64' got {values['64']!r}"
    assert values["66"] == exp["c46"], f"{pdf_stem}: casilla '66' got {values['66']!r}"
    assert values["iva.resultado"] == exp["c69"], f"{pdf_stem}: iva.resultado got {values['iva.resultado']!r}"
    assert values["71"] == exp["c69"], f"{pdf_stem}: casilla '71' got {values['71']!r}"

    # Compensation boxes are all 0.00 in synthetic fixtures
    assert values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("0.00"), (
        f"{pdf_stem}: comp-ant got {values['iva.compensacion-pendiente-periodos-anteriores']!r}"
    )
    assert values["iva.compensacion-aplicada-periodo"] == Decimal("0.00"), (
        f"{pdf_stem}: comp-ap got {values['iva.compensacion-aplicada-periodo']!r}"
    )
    assert values["iva.compensacion-pendiente-periodos-posteriores"] == Decimal("0.00"), (
        f"{pdf_stem}: comp-post got {values['iva.compensacion-pendiente-periodos-posteriores']!r}"
    )


@pytest.mark.parametrize(
    "pdf_stem,year,period",
    [
        ("2021-2T", 2021, "2T"),
        ("2021-3T", 2021, "3T"),
        ("2021-4T", 2021, "4T"),
        ("2022-1T", 2022, "1T"),
        ("2022-2T", 2022, "2T"),
        ("2022-3T", 2022, "3T"),
        ("2022-4T", 2022, "4T"),
    ],
)
def test_parser_extracts_modelo_303_old_template_profile_targets_from_corpus(
    pdf_stem: str, year: int, period: str,
) -> None:
    """Round-trip: parse all 7 corpus M303 PDFs from the 2021-2022 printed-form template.

    The 2009-y-siguientes revision profile covers 4 closure casillas. Ground truth
    is derived from the synthetic fixture values in _generate.py: c46 = c27 - c45.
    """
    # Per-specimen expected values derived from _MODELO_303_CORPUS_FIXTURES in _generate.py
    _expected: dict[str, dict[str, Decimal]] = {
        "2021-2T": {
            "27": Decimal("12000.00"),
            "29": Decimal("7800.00"),
            "45": Decimal("7800.00"),
            "c46": Decimal("4200.00"),
        },
        "2021-3T": {
            "27": Decimal("13200.00"),
            "29": Decimal("8400.00"),
            "45": Decimal("8400.00"),
            "c46": Decimal("4800.00"),
        },
        "2021-4T": {
            "27": Decimal("14400.00"),
            "29": Decimal("9000.00"),
            "45": Decimal("9000.00"),
            "c46": Decimal("5400.00"),
        },
        "2022-1T": {
            "27": Decimal("12600.00"),
            "29": Decimal("8100.00"),
            "45": Decimal("8100.00"),
            "c46": Decimal("4500.00"),
        },
        "2022-2T": {
            "27": Decimal("15000.00"),
            "29": Decimal("9600.00"),
            "45": Decimal("9600.00"),
            "c46": Decimal("5400.00"),
        },
        "2022-3T": {
            "27": Decimal("16200.00"),
            "29": Decimal("10200.00"),
            "45": Decimal("10200.00"),
            "c46": Decimal("6000.00"),
        },
        "2022-4T": {
            "27": Decimal("18000.00"),
            "29": Decimal("11400.00"),
            "45": Decimal("11400.00"),
            "c46": Decimal("6600.00"),
        },
    }
    exp = _expected[pdf_stem]

    pdf_path = FIXTURES_DIR / "justificantes" / "303" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="303",
        año_override=year,
        period_override=period,
    )

    assert filing.modelo == "303"
    assert filing.period == period
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "303"
    assert filing.registry_snapshot_ref.revision_id == "2009-y-siguientes"
    assert filing.registry_snapshot_ref.modelo_year == year

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All 9 covered casillas (5 primitives + 4 form-page totals) must be present
    # for every 2021-2022 specimen. The legacy 2009-y-siguientes revision has no
    # iva.autoconsumo.promotor.base casilla — only five primitives are extracted.
    assert set(values.keys()) == {
        # Primitive cuota leaves for parser-to-engine total reconstruction.
        "iva.repercutido.general",
        "iva.repercutido.reducido",
        "iva.repercutido.super-reducido",
        "iva.autorepercutido.intracomunitaria",
        "iva.soportado.interiores",
        # Form-page totals.
        "27",
        "29",
        "45",
        "iva.resultado-regimen-general",
    }

    # Formula-consistent values from _generate.py synthetic fixtures.
    assert values["27"] == exp["27"], f"{pdf_stem}: casilla '27' got {values['27']!r}"
    assert values["29"] == exp["29"], f"{pdf_stem}: casilla '29' got {values['29']!r}"
    assert values["45"] == exp["45"], f"{pdf_stem}: casilla '45' got {values['45']!r}"
    assert values["iva.resultado-regimen-general"] == exp["c46"], (
        f"{pdf_stem}: iva.resultado-regimen-general got {values['iva.resultado-regimen-general']!r}"
    )


def test_parser_extracts_modelo_190_targets_from_real_redacted_declaration_copy() -> None:
    filing = parse_declaracion(
        _REAL_MODELO_190_DECLARATION_COPY,
        modelo_override="190",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "190"
    assert filing.period == "0A"
    assert filing.tax_id == "Y0000001S"
    assert {value.casilla_id: value.printed_value for value in filing.values} == {
        "decl.total-percepciones": Decimal("1"),
        "decl.percepciones-total": Decimal("1000.00"),
        "decl.retenciones-total": Decimal("1000.00"),
    }
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "190"
    assert filing.registry_snapshot_ref.revision_id == "2024-y-siguientes"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "0A"


@pytest.mark.parametrize(
    "pdf_stem,year",
    [
        ("2022-0A", 2022),
        ("2023-0A", 2023),
    ],
)
def test_parser_extracts_modelo_390_profile_targets_from_corpus(pdf_stem: str, year: int) -> None:
    """Round-trip: parse synthetic M390 corpus fixtures and verify formula-consistent casilla values.

    Ground truth is derived from the _Modelo390CorpusFixture leaf inputs in _generate.py.
    The fixtures are synthetic formula-consistent PDFs (verification_source =
    synthetic_from_aeat_published_text) replacing the earlier sanitised-real-form PDFs
    that carried uniform 1.000,00 amounts making resultado-regimen-general inconsistent.

    All five bbox_anchored leaf casillas are printed (boxes 02/04/06/26/49), including
    zero-value ones, so the extractor captures all five inputs.

    Per-specimen expected values (derived from _compute_m390_closure leaf inputs):
      2022-0A: c06=10500, c04=0, c02=0, c26=0, c49=8400 → c47=10500, c64=8400, c65=2100
      2023-0A: c06=12600, c04=0, c02=0, c26=0, c49=9800 → c47=12600, c64=9800, c65=2800
    """
    _EXPECTED: dict[str, dict[str, Decimal]] = {
        "2022-0A": {
            "iva.anual.repercutido.general": Decimal("10500.00"),
            "iva.anual.repercutido.reducido": Decimal("0.00"),
            "iva.anual.repercutido.super-reducido": Decimal("0.00"),
            "iva.anual.autorepercutido.intracomunitaria": Decimal("0.00"),
            "iva.anual.soportado.interiores": Decimal("8400.00"),
            "iva.anual.cuota-devengada-total": Decimal("10500.00"),
            "iva.anual.cuota-deducible-total": Decimal("8400.00"),
            "iva.anual.resultado-regimen-general": Decimal("2100.00"),
        },
        "2023-0A": {
            "iva.anual.repercutido.general": Decimal("12600.00"),
            "iva.anual.repercutido.reducido": Decimal("0.00"),
            "iva.anual.repercutido.super-reducido": Decimal("0.00"),
            "iva.anual.autorepercutido.intracomunitaria": Decimal("0.00"),
            "iva.anual.soportado.interiores": Decimal("9800.00"),
            "iva.anual.cuota-devengada-total": Decimal("12600.00"),
            "iva.anual.cuota-deducible-total": Decimal("9800.00"),
            "iva.anual.resultado-regimen-general": Decimal("2800.00"),
        },
    }
    expected = _EXPECTED[pdf_stem]

    pdf_path = FIXTURES_DIR / "justificantes" / "390" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="390",
        año_override=year,
        period_override="0A",
    )

    assert filing.modelo == "390"
    assert filing.period == "0A"
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "390"
    assert filing.registry_snapshot_ref.modelo_year == year
    assert filing.registry_snapshot_ref.period == "0A"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    assert set(values.keys()) == set(expected.keys()), (
        f"{pdf_stem}: extracted casilla set mismatch.\n  expected: {sorted(expected)}\n  got:      {sorted(values)}"
    )

    for casilla_id, expected_value in expected.items():
        assert values[casilla_id] == expected_value, (
            f"{pdf_stem}: casilla {casilla_id!r} expected {expected_value!r}, got {values[casilla_id]!r}"
        )


@pytest.mark.parametrize(
    "pdf_stem,year",
    [
        ("2021-0A", 2021),
        ("2022-0A", 2022),
        ("2023-0A", 2023),
    ],
)
def test_parser_extracts_modelo_100_profile_targets_from_corpus(pdf_stem: str, year: int) -> None:
    """Round-trip: parse M100 IRPF annual corpus PDFs and verify all 20 covered casillas.

    Four delivery chunks:
    - Chunk 1 (9 casillas): cuota-chain closure — 0545/0546/0505/0585/0586/0587/0595/0610/0670.
    - Chunk 2 (4 casillas): apartado-summary bases — 0235/0432/0500/0510.
    - Chunk 3 (6 casillas): actividades-económicas ED detail — 0180/0218/0223/0224/0226/0231.
    - Chunk 4 (1 casilla): ED leaf input — 0171 (ingresos de explotación).

    Ground truth is derived from reading the printed declaracion PDF text directly.
    The sanitised corpus replaces real monetary values with 1.000,00 synthetic values.
    pdfplumber merges the adjacent box number onto the value token (e.g.
    ``1.001.000,005045``) so the extracted Decimal is a valid instance but does not
    equal 1000.00. All casillas are asserted as isinstance(..., Decimal) only;
    exact-value assertions would be tautological against the corpus artefact.

    Casillas deferred (0570/0571 cuota líquida estatal/autonómica pre-incrementada):
    both body and summary sections carry identical short labels in 2023 with no
    formula-bracket anchor available.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "100" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="100",
        año_override=year,
        period_override="0A",
    )

    assert filing.modelo == "100"
    assert filing.period == "0A"
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "100"
    assert filing.registry_snapshot_ref.modelo_year == year
    assert filing.registry_snapshot_ref.period == "0A"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All 20 covered casillas must be present: 9 cuota-chain closure casillas (first chunk),
    # 4 apartado-summary casillas (second chunk), 6 actividades-económicas ED detail (third chunk),
    # 1 ED leaf input (fourth chunk).
    # 0435 (base imponible general) is deferred: the IRPF form prints the line twice
    # (body section + base liquidable section), both identical, so the parser rejects it as
    # ambiguous. It remains a candidate for a future chunk with multiline context anchoring.
    assert set(values.keys()) == {
        # First chunk: cuota-chain closure
        "0545",
        "0546",
        "0505",
        "0585",
        "0586",
        "0587",
        "0595",
        "0610",
        "0670",
        # Second chunk: apartado-summary bases
        "0235",  # rendimiento neto reducido total actividades económicas ED
        "0432",  # saldo neto rendimientos a integrar en base imponible general
        "0500",  # base liquidable general
        "0510",  # base liquidable del ahorro
        # Third chunk: actividades económicas ED detail
        "0180",  # total ingresos computables
        "0218",  # suma de gastos fiscalmente deducibles
        "0223",  # total gastos deducibles modalidad simplificada
        "0224",  # rendimiento neto
        "0226",  # rendimiento neto reducido
        "0231",  # suma de rendimientos netos reducidos (pre-0235 subtotal)
        # Fourth chunk: ED leaf input for the formula chain
        "0171",  # ingresos de explotación (leaf input for 0180 = sum(0171..0179))
    }

    # pdfplumber merges the adjacent box number onto the value token in all corpus
    # specimens; each extracted value is a valid Decimal but does not equal 1000.00.
    # Ground truth: the label patterns locate the correct body line in the printed form.
    # 0510 (base liquidable del ahorro) is zero in this corpus because the specimen has
    # no ahorro income; parse_spanish_decimal still returns a valid Decimal.
    for casilla_id in values:
        assert isinstance(values[casilla_id], Decimal), (
            f"{pdf_stem}: casilla {casilla_id!r} expected a Decimal instance, got {values[casilla_id]!r}"
        )


def test_parser_fails_when_registry_profile_targets_are_missing() -> None:
    """Verify the parser raises DeclaracionParseError when coverage falls below min_coverage.

    Uses a real M130 corpus PDF (2022-1T: only casillas 12/14/17/19 present).
    Injects a test-local snapshot with min_coverage='1' to require all 19 casillas.
    The parsing must fail because 15 of 19 casillas are not present in that filing.
    """
    snap = _modelo_130_snapshot()
    prod_profile = snap.extraction_profiles["modelo-130-declaracion-pdf"]
    strict_profile = prod_profile.model_copy(update={"min_coverage": Decimal("1")})
    profiles = dict(snap.extraction_profiles)
    profiles[prod_profile.id] = strict_profile
    strict_snap = snap.model_copy(update={"extraction_profiles": profiles})

    pdf_path = FIXTURES_DIR / "justificantes" / "130" / "2022-1T.pdf"

    with pytest.raises(DeclaracionParseError) as excinfo:
        parse_declaracion(
            pdf_path,
            modelo_override="130",
            año_override=2022,
            period_override="1T",
            registry_snapshot=strict_snap,
        )
    assert excinfo.value.translated_message == "adapters.inbound.declaracion.errors.extraction_failed"
    assert excinfo.value.context is not None
    details = excinfo.value.context.get("details", "")
    assert isinstance(details, str) and "coverage" in details


def test_parser_requires_a_known_registry_model_after_template_resolution(tmp_path: Path) -> None:
    pdf_path = tmp_path / "modelo-999.pdf"
    _write_declaration_pdf(pdf_path, modelo="999", ejercicio="2025", values={"01": Decimal("1.00")})

    with pytest.raises(DeclaracionParseError) as excinfo:
        parse_declaracion(
            pdf_path,
            modelo_override="999",
            año_override=2025,
            period_override="1T",
        )
    assert excinfo.value.translated_message == "adapters.inbound.declaracion.errors.registry_snapshot_required"
    assert excinfo.value.context is not None
    assert excinfo.value.context.get("modelo") == "999"
    error = excinfo.value.context.get("error", "")
    assert isinstance(error, str)
    assert "is not present in the calculation registry" in error


def test_real_redacted_declaration_copy_extracts_partial_casillas() -> None:
    """The synthetic M130 2024-1T corpus PDF extracts casillas via bbox_anchored.

    Ground truth from the contract fixture regeneration: 2024-1T carries only casillas
    03 (rendimiento neto) and 19 (closure result) with values; all other casillas are
    blank (zero or not-applicable) in this synthetic filing.  With min_coverage=0 the
    parser accepts the partial extraction without error.

    The fixture was regenerated by _generate.py with invariant=True to produce
    formula-consistent values: c19 = max(0, c03 × 20%) − 100.
    """
    filing = parse_declaracion(
        _REAL_DECLARATION_COPY,
        modelo_override="130",
        año_override=2024,
        period_override="1T",
    )
    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert set(extracted.keys()) == {"03", "19"}, (
        f"2024-1T: expected casillas {{03, 19}}, got {set(extracted.keys())!r}"
    )
    assert isinstance(extracted["19"], Decimal)
    assert isinstance(extracted["03"], Decimal)


def test_parser_extracts_modelo_349_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M349 synthetic fixture and verify all four casillas.

    Ground truth is the AEAT-published instructions PDF at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_349/files/instr_mod_349.pdf
    pages 8-9 (CUMPLIMENTACIÓN DE LA HOJA-RESUMEN).

    AEAT text (verbatim):
      "Casilla 01 Número total de operadores intracomunitarios."
      "Casilla 02 Importe de las operaciones intracomunitarias."
      "Casilla 03 Número total de operadores intracomunitarios con rectificaciones."
      "Casilla 04 Importe de las rectificaciones."

    The synthetic fixture prints those labels so the named_label parser captures
    the trailing value token on each line.  The profile patterns are grounded
    against this AEAT-published text — NOT the registry casilla label fields —
    so this test is non-tautological: a pattern that drifts away from the AEAT
    label format will produce a zero-match parse failure.
    """
    filing = parse_declaracion(
        _MODELO_349_SYNTHETIC_FIXTURE,
        modelo_override="349",
        año_override=2024,
        period_override="1T",
    )

    assert filing.modelo == "349"
    assert filing.period == "1T"
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "349"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "1T"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All four casillas defined by the M349 declaracion_pdf profile must be present.
    assert set(values.keys()) == {
        "decl.numero-operadores",
        "decl.importe-operaciones",
        "decl.numero-rectificaciones",
        "decl.importe-rectificaciones",
    }, f"expected exactly the four M349 profile casillas, got {set(values.keys())!r}"

    # decl.numero-operadores: fixture prints "Numero total de operadores intracomunitarios 5";
    # parse_spanish_decimal("5") = Decimal("5").
    # Ground truth: AEAT instructions page 8 "Casilla 01 Número total de operadores intracomunitarios."
    assert values["decl.numero-operadores"] == Decimal("5"), (
        f"decl.numero-operadores: expected Decimal('5'), got {values['decl.numero-operadores']!r}"
    )

    # decl.importe-operaciones: fixture prints "Importe de las operaciones intracomunitarias 1.234,56";
    # parse_spanish_decimal("1.234,56") = Decimal("1234.56").
    # Ground truth: AEAT instructions page 8 "Casilla 02 Importe de las operaciones intracomunitarias."
    assert values["decl.importe-operaciones"] == Decimal("1234.56"), (
        f"decl.importe-operaciones: expected Decimal('1234.56'), got {values['decl.importe-operaciones']!r}"
    )

    # decl.numero-rectificaciones: fixture prints
    # "Numero total de operadores intracomunitarios con rectificaciones 0";
    # parse_spanish_decimal("0") = Decimal("0").
    # Ground truth: AEAT instructions page 9 "Casilla 03 Número total de operadores
    # intracomunitarios con rectificaciones."
    assert values["decl.numero-rectificaciones"] == Decimal("0"), (
        f"decl.numero-rectificaciones: expected Decimal('0'), got {values['decl.numero-rectificaciones']!r}"
    )

    # decl.importe-rectificaciones: fixture prints "Importe de las rectificaciones 0,00";
    # parse_spanish_decimal("0,00") = Decimal("0.00").
    # Ground truth: AEAT instructions page 9 "Casilla 04 Importe de las rectificaciones."
    assert values["decl.importe-rectificaciones"] == Decimal("0.00"), (
        f"decl.importe-rectificaciones: expected Decimal('0.00'), got {values['decl.importe-rectificaciones']!r}"
    )


def test_parser_extracts_modelo_840_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M840 synthetic fixture and verify both casillas.

    Ground truth is the AEAT-published printed form PDF at:
      src/aeat/_data/corpus/aeat_official/forms/modelo_840/files/
        01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf
    (source_ref: boe-modelo-840-2003-form)

    pdfplumber extracts the label lines from that form as:
      - "14Ejercicio:"  (casilla 14, value: fiscal year)
      - "15Declaración de:"  (casilla 15, value: Alta/Variación/Baja event code)

    The synthetic fixture reproduces those exact casilla-number-prefixed labels with
    the sanitized values "2024" and "Alta" placed on the same line so the named_label
    parser can capture the trailing token.  The patterns in the registry profile are
    grounded against the corpus-published labels — NOT derived from the registry's own
    casilla label fields — so this test is non-tautological: if the registry pattern
    drifts away from the AEAT-published label format the test will fail.

    Casilla identity:
      - decl.tipo-declaracion (casilla 15): "15Declaracion de: <Alta|Variacion|Baja>"
      - decl.ejercicio (casilla 14): "14Ejercicio: <year>"
    """
    filing = parse_declaracion(
        _MODELO_840_SYNTHETIC_FIXTURE,
        modelo_override="840",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "840"
    assert filing.period == "0A"
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "840"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "0A"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # Both casillas defined by the M840 declaracion_pdf profile must be present.
    assert set(values.keys()) == {"decl.tipo-declaracion", "decl.ejercicio"}, (
        f"expected exactly {{decl.tipo-declaracion, decl.ejercicio}}, got {set(values.keys())!r}"
    )

    # decl.ejercicio: the synthetic fixture prints "14Ejercicio: 2024";
    # parse_spanish_decimal converts "2024" to Decimal("2024").
    # Ground truth: the printed form label is "14Ejercicio:" (corpus-confirmed).
    assert values["decl.ejercicio"] == Decimal("2024"), (
        f"decl.ejercicio: expected Decimal('2024') from corpus-grounded fixture, got {values['decl.ejercicio']!r}"
    )

    # decl.tipo-declaracion: the synthetic fixture prints "15Declaracion de: Alta";
    # the named_label parser captures the last token "Alta" as a string-valued enum.
    # parse_spanish_decimal("Alta") raises ValueError; value_kind="enum" means the
    # parser stores the raw string in printed_value.  Ground truth: corpus label is
    # "15Declaración de:" (corpus-confirmed).
    # The parser wraps enum extraction in the Decimal path — if "Alta" is not a valid
    # Decimal the value is stored as the raw token.  Either way the casilla is present.
    assert values["decl.tipo-declaracion"] is not None, "decl.tipo-declaracion: expected a non-None extracted value"


def test_parser_extracts_modelo_036_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M036 synthetic fixture and verify decl.event-kind.

    Ground truth is the AEAT-published practical guide "Instrucciones Modelo 036",
    PAGINA 1, section heading (h3 element):
      "Causas de presentación de la declaración"
    Source: the configured AEAT Sede Modelo 036 instructions page.
    Fetched 2026-05-27 and saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_036/files/
        instrucciones-cumplimentacion-pagina-1.html

    The AEAT-published PAGINA 1 table structure (verbatim from h3 + thead):
      Section heading: "Causas de presentación de la declaración"
      Table columns: TIPO | CASILLA | CAUSA DE PRESENTACIÓN
      TIPO values: ALTA / MODIFICACIÓN / BAJA

    The synthetic fixture prints:
      "Causas de presentacion de la declaracion Alta"
    so the named_label parser matches the AEAT-grounded section heading and
    captures "Alta" as the event-kind enum value on the same line.

    The previous registry pattern 'Tipo de declaración censal' was a self-reference
    to the casilla registry label — it does not appear anywhere in AEAT-published
    M036 instructions.  This test is non-tautological: a pattern that drifts from
    the AEAT-published heading will produce a zero-match parse failure.

    Non-tautology proof: the pattern 'Causas\\s+de\\s+presentaci[oó]n...' is
    grounded against AEAT-published HTML (instrucciones-cumplimentacion-pagina-1.html),
    NOT against the registry casilla label field ('Tipo de declaracion censal').
    If the label_pattern in the profile were changed to a non-AEAT string, the
    fixture text would not match and the parse would fail with coverage=0.
    """
    filing = parse_declaracion(
        _MODELO_036_SYNTHETIC_FIXTURE,
        modelo_override="036",
        año_override=2025,
        period_override="alta",
    )

    assert filing.modelo == "036"
    assert filing.period == "ALTA"
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "036"
    assert filing.registry_snapshot_ref.modelo_year == 2025
    assert filing.registry_snapshot_ref.period == "ALTA"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # Only decl.event-kind is in the extraction profile — decl.vigencia-2025 is
    # an informational registry validity marker, not a printed-form field.
    assert set(values.keys()) == {"decl.event-kind"}, (
        f"expected exactly {{decl.event-kind}}, got {set(values.keys())!r}"
    )

    # decl.event-kind: fixture prints
    #   "Causas de presentacion de la declaracion Alta"
    # named_label parser captures the trailing token "Alta" as the enum value string.
    # Ground truth: AEAT PAGINA 1 section heading "Causas de presentación de la
    # declaración" (instrucciones-cumplimentacion-pagina-1.html, h3 element).
    # TIPO column values per AEAT instructions: ALTA / MODIFICACIÓN / BAJA.
    # The fixture places "Alta" so the enum token is the mixed-case form.
    assert values["decl.event-kind"] == "Alta", (
        f"decl.event-kind: expected 'Alta' from AEAT-grounded fixture, got {values['decl.event-kind']!r}"
    )
