"""Re-verifying a work unit whose payer fact the schema-8 migration cleared.

The migration drops a stored ``false`` on ``withholding.has_employees``,
``withholding.pays_professionals_with_retencion``,
``withholding.pays_rent_with_retencion`` and ``iva.does_intracomunitario``,
because a version-7 negative on those paths cannot be proven to be an answer.
A work unit for one of the modelos they gate can already exist when that
happens, so the next verification of it reads a profile that no longer answers
the question.

Two outcomes would both be wrong, and they fail in opposite directions:

* Reading the cleared answer as a *no* would make the applicability verdict
  NOT_APPLICABLE, and the readiness gate would refuse the work unit outright.
  The operator's own figures would become unverifiable because a question
  nobody asked was answered for them. The assertions call
  :func:`~cadrumo.application.modelo.profile_readiness_gate.modelo_applicability_refusal`,
  the applicability arm itself, which
  :func:`~cadrumo.application.modelo.profile_readiness_gate.require_profile_ready_for_work_unit`
  consults when ``enforce_applicability`` is on; that is the decision under
  test, without the gate's unrelated profile-readiness axes.
* Letting the cleared answer scope the modelo's cross-period source dependency
  out as "not a filing the taxpayer owes" would drop a prior-period leg from
  the verdict, which is the silent exclusion the cross-period gate exists to
  prevent.

Both are asserted against the production components: the applicability arm of
the readiness gate, and the registry-grounded non-filer set the cross-period
clean-state verdict is built from. The profile is a real
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord` under the pinned
authority schema, shared with the projection test that owns it.
"""

from __future__ import annotations

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.modelo import Modelo
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ...calculations.cross_period_clean_state import cross_period_clean_state_non_filer_modelos
from ...user_profile.tests.payer_fact_record_support import (
    PAYER_FACT_GATED_MODELOS,
    PROFILE_ID,
    payer_fact_record,
)
from ..profile_readiness_gate import BLOCKING_APPLICABILITY_VERDICTS, modelo_applicability_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WITHHOLDING_ANNUAL_PAIRS = (
    (Modelo("190").value, Modelo("111").value),
    (Modelo("180").value, Modelo("115").value),
)
"""Annual summary and the periodic withholding filing it folds in.

Both source modelos are gated by one of the cleared payer facts, which is
exactly what makes them the pair worth asserting: the source is the filing a
misread clearance would declare the taxpayer does not owe.
"""


def _latest_supported_filing_year() -> int:
    supported = published_supported_filing_years()
    assert supported is not None, "the published registry declares no supported filing years"
    return supported.years[-1]


def _annual_snapshot(modelo: str, *, operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot(
        modelo,
        filing_year=_latest_supported_filing_year(),
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )


@pytest.mark.parametrize("modelo", PAYER_FACT_GATED_MODELOS)
def test_a_cleared_payer_fact_does_not_refuse_re_verification(
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> None:
    """An unanswered fact leaves the verdict INCOMPLETE, which the gate must not block on."""
    refusal = modelo_applicability_refusal(
        record=payer_fact_record(operation, answer=None),
        bucket_id=PROFILE_ID,
        modelo=modelo,
        operation=operation,
    )

    assert refusal is None
    # Current policy: an unanswered gating fact is a warning, not a refusal, so
    # an INCOMPLETE verdict stays outside the blocking set. It is a policy
    # choice, not a law: whether an unanswered payer fact should instead stop
    # the work unit is still open, and a ruling that it should has to change
    # this assertion deliberately rather than find it already contradicted.
    assert ApplicabilityVerdict.INCOMPLETE not in BLOCKING_APPLICABILITY_VERDICTS


@pytest.mark.parametrize("modelo", PAYER_FACT_GATED_MODELOS)
def test_a_payer_fact_answered_no_still_refuses_re_verification(
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> None:
    """The operator's own no keeps its force; only the unprovable default was dropped."""
    refusal = modelo_applicability_refusal(
        record=payer_fact_record(operation, answer=False),
        bucket_id=PROFILE_ID,
        modelo=modelo,
        operation=operation,
    )

    assert refusal is not None
    _message, context = refusal
    assert context["applicability_verdict"] == ApplicabilityVerdict.NOT_APPLICABLE.value
    assert context["modelo"] == modelo


@pytest.mark.parametrize("modelo", PAYER_FACT_GATED_MODELOS)
def test_a_payer_fact_answered_yes_does_not_refuse_re_verification(
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> None:
    refusal = modelo_applicability_refusal(
        record=payer_fact_record(operation, answer=True),
        bucket_id=PROFILE_ID,
        modelo=modelo,
        operation=operation,
    )

    assert refusal is None


@pytest.mark.parametrize(("annual", "source"), _WITHHOLDING_ANNUAL_PAIRS)
def test_the_payer_gated_source_is_outside_the_suppressible_candidate_set(
    annual: str,
    source: str,
    operation: PinnedAuthorityOperation,
) -> None:
    """Only an economic-activity-conditional classification can ever be scoped out.

    :func:`~cadrumo.application.modelo.verification_cross_period.cross_period_clean_state_verdict_for_work_unit`
    derives its suppression set from the revision's
    ``conditional_on_economic_activity`` rows alone. A revision that made a
    payer-gated withholding source conditional would put it inside that set, so
    this is asserted against the published revision rather than assumed.
    """
    snapshot = _annual_snapshot(annual, operation=operation)
    classifications = {row.source_modelo: row for row in snapshot.revision.dependency_classifications}

    assert source in classifications, f"Modelo {annual} no longer declares Modelo {source} as a source"
    assert not classifications[source].conditional_on_economic_activity
    assert classifications[source].taxpayer_files_source


@pytest.mark.parametrize(("annual", "source"), _WITHHOLDING_ANNUAL_PAIRS)
def test_no_suppression_input_scopes_out_the_withholding_source(
    annual: str,
    source: str,
    operation: PinnedAuthorityOperation,
) -> None:
    """The source dependency stays enforced whatever the suppression input says.

    The suppression set is supplied here as every declared source plus the
    payer-gated one, which is strictly wider than anything the production
    derivation can produce from any profile answer. The source still stays
    enforced, so no reachable suppression input can drop this leg, and the
    cleared payer fact cannot either.
    """
    snapshot = _annual_snapshot(annual, operation=operation)
    widest_suppression = frozenset(
        {source, *(row.source_modelo for row in snapshot.revision.dependency_classifications)},
    )

    for files_economic_activity in (None, True, False):
        non_filer = cross_period_clean_state_non_filer_modelos(
            snapshot,
            taxpayer_files_economic_activity=files_economic_activity,
            not_applicable_source_modelos=widest_suppression,
        )
        assert source not in non_filer, (
            f"Modelo {annual} must keep its Modelo {source} dependency enforced; a cleared payer fact "
            "states nothing about whether that filing was owed"
        )
