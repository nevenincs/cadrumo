"""A replaced TUI session cannot receive a reply from its old exchange."""

from __future__ import annotations

import asyncio
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import RuntimeOperationAcknowledged, RuntimeOperationControl
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64


class _SessionChangingClient:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.session_id = uuid4()
        self.replacement_session_id = uuid4()
        self.reply: RuntimeOperationAcknowledged | None = None

    def operation(self, request: RuntimeOperationControl, *, deadline: float) -> RuntimeOperationAcknowledged:
        del deadline
        assert request.session_id == self.session_id
        self.session_id = self.replacement_session_id
        self.reply = RuntimeOperationAcknowledged(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            operation_id=_OPERATION_ID,
        )
        return self.reply


def test_exchange_discards_old_reply_when_session_changes_while_awaiting() -> None:
    client = _SessionChangingClient()
    original_session_id = client.session_id
    controller = RuntimeOperationController(
        client=cast(RuntimeFrontendClient, client),
        operation_id=_OPERATION_ID,
        session_id=original_session_id,
    )
    request = RuntimeOperationControl(
        request_id=uuid4(),
        profile_id=uuid4(),
        session_id=original_session_id,
        action="operation_start",
        operation_id=_OPERATION_ID,
    )

    with pytest.raises(RuntimeRefusalError) as raised:
        asyncio.run(controller._exchange(request))

    assert client.reply is not None
    assert client.session_id == client.replacement_session_id
    assert raised.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
