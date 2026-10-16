"""Invalidation cues reach their subscribers and never retire, retarget or revive a lease."""

from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection

from ...contracts.contracts import RefusalError
from ...contracts.session_events import AttendanceChanged, ServiceLeaseChanged, SignInChanged
from ..framing import VerifiedConnection
from ..frontend_client import FrontendClient

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
