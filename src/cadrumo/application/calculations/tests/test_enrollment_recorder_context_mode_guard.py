"""Unit tests defending the EnrollmentRecorder context-mode guard invariants.

These tests exist specifically to prove the ``record_context_year`` guard is
load-bearing. Deleting the ``persisted_observation_count <= 0`` check inside
``_multi_year.py`` would make the ``count=0`` test below go RED immediately —
which is the anti-tautology proof this test owes.

Three contracts under test:

1. ``record_context_year`` raises :exc:`EnrollmentEvidenceError` when
   ``persisted_observation_count=0`` (the guard is enforced).
2. ``record_context_year`` raises :exc:`EnrollmentEvidenceError` when
   ``context_label`` is blank or whitespace (the label guard is still enforced).
3. The positive path — a non-blank label AND a strictly positive count — records
   the year and allows :meth:`EnrollmentRecorder.evidence` to succeed (the happy
   path works).

No mocks, no skips, no xfail.  The recorder and error classes are pure-Python;
no encrypted SQL or real adapters are needed to exercise these guards.
"""

from __future__ import annotations

import pytest

from ..multi_year import EnrollmentEvidenceError, EnrollmentRecorder

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "347"  # any valid modelo id; 347 is a known enrolled context-mode modelo
_LABEL = "347-fidelity-year-over-year"


# ---------------------------------------------------------------------------
# B1 — persisted_observation_count guard
# ---------------------------------------------------------------------------


def test_record_context_year_raises_on_zero_persisted_observation_count() -> None:
    """record_context_year refuses count=0 with EnrollmentEvidenceError.

    Anti-tautology anchor: if the ``persisted_observation_count <= 0`` guard
    inside ``record_context_year`` is removed, this test goes RED — proving the
    guard is not dead code and cannot be silently elided.

    A context-year recorded with count=0 would allow a test to claim a year
    without any real CalculationObservationRepository interaction, making the
    enrollment contract label-only and therefore fakeable.
    """
    recorder = EnrollmentRecorder(_MODELO)
    with pytest.raises(EnrollmentEvidenceError, match="persisted_observation_count"):
        recorder.record_context_year(
            filing_year=2024,
            context_label=_LABEL,
            persisted_observation_count=0,
        )


def test_record_context_year_raises_on_negative_persisted_observation_count() -> None:
    """record_context_year refuses negative counts too (same guard path)."""
    recorder = EnrollmentRecorder(_MODELO)
    with pytest.raises(EnrollmentEvidenceError, match="persisted_observation_count"):
        recorder.record_context_year(
            filing_year=2024,
            context_label=_LABEL,
            persisted_observation_count=-1,
        )


# ---------------------------------------------------------------------------
# B2 — blank/whitespace label guard (pre-existing, must still hold)
# ---------------------------------------------------------------------------


def test_record_context_year_raises_on_blank_label() -> None:
    """record_context_year refuses a blank context_label regardless of count."""
    recorder = EnrollmentRecorder(_MODELO)
    with pytest.raises(EnrollmentEvidenceError, match="context label"):
        recorder.record_context_year(
            filing_year=2024,
            context_label="",
            persisted_observation_count=1,
        )


def test_record_context_year_raises_on_whitespace_label() -> None:
    """record_context_year refuses a whitespace-only label."""
    recorder = EnrollmentRecorder(_MODELO)
    with pytest.raises(EnrollmentEvidenceError, match="context label"):
        recorder.record_context_year(
            filing_year=2024,
            context_label="   ",
            persisted_observation_count=1,
        )


# ---------------------------------------------------------------------------
# B3 — positive path: valid label + positive count records successfully
# ---------------------------------------------------------------------------


def test_record_context_year_positive_path_records_year() -> None:
    """A non-blank label AND a positive count records the year and evidence() succeeds.

    Proves the guards do not over-block the happy path: a caller that genuinely
    drove the real repository (count > 0) and named the context (non-blank label)
    can record two distinct years and obtain verified :class:`EnrollmentEvidence`.
    """
    recorder = EnrollmentRecorder(_MODELO)
    recorder.record_context_year(
        filing_year=2024,
        context_label=_LABEL,
        persisted_observation_count=1,
    )
    recorder.record_context_year(
        filing_year=2025,
        context_label=_LABEL,
        persisted_observation_count=1,
    )
    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (2024, 2025)
    assert evidence.modelo == _MODELO
    # Every observation carries has_evidence=True (both label and count satisfied).
    assert all(obs.has_evidence for obs in evidence.observations)
    assert all(obs.persisted_observation_count == 1 for obs in evidence.observations)


def test_record_context_year_count_2_records_correctly() -> None:
    """A count greater than 1 is accepted and preserved in the observation.

    Some enrollment scenarios may persist more than one observation per year
    (e.g. multiple detail rows). The recorder must accept any count >= 1.
    """
    recorder = EnrollmentRecorder(_MODELO)
    recorder.record_context_year(
        filing_year=2024,
        context_label=_LABEL,
        persisted_observation_count=3,
    )
    recorder.record_context_year(
        filing_year=2025,
        context_label=_LABEL,
        persisted_observation_count=2,
    )
    evidence = recorder.evidence()
    obs_by_year = {obs.filing_year: obs for obs in evidence.observations}
    assert obs_by_year[2024].persisted_observation_count == 3
    assert obs_by_year[2025].persisted_observation_count == 2
    assert all(obs.has_evidence for obs in evidence.observations)
