"""Measured parser outcomes for every adjudicated external layout candidate.

The candidates are third-party samples derived from official form layouts, not
authenticated AEAT evidence.  Registry-aligned rows select the exact revision the
sidecar declares.  Historical layouts without an authored revision remain explicit
out-of-revision parser exercises and never count as current-form verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.modelo import Modelo
from .....domain.calculations.registry.authority import bundled_authority
from .....tests import FIXTURES_DIR
from .....tests.fixtures.external_layout_candidates.models import (
    ExternalLayoutCandidate,
    ExternalLayoutCandidateKind,
    ExternalLayoutRegistryApplicabilityVerdict,
    load_external_layout_candidate,
)
from ...pdf.extracted_casilla import ExtractedCasilla
from ..parser import (
    _classify_target,
    _load_pages_words,
    _numeric_casilla_anchors,
    _partition_target_outcomes,
    _printed_box_numbers,
    _select_extraction_profile,
    extract_pages_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_CANDIDATE_ROOT = FIXTURES_DIR / "external_layout_candidates"


class _OutcomeKind(StrEnum):
    """Closed set of honest conclusions this candidate matrix may report."""

    BLANK_NO_VALUES = "blank_no_values"
    UNSUPPORTED_LAYOUT = "unsupported_layout"


@dataclass(frozen=True)
class _MeasuredOutcome:
    """Typed result of driving one candidate through extraction classification."""

    kind: _OutcomeKind
    values: tuple[ExtractedCasilla, ...] = ()
    missing: tuple[str, ...] = ()
    malformed: tuple[str, ...] = ()
    ambiguous: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RegistryAlignedCandidateCase:
    """One candidate whose sidecar names the exact registry revision under test."""

    modelo: Modelo
    candidate_kind: ExternalLayoutCandidateKind
    filing_year: int
    period: str
    revision_id: str
    applicability_verdict: ExternalLayoutRegistryApplicabilityVerdict
    expected: _MeasuredOutcome

    @property
    def label(self) -> str:
        return f"{self.modelo.value}-{self.candidate_kind}"


@dataclass(frozen=True)
class _OutOfRevisionParserExercise:
    """A historical layout used only to challenge current parser primitives."""

    modelo: Modelo
    candidate_kind: ExternalLayoutCandidateKind
    parser_exercise_filing_year: int
    parser_exercise_period: str
    expected: _MeasuredOutcome

    @property
    def label(self) -> str:
        return f"{self.modelo.value}-{self.candidate_kind}-out-of-revision-parser-exercise"


type _CandidateCase = _RegistryAlignedCandidateCase | _OutOfRevisionParserExercise


_M130_MISSING = tuple(f"{number:02d}" for number in range(1, 20))
_M131_MALFORMED = ("01", "02", "04", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15")
_M303_MISSING = (
    "27",
    "29",
    "37",
    "45",
    "iva.resultado-regimen-general",
    "64",
    "66",
    "iva.compensacion-pendiente-periodos-anteriores",
    "iva.compensacion-aplicada-periodo",
    "iva.compensacion-pendiente-periodos-posteriores",
    "iva.resultado",
    "71",
)
_M349_MISSING = (
    "decl.numero-operadores",
    "decl.importe-operaciones",
    "decl.numero-rectificaciones",
    "decl.importe-rectificaciones",
)


def _registry_aligned_cases_for_both_variants(
    modelo: Modelo,
    *,
    filing_year: int,
    period: str,
    revision_id: str,
    applicability_verdict: ExternalLayoutRegistryApplicabilityVerdict,
    expected: _MeasuredOutcome,
) -> tuple[_RegistryAlignedCandidateCase, _RegistryAlignedCandidateCase]:
    plain_case, fillable_case = tuple(
        _RegistryAlignedCandidateCase(
            modelo=modelo,
            candidate_kind=candidate_kind,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
            applicability_verdict=applicability_verdict,
            expected=expected,
        )
        for candidate_kind in ("plain", "fillable")
    )
    return plain_case, fillable_case


def _out_of_revision_exercises_for_both_variants(
    modelo: Modelo,
    *,
    parser_exercise_period: str,
    expected: _MeasuredOutcome,
) -> tuple[_OutOfRevisionParserExercise, _OutOfRevisionParserExercise]:
    plain_case, fillable_case = tuple(
        _OutOfRevisionParserExercise(
            modelo=modelo,
            candidate_kind=candidate_kind,
            parser_exercise_filing_year=2026,
            parser_exercise_period=parser_exercise_period,
            expected=expected,
        )
        for candidate_kind in ("plain", "fillable")
    )
    return plain_case, fillable_case


_MATRIX = (
    *_registry_aligned_cases_for_both_variants(
        Modelo.M130,
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        applicability_verdict="current_authored_revision",
        expected=_MeasuredOutcome(kind=_OutcomeKind.BLANK_NO_VALUES, missing=_M130_MISSING),
    ),
    *_registry_aligned_cases_for_both_variants(
        Modelo.M131,
        filing_year=2026,
        period="1T",
        revision_id="2026",
        applicability_verdict="current_authored_revision",
        expected=_MeasuredOutcome(
            kind=_OutcomeKind.UNSUPPORTED_LAYOUT,
            malformed=_M131_MALFORMED,
            ambiguous=("03", "05"),
        ),
    ),
    *_registry_aligned_cases_for_both_variants(
        Modelo.M303,
        filing_year=2025,
        period="1T",
        revision_id="2025",
        applicability_verdict="historical_authored_revision",
        expected=_MeasuredOutcome(kind=_OutcomeKind.BLANK_NO_VALUES, missing=_M303_MISSING),
    ),
    *_out_of_revision_exercises_for_both_variants(
        Modelo.M036,
        parser_exercise_period="alta",
        expected=_MeasuredOutcome(kind=_OutcomeKind.BLANK_NO_VALUES, missing=("decl.event-kind",)),
    ),
    *_out_of_revision_exercises_for_both_variants(
        Modelo.M349,
        parser_exercise_period="01",
        expected=_MeasuredOutcome(kind=_OutcomeKind.BLANK_NO_VALUES, missing=_M349_MISSING),
    ),
)


def _load_candidate(case: _CandidateCase) -> tuple[ExternalLayoutCandidate, Path]:
    modelo = case.modelo.value
    candidate_path = _CANDIDATE_ROOT / modelo / f"{case.candidate_kind}.pdf"
    sidecar_path = candidate_path.with_suffix(".json")
    candidate = load_external_layout_candidate(sidecar_path)
    assert candidate.modelo == modelo
    assert candidate.candidate_kind == case.candidate_kind
    return candidate, candidate_path


def _measure(case: _CandidateCase) -> _MeasuredOutcome:
    _candidate, candidate_path = _load_candidate(case)

    if isinstance(case, _RegistryAlignedCandidateCase):
        snapshot = bundled_authority().snapshot(
            case.modelo.value,
            filing_year=case.filing_year,
            period=case.period,
            revision_id=case.revision_id,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )
        assert str(snapshot.revision.id) == case.revision_id
    else:
        # This deliberately uses current parser anchors only as an adversarial
        # safety exercise.  The candidate sidecar declares no applicable authored
        # revision, and the separate applicability test below refuses alignment.
        snapshot = bundled_authority().snapshot(
            case.modelo.value,
            filing_year=case.parser_exercise_filing_year,
            period=case.parser_exercise_period,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )

    profile = _select_extraction_profile(snapshot, extraction_profile_id=None)
    pages = extract_pages_text(candidate_path)
    pages_words = _load_pages_words(profile, source_pdf_path=candidate_path, pdf_bytes=None)
    outcomes = _partition_target_outcomes(
        _classify_target(
            target,
            pages=pages,
            pages_words=pages_words,
            numeric_anchors=_numeric_casilla_anchors(profile, snapshot.revision),
            printed_box_numbers=_printed_box_numbers(profile, snapshot.revision),
        )
        for target in profile.target_casillas
    )
    kind = _OutcomeKind.UNSUPPORTED_LAYOUT if outcomes.malformed or outcomes.ambiguous else _OutcomeKind.BLANK_NO_VALUES
    return _MeasuredOutcome(
        kind=kind,
        values=tuple(outcomes.values),
        missing=tuple(str(casilla_id) for casilla_id in outcomes.missing),
        malformed=tuple(str(casilla_id) for casilla_id in outcomes.malformed),
        ambiguous=tuple(str(casilla_id) for casilla_id in outcomes.ambiguous),
    )


@pytest.mark.parametrize("case", _MATRIX, ids=lambda case: case.label)
def test_external_layout_candidate_registry_applicability_is_exact(case: _CandidateCase) -> None:
    """Sidecars agree with a selected revision or explicitly refuse alignment."""
    candidate, _candidate_path = _load_candidate(case)
    adjudication = candidate.authority_adjudication
    assert adjudication is not None
    applicability = adjudication.registry_applicability

    if isinstance(case, _RegistryAlignedCandidateCase):
        assert applicability.verdict == case.applicability_verdict
        assert applicability.revision_id == case.revision_id
        snapshot = bundled_authority().snapshot(
            case.modelo.value,
            filing_year=case.filing_year,
            period=case.period,
            revision_id=case.revision_id,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )
        assert str(snapshot.revision.id) == applicability.revision_id
    else:
        assert applicability.verdict == "historical_layout_without_authored_revision"
        assert applicability.revision_id is None


@pytest.mark.parametrize("case", _MATRIX, ids=lambda case: case.label)
def test_external_layout_candidate_has_exact_measured_outcome(case: _CandidateCase) -> None:
    """Each route keeps its exact values/missing/malformed/ambiguous buckets."""
    measured = _measure(case)

    assert measured == case.expected
    assert measured.values == (), (
        f"{case.label}: blank external layout fabricated values "
        f"{[(str(value.casilla_id), value.printed_value) for value in measured.values]}"
    )


def test_matrix_is_exactly_five_modelos_by_two_variants() -> None:
    """No candidate can disappear from the explicit outcome report."""
    identities = {(case.modelo, case.candidate_kind) for case in _MATRIX}
    assert identities == {
        (modelo, candidate_kind)
        for modelo in (Modelo.M036, Modelo.M130, Modelo.M131, Modelo.M303, Modelo.M349)
        for candidate_kind in ("plain", "fillable")
    }
    assert len(_MATRIX) == 10
