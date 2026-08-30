"""Modelo 131 current-year (2024/2025) declaración extractor tests.

No real ejercicio-2024/2025 declaración PDF specimen is bundled for Modelo
131 (the corpus under ``tests/fixtures/justificantes/131/`` covers the
committed synthetic 2024-1T fixture only, which is also the fixture the
already-shipped 2026 ``declaracion_pdf`` profile round-trips against -- see
``test_parser_extracts_modelo_131_casillas_from_synthetic_fixture`` in
``test_parser_synthetic_fixtures_quarterly.py``). These tests round-trip the
registry ``declaracion_pdf`` extraction profiles for the 2024 and 2025
revisions against that same committed fixture (forced onto each target
revision via ``template_revision_override``), grounded in the bundled
AEAT-published Diseño de Registro field dictionaries for ejercicio 2024/2025
(see ``corpus/aeat_official/disenos_registro/modelo_131/files/``), per the
``verification_source = "synthetic_from_aeat_published_text"`` grounding
tier the registry profile declares. The printed layout (line-end box number,
value immediately to the right) is unchanged across the 2024/2025/2026
revisions per the bundled DR dictionaries, so the one committed fixture
grounds all three revisions' profiles.

See Also:
    :func:`~adapters.inbound.declaracion.parse_declaracion`
        Public parser entry point exercised for the 2024 and 2025 profiles.
    :class:`~domain.calculations.registry._schema_extraction.ExtractionProfileDefinition`
        Registry-owned ``declaracion_pdf`` profile contract asserted here.
    ``test_parser_synthetic_fixtures_quarterly.py``
        Sibling 2026 fixture round-trip reused as the current-year layout
        precedent.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import FIXTURES_DIR, CasillaId, _expected_period, _modelo_snapshot, parse_declaracion

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

# Ground truth mirrors the amounts _generate_misc_b.py stamps onto the
# committed fixture PDF (the single source of the fixture's printed values);
# identical to _M131_EXPECTED_VALUES in _parser_synthetic_quarterly_support.py.
_M131_CURRENT_YEAR_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    validated_casilla_id("01", surface="declaracion_parser_boundary.casilla"): Decimal("5000.00"),
    validated_casilla_id("02", surface="declaracion_parser_boundary.casilla"): Decimal("100.00"),
    validated_casilla_id("03", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("04", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("05", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("06", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("07", surface="declaracion_parser_boundary.casilla"): Decimal("100.00"),
    validated_casilla_id("08", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("09", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("10", surface="declaracion_parser_boundary.casilla"): Decimal("100.00"),
    validated_casilla_id("11", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("12", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("13", surface="declaracion_parser_boundary.casilla"): Decimal("100.00"),
    validated_casilla_id("14", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("15", surface="declaracion_parser_boundary.casilla"): Decimal("100.00"),
}

_M131_CURRENT_YEAR_EXPECTED_CASILLAS = frozenset(_M131_CURRENT_YEAR_EXPECTED_VALUES)


@pytest.mark.parametrize(
    ("year", "profile_id"),
    [
        (2024, "modelo-131-2024-declaracion-pdf"),
        (2025, "modelo-131-2025-declaracion-pdf"),
    ],
    ids=["2024", "2025"],
)
def test_parser_extracts_modelo_131_current_year_profile_targets(year: int, profile_id: str) -> None:
    """Registry profile declares exactly the 15-casilla current-year target set."""
    snapshot = _modelo_snapshot("131", filing_year=year, period="1T")
    profile = snapshot.extraction_profiles[profile_id]
    assert {target.casilla_id for target in profile.target_casillas} == _M131_CURRENT_YEAR_EXPECTED_CASILLAS
    for target in profile.target_casillas:
        assert target.match_strategy == "bbox_anchored"
        assert target.bbox_anchor is not None
        assert target.bbox_anchor.box_number_pattern


@pytest.mark.parametrize("year", [2024, 2025], ids=["2024", "2025"])
def test_parser_extracts_modelo_131_current_year_profile_targets_from_committed_synthetic_fixture(
    year: int,
) -> None:
    """Round-trip the committed DR-faithful synthetic Modelo 131 fixture per revision.

    Ground truth: the committed fixture PDF (built by ``_generate_misc_b.py``)
    reproduces the AEAT-published Diseño de Registro line-end box-number
    layout verbatim for each target casilla, followed by its stamped amount.
    The parser must recover every declared value exactly -- a drift between
    the registry ``bbox_anchor.box_number_pattern`` and the real DR layout
    produces a zero-match parse failure on this fixture.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "131" / "2024-1T.pdf"
    assert pdf_path.is_file(), f"missing committed M131 synthetic fixture at {pdf_path}"

    # The committed fixture stamps "Ejercicio: 2024" in its printed body; force
    # the target revision explicitly (as the existing 2026 round-trip test
    # already does) rather than relying on año-detection, since this single
    # fixture is reused to ground the 2024 and 2025 profiles alike.
    filing = parse_declaracion(
        pdf_path,
        modelo_override="131",
        template_revision_override=str(year),
        año_override=year,
        period_override="1T",
    )

    assert filing.modelo == "131"
    assert filing.period == _expected_period(year, "1T")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "131"
    assert filing.registry_snapshot_ref.modelo_year == year
    assert filing.registry_snapshot_ref.period == "1T"

    extracted = {value.casilla_id: value.printed_value for value in filing.values}
    assert extracted == _M131_CURRENT_YEAR_EXPECTED_VALUES, (
        f"{year}: unexpected extracted values.\n  got: {extracted}\n  expected: {_M131_CURRENT_YEAR_EXPECTED_VALUES}"
    )
