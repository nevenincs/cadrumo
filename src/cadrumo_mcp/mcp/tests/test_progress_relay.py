"""An observed operation's progress reaches an MCP client as ``notifications/progress``.

The relay reads the reply the ``observe`` tool already returned. These tests
build that reply from the real public event models, check the figures it
relays, and then run the real server over the SDK's
in-memory transport so a client that sends a progress token receives one
notification per progress event, and a client that sends none receives none.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import pytest

from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicPhaseEventV1,
    OperationPublicProgressEventV1,
)
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo_client.contracts.operation_access import OperationObserved

from ..progress_relay import RelayedProgress, relayed_progress
from ..server import build_server
from ..surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES
from .session import connected_server_and_client_session

if TYPE_CHECKING:
    from ..runtime_adapter import RuntimeMcpAdapter

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_OPERATION_ID = "c" * 64
_NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def _observe_reply() -> dict[str, Any]:
    """Return an ``observe`` tool result whose page carries one phase and two progress events."""
    phase = "ledger.evidence.read"
    page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=3,
        requested_cursor=0,
        status=OperationReplayStatus.PAGE,
        events=(
            OperationPublicPhaseEventV1(revision=1, sequence=1, timestamp=_NOW, code=phase, phase_code=phase),
            OperationPublicProgressEventV1(
                revision=1,
                sequence=2,
                timestamp=_NOW,
                code="ledger.evidence.progress",
                completed=25,
                total=100,
                unit_code="bytes",
            ),
            OperationPublicProgressEventV1(
                revision=1,
                sequence=3,
                timestamp=_NOW,
                code="ledger.evidence.progress",
                completed=3,
                total=4,
                unit_code=None,
            ),
        ),
        next_cursor=3,
        restart_cursor=None,
    )
    # The reply's envelope names exactly the fields the real reply models declare.
    assert {"kind", "observation"} <= set(OperationObserved.model_fields)
    assert {"outcome", "event_page"} <= set(OperationObservationSuccessV1.model_fields)
    return {
        "outcome": "reply",
        "reply": {
            "kind": "operation_observed",
            "observation": {"outcome": "success", "event_page": page.model_dump(mode="json")},
        },
    }


def test_an_observe_reply_relays_each_progress_event() -> None:
    relayed = relayed_progress("observe", _observe_reply())

    assert relayed == (RelayedProgress(progress=25.0, total=100.0), RelayedProgress(progress=3.0, total=4.0))


def test_no_other_tool_and_no_refused_observation_relays_progress() -> None:
    reply = _observe_reply()
    refused = {"outcome": "reply", "reply": {"kind": "operation_observed", "observation": {"outcome": "refused"}}}

    assert relayed_progress("execute", reply) == ()
    assert relayed_progress("observe", refused) == ()
    assert relayed_progress("observe", {"outcome": "unresolved", "code": "deadline_exceeded"}) == ()


class _ObservingAdapter:
    """Answers every call with one observation, as the runtime adapter would after observing."""

    surface = MCP_SURFACES[DEFAULT_MCP_SURFACE]

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        del name, arguments
        return _observe_reply()


@pytest.mark.anyio
async def test_a_client_with_a_progress_token_receives_one_notification_per_progress_event() -> None:
    received: list[tuple[float, float | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        assert message is None
        received.append((progress, total))

    server = build_server(cast("RuntimeMcpAdapter", _ObservingAdapter()))
    async with connected_server_and_client_session(server) as session:
        await session.call_tool("observe", {"observation": {}}, progress_callback=on_progress)
        without = len(received)
        await session.call_tool("observe", {"observation": {}})

    assert received == [(25.0, 100.0), (3.0, 4.0)]
    assert len(received) == without
