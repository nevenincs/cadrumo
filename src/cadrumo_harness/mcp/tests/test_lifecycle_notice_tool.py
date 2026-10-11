"""What the adapter does with what the runtime tells its connection between calls.

The adapter's own part is shown here: where it puts a lifecycle notice, how
often, and what it does with a key lease the runtime retired. The runtime's
side is a connection double that keeps the receivers the adapter hands it,
because sending a notice and retiring a lease are the runtime's acts and are
proven against the real runtime where that runtime lives.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast, override
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.session_events import RuntimeLifecycleNotice
from cadrumo_harness.mcp import runtime_adapter as mcp_runtime
from cadrumo_harness.mcp.lifecycle_notices import LifecycleNoticeBoard
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.tests.test_authentication_handover import _Client

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _notice() -> RuntimeLifecycleNotice:
    return RuntimeLifecycleNotice(runtime_boot_id=uuid4(), connection_id=uuid4(), notice_id=uuid4())


def _told(board: LifecycleNoticeBoard, tool: str) -> dict[str, str] | None:
    reply: dict[str, object] = {"outcome": "found"}
    board.annotate(tool, reply)
    return cast("dict[str, str] | None", reply.get("notice"))


def test_a_notice_is_told_once_and_status_repeats_it_while_its_connection_is_held() -> None:
    board, notice = LifecycleNoticeBoard(), _notice()
    assert _told(board, "search") is None and _told(board, "status") is None

    board.receive(1, notice)

    expected = {"event": "upgrade_pending", "notice_id": str(notice.notice_id)}
    assert _told(board, "search") == expected
    assert _told(board, "search") is None
    assert _told(board, "status") == expected
    # Letting go of another connection changes nothing; letting go of the one it arrived on ends it.
    board.released(2)
    assert _told(board, "status") == expected
    board.released(1)
    assert _told(board, "status") is None


def test_a_notice_not_yet_told_outlives_its_connection_for_exactly_one_result() -> None:
    board, notice = LifecycleNoticeBoard(), _notice()
    board.receive(1, notice)

    board.released(1)

    assert _told(board, "execute") == {"event": "upgrade_pending", "notice_id": str(notice.notice_id)}
    assert _told(board, "status") is None


class _WatchedClient(_Client):
    """A key lease that keeps the receivers the adapter subscribes, as the runtime's connection does."""

    def __init__(self, profile_id: UUID) -> None:
        super().__init__(profile_id)
        self.retire: Callable[[], None] | None = None
        self.notify: Callable[[RuntimeLifecycleNotice], None] | None = None

    @override
    def subscribe_session_retirement(self, receive: object) -> None:
        self.retire = cast("Callable[[], None]", receive)

    @override
    def subscribe_lifecycle_notices(self, receive: object) -> None:
        self.notify = cast("Callable[[RuntimeLifecycleNotice], None]", receive)


async def _authenticated(
    monkeypatch: pytest.MonkeyPatch, *, refusal: str | None
) -> tuple[RuntimeMcpAdapter, list[_WatchedClient], list[UUID]]:
    """Return an adapter holding a key lease, the connections the runtime opened, and every reference it was asked."""
    profile_id, reference = uuid4(), uuid4()
    opened: list[_WatchedClient] = []
    asked: list[UUID] = []

    async def admit(
        *, profile_id: UUID, credential_reference: UUID, frontend: OperationFrontendProjection
    ) -> RuntimeFrontendClient:
        assert frontend is OperationFrontendProjection.MCP
        asked.append(credential_reference)
        if opened and refusal is not None:
            raise RuntimeFrontendRefusedError(refusal)
        opened.append(_WatchedClient(profile_id))
        return cast(RuntimeFrontendClient, opened[-1])

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", admit)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    authenticated = await adapter.call("authenticate", {"credential_reference": str(reference)})
    assert authenticated["outcome"] == "authenticated"
    assert (await adapter.call("status", {}))["session"] == "key"
    assert len(opened) == 1 and asked == [reference]
    return adapter, opened, asked


@pytest.mark.anyio
@pytest.mark.parametrize("refusal", [None, "grant_inactive"], ids=["runtime-readmits", "runtime-refuses"])
async def test_a_key_lease_whose_connection_was_lost_is_authenticated_anew_once_per_call(
    monkeypatch: pytest.MonkeyPatch, refusal: str | None
) -> None:
    adapter, opened, asked = await _authenticated(monkeypatch, refusal=refusal)
    try:
        first = opened[0]
        assert first.retire is not None and first.notify is not None
        notice = _notice()
        first.notify(notice)
        first.retire()

        status = await adapter.call("status", {})
        again = await adapter.call("status", {})
    finally:
        await adapter.close()

    # The lost lease is let go, and the notice that explained the loss still reaches the next result.
    assert first.close_count == 1
    assert status["notice"] == {"event": "upgrade_pending", "notice_id": str(notice.notice_id)}
    assert "notice" not in again
    assert len(set(asked)) == 1
    if refusal is None:
        assert len(opened) == 2 and len(asked) == 2
        assert status["session"] == "key" and again["session"] == "key"
    else:
        # One request per call, none in a loop: the first call and the second each asked once.
        assert len(opened) == 1 and len(asked) == 3
        assert status["session"] == "none" and status["denial"] == refusal
        assert again["session"] == "none" and again["denial"] == refusal


@pytest.mark.anyio
@pytest.mark.parametrize(
    "refusal",
    ["key_inactive", "grant_inactive", "profile_locked", None],
    ids=["revoked-key", "revoked-grant", "locked", "expired-with-live-grant"],
)
async def test_a_key_session_the_runtime_ended_is_authenticated_anew_and_the_runtime_decides(
    monkeypatch: pytest.MonkeyPatch, refusal: str | None
) -> None:
    adapter, opened, asked = await _authenticated(monkeypatch, refusal=refusal)
    try:
        first = opened[0]
        assert first.retire is not None
        first.retire()

        status = await adapter.call("status", {})
        refused = await adapter.call("search", {"query": "auth"})
    finally:
        await adapter.close()

    assert first.close_count == 1 and len(set(asked)) == 1
    if refusal is None:
        # The grant is live, so the runtime admits the key again and the calls proceed under the new session.
        assert len(opened) == 2 and len(asked) == 2
        assert status["session"] == "key" and refused.get("code") != "authentication_required"
    else:
        # The runtime's own refusal is the answer, no session is held, and each call asked once.
        assert len(opened) == 1 and len(asked) == 3 and adapter.client is None
        assert status["session"] == "none" and status["denial"] == refusal
        assert refused == {"outcome": "refused", "code": refusal}
