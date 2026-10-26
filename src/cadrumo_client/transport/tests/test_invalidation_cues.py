"""Invalidation cues reach their subscribers and never retire, retarget or revive a lease."""

from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind

from ...contracts.access_refusals import AccessDenialCode
from ...contracts.contracts import RefusalError
from ...contracts.model_runs import ModelRunRequested
from ...contracts.session_events import AttendanceChanged, ServiceLeaseChanged, SessionEvent, SignInChanged
from ..framing import VerifiedConnection
from ..frontend_client import FrontendClient
from ..frontend_client_contracts import FrontendRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _client(profile_id=None) -> FrontendClient:
    client = FrontendClient(
        cast(VerifiedConnection, object()),
        profile_id=profile_id or uuid4(),
        frontend=OperationFrontendProjection.DESKTOP,
    )
    # A fixture subscription already installed on the verified stream; exercise
    # the real frontend's routing without claiming admission.
    client._event_subscription = lambda: None
    return client


def test_a_sign_in_cue_names_no_profile_and_leaves_the_session_alone() -> None:
    client = _client()
    session_id = uuid4()
    client._session_id = session_id
    heard: list[None] = []
    client._sign_in_receivers.append(lambda: heard.append(None))
    client._session_retired(SignInChanged(runtime_boot_id=uuid4(), connection_id=uuid4()))
    assert heard == [None]
    assert client.session_id == session_id


def test_a_broken_retirement_receiver_does_not_strand_operation_or_attendance_waiters() -> None:
    client = _client()
    client._session_id = uuid4()
    heard: list[str] = []

    def broken() -> None:
        raise ValueError("synthetic callback failure")

    client._retirement_receivers.append(broken)
    client._sign_in_receivers.append(lambda: heard.append("sign-in"))
    client._operation_receivers.append(lambda: heard.append("operation"))
    client._answer_receivers.append(lambda: heard.append("attendance"))
    client._connection_failed()
    with pytest.raises(FrontendRefusedError, match="authentication_required"):
        _ = client.session_id
    assert heard == ["sign-in", "operation", "attendance"]


def test_attendance_cues_follow_only_the_current_session_of_the_profile() -> None:
    profile_id, session_id = uuid4(), uuid4()
    client = _client(profile_id)
    client._session_id = session_id
    heard: list[None] = []
    unsubscribe = client.subscribe_attendance_changes(lambda: heard.append(None))
    cue = AttendanceChanged(
        runtime_boot_id=uuid4(), connection_id=uuid4(), profile_id=profile_id, session_id=session_id
    )
    client._session_retired(cue)
    assert heard == [None] and client.session_id == session_id
    client._session_retired(cue.model_copy(update={"session_id": uuid4()}))
    assert heard == [None]
    with pytest.raises(RefusalError):
        client._session_retired(cue.model_copy(update={"profile_id": uuid4()}))
    unsubscribe()
    client._session_retired(cue)
    assert heard == [None]


def test_a_frontend_refuses_a_service_lease_cue() -> None:
    profile_id = uuid4()
    client = _client(profile_id)
    with pytest.raises(RefusalError):
        client._session_retired(
            ServiceLeaseChanged(runtime_boot_id=uuid4(), connection_id=uuid4(), profile_id=profile_id)
        )


def test_session_retirement_wakes_operation_waiters_even_if_a_view_callback_fails() -> None:
    client = _client()
    session_id = uuid4()
    client._session_id = session_id
    heard: list[None] = []
    client.subscribe_operation_changes(lambda: heard.append(None))

    def failed_view() -> None:
        raise RuntimeError("view has already closed")

    client.subscribe_session_retirement(failed_view)
    event = SessionEvent(
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        profile_id=client.profile_id,
        session_id=session_id,
        event=SessionRetirementKind.REVOKED,
        reason=AccessDenialCode.SESSION_EXPIRED,
    )
    client._session_retired(event.model_copy(update={"session_id": uuid4()}))
    assert heard == []
    client._session_retired(event)
    assert heard == [None]
    with pytest.raises(FrontendRefusedError) as caught:
        _ = client.session_id
    assert caught.value.reason == AccessDenialCode.AUTHENTICATION_REQUIRED.value


def test_a_frontend_refuses_a_model_run_announcement_and_keeps_its_session() -> None:
    profile_id, session_id = uuid4(), uuid4()
    client = _client(profile_id)
    client._session_id = session_id
    with pytest.raises(RefusalError):
        client._session_retired(
            ModelRunRequested(runtime_boot_id=uuid4(), connection_id=uuid4(), profile_id=profile_id, run_id=uuid4())
        )
    assert client.session_id == session_id
