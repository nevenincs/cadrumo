"""A requested page reaches only this exact session's listeners and never retires or retargets it."""

from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection

from ...contracts.contracts import RefusalError
from ...contracts.navigation import ViewLink
from ...contracts.session_events import PresentationRequested
from ..framing import VerifiedConnection
from ..frontend_client import FrontendClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_TRANSACTION = "0123456789abcdef" * 4
_SELECTED = ViewLink(view_id="ledger", params=(("select", _TRANSACTION),))


def test_presentation_reaches_only_the_current_session_and_refuses_a_foreign_profile() -> None:
    profile_id, session_id = uuid4(), uuid4()
    client = FrontendClient(
        cast(VerifiedConnection, object()), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
    )
    client._session_id = session_id
    # A fixture subscription already installed on the verified stream; exercise
    # the real frontend's observer and identity checks without claiming admission.
    client._event_subscription = lambda: None
    retired: list[bool] = []
    client._retirement_receivers.append(lambda: retired.append(True))
    seen: list[ViewLink] = []
    unsubscribe = client.subscribe_presentation_requests(seen.append)
    event = PresentationRequested(
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        destination="ledger",
        params={"select": _TRANSACTION},
    )

    client._session_retired(event)
    assert seen == [_SELECTED]
    assert client.session_id == session_id
    assert retired == []

    # A request addressed to an earlier session of this connection is not this session's.
    client._session_retired(event.model_copy(update={"session_id": uuid4()}))
    assert seen == [_SELECTED]
    with pytest.raises(RefusalError):
        client._session_retired(event.model_copy(update={"profile_id": uuid4()}))

    unsubscribe()
    client._session_retired(event)
    assert seen == [_SELECTED]
    assert retired == []
