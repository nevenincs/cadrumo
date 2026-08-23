"""Measured parser outcomes for every unverified external layout candidate.

The candidates are independent parser-adversarial bytes, not authenticated AEAT
evidence.  This matrix records only what the production extraction primitives do
with each blank layout and keeps unsupported routes visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pytest

from .....core import Modelo, RegistryAuthorityGrade
from .....core.resources import resources
from .....tests import FIXTURES_DIR
from .....tests.fixtures.external_layout_candidates import (
    ExternalLayoutCandidateKind,
    load_external_layout_candidate,
)
from ...pdf import ExtractedCasilla
from .._parser import (
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
class _CandidateCase:
    """One explicit modelo/variant route and its exact expected buckets."""

    modelo: Modelo
    candidate_kind: ExternalLayoutCandidateKind
    filing_year: int
    period: str
    expected: _MeasuredOutcome

    @property
    def label(self) -> str:
        return f"{self.modelo.value}-{self.candidate_kind}"


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


def _cases_for_both_variants(
    modelo: Modelo,
    *,
    period: str,
    expected: _MeasuredOutcome,
) -> tuple[_CandidateCase, _CandidateCase]:
    return tuple(
        _CandidateCase(
            modelo=modelo,
            candidate_kind=candidate_kind,
            filing_year=2026,
            period=period,
            expected=expected,
        )
        for candidate_kind in ("plain", "fillable")
    )


_MATRIX = (
    *_cases_for_both_variants(
        Modelo.M130,
        period="1T",
        expected=_MeasuredOutcome(kind=_OutcomeKind.BLANK_NO_VALUES, missing=_M130_MISSING),
    ),
    *_cases_for_both_variants(
        Modelo.M131,
        period="1T",
        expected=_MeasuredOutcome(
            kind=_OutcomeKind.UNSUPPORTED_LAYOUT,
            malformed=_M131_MALFORMED,
            ambiguous=("03", "05"),
        ),
    ),
    *_cases_for_both_variants(
        Modelo.M303,
        period="1T",
        expected=_MeasuredOutcome(kind=_OutcomeKind.BLANK_NO_VALUES, missing=_M303_MISSING),
    ),
    *_cases_for_both_variants(
        Modelo.M036,
        period="alta",
        expected=_MeasuredOutcome(kind=_OutcomeKind.BLANK_NO_VALUES, missing=("decl.event-kind",)),
    ),
    *_cases_for_both_variants(
        Modelo.M349,
        period="01",
        expected=_MeasuredOutcome(kind=_OutcomeKind.BLANK_NO_VALUES, missing=_M349_MISSING),
    ),
)


def _measure(case: _CandidateCase) -> _MeasuredOutcome:
    modelo = case.modelo.value
    candidate_path = _CANDIDATE_ROOT / modelo / f"{case.candidate_kind}.pdf"
    sidecar_path = candidate_path.with_suffix(".json")
    candidate = load_external_layout_candidate(sidecar_path)
    assert candidate.modelo == modelo
    assert candidate.candidate_kind == case.candidate_kind

    snapshot = resources().modelos.authority.snapshot(
        modelo,
        filing_year=case.filing_year,
        period=case.period,
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
    kind = (
        _OutcomeKind.UNSUPPORTED_LAYOUT
        if outcomes.malformed or outcomes.ambiguous
        else _OutcomeKind.BLANK_NO_VALUES
    )
    return _MeasuredOutcome(
        kind=kind,
        values=tuple(outcomes.values),
        missing=tuple(str(casilla_id) for casilla_id in outcomes.missing),
        malformed=tuple(str(casilla_id) for casilla_id in outcomes.malformed),
        ambiguous=tuple(str(casilla_id) for casilla_id in outcomes.ambiguous),
    )


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
