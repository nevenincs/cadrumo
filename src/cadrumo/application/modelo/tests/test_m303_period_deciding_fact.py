"""Calculating a Modelo 303 period names the unanswered fact that decides its cadence.

RIVA art. 71.3 makes the IVA period monthly for a gran empresa or a REDEME
enrolee and quarterly otherwise. A profile that never answered the gran empresa
question matches neither filing schedule, so the work gate must refuse with
that fact's own profile row as its next step, not with an opaque period
refusal that names nothing the filer can put right.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...operations.error_detail import build_operation_error_detail
from ...operations.next_step import OperationOpenProfileFieldStepV1
from ...user_profile.tests.persona_profile_facts import persona_facts_beneath
from ..action_errors import ModeloProfileReadinessError
from ..profile_readiness_gate import require_profile_ready_for_modelo_work
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "55555555-5555-4555-8555-555555555555"
_MODELO = "303"
_LARGE_COMPANY = "censo.large_company"


def _require_ready(*, large_company: bool | None) -> None:
    stated = () if large_company is None else (UserProfileFact(path=_LARGE_COMPANY, value=large_company),)
    with bundled_indexed_authority().operation() as operation:
        record = create_user_profile_record(
            context=operation.profile_create_context(),
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.COMPLETE,
            facts=persona_facts_beneath(stated, without=(_LARGE_COMPANY,)),
        )
        period = Period.from_year_and_code(operation.supported_filing_years().horizon, "1T")
        revision = operation.revision_for_context(_MODELO, filing_year=period.filing_year, period=period.registry_token)
        require_profile_ready_for_modelo_work(
            bucket_id=_PROFILE_ID,
            modelo=_MODELO,
            revision_id=revision.id,
            filing_year=period.filing_year,
            period=period,
            enforce_applicability=False,
            profile_decode_context=operation.profile_decode_context(),
            operation=operation,
            profile=ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context()),
        )


def test_an_unanswered_gran_empresa_question_is_the_refusal_s_door() -> None:
    """DISCRIMINATING: the refusal opens the gran empresa row the cadence depends on."""
    with pytest.raises(ModeloProfileReadinessError) as refused:
        _require_ready(large_company=None)
    detail = build_operation_error_detail(refused.value)

    assert detail is not None
    assert isinstance(detail.next_step, OperationOpenProfileFieldStepV1)
    assert detail.next_step.path == _LARGE_COMPANY
    assert detail.next_step.words.strip() != ""


def test_an_answered_gran_empresa_question_admits_the_quarter() -> None:
    """ANTI-VACUITY: the persona with the question answered is ready for its quarter."""
    _require_ready(large_company=False)
