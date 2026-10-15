"""Language invalidation cannot retire, retarget, or revive an exact-profile lease."""

from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection

from ...contracts.contracts import RefusalError
from ...contracts.session_events import ProfileLanguageChanged
from ..framing import VerifiedConnection
from ..frontend_client import FrontendClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_language_notification_ignores_retired_session_and_refuses_foreign_profile() -> None:
    profile_id, session_id = uuid4(), uuid4()
    client = FrontendClient(
        cast(VerifiedConnection, object()), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
    )
    client._session_id = session_id
    # A fixture subscription already installed on the verified stream; exercise
    # the real frontend's observer and identity checks without claiming admission.
    client._event_subscription = lambda: None
    seen: list[ProfileLanguageChanged] = []
    unsubscribe = client.subscribe_profile_language_changes(seen.append)
    event = ProfileLanguageChanged(
        runtime_boot_id=uuid4(), connection_id=uuid4(), profile_id=profile_id, session_id=session_id
    )
    client._session_retired(event)
    assert seen == [event]
    assert client.session_id == session_id
    client._session_retired(event.model_copy(update={"session_id": uuid4()}))
    assert seen == [event]
    with pytest.raises(RefusalError):
        client._session_retired(event.model_copy(update={"profile_id": uuid4()}))
    client._session_id = None
    client._session_retired(event)
    assert seen == [event]
    assert client._session_id is None
    unsubscribe()
    client._session_id = session_id
    client._session_retired(event)
    assert seen == [event]
