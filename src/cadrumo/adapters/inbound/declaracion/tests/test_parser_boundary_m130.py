"""Modelo 130 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_casillas import (
    _M130_RENDIMIENTO_NETO_CASILLA,
    _M130_RESULTADO_CASILLA,
)
from ._parser_boundary_support import (
    _MODELO_130_EXPECTED_TARGETS,
    _MODELO_130_SYNTHETIC_FIXTURE,
    FIXTURES_DIR,
    Decimal,
    DeclaracionParseError,
    _modelo_130_snapshot,
    parse_declaracion,
    source_pdf_reference_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_parser_extracts_modelo_130_registry_profile_targets_from_pdf() -> None:
    """Assert the M130 declaracion_pdf profile declares exactly the expected 19 targets."""
    snapshot = _modelo_130_snapshot()
    profile = snapshot.extraction_profiles["modelo-130-declaracion-pdf"]
    assert profile.provisional_pending_specimen is True
    assert profile.corpus_round_trip_verified is False
    assert profile.verification_source is None
    assert profile.confidence == "review_required"
    assert tuple(target.casilla_id for target in profile.target_casillas) == _MODELO_130_EXPECTED_TARGETS
    assert profile.min_coverage == Decimal("0.1052")
    for target in profile.target_casillas:
        assert target.match_strategy == "bbox_anchored", (
            f"casilla {target.casilla_id}: expected match_strategy='bbox_anchored', got {target.match_strategy!r}"
        )
        assert target.bbox_anchor is not None, (
            f"casilla {target.casilla_id}: bbox_anchor must be set for bbox_anchored targets"
        )


def test_parser_extracts_modelo_130_legal_entity_nif_from_pdf() -> None:
    """Verify NIF extraction from a synthetic M130 PDF for a CIF-format declarant."""
    pdf_path = FIXTURES_DIR / "justificantes" / "130" / "2022-2T.pdf"
    filing = parse_declaracion(pdf_path, modelo_override="130", año_override=2022, period_override="2T")
    assert filing.tax_id == "Y0000001S"
    assert filing.source_pdf_path == source_pdf_reference_path(filing.source_pdf_sha256)
    assert pdf_path.name not in str(filing.source_pdf_path)


def test_parser_fails_when_modelo_130_registry_profile_targets_are_missing() -> None:
    """Parsing fails when the M130 profile coverage falls below the registry minimum."""
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


def test_modelo_130_synthetic_fixture_extracts_partial_casillas() -> None:
    """The synthetic M130 2024-1T corpus PDF extracts casillas via bbox_anchored.

    The fixture is ``synthetic_generated``, and the test name now says so. It
    was previously named for a real redacted declaration copy while this
    docstring already said "synthetic" -- the name asserted an external
    grounding no M130 fixture in the repository carries.
    """
    filing = parse_declaracion(
        _MODELO_130_SYNTHETIC_FIXTURE,
        modelo_override="130",
        año_override=2024,
        period_override="1T",
    )
    extracted = {value.casilla_id: value.printed_value for value in filing.values}
    assert filing.extraction_profile_provisional is True
    assert set(extracted.keys()) == {_M130_RENDIMIENTO_NETO_CASILLA, _M130_RESULTADO_CASILLA}, (
        f"2024-1T: expected casillas {{03, 19}}, got {set(extracted.keys())!r}"
    )
    assert isinstance(extracted[_M130_RESULTADO_CASILLA], Decimal)
    assert isinstance(extracted[_M130_RENDIMIENTO_NETO_CASILLA], Decimal)
