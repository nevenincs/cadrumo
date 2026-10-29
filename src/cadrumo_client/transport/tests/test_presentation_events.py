"""A requested page never retires or retargets this exact session."""

from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection

from ...contracts.contracts import RefusalError
from ...contracts.presentation import PresentationDelivered, PresentationRequest
from ...contracts.session_events import PresentationRequested
from ..framing import VerifiedConnection
from ..frontend_client import FrontendClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_TRANSACTION = "0123456789abcdef" * 4


def test_a_presentation_request_neither_retires_nor_retargets_the_session_and_a_foreign_profile_is_refused() -> None:
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
    event = PresentationRequested(
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        destination="ledger",
        params={"select": _TRANSACTION},
    )

    client._session_retired(event)
    assert client.session_id == session_id
    assert retired == []

    client._session_retired(event.model_copy(update={"session_id": uuid4()}))
    assert client.session_id == session_id
    assert retired == []
    with pytest.raises(RefusalError):
        client._session_retired(event.model_copy(update={"profile_id": uuid4()}))


class _PresentingConnection:
    """A verified connection whose runtime answers a view request, echoing the parameters it was given or others."""

    def __init__(self, echoed: dict[str, str] | None) -> None:
        self.echoed = echoed

    def present(self, request: PresentationRequest, *, deadline: float) -> PresentationDelivered:
        return PresentationDelivered(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            destination=request.destination,
            params=request.params if self.echoed is None else self.echoed,
            delivered=1,
        )


@pytest.mark.parametrize("params", [{}, {"select": _TRANSACTION}])
def test_a_delivered_view_echoes_exactly_the_parameters_asked_for(params: dict[str, str]) -> None:
    client = FrontendClient(
        cast(VerifiedConnection, _PresentingConnection(None)),
        profile_id=uuid4(),
        frontend=OperationFrontendProjection.DESKTOP,
    )
    client._session_id = uuid4()

    delivered = client.present_destination("ledger", params)
    assert (delivered.destination, delivered.params) == ("ledger", params)


def test_a_reply_echoing_other_parameters_is_refused() -> None:
    client = FrontendClient(
        cast(VerifiedConnection, _PresentingConnection({})),
        profile_id=uuid4(),
        frontend=OperationFrontendProjection.DESKTOP,
    )
    client._session_id = uuid4()

    with pytest.raises(RefusalError):
        client.present_destination("ledger", {"select": _TRANSACTION})
