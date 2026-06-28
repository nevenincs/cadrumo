"""Focused unit tests for verification._verify dispatch helpers.

Four private dispatch helpers gate the printed-vs-computed
verification report:

- ``_classify_discrepancy`` — assigns one of four
  :class:`DiscrepancyCause` categories with a documented
  precedence order: ``EXTRACTION_UNRELIABLE`` (extractor flagged
  the casilla) > ``UNMODELLED_RULE`` (casilla absent from
  registry) > ``ROUNDING`` (small delta) > ``CORRECTNESS_DIVERGENCE``
  (material delta). A regression that swapped any two branches
  would silently relabel discrepancies and change the operator's
  routing decision (e.g. an extractor-flagged casilla downgraded
  to a "rounding" finding would be silently dismissed).
- ``_compute_coverage`` — returns ``len(expected & provided) /
  len(expected)`` with a documented ``0.0`` short-circuit when
  ``expected`` is empty so downstream coverage thresholds stay
  well-defined.
- ``_derive_status`` — maps classified discrepancies + coverage
  onto :class:`VerificationStatus`. Blocking causes
  (``EXTRACTION_UNRELIABLE`` / ``UNMODELLED_RULE`` /
  ``CORRECTNESS_DIVERGENCE``) ALWAYS yield ``NEEDS_REVIEW``;
  coverage below ``min_coverage`` ALSO
  yields ``NEEDS_REVIEW``; otherwise ``VERIFIED``.
- ``_compose_narrative`` — translation key picker keyed on status.

Assertions test precedence + predicate contract + identity /
boundary properties; they do NOT hand-compute coverage ratios
from arbitrary synthetic inputs (the contract is the documented
boundary behaviour: empty → 0.0, full overlap → 1.0, partial
overlap → strictly between 0.0 and 1.0). No calculation
tautologies.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....adapters.inbound.declaracion._schema import (
    DeclaracionObservation,
    TemplateRevision,
)
from ....adapters.inbound.pdf._shared import ExtractedCasilla
from ....core import Period
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from .._schema import DiscrepancyCause, VerificationStatus
from .._verify import (
    _classify_discrepancy,
    _compose_narrative,
    _compute_coverage,
    _derive_status,
)
from .._verify import (
    _Discrepancy as DiscrepancyRecord,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DEFAULT_DISCREPANCY_CASILLA: CasillaId = validated_casilla_id("01", surface="_DEFAULT_DISCREPANCY_CASILLA")
_SECOND_DISCREPANCY_CASILLA: CasillaId = validated_casilla_id("02", surface="_SECOND_DISCREPANCY_CASILLA")
_THIRD_DISCREPANCY_CASILLA: CasillaId = validated_casilla_id("03", surface="_THIRD_DISCREPANCY_CASILLA")
_UNKNOWN_DISCREPANCY_CASILLA: CasillaId = validated_casilla_id("UNKNOWN", surface="_UNKNOWN_DISCREPANCY_CASILLA")
_MATERIAL_DELTA_CASILLA: CasillaId = validated_casilla_id("42", surface="_MATERIAL_DELTA_CASILLA")
_EXTRA_CASILLA: CasillaId = validated_casilla_id("EXTRA", surface="_EXTRA_CASILLA")
_EXTRA_ONE_CASILLA: CasillaId = validated_casilla_id("EXTRA1", surface="_EXTRA_ONE_CASILLA")
_EXTRA_TWO_CASILLA: CasillaId = validated_casilla_id("EXTRA2", surface="_EXTRA_TWO_CASILLA")


def _discrepancy(
    casilla_id: CasillaId = _DEFAULT_DISCREPANCY_CASILLA,
    delta: Decimal = Decimal("0.50"),
) -> DiscrepancyRecord:
    return DiscrepancyRecord(
        casilla_id=casilla_id,
        computed_value=Decimal("100.00"),
        user_value=Decimal("100.00") + delta,
        delta=delta,
    )


# ---------------------------------------------------------------------------
# _classify_discrepancy — branch precedence
# ---------------------------------------------------------------------------


def test_classify_discrepancy_routes_extraction_warning_to_extraction_unreliable() -> None:
    discrepancy = _discrepancy(casilla_id=_DEFAULT_DISCREPANCY_CASILLA)

    result = _classify_discrepancy(
        discrepancy,
        unreliable_ids={_DEFAULT_DISCREPANCY_CASILLA},
        registry_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA},
        tolerance=Decimal("0.01"),
    )

    assert result.cause is DiscrepancyCause.EXTRACTION_UNRELIABLE


def test_classify_discrepancy_routes_missing_registry_to_unmodelled_rule() -> None:
    """When the casilla is not in the registry's known set, the
    classifier routes to UNMODELLED_RULE."""
    discrepancy = _discrepancy(casilla_id=_UNKNOWN_DISCREPANCY_CASILLA)

    result = _classify_discrepancy(
        discrepancy,
        unreliable_ids=set(),
        registry_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA},
        tolerance=Decimal("0.01"),
    )

    assert result.cause is DiscrepancyCause.UNMODELLED_RULE


def test_classify_discrepancy_routes_small_delta_to_rounding() -> None:
    """A delta within ``10 * tolerance`` on a known registry casilla
    classifies as ROUNDING — non-blocking."""
    discrepancy = _discrepancy(casilla_id=_DEFAULT_DISCREPANCY_CASILLA, delta=Decimal("0.05"))

    result = _classify_discrepancy(
        discrepancy,
        unreliable_ids=set(),
        registry_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA},
        tolerance=Decimal("0.01"),
    )

    assert result.cause is DiscrepancyCause.ROUNDING


def test_classify_discrepancy_routes_material_delta_to_correctness_divergence() -> None:
    """A delta outside the rounding envelope on a known registry
    casilla classifies as CORRECTNESS_DIVERGENCE — blocking."""
    discrepancy = _discrepancy(casilla_id=_DEFAULT_DISCREPANCY_CASILLA, delta=Decimal("100.00"))

    result = _classify_discrepancy(
        discrepancy,
        unreliable_ids=set(),
        registry_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA},
        tolerance=Decimal("0.01"),
    )

    assert result.cause is DiscrepancyCause.CORRECTNESS_DIVERGENCE


def test_classify_discrepancy_precedence_extraction_unreliable_over_unmodelled_rule() -> None:
    """When a casilla is BOTH extractor-flagged AND absent from the
    registry, EXTRACTION_UNRELIABLE wins. A regression that flipped
    the branch order would silently classify a missing-registry
    casilla as a routine extractor warning."""
    discrepancy = _discrepancy(casilla_id=_UNKNOWN_DISCREPANCY_CASILLA)

    result = _classify_discrepancy(
        discrepancy,
        unreliable_ids={_UNKNOWN_DISCREPANCY_CASILLA},
        registry_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA},  # UNKNOWN is missing
        tolerance=Decimal("0.01"),
    )

    assert result.cause is DiscrepancyCause.EXTRACTION_UNRELIABLE


def test_classify_discrepancy_precedence_unmodelled_rule_over_rounding() -> None:
    """An unknown-registry casilla with a small delta still routes
    to UNMODELLED_RULE — registry membership is checked before
    rounding-envelope sizing."""
    discrepancy = _discrepancy(casilla_id=_UNKNOWN_DISCREPANCY_CASILLA, delta=Decimal("0.05"))

    result = _classify_discrepancy(
        discrepancy,
        unreliable_ids=set(),
        registry_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA},
        tolerance=Decimal("0.01"),
    )

    assert result.cause is DiscrepancyCause.UNMODELLED_RULE


def test_classify_discrepancy_round_trips_casilla_id_and_delta() -> None:
    """The classified output preserves the casilla_id and delta
    from the input; the helper does not normalise / reshape them."""
    discrepancy = _discrepancy(casilla_id=_MATERIAL_DELTA_CASILLA, delta=Decimal("7.50"))

    result = _classify_discrepancy(
        discrepancy,
        unreliable_ids=set(),
        registry_casilla_ids={_MATERIAL_DELTA_CASILLA},
        tolerance=Decimal("0.01"),
    )

    assert result.casilla_id == _MATERIAL_DELTA_CASILLA
    assert result.delta == Decimal("7.50")


# ---------------------------------------------------------------------------
# _compute_coverage — boundary contract
# ---------------------------------------------------------------------------


def _declaracion(casilla_ids: tuple[CasillaId, ...]) -> DeclaracionObservation:
    """Build a real :class:`DeclaracionObservation` with the given casillas.

    Uses the actual pydantic model with no stand-ins. Required
    PDF-provenance fields are filled with stable test-only values
    because the helpers under test (`_compute_coverage`,
    `_compose_narrative`) only read ``.values``."""
    values = tuple(
        ExtractedCasilla(
            casilla_id=cid,
            printed_value=None,
            source_page=1,
            extraction_confidence=1.0,
        )
        for cid in casilla_ids
    )
    return DeclaracionObservation(
        modelo="100",
        period=Period.from_year_and_code(2025, "0A"),
        ejercicio="2025",
        tax_id="12345678Z",
        template_revision=TemplateRevision(
            modelo="100",
            año=2025,
            revision="2025.01",
            detected_from="explicit_override",
        ),
        values=values,
        source_pdf_path=Path(__file__),
        source_pdf_sha256="a" * 64,
        parsed_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
    )


def test_compute_coverage_empty_expected_returns_zero_documented_short_circuit() -> None:
    """The helper short-circuits to ``0.0`` when ``expected`` is
    empty — division-by-zero would otherwise break downstream
    threshold comparisons."""
    declaracion = _declaracion((_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA))

    assert _compute_coverage(declaracion, expected_casilla_ids=set()) == 0.0


def test_compute_coverage_empty_provided_returns_zero() -> None:
    """When the extractor produced no casillas, coverage is 0.0
    regardless of how many the registry expects."""
    declaracion = _declaracion(())

    assert (
        _compute_coverage(
            declaracion,
            expected_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA},
        )
        == 0.0
    )


def test_compute_coverage_full_overlap_returns_one() -> None:
    """When every expected casilla appears in the provided set,
    coverage is 1.0 — full overlap is the documented happy path."""
    declaracion = _declaracion((_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA))

    assert (
        _compute_coverage(
            declaracion,
            expected_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA},
        )
        == 1.0
    )


def test_compute_coverage_ignores_extra_provided_ids() -> None:
    """Provided casillas outside ``expected`` do not count toward
    coverage; the helper measures expected-set saturation, not
    provided-set extent. Coverage = 1.0 when expected ⊆ provided."""
    declaracion = _declaracion((_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA, _EXTRA_CASILLA))

    assert (
        _compute_coverage(
            declaracion,
            expected_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA},
        )
        == 1.0
    )


def test_compute_coverage_no_overlap_returns_zero() -> None:
    """Disjoint provided and expected sets yield 0.0 coverage."""
    declaracion = _declaracion((_EXTRA_ONE_CASILLA, _EXTRA_TWO_CASILLA))

    assert (
        _compute_coverage(
            declaracion,
            expected_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA},
        )
        == 0.0
    )


def test_compute_coverage_partial_overlap_strictly_between_zero_and_one() -> None:
    """Partial overlap (some expected casillas provided, others
    missing) yields a value in the open interval (0.0, 1.0). The
    test asserts the bounded property, not the specific ratio,
    so it does not duplicate the helper's arithmetic."""
    declaracion = _declaracion((_DEFAULT_DISCREPANCY_CASILLA,))

    coverage = _compute_coverage(
        declaracion,
        expected_casilla_ids={_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA},
    )

    assert 0.0 < coverage < 1.0


def test_compute_coverage_is_monotonic_in_provided_set() -> None:
    """Adding a provided casilla that's in the expected set
    increases coverage; adding one outside the expected set
    leaves coverage unchanged. Monotonicity is the documented
    contract that downstream thresholds depend on."""
    expected = {_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA, _THIRD_DISCREPANCY_CASILLA}
    coverage_one = _compute_coverage(_declaracion((_DEFAULT_DISCREPANCY_CASILLA,)), expected_casilla_ids=expected)
    coverage_two = _compute_coverage(
        _declaracion((_DEFAULT_DISCREPANCY_CASILLA, _SECOND_DISCREPANCY_CASILLA)),
        expected_casilla_ids=expected,
    )
    coverage_extra = _compute_coverage(
        _declaracion((_DEFAULT_DISCREPANCY_CASILLA, _EXTRA_CASILLA)),
        expected_casilla_ids=expected,
    )

    assert coverage_two > coverage_one
    assert coverage_extra == coverage_one


# ---------------------------------------------------------------------------
# _derive_status — predicate contract
# ---------------------------------------------------------------------------


def _classified(*causes: DiscrepancyCause) -> tuple[Any, ...]:
    from .._schema import ClassifiedDiscrepancy

    return tuple(
        ClassifiedDiscrepancy(
            casilla_id=_DEFAULT_DISCREPANCY_CASILLA,
            expected=Decimal("100.00"),
            actual=Decimal("100.50"),
            delta=Decimal("0.50"),
            cause=cause,
            cause_rationale="rationale",
        )
        for cause in causes
    )


def test_derive_status_returns_verified_on_empty_input() -> None:
    result = _derive_status((), coverage=1.0, min_coverage=Decimal("0.30"))

    assert result is VerificationStatus.VERIFIED


def test_derive_status_returns_needs_review_for_correctness_divergence() -> None:
    classified = _classified(DiscrepancyCause.CORRECTNESS_DIVERGENCE)

    result = _derive_status(classified, coverage=1.0, min_coverage=Decimal("0.30"))

    assert result is VerificationStatus.NEEDS_REVIEW


def test_derive_status_returns_needs_review_for_extraction_unreliable() -> None:
    classified = _classified(DiscrepancyCause.EXTRACTION_UNRELIABLE)

    result = _derive_status(classified, coverage=1.0, min_coverage=Decimal("0.30"))

    assert result is VerificationStatus.NEEDS_REVIEW


def test_derive_status_returns_verified_for_rounding_only() -> None:
    """ROUNDING discrepancies are non-blocking; the status remains
    VERIFIED so long as coverage meets the threshold."""
    classified = _classified(DiscrepancyCause.ROUNDING)

    result = _derive_status(classified, coverage=1.0, min_coverage=Decimal("0.30"))

    assert result is VerificationStatus.VERIFIED


def test_derive_status_returns_needs_review_for_unmodelled_rule() -> None:
    """UNMODELLED_RULE discrepancies block verification.

    A registry gap means the declaration was not actually verified, even when
    coverage over modelled casillas otherwise meets the threshold.
    """
    classified = _classified(DiscrepancyCause.UNMODELLED_RULE)

    result = _derive_status(classified, coverage=1.0, min_coverage=Decimal("0.30"))

    assert result is VerificationStatus.NEEDS_REVIEW


def test_derive_status_low_coverage_routes_to_needs_review_even_without_blocking_findings() -> None:
    """Coverage below ``min_coverage`` triggers NEEDS_REVIEW even
    when no discrepancy is blocking."""
    classified = _classified(DiscrepancyCause.ROUNDING)

    result = _derive_status(classified, coverage=0.10, min_coverage=Decimal("0.30"))

    assert result is VerificationStatus.NEEDS_REVIEW


def test_derive_status_blocking_finding_overrides_high_coverage() -> None:
    """A single blocking finding raises NEEDS_REVIEW even at
    100% coverage."""
    classified = _classified(DiscrepancyCause.CORRECTNESS_DIVERGENCE)

    result = _derive_status(classified, coverage=1.0, min_coverage=Decimal("0.30"))

    assert result is VerificationStatus.NEEDS_REVIEW


# ---------------------------------------------------------------------------
# _compose_narrative — translation-key lookup
# ---------------------------------------------------------------------------


def test_compose_narrative_returns_verified_key_for_verified_status() -> None:
    declaracion = _declaracion(())

    result = _compose_narrative(declaracion, VerificationStatus.VERIFIED, (), 1.0)

    assert result == "verification.status.verified"


def test_compose_narrative_returns_needs_review_key_for_needs_review_status() -> None:
    declaracion = _declaracion(())

    result = _compose_narrative(declaracion, VerificationStatus.NEEDS_REVIEW, (), 0.10)

    assert result == "verification.status.needs_review"
