"""The setup tools read, plan and run setup through the components role, bound to the approved plan's digest.

Each case runs the real server over the SDK's in-memory transport, or the real
adapter, with a lease the runtime admitted and the real components client.
Only the role's process is replaced: each start replays a conversation the real
role recorded (:mod:`.components_role`), so what is checked is this service's
own part: the command line it starts the role with, the answer it sends, the
reply it builds and the progress it relays. A setup without the exact digest of
a plan is refused before any role starts.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.outbound.components.protocol import CANCEL_LINE
from cadrumo.adapters.outbound.components.role_image import DEVELOPMENT_ROLE_IMAGE_VARIABLE
from cadrumo.tests.components_role_dispatch import RoleReplay
from cadrumo.tests.components_role_replay import transcript_lines
from cadrumo_client.transport.frontend_client import FrontendClient

from ..runtime_adapter import RuntimeMcpAdapter
from ..server import build_server
from .components_role import role_replay_fixture
from .session import connected_server_and_client_session
from .test_operation_search_tool import _AdmittedClient, _registry

__all__ = ["role_replay_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

type _Replay = Callable[..., RoleReplay]

_BROWSER_ES = "Navegador para la web de la Agencia Tributaria"
_PROGRESS_LINES = sum(1 for line in transcript_lines("setup_browser_completed") if b'"type":"progress"' in line)


class _Lease(_AdmittedClient):
    """A lease the runtime admitted, whose profile names no language, so words come in the default one."""

    def __init__(self, profile_id: UUID) -> None:
        super().__init__(profile_id, _registry())

    def read_profile_view(self, page_kinds: tuple[object, ...]) -> SimpleNamespace:
        del page_kinds
        return SimpleNamespace(items=lambda _kind: (), record_revision=1, content_digest="0" * 64)


def _adapter() -> RuntimeMcpAdapter:
    lease = _Lease(uuid4())
    return RuntimeMcpAdapter(profile_id=lease.profile_id, client=cast(FrontendClient, lease))


async def _until(reached: Callable[[], bool]) -> None:
    """Yield to the role's threads until ``reached`` holds; the bound only fails a test that would hang."""
    async with asyncio.timeout(60):
        while not reached():
            await asyncio.sleep(0.01)


def _digest(name: str) -> str:
    review = next(json.loads(line) for line in transcript_lines(name) if b'"type":"review"' in line)
    return cast(str, review["plan_digest"])


@pytest.mark.anyio
async def test_the_quick_status_answers_every_row_with_its_codes_and_words(role_replay: _Replay) -> None:
    replay = role_replay(status=["status_quick"])
    adapter = _adapter()
    try:
        reply = await adapter.call("setup_status", {})
    finally:
        await adapter.close()

    assert replay.commands() == [("status",)]
    assert reply["outcome"] == "ok" and reply["mode"] == "quick" and reply["setup_complete"] is False
    browser, local_ai = reply["rows"]
    assert browser["item_id"] == "browser" and browser["state"] == "absent"
    assert browser["recovery_action_id"] == "operator.provision.browser"
    assert browser["words"] == {"name": _BROWSER_ES, "sentence": "Aún no está configurado.", "action": "Configurar"}
    assert local_ai["words"]["name"] == "IA local"


@pytest.mark.anyio
async def test_a_full_check_of_one_item_runs_the_roles_verify(role_replay: _Replay) -> None:
    replay = role_replay(verify=["verify_browser_blocked_by_network"])
    adapter = _adapter()
    try:
        reply = await adapter.call("setup_status", {"full": True, "items": ["browser"]})
    finally:
        await adapter.close()

    assert replay.commands() == [("verify", "--item", "browser")]
    assert reply["outcome"] == "ok" and reply["mode"] == "full"
    assert [row["item_id"] for row in reply["rows"]] == ["browser"]


@pytest.mark.anyio
async def test_the_plan_carries_its_digest_and_asks_nothing(role_replay: _Replay) -> None:
    replay = role_replay(plan=["plan_every_item"])
    adapter = _adapter()
    try:
        reply = await adapter.call("setup_plan", {})
    finally:
        await adapter.close()

    recorded = json.loads(transcript_lines("plan_every_item")[1])
    assert replay.commands() == [("plan",)]
    assert [launch.written for launch in replay.launches] == [b""]
    assert reply["outcome"] == "ok"
    assert reply["plan_digest"] == recorded["plan_digest"]
    assert reply["plan"] == recorded["plan"]
    # Every planned model comes under a licence that permits commercial use.
    assert reply["notices"] == []


@pytest.mark.anyio
@pytest.mark.parametrize("arguments", [{}, {"plan_digest": "abc"}, {"plan_digest": "A" * 64}])
async def test_a_setup_without_the_exact_digest_of_a_plan_starts_no_role(
    role_replay: _Replay, arguments: dict[str, object]
) -> None:
    replay = role_replay(setup=["setup_browser_completed"])
    adapter = _adapter()
    try:
        reply = await adapter.call("setup", arguments)
    finally:
        await adapter.close()

    assert reply == {"outcome": "refused", "code": "invalid_request"}
    assert replay.launches == []


@pytest.mark.anyio
async def test_an_unknown_item_is_refused_before_any_role_starts(role_replay: _Replay) -> None:
    replay = role_replay(status=["status_quick"])
    adapter = _adapter()
    try:
        reply = await adapter.call("setup_status", {"items": ["google"]})
    finally:
        await adapter.close()

    assert reply == {"outcome": "refused", "code": "invalid_request"}
    assert replay.launches == []


@pytest.mark.anyio
async def test_a_setup_runs_under_the_approved_digest_and_relays_its_progress(role_replay: _Replay) -> None:
    digest = _digest("setup_browser_completed")
    replay = role_replay(setup=["setup_browser_completed"])
    received: list[tuple[float, float | None, str | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        received.append((progress, total, message))

    adapter = _adapter()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            called = await sdk.call_tool(
                "setup", {"plan_digest": digest, "items": ["browser"]}, progress_callback=on_progress
            )
    finally:
        await adapter.close()

    assert replay.commands() == [("setup", "--item", "browser", "--approve", digest)]
    # Under an approval the role asks nothing, so nothing is answered.
    assert [launch.written for launch in replay.launches] == [b""]
    reply = cast(dict[str, Any], called.structured_content)
    assert called.is_error is False
    assert reply["outcome"] == "completed" and reply["plan_digest"] == digest
    assert reply["progress"] == [{"item_id": "browser", "completed": 332691793, "total": 332691793}]
    assert len(received) == _PROGRESS_LINES
    assert received[-1] == (332691793.0, 332691793.0, _BROWSER_ES)


@pytest.mark.anyio
async def test_a_changed_plan_is_answered_with_the_new_plan_and_nothing_moves(role_replay: _Replay) -> None:
    approved = "0" * 64
    role_replay(setup=["setup_plan_changed"])
    adapter = _adapter()
    try:
        reply = await adapter.call("setup", {"plan_digest": approved, "items": ["browser"]})
    finally:
        await adapter.close()

    recorded = json.loads(transcript_lines("setup_plan_changed")[-1])
    assert reply["outcome"] == "plan_changed"
    assert reply["plan_digest"] == recorded["plan_digest"] != approved
    assert "progress" not in reply


@pytest.mark.anyio
async def test_a_setup_the_network_blocks_is_refused_with_its_sentence(role_replay: _Replay) -> None:
    role_replay(setup=["setup_refused_blocked_by_network"])
    adapter = _adapter()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            called = await sdk.call_tool("setup", {"plan_digest": "1" * 64})
    finally:
        await adapter.close()

    reply = cast(dict[str, Any], called.structured_content)
    assert called.is_error is True
    assert reply["outcome"] == "refused" and reply["failure_category"] == "blocked_by_network"
    assert reply["failure"] == f"{_BROWSER_ES}: Tu red ha bloqueado la descarga."


@pytest.mark.anyio
async def test_a_running_setup_holds_no_lock_and_cancelling_the_call_stops_the_role(role_replay: _Replay) -> None:
    digest = _digest("setup_browser_completed")
    # The recorded setup stops writing after its first byte figures, as a slow download would.
    replay = role_replay(
        setup=["setup_browser_completed"], status=["status_quick"], stall_after={"setup_browser_completed": 7}
    )
    adapter = _adapter()
    try:
        running = asyncio.ensure_future(adapter.call("setup", {"plan_digest": digest}))
        await _until(lambda: bool(replay.launches))
        # The connection answers other calls while the setup runs.
        status = await adapter.call("setup_status", {})
        assert status["outcome"] == "ok"
        running.cancel()
        setup = replay.launches[0]
        await _until(lambda: CANCEL_LINE in setup.written)
        # The role ends; only then does the cancelled call return.
        setup.end()
        with pytest.raises(asyncio.CancelledError):
            await running
    finally:
        await adapter.close()

    assert setup.written == CANCEL_LINE


@pytest.mark.anyio
async def test_a_connection_nothing_admits_starts_no_role(role_replay: _Replay) -> None:
    replay = role_replay(status=["status_quick"])
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        reply = await adapter.call("setup_status", {})
    finally:
        await adapter.close()

    assert reply["outcome"] == "refused" and "remedy" in reply
    assert replay.launches == []


@pytest.mark.anyio
async def test_a_build_without_the_engine_reads_every_item_as_not_in_this_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, raising=False)
    adapter = _adapter()
    try:
        reply = await adapter.call("setup_status", {})
    finally:
        await adapter.close()

    assert [row["blocked_reason"] for row in reply["rows"]] == ["not_in_this_build"] * 2
    assert {row["words"]["sentence"] for row in reply["rows"]} == {"Esta versión de Cadrumo no lo incluye."}


@pytest.mark.anyio
async def test_a_setup_already_running_elsewhere_is_followed_and_its_progress_relayed(role_replay: _Replay) -> None:
    approved = "2" * 64
    replay = role_replay(setup=["setup_followed_completed"])
    lines = [json.loads(line) for line in transcript_lines("setup_followed_completed")]
    following = next(line for line in lines if line.get("notice_code") == "following")
    figures = [line for line in lines if line["type"] == "progress"]
    received: list[tuple[float, float | None, str | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        received.append((progress, total, message))

    adapter = _adapter()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            called = await sdk.call_tool("setup", {"plan_digest": approved}, progress_callback=on_progress)
    finally:
        await adapter.close()

    reply = cast(dict[str, Any], called.structured_content)
    assert [launch.written for launch in replay.launches] == [b""]
    # The reply is the followed setup's result, run under its own plan, not the one this call carried.
    assert reply["outcome"] == "completed" and "plan" not in reply
    assert reply["followed"] == [{"item_id": "browser", "plan_digest": following["plan_digest"]}]
    assert following["plan_digest"] != approved
    assert [(progress, total) for progress, total, _message in received] == [
        (float(line["completed"]), float(line["total"])) for line in figures
    ]


@pytest.mark.anyio
async def test_a_following_that_stops_ends_busy_while_the_followed_setup_goes_on(role_replay: _Replay) -> None:
    role_replay(setup=["setup_follow_stopped"])
    adapter = _adapter()
    try:
        reply = await adapter.call("setup", {"plan_digest": "2" * 64})
    finally:
        await adapter.close()

    assert reply["outcome"] == "busy" and reply["item_id"] == "browser"
    assert [row["state"] for row in reply["rows"] if row["item_id"] == "browser"] == ["provisioning"]
    assert reply["followed"][0]["item_id"] == "browser"
