"""Real-behavior coverage for first-year Modelo 202 modalidad-cuota suppression.

A first-year Impuesto sobre
Sociedades filer under modalidad cuota (LIS art. 40.2) has no Modelo 202 pago-
fraccionado obligation; the cross-period dependency demanding evidence of a prior
Modelo 200/202 that never existed is scoped out under a distinct typed facet, with
an operator-declared advisory, and fail-closed everywhere else.

The suppression predicate, the evidence builder, and the verdict-property surface
are exercised here over real registry-derived requirement objects (built directly,
without a full snapshot load) so the behaviour is proven independently of the
registry-snapshot evaluator path. The evaluator-integration tests against a live
Modelo 202 snapshot live in ``test_cross_period_clean_state.py``; this module
proves the load-bearing decision logic with real objects and no mocks.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core import CasillaId, Period, validated_casilla_id
from ....domain.calculations.registry.applicability_modelo202 import Modelo202Modality
from .. import (
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
    NoPriorObligationProvenanceKind,
)
from ..cross_period_clean_state import (
    _qualifies_for_first_year_fractional_suppression,
    _suppressed_first_year_fractional_evidence,
    _suppressed_pre_activity_evidence,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TARGET_YEAR = 2026
_M202_SOURCE_CASILLA_03: CasillaId = validated_casilla_id("03", surface="_M202_SOURCE_CASILLA_03")
_M202_REQUIREMENT_LEGAL_REFS = ("ley-27-2014:art-40",)
_M202_REQUIREMENT_SOURCE_REFS = ("aeat-modelo-202-instructions",)


def _requirement(
    source_modelo: str,
    *,
    period_code: str = "1P",
    year: int = _TARGET_YEAR,
) -> CrossPeriodDependencyRequirement:
    return CrossPeriodDependencyRequirement(
        source_modelo=source_modelo,
        filing_year=year,
        period=Period.from_year_and_code(year, period_code),
        source_casilla_ids=(_M202_SOURCE_CASILLA_03,),
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=(f"binding-{source_modelo}",),
        legal_refs=_M202_REQUIREMENT_LEGAL_REFS,
        source_refs=_M202_REQUIREMENT_SOURCE_REFS,
    )


def test_cross_period_requirement_rejects_retired_source_casillas_key() -> None:
    payload = _requirement("202").model_dump()
    payload["source_casillas"] = payload.pop("source_casilla_ids")

    with pytest.raises(ValidationError) as exc_info:
        CrossPeriodDependencyRequirement.model_validate(payload)

    detail = str(exc_info.value)
    assert "source_casilla_ids" in detail
    assert "source_casillas" in detail


def _verdict(*dependencies: CrossPeriodDependencyEvidence) -> CrossPeriodCleanStateVerdict:
    return CrossPeriodCleanStateVerdict(
        bucket_id="default",
        target_modelo="202",
        target_filing_year=_TARGET_YEAR,
        target_period=Period.from_year_and_code(_TARGET_YEAR, "1P"),
        dependencies=dependencies,
    )


def test_first_year_modalidad_cuota_m202_dependency_qualifies_for_suppression() -> None:
    """(a) First IS year + ART_40_2_OPTIONAL -> the Modelo 202 dependency is suppressed.

    The evidence row is clean (no blockers), carries the first-year fractional
    facet, and the verdict reports the advisory.
    """
    requirement = _requirement("202")
    assert (
        _qualifies_for_first_year_fractional_suppression(
            requirement,
            modelo_202_modality=Modelo202Modality.ART_40_2_OPTIONAL,
            activity_start_date=date(_TARGET_YEAR, 3, 1),
            target_filing_year=_TARGET_YEAR,
        )
        is True
    )
    evidence = _suppressed_first_year_fractional_evidence(requirement, activity_start_date=date(_TARGET_YEAR, 3, 1))
    assert evidence.clean is True
    assert evidence.blockers == ()
    assert evidence.suppressed_first_year_fractional is True
    assert evidence.no_prior_obligation is not None
    assert (
        evidence.no_prior_obligation.facet_kind
        is NoPriorObligationProvenanceKind.NO_FRACTIONAL_PAYMENT_OBLIGATION_FIRST_YEAR
    )
    assert evidence.no_prior_obligation.provenance_kind is NoPriorObligationProvenanceKind.OPERATOR_DECLARED

    verdict = _verdict(evidence)
    assert verdict.clean is True
    assert verdict.has_first_year_fractional_suppression_advisory is True
    assert verdict.suppressed_first_year_fractional_dependencies == (evidence,)


def test_mandatory_modalidad_base_m202_dependency_is_not_suppressed() -> None:
    """(b) ART_40_3_MANDATORY -> NOT suppressed; the Modelo 202 dependency stays in scope.

    Under modalidad base (art. 40.3, INCN > 6.000.000 EUR) the pago fraccionado is
    computed on the current year's running base and IS owed in the first year, so
    the suppression is refused (fail-closed).
    """
    requirement = _requirement("202")
    assert (
        _qualifies_for_first_year_fractional_suppression(
            requirement,
            modelo_202_modality=Modelo202Modality.ART_40_3_MANDATORY,
            activity_start_date=date(_TARGET_YEAR, 3, 1),
            target_filing_year=_TARGET_YEAR,
        )
        is False
    )


def test_incomplete_and_none_modality_m202_dependency_is_not_suppressed() -> None:
    """(c) INCOMPLETE / None modality -> NOT suppressed (fail-closed).

    A modality that could not be derived (not a legal entity, or INCN undeclared,
    or the modality simply not threaded) must never read as "no obligation".
    """
    requirement = _requirement("202")
    for modality in (Modelo202Modality.INCOMPLETE, None):
        assert (
            _qualifies_for_first_year_fractional_suppression(
                requirement,
                modelo_202_modality=modality,
                activity_start_date=date(_TARGET_YEAR, 3, 1),
                target_filing_year=_TARGET_YEAR,
            )
            is False
        )


def test_non_first_year_m202_dependency_is_not_suppressed() -> None:
    """(d) Activity start before the target year -> NOT suppressed.

    When the declared activity-start year is strictly before the target filing
    year, a prior IS return exists to provide the art. 40.2 cuota basis, so the
    Modelo 202 dependency stays in scope and keeps demanding evidence.
    """
    requirement = _requirement("202")
    assert (
        _qualifies_for_first_year_fractional_suppression(
            requirement,
            modelo_202_modality=Modelo202Modality.ART_40_2_OPTIONAL,
            activity_start_date=date(_TARGET_YEAR - 1, 11, 1),
            target_filing_year=_TARGET_YEAR,
        )
        is False
    )


def test_missing_activity_start_date_m202_dependency_is_not_suppressed() -> None:
    """No recorded activity-start date -> NOT suppressed (fail-closed).

    Without the declared first-year proof the gate cannot assert this is the first
    IS year, so the Modelo 202 dependency stays in scope.
    """
    requirement = _requirement("202")
    assert (
        _qualifies_for_first_year_fractional_suppression(
            requirement,
            modelo_202_modality=Modelo202Modality.ART_40_2_OPTIONAL,
            activity_start_date=None,
            target_filing_year=_TARGET_YEAR,
        )
        is False
    )


def test_non_m202_dependency_is_never_first_year_fractional_suppressed() -> None:
    """A non-202 source modelo never qualifies for first-year fractional suppression.

    The suppression is Modelo-202-specific; a Modelo 303 (or any non-202)
    dependency is left to its own evidence gate even under modalidad cuota.
    """
    requirement = _requirement("303")
    assert (
        _qualifies_for_first_year_fractional_suppression(
            requirement,
            modelo_202_modality=Modelo202Modality.ART_40_2_OPTIONAL,
            activity_start_date=date(_TARGET_YEAR, 3, 1),
            target_filing_year=_TARGET_YEAR,
        )
        is False
    )


def test_first_year_fractional_facet_is_distinct_from_pre_activity_facet() -> None:
    """(e) The new facet is distinct from the pre-activity facet; advisories do not cross-fire.

    A pre-activity suppression still reads as ``suppressed_pre_activity`` and
    raises the operator-declared pre-activity advisory; a first-year fractional
    suppression reads ONLY as ``suppressed_first_year_fractional`` and does NOT
    trip the pre-activity advisory — and vice versa. This proves the two
    suppressions are independent and their advisory channels never collide.
    """
    requirement = _requirement("202")
    pre_activity = _suppressed_pre_activity_evidence(requirement, activity_start_date=date(_TARGET_YEAR, 3, 1))
    first_year = _suppressed_first_year_fractional_evidence(requirement, activity_start_date=date(_TARGET_YEAR, 3, 1))

    # Pre-activity facet behaves exactly as before and never reads as first-year.
    assert pre_activity.suppressed_pre_activity is True
    assert pre_activity.suppressed_first_year_fractional is False
    assert pre_activity.operator_declared_suppression_advisory is True

    # First-year fractional facet is distinct and never reads as pre-activity, and
    # never trips the pre-activity operator-declared advisory.
    assert first_year.suppressed_first_year_fractional is True
    assert first_year.suppressed_pre_activity is False
    assert first_year.operator_declared_suppression_advisory is False

    # On a verdict carrying both, each advisory flag is driven only by its own facet.
    verdict = _verdict(pre_activity, first_year)
    assert verdict.has_operator_declared_suppression_advisory is True
    assert verdict.has_first_year_fractional_suppression_advisory is True
    assert verdict.suppressed_pre_activity_dependencies == (pre_activity,)
    assert verdict.suppressed_first_year_fractional_dependencies == (first_year,)
    assert verdict.clean is True
