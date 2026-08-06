"""Modelo 111 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_m111_support import (
    _M111_CASILLA_30,
    _M111_CORPUS_IDS,
    _M111_CORPUS_PARAMS,
    _M111_EXPECTED_VALUES_BY_STEM,
    _M111_FORM_TIED_CASILLAS,
)
from ._parser_boundary_support import (
    _MODELO_111_EXPECTED_TARGETS,
    FIXTURES_DIR,
    Decimal,
    _expected_period,
    _modelo_snapshot,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_parser_extracts_modelo_111_registry_profile_targets_from_pdf() -> None:
    """Assert the M111 declaracion_pdf profile declares exactly the expected 29 targets."""
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


@pytest.mark.parametrize("pdf_stem,year,period", _M111_CORPUS_PARAMS, ids=_M111_CORPUS_IDS)
def test_parser_extracts_modelo_111_casillas_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Round-trip all M111 corpus PDFs through the production bbox_anchored profile."""
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

    values = {value.casilla_id: value.printed_value for value in filing.values}
    assert _M111_CASILLA_30 in values, (
        f"{pdf_stem}: expected casilla {_M111_CASILLA_30!r} in extracted values, got {set(values.keys())!r}"
    )

    # Exact map, not a subset: the extracted set IS the claim. A ratio or a
    # subset check survives a bbox anchor that stopped resolving one column
    # while another started, and the three-column layout is exactly where that
    # can happen. Each quarter's amounts are distinct from every other
    # quarter's, so a cross-fixture misread names itself too.
    expected = _M111_EXPECTED_VALUES_BY_STEM[pdf_stem]
    assert values == expected, (
        f"{pdf_stem}: extracted casillas drifted from what the render prints.\n"
        f"  unexpectedly absent: {sorted(set(expected) - set(values))}\n"
        f"  unexpectedly present: {sorted(set(values) - set(expected))}\n"
        f"  differing: {sorted(k for k in set(expected) & set(values) if values[k] != expected[k])}"
    )
    for value in values.values():
        assert isinstance(value, Decimal), f"{pdf_stem}: expected a Decimal instance, got {value!r}"


def test_the_expected_maps_keep_their_discriminating_power() -> None:
    """The guard on the guard: the quarters must stay tellable apart.

    The exact-map assertion above is only stronger than the constant check it
    replaced BECAUSE the amounts differ. The withdrawn renders printed one
    redaction constant into every money box of all four quarters, so nothing
    could distinguish a cross-column misread from a test reading the wrong
    quarter's file.

    Within a quarter this asserts less than the Modelo 100 sibling, and the
    difference is principled rather than an oversight: casillas 09, 28 and 30
    are REQUIRED to repeat, because with one epigrafe filled and no prior
    autoliquidacion ``28 = 03+...+27`` reduces to ``09`` and ``30 = 28 - 29``
    reduces to ``28``. Forcing them apart would print a form contradicting its
    own stated formula. So the assertion is: every casilla the form leaves free
    differs from the ones it does not constrain, and every quarter differs from
    every other.
    """
    stems = sorted(_M111_EXPECTED_VALUES_BY_STEM)
    resultado_by_stem = {stem: _M111_EXPECTED_VALUES_BY_STEM[stem][_M111_CASILLA_30] for stem in stems}
    assert len(set(resultado_by_stem.values())) == len(stems), (
        f"casilla 30 must differ in every quarter or a test reading the wrong quarter's "
        f"fixture would go unnoticed; got {resultado_by_stem}"
    )

    for stem in stems:
        amounts = _M111_EXPECTED_VALUES_BY_STEM[stem]
        unconstrained = [value for casilla_id, value in amounts.items() if casilla_id not in _M111_FORM_TIED_CASILLAS]
        assert len(set(unconstrained)) == len(unconstrained), (
            f"{stem}: the perceptor count and the base are independent of the retencion chain, "
            f"so they must be distinct; got {unconstrained}"
        )
