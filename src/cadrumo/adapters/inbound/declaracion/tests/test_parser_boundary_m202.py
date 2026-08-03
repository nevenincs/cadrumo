"""Modelo 202 declaración extractor tests.

No real Modelo 202 declaración-copy PDF specimen is bundled (Tier-R
real-corpus acquisition for this modelo family is tracked separately).
The registry ``declaracion_pdf`` extraction profile for the
2025-y-siguientes revision is grounded against the bundled AEAT-published
Diseño de Registro (per-clave ``[NN]`` box-number notation confirmed in
``corpus/aeat_official/disenos_registro/modelo_202/files/``) and the
AEAT-published instructions HTML, which references "clave 01", "clave 03",
"clave 34" for the same casillas -- per the
``verification_source = "synthetic_from_aeat_published_text"`` grounding
tier the registry profile declares, with
``provisional_pending_specimen = true`` recorded pending a real specimen.

These tests round-trip the registry profile against the committed synthetic
fixture (``202/2025-1P.pdf``), which reproduces the confirmed box-number
notation as a ``bbox_anchored`` layout (box number, then the value
immediately to its right) -- the same discipline
``test_parser_boundary_m131_current_year.py`` applies when the printed
layout's exact wording cannot be confirmed against a real specimen.

See Also:
    :func:`~adapters.inbound.declaracion.parse_declaracion`
        Public parser entry point exercised against the synthetic fixture.
    :class:`~domain.calculations.registry._schema_extraction.ExtractionProfileDefinition`
        Registry-owned ``declaracion_pdf`` profile contract asserted here.
    :class:`~adapters.inbound.declaracion.DeclaracionParseError`
        Structured failure raised when a bbox anchor misses coverage.
    ``test_parser_boundary_m131_current_year.py``
        Sibling current-year synthetic-fixture discipline for provisional
        declaration profiles.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._errors import DeclaracionParseError
from ._parser_boundary_support import (
    _MODELO_202_SYNTHETIC_FIXTURE,
    CasillaId,
    _casilla_id,
    _expected_period,
    _modelo_snapshot,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

# Ground truth mirrors the amounts _MODELO_202_PRINTED_ROWS stamps onto the
# committed fixture PDF (_generate_misc_b.py is the single source of the
# fixture's printed values).
_M202_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    _casilla_id("01"): Decimal("50000.00"),
    _casilla_id("03"): Decimal("8500.00"),
    _casilla_id("04"): Decimal("140000.00"),
    _casilla_id("34"): Decimal("29400.00"),
}

_M202_EXPECTED_CASILLAS = frozenset(_M202_EXPECTED_VALUES)


def test_modelo_202_declaracion_pdf_profile_declares_expected_target_casillas() -> None:
    """Registry profile declares exactly the bounded four-casilla target set.

    Every target uses ``bbox_anchored`` -- no real M202 specimen is bundled
    to confirm a ``named_label`` or ``numeric_casilla`` printed layout (see
    the module docstring), so the profile anchors on the printed box number
    the bundled Diseño de Registro confirms is present in the form.
    """
    snapshot = _modelo_snapshot("202", filing_year=2025, period="1P")
    profile = snapshot.extraction_profiles["modelo-202-declaracion-pdf"]
    assert profile.surface == "declaracion_pdf"
    assert profile.provisional_pending_specimen is True
    assert profile.verification_source == "synthetic_from_aeat_published_text"
    assert {target.casilla_id for target in profile.target_casillas} == _M202_EXPECTED_CASILLAS
    for target in profile.target_casillas:
        assert target.match_strategy == "bbox_anchored"
        assert target.bbox_anchor is not None
        assert target.bbox_anchor.box_number_pattern


def test_parser_extracts_modelo_202_casillas_from_synthetic_fixture() -> None:
    """Round-trip the committed DR-grounded synthetic Modelo 202 fixture.

    Ground truth: the committed fixture PDF (built by ``_generate_misc_b.py``)
    reproduces the AEAT-published Diseño de Registro box-number notation
    verbatim for each target casilla, followed by its stamped amount. The
    parser must recover every declared value exactly -- a drift between the
    registry ``bbox_anchor.box_number_pattern`` and the fixture layout
    produces a zero-match parse failure on this fixture.
    """
    assert _MODELO_202_SYNTHETIC_FIXTURE.is_file(), (
        f"missing committed M202 synthetic fixture at {_MODELO_202_SYNTHETIC_FIXTURE}"
    )

    filing = parse_declaracion(
        _MODELO_202_SYNTHETIC_FIXTURE,
        modelo_override="202",
        template_revision_override="2025-y-siguientes",
        año_override=2025,
        period_override="1P",
    )

    assert filing.modelo == "202"
    assert filing.period == _expected_period(2025, "1P")
    assert filing.tax_id == "B00000000"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "202"
    assert filing.registry_snapshot_ref.modelo_year == 2025
    assert filing.registry_snapshot_ref.period == "1P"

    extracted = {value.casilla_id: value.printed_value for value in filing.values}
    assert extracted == _M202_EXPECTED_VALUES, (
        f"unexpected extracted values.\n  got: {extracted}\n  expected: {_M202_EXPECTED_VALUES}"
    )

    # provisional_pending_specimen=true is stamped onto the observation so
    # downstream consumers (modelo reconcile, live sede pull) can disclose
    # that the M202 layout has not been confirmed against a real specimen.
    assert filing.extraction_profile_id == "modelo-202-declaracion-pdf"
    assert filing.extraction_profile_provisional is True


def test_bbox_anchor_miss_fails_coverage_rather_than_mis_extracting() -> None:
    """A ``bbox_anchored`` target whose printed box number is absent from the
    page yields NO hit -- never a value read from an unrelated position.

    This is the safety property that makes a provisional (unconfirmed)
    ``bbox_anchored`` profile tolerable on a real PDF with a diverging layout:
    the anchor search only matches an exact ``box_number_pattern`` occurrence,
    so a real M202 filing whose printed box numbering differs from the
    registry's guessed layout raises a hard, enumerated
    ``DeclaracionParseError`` (``no-silent-under-declaration``) instead of
    silently extracting a value from the wrong printed position.
    """
    snapshot = _modelo_snapshot("202", filing_year=2025, period="1P")
    profile = snapshot.extraction_profiles["modelo-202-declaracion-pdf"]

    # Mutate one target's anchor pattern to a box number that is never printed
    # on the committed synthetic fixture, forcing a genuine anchor miss.
    mutated_targets = []
    for target in profile.target_casillas:
        if target.casilla_id == _casilla_id("01"):
            bbox_anchor = target.bbox_anchor
            assert bbox_anchor is not None
            target = target.model_copy(
                update={"bbox_anchor": bbox_anchor.model_copy(update={"box_number_pattern": "^999$"})},
            )
        mutated_targets.append(target)
    mutated_profile = profile.model_copy(update={"target_casillas": mutated_targets})
    profiles = dict(snapshot.extraction_profiles)
    profiles[profile.id] = mutated_profile
    mutated_snapshot = snapshot.model_copy(update={"extraction_profiles": profiles})

    with pytest.raises(DeclaracionParseError) as excinfo:
        parse_declaracion(
            _MODELO_202_SYNTHETIC_FIXTURE,
            modelo_override="202",
            template_revision_override="2025-y-siguientes",
            año_override=2025,
            period_override="1P",
            registry_snapshot=mutated_snapshot,
        )

    assert excinfo.value.translated_message == "adapters.inbound.declaracion.errors.extraction_failed"
    assert excinfo.value.missing is not None
    assert _casilla_id("01") in excinfo.value.missing
