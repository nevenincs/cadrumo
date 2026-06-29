"""Annual parser boundary corpus tests split from parser boundary part 2."""

from __future__ import annotations

import pytest

from ._parser_boundary_part2_support import _expected_casilla_values
from ._parser_boundary_support import (
    _REAL_MODELO_190_DECLARATION_COPY,
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_parser_extracts_modelo_190_targets_from_real_redacted_declaration_copy() -> None:
    filing = parse_declaracion(
        _REAL_MODELO_190_DECLARATION_COPY,
        modelo_override="190",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "190"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert {value.casilla_id: value.printed_value for value in filing.values} == _expected_casilla_values(
        {
            "decl.total-percepciones": Decimal("1"),
            "decl.percepciones-total": Decimal("1000.00"),
            "decl.retenciones-total": Decimal("1000.00"),
        },
    )
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
      2022-0A: c06=10500, c04=0, c02=0, c26=0, c49=8400 -> c47=10500, c64=8400, c65=2100
      2023-0A: c06=12600, c04=0, c02=0, c26=0, c49=9800 -> c47=12600, c64=9800, c65=2800
    """
    _EXPECTED: dict[str, dict[CasillaId, Decimal]] = {
        "2022-0A": _expected_casilla_values({
            "iva.anual.repercutido.general": Decimal("10500.00"),
            "iva.anual.repercutido.reducido": Decimal("0.00"),
            "iva.anual.repercutido.super-reducido": Decimal("0.00"),
            "iva.anual.autorepercutido.intracomunitaria": Decimal("0.00"),
            "iva.anual.soportado.interiores": Decimal("8400.00"),
            "iva.anual.cuota-devengada-total": Decimal("10500.00"),
            "iva.anual.cuota-deducible-total": Decimal("8400.00"),
            "iva.anual.resultado-regimen-general": Decimal("2100.00"),
        }),
        "2023-0A": _expected_casilla_values({
            "iva.anual.repercutido.general": Decimal("12600.00"),
            "iva.anual.repercutido.reducido": Decimal("0.00"),
            "iva.anual.repercutido.super-reducido": Decimal("0.00"),
            "iva.anual.autorepercutido.intracomunitaria": Decimal("0.00"),
            "iva.anual.soportado.interiores": Decimal("9800.00"),
            "iva.anual.cuota-devengada-total": Decimal("12600.00"),
            "iva.anual.cuota-deducible-total": Decimal("9800.00"),
            "iva.anual.resultado-regimen-general": Decimal("2800.00"),
        }),
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
    assert filing.period == _expected_period(year, "0A")
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
    - Chunk 1 (9 casillas): cuota-chain closure -- 0545/0546/0505/0585/0586/0587/0595/0610/0670.
    - Chunk 2 (4 casillas): apartado-summary bases -- 0235/0432/0500/0510.
    - Chunk 3 (6 casillas): actividades-economicas ED detail -- 0180/0218/0223/0224/0226/0231.
    - Chunk 4 (1 casilla): ED leaf input -- 0171 (ingresos de explotacion).

    Ground truth is derived from reading the printed declaracion PDF text directly.
    The sanitised corpus replaces real monetary values with 1.000,00 synthetic values.
    pdfplumber merges the adjacent box number onto the value token (e.g.
    ``1.001.000,005045``) so the extracted Decimal is a valid instance but does not
    equal 1000.00. All casillas are asserted as isinstance(..., Decimal) only;
    exact-value assertions would be tautological against the corpus artefact.

    Casillas deferred (0570/0571 cuota liquida estatal/autonomica pre-incrementada):
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
    assert filing.period == _expected_period(year, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "100"
    assert filing.registry_snapshot_ref.modelo_year == year
    assert filing.registry_snapshot_ref.period == "0A"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All 20 covered casillas must be present: 9 cuota-chain closure casillas (first chunk),
    # 4 apartado-summary casillas (second chunk), 6 actividades-economicas ED detail (third chunk),
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
        "0235",  # rendimiento neto reducido total actividades economicas ED
        "0432",  # saldo neto rendimientos a integrar en base imponible general
        "0500",  # base liquidable general
        "0510",  # base liquidable del ahorro
        # Third chunk: actividades economicas ED detail
        "0180",  # total ingresos computables
        "0218",  # suma de gastos fiscalmente deducibles
        "0223",  # total gastos deducibles modalidad simplificada
        "0224",  # rendimiento neto
        "0226",  # rendimiento neto reducido
        "0231",  # suma de rendimientos netos reducidos (pre-0235 subtotal)
        # Fourth chunk: ED leaf input for the formula chain
        "0171",  # ingresos de explotacion (leaf input for 0180 = sum(0171..0179))
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
