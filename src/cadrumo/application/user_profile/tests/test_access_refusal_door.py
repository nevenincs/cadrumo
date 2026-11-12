"""A refused profile access carries the door its reason deserves."""

from __future__ import annotations

import pytest

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ....core.operator_action_enums import NoRecoveryOutcome
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
_SAFETY = (
    AccessDenialCode.PROFILE_MISMATCH,
    AccessDenialCode.CONNECTION_MISMATCH,
    AccessDenialCode.CLIENT_MISMATCH,
    AccessDenialCode.PARENT_INVALID,
    AccessDenialCode.PRIVILEGE_EXPANSION,
    AccessDenialCode.CLOCK_INVALID,
    AccessDenialCode.FRONTEND_DENIED,
    AccessDenialCode.OPERATION_DENIED,
    AccessDenialCode.DISCLOSURE_DENIED,
    AccessDenialCode.PERIOD_DENIED,
    AccessDenialCode.ADMINISTRATION_DENIED,
)
_DECISION = (
    AccessDenialCode.SUBJECT_BUSY,
    AccessDenialCode.OS_LOCKED,
    AccessDenialCode.OS_SESSION_UNAVAILABLE,
    AccessDenialCode.AUTOMATION_SUSPENDED,
    AccessDenialCode.GRANT_INACTIVE,
    AccessDenialCode.GRANT_EXPIRED,
    AccessDenialCode.KEY_INACTIVE,
    AccessDenialCode.KEY_EXPIRED,
    AccessDenialCode.PROVIDER_REQUIRED,
    AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED,
    AccessDenialCode.TRANSACTION_AUTHORITY_REQUIRED,
    AccessDenialCode.HUMAN_AUTHORITY_REQUIRED,
    AccessDenialCode.PERSON_ACT_REQUIRED,
)
_UNAVAILABLE = (
    AccessDenialCode.STORAGE_UNAVAILABLE,
    AccessDenialCode.CUSTODY_UNAVAILABLE,
    AccessDenialCode.OPERATION_UNAVAILABLE,
    AccessDenialCode.BACKEND_UNAVAILABLE,
    AccessDenialCode.AUTHORITY_UNAVAILABLE,
)
_NO_ACTION = (
    *((code, NoRecoveryOutcome.SAFETY) for code in _SAFETY),
    *((code, NoRecoveryOutcome.OPERATOR_DECISION) for code in _DECISION),
    *((code, NoRecoveryOutcome.TERMINAL) for code in _UNAVAILABLE),
)


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


def test_every_reason_is_classified_once() -> None:
    classified = (*_SIGN_IN, *_SAFETY, *_DECISION, *_UNAVAILABLE)
    assert len(classified) == len(set(classified))
    assert set(classified) == set(AccessDenialCode)


@pytest.mark.parametrize(("reason", "outcome"), _NO_ACTION)
def test_a_refusal_no_sign_in_repairs_names_why_it_offers_no_action(
    reason: AccessDenialCode, outcome: NoRecoveryOutcome
) -> None:
    verdict = _verdict(reason)
    assert verdict.failed_condition_id == ACCESS_ADMITTED_CONDITION
    assert verdict.action is None
    assert verdict.no_recovery_outcome is outcome


def test_cross_profile_refusal_offers_no_door() -> None:
    verdict = _verdict(AccessDenialCode.PROFILE_MISMATCH)
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.SAFETY


def test_busy_subject_keeps_its_holder_and_waits_on_the_person() -> None:
    error = ProfileAccessRefusedError(AccessDenialCode.SUBJECT_BUSY, holder_operation_id="op-1")
    assert error.holder_operation_id == "op-1"
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
