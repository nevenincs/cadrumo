"""Round-trip extractor test against the synthetic Modelo 130 generator.

Every parametrised case renders a synthetic PDF via the L3 generator,
runs :func:`aeat.declaracion.parse_declaracion` against the bytes, and
asserts the extracted casillas equal the ground truth. This is the
scale primitive cluster D's ADR (§9 exit criteria) mandates.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .._pdf_import._shared import ExtractedCasilla
from . import (
    DeclaracionFiling,
    DeclaracionParseError,
    ExtractionStatus,
    parse_declaracion,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_financial_input,
    pytest.mark.fixture_tier_l3,
]


def _generate_pdf(
    tmp_path: Path,
    casilla_values: dict[str, str],
    *,
    año: int = 2025,
) -> Path:
    """Render a synthetic Modelo 130 PDF and return its on-disk path."""
    from tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_130_generator import (
        Modelo130GenParams,
        generate,
    )

    values = {k: Decimal(v) for k, v in casilla_values.items()}
    params = Modelo130GenParams(
        año=año,
        template_revision=f"{año}.01",
        tax_id="00000000T",
        ejercicio=str(año),
        period_printed="1T",
        csv="ABCD1234EFGH5678",
        presented_at=f"{año}-04-20 10:00:00",
        casilla_values=values,
    )
    pdf_bytes, _ = generate(params)
    pdf_path = tmp_path / f"modelo_130_{año}Q1_synthetic.pdf"
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


def _values_by_id(filing: DeclaracionFiling) -> dict[str, ExtractedCasilla]:
    return {v.casilla_id: v for v in filing.values}


@pytest.mark.parametrize(
    ("case", "casilla_values"),
    [
        (
            "happy-path",
            {
                "01": "12500.00",
                "02": "3500.00",
                "03": "9000.00",
                "04": "1800.00",
                "05": "400.00",
                "06": "0.00",
                "07": "1400.00",
            },
        ),
        (
            "zero-income",
            {
                "01": "0.00",
                "02": "0.00",
                "03": "0.00",
                "04": "0.00",
                "05": "0.00",
                "06": "0.00",
                "07": "0.00",
            },
        ),
        (
            "negative-carry-forward",
            {
                "01": "5000.00",
                "02": "8000.00",
                "03": "-3000.00",
                "04": "0.00",
                "05": "200.00",
                "06": "150.00",
                "07": "0.00",
            },
        ),
        (
            "large-amounts",
            {
                "01": "987654.32",
                "02": "123456.78",
                "03": "864197.54",
                "04": "172839.51",
                "05": "50000.00",
                "06": "25000.00",
                "07": "97839.51",
            },
        ),
    ],
)
def test_roundtrip_extract_matches_ground_truth(
    tmp_path: Path,
    case: str,
    casilla_values: dict[str, str],
) -> None:
    """Synthetic round-trip: generated PDF → extractor → ground truth."""
    del case  # present in test id for xfail targeting
    pdf_path = _generate_pdf(tmp_path, casilla_values)

    filing = parse_declaracion(pdf_path)

    assert filing.modelo == "130"
    assert filing.period == "2025Q1"
    assert filing.ejercicio == "2025"
    assert filing.tax_id == "00000000T"
    assert filing.extraction_status is ExtractionStatus.COMPLETE

    by_id = _values_by_id(filing)
    for casilla_id, expected_raw in casilla_values.items():
        assert casilla_id in by_id, f"casilla {casilla_id} not extracted"
        assert by_id[casilla_id].printed_value == Decimal(expected_raw)


def test_template_auto_detection(tmp_path: Path) -> None:
    """The parser detects Modelo 130 + 2025 without explicit overrides."""
    pdf_path = _generate_pdf(
        tmp_path,
        {"01": "100.00", "02": "50.00", "03": "50.00", "04": "10.00", "05": "0.00", "06": "0.00", "07": "10.00"},
    )
    filing = parse_declaracion(pdf_path)
    assert filing.template_revision.modelo == "130"
    assert filing.template_revision.año == 2025
    assert filing.template_revision.revision == "2025.01"


def test_missing_pdf_raises(tmp_path: Path) -> None:
    with pytest.raises(DeclaracionParseError, match="not found"):
        parse_declaracion(tmp_path / "nowhere.pdf")


def test_partial_extraction_surfaces_warnings(tmp_path: Path) -> None:
    """Leaving out some casillas still produces a filing with warnings."""
    pdf_path = _generate_pdf(tmp_path, {"01": "1000.00", "02": "500.00"})
    filing = parse_declaracion(pdf_path)
    assert filing.extraction_status is not ExtractionStatus.COMPLETE
    missing_ids = {w.casilla_id for w in filing.warnings}
    assert missing_ids >= {"03", "04", "05", "06", "07"}


@pytest.mark.parametrize("año", [2024, 2025, 2026], ids=["2024", "2025", "2026"])
def test_per_year_round_trip_resolves_to_correct_template(tmp_path: Path, año: int) -> None:
    """Issue #321: 2024 / 2025 / 2026 declaraciones each resolve to a registered extractor.

    Gemini PR-440 review surfaced that the extractor registry was
    keyed only on `(modelo="130", año=2025, revision="2025.01")` —
    so 2024 and 2026 PDFs raised `NoExtractorRegisteredError`. This
    parametrised case asserts that a synthetic PDF for each of the
    three Tier-L years parses cleanly, the resolved
    ``template_revision.año`` matches the printed ejercicio, and
    every supplied casilla round-trips to the printed value.

    The form layout is identical across 2024 / 2025 / 2026 (RIRPF
    art. 110 unchanged per the rule-delta manifest), so the same
    seven-casilla MVP fixture suffices for all three years; a future
    AEAT layout reshuffle would require a per-year fixture of its own.
    """
    casilla_values = {
        "01": "12500.00",
        "02": "3500.00",
        "03": "9000.00",
        "04": "1800.00",
        "05": "400.00",
        "06": "0.00",
        "07": "1400.00",
    }
    pdf_path = _generate_pdf(tmp_path, casilla_values, año=año)
    filing = parse_declaracion(pdf_path)

    assert filing.modelo == "130"
    assert filing.ejercicio == str(año)
    assert filing.template_revision.año == año
    assert filing.template_revision.revision == f"{año}.01"
    assert filing.extraction_status is ExtractionStatus.COMPLETE

    by_id = _values_by_id(filing)
    for casilla_id, expected_raw in casilla_values.items():
        assert casilla_id in by_id, f"casilla {casilla_id} not extracted for año={año}"
        assert by_id[casilla_id].printed_value == Decimal(expected_raw)


def test_modelo_130_ruleset_extractor_year_symmetry() -> None:
    """Issue #321: every Modelo 130 ruleset year has a matching extractor key.

    Locks in the Gemini PR-440 fix. Walks `ALL_RULESETS` for the
    Modelo 130 modelo code and the extractor `_REGISTRY` for the
    same modelo, then asserts the year-sets are equal. A future
    contributor that adds a new M130 ruleset year (e.g., 2027) is
    forced to also register the matching extractor; conversely, a
    refactor that drops V2024 or V2026 from the extractor registry
    fails this assertion before the gap can ship.

    Scoped narrowly to Modelo 130 to avoid surfacing the pre-
    existing cross-coverage gaps on other modelos (M111 2024,
    M115 2024, etc.) that EPIC #316's per-modelo Tier-L issues
    (#318, #319, #320, #322, #323, #324) will each close on their
    own schedule.
    """
    from ..formulas._rulesets import ALL_RULESETS
    from ._extractors import _REGISTRY

    ruleset_years = {r.effective_from.year for r in ALL_RULESETS if r.modelo.value == "130"}
    extractor_years = {year for (modelo, year, _rev) in _REGISTRY if modelo == "130"}
    assert ruleset_years == extractor_years, (
        f"Modelo 130 ruleset/extractor year-sets must match.\n"
        f"  ruleset years (in ALL_RULESETS):    {sorted(ruleset_years)}\n"
        f"  extractor years (in _REGISTRY):    {sorted(extractor_years)}\n"
        f"  rulesets without extractor:         {sorted(ruleset_years - extractor_years)}\n"
        f"  extractors without ruleset:         {sorted(extractor_years - ruleset_years)}\n"
        f"Add the missing class to balance the two registries."
    )


def test_full_19_casilla_liquidacion_round_trip(tmp_path: Path) -> None:
    """Issue #321: full 19-casilla liquidación block round-trips end-to-end.

    Synthetic generator renders all 19 boxes with non-zero values in
    every casilla; the extractor must recognise every label, parse
    every Spanish-formatted amount, and surface zero warnings. The
    resulting filing carries 19 ExtractedCasilla entries and an
    extraction_status of COMPLETE.

    The values below mirror the operand-swap rich fixture used by the
    mutation harness (`_modelo_130_rich_fixture`); every casilla is
    non-zero and asymmetric, so a regex collision (e.g. cas. 01 vs
    cas. 11) would surface as a value mismatch instead of a missing
    warning.
    """
    full_19 = {
        "01": "48000.00",
        "02": "12500.00",
        "03": "35500.00",
        "04": "7100.00",
        "05": "1000.00",
        "06": "500.00",
        "07": "5600.00",
        "08": "5000.00",
        "09": "100.00",
        "10": "50.00",
        "11": "50.00",
        "12": "5650.00",
        "13": "150.00",
        "14": "5500.00",
        "15": "200.00",
        "16": "300.00",
        "17": "5000.00",
        "18": "400.00",
        "19": "4600.00",
    }
    pdf_path = _generate_pdf(tmp_path, full_19)
    filing = parse_declaracion(pdf_path)

    assert filing.extraction_status is ExtractionStatus.COMPLETE
    assert len(filing.warnings) == 0, [w.casilla_id for w in filing.warnings]

    by_id = _values_by_id(filing)
    assert set(by_id.keys()) == set(full_19.keys()), (
        f"missing: {set(full_19.keys()) - set(by_id.keys())}; extra: {set(by_id.keys()) - set(full_19.keys())}"
    )
    for casilla_id, expected_raw in full_19.items():
        assert by_id[casilla_id].printed_value == Decimal(expected_raw), (
            f"cas. {casilla_id}: expected {expected_raw}, got {by_id[casilla_id].printed_value}"
        )
