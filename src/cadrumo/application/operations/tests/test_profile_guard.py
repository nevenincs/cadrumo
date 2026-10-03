"""Tests for the shared exact-profile executor boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

import pytest

from ....core.operations import profile_operation_subject
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import profile_guard
from ..models import CredentialFreeOperationRequest, OperationIdentity, OperationRequest
from ..owner import OperationExecutorContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = uuid4()
_OTHER_PROFILE_ID = uuid4()
_DEFINITION_ID = "profile.guard.test"


class _ProfilePayload(CredentialFreeOperationRequest):
    """Small immutable operand for the shared profile guard."""

    profile_id: UUID


@dataclass(frozen=True)
class _Context:
    identity: OperationIdentity


def _request(
    *, subject_profile_id: UUID = _PROFILE_ID, subject_ref: str | None = None
) -> OperationRequest[_ProfilePayload]:
    return OperationRequest[_ProfilePayload](
        definition_id=_DEFINITION_ID,
        subject_ref=subject_ref or profile_operation_subject(str(subject_profile_id)),
        payload=_ProfilePayload(profile_id=_PROFILE_ID),
    )


def _context(
    request: OperationRequest[_ProfilePayload], *, definition_id: str | None = None, subject_ref: str | None = None
) -> _Context:
    return _Context(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=definition_id or request.definition_id,
            subject_ref=subject_ref or request.subject_ref,
        )
    )


@pytest.mark.parametrize(
    ("subject_profile_id", "identity_definition", "identity_subject"),
    [
        (_OTHER_PROFILE_ID, None, None),
        (_PROFILE_ID, "profile.guard.other", None),
        (_PROFILE_ID, None, profile_operation_subject(str(_OTHER_PROFILE_ID))),
    ],
)
def test_request_or_executor_identity_mismatch_refuses(
    monkeypatch: pytest.MonkeyPatch,
    subject_profile_id: UUID,
    identity_definition: str | None,
    identity_subject: str | None,
) -> None:
    request = _request(subject_profile_id=subject_profile_id)
    context = _context(request, definition_id=identity_definition, subject_ref=identity_subject)

    def active_bucket_must_not_be_read() -> str:
        raise AssertionError("identity refusal must short-circuit before the active-profile lookup")

    monkeypatch.setattr(profile_guard, "require_active_bucket_id", active_bucket_must_not_be_read)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        profile_guard.require_operation_profile(request, cast(OperationExecutorContext, context), _PROFILE_ID)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.parametrize(
    ("subject_profile_id", "identity_definition", "identity_subject"),
    [
        (_OTHER_PROFILE_ID, None, None),
        (_PROFILE_ID, "profile.guard.other", None),
        (_PROFILE_ID, None, profile_operation_subject(str(_OTHER_PROFILE_ID))),
    ],
)
def test_identity_only_guard_refuses_target_or_executor_identity_mismatch_without_active_lookup(
    monkeypatch: pytest.MonkeyPatch,
    subject_profile_id: UUID,
    identity_definition: str | None,
    identity_subject: str | None,
) -> None:
    request = _request(subject_profile_id=subject_profile_id)
    context = _context(request, definition_id=identity_definition, subject_ref=identity_subject)

    def active_bucket_must_not_be_read() -> str:
        raise AssertionError("identity-only guard must not read the active profile")

    monkeypatch.setattr(profile_guard, "require_active_bucket_id", active_bucket_must_not_be_read)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        profile_guard.require_profile_operation_identity(
            request,
            cast(OperationExecutorContext, context),
            _PROFILE_ID,
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_identity_only_guard_accepts_matching_target_and_executor_without_active_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    context = _context(request)

    def active_bucket_must_not_be_read() -> str:
        raise AssertionError("identity-only guard must not read the active profile")

    monkeypatch.setattr(profile_guard, "require_active_bucket_id", active_bucket_must_not_be_read)

    assert (
        profile_guard.require_profile_operation_identity(
            request,
            cast(OperationExecutorContext, context),
            _PROFILE_ID,
        )
        is None
    )


def test_active_bucket_swap_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()
    context = _context(request)
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_OTHER_PROFILE_ID))

    with pytest.raises(ProfileAccessRefusedError) as refused:
        profile_guard.require_operation_profile(request, cast(OperationExecutorContext, context), _PROFILE_ID)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_matching_request_context_and_active_bucket_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()
    context = _context(request)
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE_ID))

    assert (
        profile_guard.require_operation_profile(request, cast(OperationExecutorContext, context), _PROFILE_ID) is None
    )


def test_explicit_work_unit_subject_passes_while_another_target_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request(subject_ref="work-unit:target")
    context = _context(request)
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE_ID))

    assert (
        profile_guard.require_operation_profile(
            request, cast(OperationExecutorContext, context), _PROFILE_ID, expected_subject_ref="work-unit:target"
        )
        is None
    )
    with pytest.raises(ProfileAccessRefusedError) as refused:
        profile_guard.require_operation_profile(
            request, cast(OperationExecutorContext, context), _PROFILE_ID, expected_subject_ref="work-unit:other"
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
