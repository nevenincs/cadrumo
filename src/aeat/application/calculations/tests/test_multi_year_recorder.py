"""Tests for the multi-year enrollment evidence type boundary."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._multi_year import EnrollmentEvidence, EnrollmentYearObservation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "130"


def _calculation_observation(*, filing_year: int) -> EnrollmentYearObservation:
    return EnrollmentYearObservation(
        modelo=_MODELO,
        filing_year=filing_year,
        calculation_mode=True,
        produced_value_count=1,
    )


def test_enrollment_evidence_rejects_single_distinct_renta_year() -> None:
    """EnrollmentEvidence itself refuses evidence that spans only one renta year."""
    observation = _calculation_observation(filing_year=2024)

    with pytest.raises(ValidationError, match="distinct renta year"):
        EnrollmentEvidence(modelo=_MODELO, observations=(observation,))


def test_enrollment_evidence_accepts_two_distinct_renta_years_sorted() -> None:
    """Two real observations construct and report the distinct years sorted."""
    evidence = EnrollmentEvidence(
        modelo=_MODELO,
        observations=(
            _calculation_observation(filing_year=2025),
            _calculation_observation(filing_year=2024),
        ),
    )

    assert evidence.distinct_renta_years == (2024, 2025)
