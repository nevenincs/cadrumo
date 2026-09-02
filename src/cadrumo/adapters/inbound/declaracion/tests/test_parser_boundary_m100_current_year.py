"""Modelo 100 current-year (2024/2025) declaración extractor tests.

No real ejercicio-2024/2025 declaración PDF specimen is bundled (the corpus
under ``tests/fixtures/justificantes/100/`` covers 2021-2023 only). These
tests round-trip the registry ``declaracion_pdf`` extraction profile against
the committed DR-faithful synthetic fixtures at
``tests/fixtures/justificantes/100/{2024,2025}-0A.pdf``, built from the
bundled AEAT-published Diseño de Registro field dictionaries for ejercicio
2024 and 2025 (see ``corpus/aeat_official/disenos_registro/modelo_100/files/``),
per the ``verification_source = "synthetic_from_aeat_published_text"``
grounding tier the registry profile declares.

See Also:
    :func:`~adapters.inbound.declaracion.parser.parse_declaracion`
        Public declaration-copy parser exercised against the current-year
        synthetic fixtures.
    :class:`~domain.calculations.registry._schema_extraction.ExtractionProfileDefinition`
        Registry-owned ``declaracion_pdf`` profile contract asserted here.
    :mod:`~adapters.inbound.declaracion.tests._parser_boundary_m100_current_support`
        Shared typed expected-casilla set for the 2024/2025 fixtures.
    ``tests/fixtures/justificantes/_generate_modelo_100_current.py``
        Fixture generator that stamps the expected printed values.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._parser_boundary_m100_current_support import M100_CURRENT_YEAR_EXPECTED_CASILLAS
from ._parser_boundary_support import (
    FIXTURES_DIR,
    _expected_period,
    _modelo_snapshot,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

# Ground truth mirrors the amounts _generate_modelo_100_current.py stamps onto
# the committed fixture PDFs (the single source of the fixture's printed values).
_M100_CURRENT_YEAR_EXPECTED_VALUES: dict[str, Decimal] = {
    "0171": Decimal("1000.00"),
    "0180": Decimal("1000.00"),
    "0218": Decimal("0.00"),
    "0223": Decimal("0.00"),
    "0224": Decimal("1000.00"),
    "0226": Decimal("1000.00"),
    "0231": Decimal("1000.00"),
    "0235": Decimal("1000.00"),
    "0432": Decimal("1000.00"),
    "0500": Decimal("1000.00"),
    "0505": Decimal("1000.00"),
    "0510": Decimal("0.00"),
    "0545": Decimal("100.00"),
    "0546": Decimal("100.00"),
    "0585": Decimal("100.00"),
    "0586": Decimal("100.00"),
    "0587": Decimal("200.00"),
    "0595": Decimal("200.00"),
    "0604": Decimal("50.00"),
    "0610": Decimal("150.00"),
    "0670": Decimal("150.00"),
}


@pytest.mark.parametrize(
    ("year", "profile_id"),
    [
        (2024, "modelo-100-2024-declaracion-pdf"),
        (2025, "modelo-100-2025-declaracion-pdf"),
    ],
    ids=["2024", "2025"],
)
def test_parser_extracts_modelo_100_current_year_profile_targets(year: int, profile_id: str) -> None:
    """Registry profile declares exactly the 21-casilla current-year target set."""
    snapshot = _modelo_snapshot("100", filing_year=year, period="0A")
    profile = snapshot.extraction_profiles[profile_id]
    assert {target.casilla_id for target in profile.target_casillas} == M100_CURRENT_YEAR_EXPECTED_CASILLAS
    for target in profile.target_casillas:
        assert target.match_strategy == "named_label"
        assert target.label_pattern


@pytest.mark.parametrize("year", [2024, 2025], ids=["2024", "2025"])
def test_parser_extracts_modelo_100_current_year_profile_targets_from_committed_synthetic_fixture(
    year: int,
) -> None:
    """Round-trip the committed DR-faithful synthetic Modelo 100 current-year fixture.

    Ground truth: the committed fixture PDF (built by
    ``_generate_modelo_100_current.py``) reproduces the AEAT-published Diseño de
    Registro field-dictionary label text verbatim for each target casilla,
    followed by its stamped amount. The parser must recover every declared
    value exactly -- a drift between the registry ``label_pattern`` and the
    real DR vocabulary produces a zero-match parse failure on this fixture.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "100" / f"{year}-0A.pdf"
    assert pdf_path.is_file(), f"missing committed M100 current-year fixture at {pdf_path}"

    filing = parse_declaracion(pdf_path, modelo_override="100", año_override=year, period_override="0A")

    assert filing.modelo == "100"
    assert filing.period == _expected_period(year, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "100"
    assert filing.registry_snapshot_ref.modelo_year == year
    assert filing.registry_snapshot_ref.period == "0A"

    extracted = {value.casilla_id: value.printed_value for value in filing.values}
    assert set(extracted.keys()) == M100_CURRENT_YEAR_EXPECTED_CASILLAS, (
        f"{year}: unexpected casilla set.\n  got: {sorted(extracted)}\n"
        f"  expected: {sorted(M100_CURRENT_YEAR_EXPECTED_CASILLAS)}"
    )
    for casilla_id, expected_value in _M100_CURRENT_YEAR_EXPECTED_VALUES.items():
        assert extracted[casilla_id] == expected_value, (
            f"{year}: casilla {casilla_id!r}: expected {expected_value!r}, got {extracted[casilla_id]!r}"
        )
