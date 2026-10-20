"""A person's activity report through the session hold, and which refusals end the hold."""

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

from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo.core.external_constants import OutputLanguage
from cadrumo_runtime.host import session_hold

profile_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
refusals = sys.argv[1].split(",") if sys.argv[1] else []

class FakeClient:
    def __init__(self):
        self.language_reads = 0
        self.status_snapshot = SimpleNamespace(
            status=SimpleNamespace(session_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")),
            runtime_boot_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
            connection_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        )
        self.session_id = self.status_snapshot.status.session_id

    def resume_receipt(self):
        return self.status_snapshot

    def note_activity(self):
        if refusals:
            reason = refusals.pop(0)
            if reason == "language_changed":
                self.language_changed(None)
            else:
                raise FrontendRefusedError(reason)
        return SimpleNamespace(model_dump=lambda mode: {"kind": "profile_status", "request_id": "runtime"})

    def subscribe_session_retirement(self, callback):
        pass

    def subscribe_profile_language_changes(self, callback):
        self.language_changed = callback
        return lambda: None

    def subscribe_attendance_changes(self, callback):
        return lambda: None

    def subscribe_operation_changes(self, callback):
        return lambda: None

    def close(self):
        pass

async def open_client(**_kwargs):
    return FakeClient()

def read_language(client):
    client.language_reads += 1
    if refusals and refusals[0] == "language_changed_during_read":
        refusals.pop(0)
        client.language_changed(None)
    return SimpleNamespace(language=OutputLanguage.EN, record_revision=client.language_reads)

session_hold.open_installed_client = open_client
session_hold.read_profile_language = read_language
session_hold.composed_profile_persistence_ports = contextlib.nullcontext
sys.exit(session_hold.main(["--profile-id", str(profile_id)]))
"""


async def _converse(tmp_path: Path, refusals: str, requests: list[str]) -> tuple[int, list[dict[str, object]]]:
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
        refusals,
        cwd=tmp_path,
        env=environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    replies: list[dict[str, object]] = []
    try:
        held = await asyncio.wait_for(process.stdout.readline(), timeout=10)
        assert b'"kind":"session_held"' in held
        for index, action in enumerate(requests):
            request = {"request_id": f"eeeeeeee-eeee-4eee-8eee-{index:012d}", "action": action}
            process.stdin.write(json.dumps(request).encode() + b"\n")
            await process.stdin.drain()
            line = await asyncio.wait_for(process.stdout.readline(), timeout=10)
            if not line:
                break
            replies.append(json.loads(line))
        exit_code = await asyncio.wait_for(process.wait(), timeout=10)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    return exit_code, replies


@pytest.mark.asyncio
async def test_an_uncertain_os_observation_refuses_only_that_report_and_keeps_the_hold(tmp_path: Path) -> None:
    exit_code, replies = await _converse(tmp_path, "os_session_unavailable", ["activity", "activity", "close"])
    assert exit_code == 0
    assert replies[0] == {
        "kind": "session_refused",
        "code": "unavailable",
        "request_id": "eeeeeeee-eeee-4eee-8eee-000000000000",
    }
    # The same hold answers the next report with the session's status, under that request's id.
    assert replies[1] == {"kind": "profile_status", "request_id": "eeeeeeee-eeee-4eee-8eee-000000000001"}
    assert replies[2]["kind"] == "session_closed"


@pytest.mark.asyncio
async def test_a_report_on_an_ended_session_ends_the_hold(tmp_path: Path) -> None:
    exit_code, replies = await _converse(tmp_path, "session_expired", ["activity", "activity"])
    assert exit_code == 1
    assert replies == [
        {"kind": "session_refused", "request_id": "eeeeeeee-eeee-4eee-8eee-000000000000", "code": "inactive"}
    ]


@pytest.mark.asyncio
async def test_language_observations_reuse_reads_until_a_profile_change(tmp_path: Path) -> None:
    exit_code, replies = await _converse(
        tmp_path,
        "language_changed",
        ["language_observe", "language_observe", "activity", "language_observe", "language_read", "close"],
    )
    assert exit_code == 0, replies
    assert [reply["record_revision"] for reply in replies if reply["kind"] == "profile_language"] == [1, 1, 2, 3]


@pytest.mark.asyncio
async def test_language_change_arriving_during_a_read_is_not_lost(tmp_path: Path) -> None:
    exit_code, replies = await _converse(
        tmp_path,
        "language_changed_during_read",
        ["language_observe", "language_observe", "language_observe", "close"],
    )
    assert exit_code == 0, replies
    assert [reply["record_revision"] for reply in replies if reply["kind"] == "profile_language"] == [1, 2, 2]
