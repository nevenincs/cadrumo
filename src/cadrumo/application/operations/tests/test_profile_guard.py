"""Tests for the shared exact-profile executor boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....core.operations import profile_operation_subject
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import profile_guard
from ..models import CredentialFreeOperationRequest, OperationIdentity, OperationRequest
from ..owner import OperationExecutorContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("6a1f0000-0000-4000-8000-0000000000a1")
_OTHER_PROFILE_ID = UUID("6a1f0000-0000-4000-8000-0000000000b2")
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


class _WorkUnitPayload(CredentialFreeOperationRequest):
    """Operand that names its profile and addressed work unit."""

    profile_id: UUID
    work_unit_id: str


def _access_request(
    payload: BaseModel, *, definition_id: str = _DEFINITION_ID, subject_ref: str | None = None
) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=subject_ref or profile_operation_subject(str(_PROFILE_ID)),
        payload=payload,
    )


def test_profile_access_payload_returns_the_admitted_payload() -> None:
    payload = _ProfilePayload(profile_id=_PROFILE_ID)

    admitted = profile_guard.require_access_request_profile_payload(
        _access_request(payload),
        definition_id=_DEFINITION_ID,
        payload_type=_ProfilePayload,
        access_profile_id=_PROFILE_ID,
    )

    assert admitted is payload


@pytest.mark.parametrize(
    ("definition_id", "payload"),
    [
        ("profile.guard.other", _ProfilePayload(profile_id=_OTHER_PROFILE_ID)),
        (_DEFINITION_ID, _WorkUnitPayload(profile_id=_OTHER_PROFILE_ID, work_unit_id="a" * 12)),
    ],
)
def test_profile_access_payload_refuses_another_operation_before_its_profile(
    definition_id: str, payload: BaseModel
) -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        profile_guard.require_access_request_profile_payload(
            _access_request(payload, definition_id=definition_id),
            definition_id=_DEFINITION_ID,
            payload_type=_ProfilePayload,
            access_profile_id=_PROFILE_ID,
        )

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize(
    ("access_profile_id", "subject_ref"),
    [
        (_OTHER_PROFILE_ID, None),
        (_PROFILE_ID, profile_operation_subject(str(_OTHER_PROFILE_ID))),
    ],
)
def test_profile_access_payload_refuses_a_foreign_profile_or_subject(
    access_profile_id: UUID, subject_ref: str | None
) -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        profile_guard.require_access_request_profile_payload(
            _access_request(_ProfilePayload(profile_id=_PROFILE_ID), subject_ref=subject_ref),
            definition_id=_DEFINITION_ID,
            payload_type=_ProfilePayload,
            access_profile_id=access_profile_id,
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_work_unit_access_payload_requires_the_work_unit_subject() -> None:
    payload = _WorkUnitPayload(profile_id=_PROFILE_ID, work_unit_id="b" * 12)

    admitted = profile_guard.require_access_request_work_unit_payload(
        _access_request(payload, subject_ref=payload.work_unit_id),
        definition_id=_DEFINITION_ID,
        payload_type=_WorkUnitPayload,
        access_profile_id=_PROFILE_ID,
    )

    assert admitted is payload
    for request, access_profile_id in (
        (_access_request(payload), _PROFILE_ID),
        (_access_request(payload, subject_ref=payload.work_unit_id), _OTHER_PROFILE_ID),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            profile_guard.require_access_request_work_unit_payload(
                request,
                definition_id=_DEFINITION_ID,
                payload_type=_WorkUnitPayload,
                access_profile_id=access_profile_id,
            )
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_work_unit_access_payload_refuses_another_payload_type_first() -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        profile_guard.require_access_request_work_unit_payload(
            _access_request(_ProfilePayload(profile_id=_OTHER_PROFILE_ID), subject_ref="c" * 12),
            definition_id=_DEFINITION_ID,
            payload_type=_WorkUnitPayload,
            access_profile_id=_PROFILE_ID,
        )

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_access_payload_returns_the_typed_payload_and_checks_the_definition() -> None:
    payload = _ProfilePayload(profile_id=_PROFILE_ID)

    assert (
        profile_guard.require_access_request_payload(
            _access_request(payload), definition_id=_DEFINITION_ID, payload_type=_ProfilePayload
        )
        is payload
    )
    with pytest.raises(ProfileAccessRefusedError) as refused:
        profile_guard.require_access_request_payload(
            _access_request(payload, definition_id="profile.guard.other"),
            definition_id=_DEFINITION_ID,
            payload_type=_ProfilePayload,
        )
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
