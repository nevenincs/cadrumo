"""The hold's relay actions on its bridge: replies, closed refusals, and cues forwarded only while they matter."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SCRIPT = r"""
import contextlib
import sys
from types import SimpleNamespace
from uuid import UUID

from cadrumo_runtime.host import session_hold
from cadrumo_runtime.host.session_hold_operations import RelayRefusedError

profile_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
cues = []

class FakeClient:
    session_id = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

    def resume_receipt(self):
        return SimpleNamespace(
            status=SimpleNamespace(session_id=self.session_id),
            runtime_boot_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
            connection_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        )

    def subscribe_session_retirement(self, callback):
        pass

    def subscribe_profile_language_changes(self, callback):
        return lambda: None

    def subscribe_attendance_changes(self, callback):
        return lambda: None

    def subscribe_operation_changes(self, callback):
        cues.append(callback)
        return lambda: None

    def close(self):
        pass

class FakeRelay:
    def __init__(self, client):
        self.submitted = False

    def watching(self):
        return self.submitted

    def handle(self, action, request):
        if action == "operation_cancel":
            raise RelayRefusedError("stale_operation_revision")
        if action == "operation_submit":
            self.submitted = True
        # The runtime cues while the action runs; the hold forwards it only while an operation it relayed is unsettled.
        cues[0]()
        return {"kind": "operation_submitted", "operation_id": "a" * 64}

async def open_client(**_kwargs):
    return FakeClient()

session_hold.open_installed_client = open_client
session_hold.composed_profile_persistence_ports = contextlib.nullcontext
session_hold.OperationRelay = FakeRelay
sys.exit(session_hold.main(["--profile-id", str(profile_id)]))
"""


async def _converse(
    tmp_path: Path, requests: list[dict[str, object]], *, until: bytes, tail: list[dict[str, object]]
) -> tuple[int, list[dict[str, object]]]:
    """Send ``requests``, read until a line holds ``until``, then send ``tail`` and read to the end."""
    source_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(source_root), existing) if value is not None and value != ""
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        _SCRIPT,
        cwd=tmp_path,
        env=environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    seen: list[bytes] = []
    try:
        held = await asyncio.wait_for(process.stdout.readline(), timeout=20)
        assert b'"kind":"session_held"' in held
        for index, request in enumerate([*requests, *tail]):
            if index == len(requests):
                # The cue arrives beside the replies, so the tail waits for it rather than racing it.
                await process.stdin.drain()
                while True:
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=20)
                    assert line, "the hold ended before the awaited line"
                    seen.append(line)
                    if until in line:
                        break
            document = {"request_id": f"eeeeeeee-eeee-4eee-8eee-{index:012d}", **request}
            process.stdin.write(json.dumps(document).encode() + b"\n")
        await process.stdin.drain()
        output, _ = await asyncio.wait_for(process.communicate(), timeout=20)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode is not None
    return process.returncode, [json.loads(line) for line in [*seen, *output.splitlines()]]


@pytest.mark.asyncio
async def test_relay_replies_refusals_and_the_forwarded_cues(tmp_path: Path) -> None:
    exit_code, lines = await _converse(
        tmp_path,
        [
            {"action": "observe_events"},
            {"action": "operation_observe", "operation_id": "a" * 64, "after_cursor": 0},
            {"action": "operation_submit", "definition_id": "d", "subject_ref": "s", "payload": {}},
            {"action": "operation_cancel", "operation_id": "a" * 64, "expected_revision": 1},
        ],
        until=b"stale_operation_revision",
        tail=[
            {"action": "authentication_start", "method": "google"},
        ],
    )
    assert exit_code == 1
    kinds = [line["kind"] for line in lines]
    events = [line["event"] for line in lines if line["kind"] == "runtime_event"]
    # Before anything was submitted the cue matters to no one; after, it is forwarded.
    assert kinds[:3] == ["events_observed", "operation_submitted", "operation_submitted"]
    assert "operation_changed" in events
    refused = next(line for line in lines if line["kind"] == "operation_refused")
    assert (refused["code"], refused["holder_operation_id"]) == ("stale_operation_revision", None)
    assert refused["request_id"] == "eeeeeeee-eeee-4eee-8eee-000000000003"
    # A sign-in is no relay action of its own: the bridge names no provider, so it ends the hold as invalid.
    assert lines[-1] == {
        "kind": "session_refused",
        "code": "invalid",
        "request_id": "eeeeeeee-eeee-4eee-8eee-000000000004",
    }
