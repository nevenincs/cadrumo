"""A refused profile access carries the door its reason deserves."""

from __future__ import annotations

import pytest

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from ..access_errors import ProfileAccessRefusedError
from ..access_refusal_preconditions import ACCESS_ADMITTED_CONDITION, SESSION_OPEN_CONDITION

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SIGN_IN = (
    AccessDenialCode.AUTHENTICATION_REQUIRED,
    AccessDenialCode.SESSION_INACTIVE,
    AccessDenialCode.SESSION_EXPIRED,
    AccessDenialCode.PROFILE_LOCKED,
    AccessDenialCode.CUSTODY_CHANGED,
    AccessDenialCode.CUSTODY_RECOVERING,
    AccessDenialCode.RUNTIME_CHANGED,
    AccessDenialCode.FRESH_PASSWORD_REQUIRED,
)
_TERMINAL = tuple(code for code in AccessDenialCode if code not in _SIGN_IN)


def _verdict(reason: AccessDenialCode) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(ProfileAccessRefusedError(reason))
    assert verdict is not None
    return verdict


@pytest.mark.parametrize("reason", _SIGN_IN)
def test_repairable_session_refusal_opens_sign_in(reason: AccessDenialCode) -> None:
    verdict = _verdict(reason)
    assert verdict.failed_condition_id == SESSION_OPEN_CONDITION
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.login"
    assert verdict.missing_argument_names == ("name",)
    assert verdict.evidence[0].values["access_denial"] == reason.value


@pytest.mark.parametrize("reason", _TERMINAL)
def test_every_other_refusal_stays_terminal(reason: AccessDenialCode) -> None:
    verdict = _verdict(reason)
    assert verdict.failed_condition_id == ACCESS_ADMITTED_CONDITION
    assert verdict.action is None
    assert verdict.no_recovery_outcome is not None
    assert verdict.no_recovery_outcome.value == "terminal"


def test_cross_profile_refusal_offers_no_door() -> None:
    verdict = _verdict(AccessDenialCode.PROFILE_MISMATCH)
    assert verdict.action is None


def test_busy_subject_keeps_its_holder_and_stays_terminal() -> None:
    error = ProfileAccessRefusedError(AccessDenialCode.SUBJECT_BUSY, holder_operation_id="op-1")
    assert error.holder_operation_id == "op-1"
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    assert verdict.action is None
