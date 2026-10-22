"""The window signs a person in through its session hold, and hears a refused password as the CLI would.

The desktop starts a hold with the password on its standard input and asks it
to keep the sign-in for the other frontends. The hold must ask the runtime to
store the receipt, say on its held line whether one was stored, and, when the
password is refused, name the runtime's reason, the sign-in reason and any
retry wait on one line before it ends, never the password.
"""

from __future__ import annotations

import asyncio
import json
import os
import struct
import sys
from pathlib import Path

import pytest

from cadrumo.core.type_guards import is_str_keyed_dict

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PASSWORD = b"synthetic-window-password"

_SCRIPT = r"""
import contextlib
import json
import sys
import threading
from types import SimpleNamespace
from uuid import UUID

from cadrumo_client.contracts.sign_in_outcomes import SignInRefusal
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_runtime.host import session_hold

profile_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
mode = sys.argv[1]


class FakeClient:
    def login_password(self, secret, *, persist_receipt):
        sys.stderr.write(json.dumps({"persist_receipt": persist_receipt, "secret": bytes(secret).decode()}) + "\n")
        if mode == "throttled":
            raise FrontendRefusedError(
                "authentication_required", sign_in=SignInRefusal(reason="throttled", remaining_seconds=30)
            )
        if mode == "rejected":
            raise FrontendRefusedError("credential_rejected", sign_in=SignInRefusal(reason="credential_rejected"))
        return SimpleNamespace(
            status=SimpleNamespace(session_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")),
            runtime_boot_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
            connection_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
            human_login=SimpleNamespace(session_persisted=mode == "persisted"),
        )

    def resume_receipt(self):
        sys.stderr.write(json.dumps({"resumed": True}) + "\n")
        return SimpleNamespace(
            status=SimpleNamespace(session_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")),
            runtime_boot_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
            connection_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
            human_login=None,
        )

    def subscribe_session_retirement(self, callback):
        timer = threading.Timer(0.5, callback)
        timer.daemon = True
        timer.start()

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
sys.exit(session_hold.main(["--profile-id", str(profile_id), "--password-stdin", "--persist-receipt"]))
"""


async def _sign_in(
    tmp_path: Path, mode: str, password: bytes = _PASSWORD
) -> tuple[int, list[dict[str, object]], dict[str, object]]:
    source_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(value for value in (str(source_root), existing) if value is not None)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        _SCRIPT,
        mode,
        cwd=tmp_path,
        env=environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert process.stdin is not None
    process.stdin.write(struct.pack("!I", len(password)) + password)
    await process.stdin.drain()
    try:
        # Bounds only a hung child: importing the runtime takes tens of seconds on a loaded machine.
        output, errors = await asyncio.wait_for(process.communicate(), timeout=120)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode is not None
    lines = [_document(line) for line in output.splitlines() if line.strip()]
    return process.returncode, lines, _document(errors.splitlines()[0])


def _document(line: bytes) -> dict[str, object]:
    document: object = json.loads(line)
    assert is_str_keyed_dict(document)
    return document


@pytest.mark.asyncio
@pytest.mark.parametrize(("mode", "persisted"), [("persisted", True), ("unpersisted", False)])
async def test_a_window_sign_in_asks_the_runtime_to_keep_it_and_says_whether_it_did(
    tmp_path: Path, mode: str, persisted: bool
) -> None:
    exit_code, lines, asked = await _sign_in(tmp_path, mode)
    assert asked == {"persist_receipt": True, "secret": _PASSWORD.decode()}
    assert lines[0]["kind"] == "session_held"
    assert lines[0]["session_persisted"] is persisted
    assert exit_code == 0


@pytest.mark.asyncio
async def test_an_empty_password_frame_resumes_the_sign_in_the_window_stored(tmp_path: Path) -> None:
    """The window signed in on its own connection; the prepared hold resumes that sign-in instead."""
    exit_code, lines, asked = await _sign_in(tmp_path, "persisted", password=b"")
    assert asked == {"resumed": True}
    assert lines[0]["kind"] == "session_held"
    assert lines[0]["session_persisted"] is True
    assert exit_code == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (
            "throttled",
            {
                "kind": "sign_in_refused",
                "code": "authentication_required",
                "sign_in_reason": "throttled",
                "seconds": 30,
            },
        ),
        (
            "rejected",
            {
                "kind": "sign_in_refused",
                "code": "credential_rejected",
                "sign_in_reason": "credential_rejected",
                "seconds": None,
            },
        ),
    ],
)
async def test_a_refused_password_is_named_on_one_line_and_ends_the_hold(
    tmp_path: Path, mode: str, expected: dict[str, object]
) -> None:
    exit_code, lines, _ = await _sign_in(tmp_path, mode)
    assert lines == [expected]
    assert _PASSWORD.decode() not in json.dumps(lines)
    assert exit_code == 1
