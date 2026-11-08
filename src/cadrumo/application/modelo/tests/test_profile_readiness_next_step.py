"""The profile-readiness refusals name the one door that puts each right.

Creating a declaration was refused twice over, and neither refusal said where
to go. The first names a profile fact the gate demands, so it offers that
fact's own row; the second names an undeclared setup, whose only door is the
profile's "declare the setup complete" action. Both are carried on the
operation error detail a frontend reads, so the window opens the door rather
than holding a table of operator action identifiers.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.values import ProfileSetupState, create_user_profile_record
from ...operations.error_detail import build_operation_error_detail
from ...operations.next_step import OperationCompleteProfileSetupStepV1, OperationOpenProfileFieldStepV1
from ...user_profile.tests.persona_profile_facts import persona_facts_beneath
from ..action_errors import ModeloProfileReadinessError
from ..profile_readiness_gate import (
    require_existing_profile_baseline_ready_for_modelo_work,
    require_profile_ready_for_modelo_work,
)
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "44444444-4444-4444-8444-444444444444"
_MODELO = "303"
_ACTIVITY_DESCRIPTION = "activities.description"
# The gate refuses before the revision is read, so the target only has to be
# a well-formed one.
_REVISION_ID = "a" * 64


def _detail_next_step(raised: BaseException) -> object:
    detail = build_operation_error_detail(raised)
    assert detail is not None
    return detail.next_step


def test_a_missing_profile_fact_offers_that_fact_s_own_row() -> None:
    """DISCRIMINATING: the baseline refusal names the schema path the filer fills in."""
    with bundled_indexed_authority().operation() as operation:
        record = create_user_profile_record(
            context=operation.profile_create_context(),
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.INCOMPLETE,
            # The defect's profile: the persona's facts without any activity row.
            facts=persona_facts_beneath(without=("activities.",)),
        )
        period = Period.from_year_and_code(operation.supported_filing_years().horizon, "1T")
        with pytest.raises(ModeloProfileReadinessError) as refused:
            require_existing_profile_baseline_ready_for_modelo_work(
                bucket_id=_PROFILE_ID,
                modelo=_MODELO,
                filing_year=period.filing_year,
                period=period,
                enforce_applicability=False,
                profile_decode_context=operation.profile_decode_context(),
                operation=operation,
                profile=ModeloWorkProfile(
                    record=record,
                    profile_decode_context=operation.profile_decode_context(),
                ),
            )
        step = _detail_next_step(refused.value)

    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == _ACTIVITY_DESCRIPTION
    assert step.words.strip() != ""


def test_an_undeclared_setup_offers_declaring_it_complete() -> None:
    """DISCRIMINATING: a profile missing nothing but its own completion names that action."""
    with bundled_indexed_authority().operation() as operation:
        record = create_user_profile_record(
            context=operation.profile_create_context(),
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.INCOMPLETE,
            facts=persona_facts_beneath(),
        )
        period = Period.from_year_and_code(operation.supported_filing_years().horizon, "1T")
        with pytest.raises(ModeloProfileReadinessError) as refused:
            require_profile_ready_for_modelo_work(
                bucket_id=_PROFILE_ID,
                modelo=_MODELO,
                revision_id=_REVISION_ID,
                filing_year=period.filing_year,
                period=period,
                enforce_applicability=False,
                profile_decode_context=operation.profile_decode_context(),
                operation=operation,
                profile=ModeloWorkProfile(
                    record=record,
                    profile_decode_context=operation.profile_decode_context(),
                ),
            )
        step = _detail_next_step(refused.value)

    assert isinstance(step, OperationCompleteProfileSetupStepV1)
    assert step.words.strip() != ""


def test_a_declared_setup_is_not_refused_for_its_completion() -> None:
    """ANTI-VACUITY: the setup refusal is the undeclared setup's, not every profile's."""
    with bundled_indexed_authority().operation() as operation:
        record = create_user_profile_record(
            context=operation.profile_create_context(),
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.COMPLETE,
            facts=persona_facts_beneath(),
        )
        period = Period.from_year_and_code(operation.supported_filing_years().horizon, "1T")
        require_existing_profile_baseline_ready_for_modelo_work(
            bucket_id=_PROFILE_ID,
            modelo=_MODELO,
            filing_year=period.filing_year,
            period=period,
            enforce_applicability=False,
            profile_decode_context=operation.profile_decode_context(),
            operation=operation,
            profile=ModeloWorkProfile(
                record=record,
                profile_decode_context=operation.profile_decode_context(),
            ),
        )
