"""A register view the desktop asks its TUI to show, through the session hold, and which refusals end the hold."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TRANSACTION = "0123456789abcdef" * 4

_SCRIPT = r"""
import contextlib
import sys
from types import SimpleNamespace
from uuid import UUID

from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_runtime.host import session_hold

profile_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
refusals = sys.argv[1].split(",") if sys.argv[1] else []

class FakeClient:
    def __init__(self):
        self.status_snapshot = SimpleNamespace(
            status=SimpleNamespace(session_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")),
            runtime_boot_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
            connection_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        )
        self.session_id = self.status_snapshot.status.session_id

    def resume_receipt(self):
        return self.status_snapshot

    def present_destination(self, destination, params=None):
        if refusals:
            raise FrontendRefusedError(refusals.pop(0))
        print(f"presented {destination} {sorted((params or {}).items())}", file=sys.stderr)
        return SimpleNamespace(destination=destination, delivered=1)

    def subscribe_session_retirement(self, callback):
        pass

    def subscribe_profile_record_changes(self, callback):
        return lambda: None

    def subscribe_profile_language_changes(self, callback):
        return lambda: None

    def subscribe_attendance_changes(self, callback):
        return lambda: None

    def subscribe_operation_changes(self, callback):
        return lambda: None

    def close(self):
        pass

async def open_client(**_kwargs):
    return FakeClient()

session_hold.open_installed_client = open_client
session_hold.composed_profile_persistence_ports = contextlib.nullcontext
sys.exit(session_hold.main(["--profile-id", str(profile_id)]))
"""


async def _converse(
    tmp_path: Path, refusals: str, requests: list[dict[str, object]]
) -> tuple[int, list[dict[str, object]]]:
    exit_code, replies, _ = await _converse_logged(tmp_path, refusals, requests)
    return exit_code, replies


async def _converse_logged(
    tmp_path: Path, refusals: str, requests: list[dict[str, object]]
) -> tuple[int, list[dict[str, object]], str]:
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
        for index, fields in enumerate(requests):
            request = {"request_id": f"eeeeeeee-eeee-4eee-8eee-{index:012d}", **fields}
            process.stdin.write(json.dumps(request).encode() + b"\n")
            await process.stdin.drain()
            line = await asyncio.wait_for(process.stdout.readline(), timeout=10)
            if not line:
                break
            replies.append(json.loads(line))
        exit_code = await asyncio.wait_for(process.wait(), timeout=10)
        assert process.stderr is not None
        stderr = (await process.stderr.read()).decode(errors="replace")
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    return exit_code, replies, stderr


@pytest.mark.asyncio
async def test_a_presented_page_reports_how_many_tuis_were_asked(tmp_path: Path) -> None:
    exit_code, replies = await _converse(
        tmp_path, "", [{"action": "present_destination", "destination": "profile/aeat-access"}, {"action": "close"}]
    )
    assert exit_code == 0, replies
    assert replies[0] == {
        "kind": "destination_presented",
        "request_id": "eeeeeeee-eeee-4eee-8eee-000000000000",
        "profile_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "session_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "runtime_boot_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "connection_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        "destination": "profile/aeat-access",
        "delivered": 1,
    }
    assert replies[1]["kind"] == "session_closed"


@pytest.mark.parametrize(
    "request_fields",
    [
        {"action": "present_destination", "destination": "workbench.ledger"},
        {"action": "present_destination", "destination": "../ledger"},
        {"action": "present_destination", "destination": "aeat_auth"},
        {"action": "present_destination"},
        {"action": "present_destination", "destination": "ledger", "profile_id": "aaaaaaaa"},
        # Only the window implements these elements.
        {"action": "present_destination", "destination": "ledger/invoices"},
        {"action": "present_destination", "destination": "calendar"},
        # A parameter no element declares, one the element does not take, and values not of its kind.
        {"action": "present_destination", "destination": "ledger", "params": {"focus": _TRANSACTION}},
        {"action": "present_destination", "destination": "home", "params": {"select": _TRANSACTION}},
        {"action": "present_destination", "destination": "ledger", "params": {"select": "A" * 64}},
        {"action": "present_destination", "destination": "ledger", "params": {"select": 42}},
        {"action": "present_destination", "destination": "ledger", "params": "select"},
    ],
)
@pytest.mark.asyncio
async def test_a_view_no_tui_implements_or_a_parameter_the_element_refuses_is_refused(
    tmp_path: Path, request_fields: dict[str, object]
) -> None:
    exit_code, replies = await _converse(tmp_path, "", [request_fields])
    assert exit_code == 1
    assert replies == [
        {"kind": "session_refused", "code": "invalid", "request_id": "eeeeeeee-eeee-4eee-8eee-000000000000"}
    ]


@pytest.mark.asyncio
async def test_a_selected_record_is_passed_with_its_view(tmp_path: Path) -> None:
    exit_code, replies, stderr = await _converse_logged(
        tmp_path,
        "",
        [
            {"action": "present_destination", "destination": "ledger", "params": {"select": _TRANSACTION}},
            {"action": "close"},
        ],
    )
    assert exit_code == 0, replies
    assert replies[0]["kind"] == "destination_presented"
    assert replies[0]["destination"] == "ledger"
    assert f"presented ledger [('select', '{_TRANSACTION}')]" in stderr


@pytest.mark.asyncio
async def test_an_uncertain_os_observation_refuses_only_that_page_and_keeps_the_hold(tmp_path: Path) -> None:
    exit_code, replies = await _converse(
        tmp_path,
        "os_session_unavailable",
        [
            {"action": "present_destination", "destination": "ledger"},
            {"action": "present_destination", "destination": "ledger"},
            {"action": "close"},
        ],
    )
    assert exit_code == 0, replies
    assert replies[0] == {
        "kind": "session_refused",
        "code": "unavailable",
        "request_id": "eeeeeeee-eeee-4eee-8eee-000000000000",
    }
    assert replies[1]["kind"] == "destination_presented"
    assert replies[2]["kind"] == "session_closed"


@pytest.mark.asyncio
async def test_a_page_asked_on_an_ended_session_ends_the_hold(tmp_path: Path) -> None:
    exit_code, replies = await _converse(
        tmp_path, "session_expired", [{"action": "present_destination", "destination": "home"}]
    )
    assert exit_code == 1
    assert replies == [
        {"kind": "session_refused", "request_id": "eeeeeeee-eeee-4eee-8eee-000000000000", "code": "inactive"}
    ]
