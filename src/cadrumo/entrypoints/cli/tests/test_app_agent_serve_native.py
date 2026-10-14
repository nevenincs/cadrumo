"""``aeat app agent serve`` speaks the launcher protocol against a real runtime, profile and contained agent.

The command runs as its own process, as the desktop host runs it, and resumes
the person's stored sign-in from the keyring the test seeds for it. The runtime
is the real in-process runtime over a real encrypted profile; the agent is the
stand-in source tree the runtime launches inside its containment.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Coroutine, Iterator
from pathlib import Path
from threading import Thread

import keyring
import pytest

from cadrumo.core.storage_environment import STORAGE_ROOT
from cadrumo.entrypoints.runtime.tests.agent_host_support import (
    DEVELOPMENT_KEY_VARIABLE,
    FAKE_BEARER,
    FAKE_KEY,
    FRAMED_CREDENTIAL_ID,
    mark_lane_root,
    received,
    stand_in_agent_source,
    tree_reaped,
)
from cadrumo.entrypoints.runtime.tests.seeded_keyring import SEED_VARIABLE, SEEDED_KEYRING, write_seed
from cadrumo.entrypoints.runtime.tests.stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime
from cadrumo.tests.in_memory_keyring import InMemoryKeyring

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="the agent tree is contained by a native Windows job"),
]

_LINE_SECONDS = 150


class _Serve:
    """One ``aeat app agent serve`` process, driven from a private event loop thread."""

    def __init__(self, argv: list[str], environment: dict[str, str]) -> None:
        self._loop = asyncio.new_event_loop()
        Thread(target=self._loop.run_forever, name="agent-serve-test-loop", daemon=True).start()
        self.process: asyncio.subprocess.Process = self._call(
            asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=environment,
            ),
            within=30,
        )

    def _call[T](self, coroutine: Coroutine[object, object, T], *, within: float) -> T:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(timeout=within)

    def event(self, *, within: float = _LINE_SECONDS) -> dict[str, object]:
        output = self.process.stdout
        assert output is not None
        line = self._call(output.readline(), within=within)
        assert line, "aeat app agent serve closed its output"
        document: object = json.loads(line)
        assert isinstance(document, dict)
        return {str(key): value for key, value in document.items()}

    def send(self, data: bytes) -> None:
        stream = self.process.stdin
        assert stream is not None

        async def write() -> None:
            stream.write(data)
            await stream.drain()

        self._call(write(), within=10)

    def close_input(self) -> None:
        stream = self.process.stdin
        assert stream is not None

        async def close() -> None:
            stream.close()

        self._call(close(), within=10)

    def wait(self, *, within: float = 60) -> int:
        return self._call(self.process.wait(), within=within)

    def kill(self) -> None:
        async def kill() -> None:
            self.process.kill()

        self._call(kill(), within=10)


@pytest.fixture
def development_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Supply the development fallback key to every thread the runtime serves on.

    Development storage mode falls back, for an unset profile record, to the
    process environment value constructed from the lane id the agent reports.
    """
    monkeypatch.setenv(DEVELOPMENT_KEY_VARIABLE, FAKE_KEY)
    try:
        yield
    finally:
        monkeypatch.delenv(DEVELOPMENT_KEY_VARIABLE)


def _serve(runtime: StoredSignInRuntime, tmp_path: Path, source: Path | None) -> _Serve:
    store = keyring.get_keyring()
    assert isinstance(store, InMemoryKeyring)
    seed = write_seed(tmp_path / "keyring-seed.json", dict(store._entries))
    # The command keeps this checkout's configuration (its published authority included) but no provider key.
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("CADRUMO_LLM_", "PYTHON_KEYRING")) and "API_KEY" not in name
    }
    environment.update(
        {
            STORAGE_ROOT.variable: str(runtime.root),
            "CADRUMO_ACTIVE_PROFILE": str(runtime.profile_id),
            "PYTHON_KEYRING_BACKEND": SEEDED_KEYRING,
            SEED_VARIABLE: str(seed),
        }
    )
    argv = [str(Path(sys.executable).parent / "aeat.exe"), "app", "agent", "serve"]
    if source is not None:
        argv += ["--agent-source", str(source)]
    return _Serve(argv, environment)


@pytest.mark.usefixtures("development_key")
def test_serve_reports_ready_and_closing_its_input_stops_and_reaps_the_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        serve = _serve(runtime, tmp_path, source)
        serve.send(json.dumps({"bearer": FAKE_BEARER}).encode() + b"\n")
        ready = serve.event()
        assert ready["event"] == "agent_ready", ready
        assert ready["gateway_port"] == 47001 and ready["lane"] == "development"
        workspace = ready["workspace_root"]
        assert isinstance(workspace, str) and Path(workspace).is_dir()
        assert FAKE_KEY not in json.dumps(ready) and FAKE_BEARER not in json.dumps(ready)
        assert received(record)["providers"] == [FRAMED_CREDENTIAL_ID]
        serve.close_input()
        assert serve.event() == {"event": "agent_stopped", "reason": "input_closed"}
        assert serve.wait() == 0
        assert tree_reaped(record)


@pytest.mark.usefixtures("development_key")
def test_the_serving_process_dying_stops_and_reaps_the_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        serve = _serve(runtime, tmp_path, source)
        serve.send(json.dumps({"bearer": FAKE_BEARER}).encode() + b"\n")
        assert serve.event()["event"] == "agent_ready"
        serve.kill()
        serve.wait()
        assert tree_reaped(record)


@pytest.mark.usefixtures("development_key")
def test_the_persons_sign_out_ends_serving_with_session_ended(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.application.operations.registry import OperationFrontendProjection
    from cadrumo.application.runtime.profile_access import RuntimeProfileStatus

    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        serve = _serve(runtime, tmp_path, source)
        serve.send(json.dumps({"bearer": FAKE_BEARER}).encode() + b"\n")
        assert serve.event()["event"] == "agent_ready"
        person = runtime.connect()
        status = runtime.resume(person, OperationFrontendProjection.CLI)
        assert isinstance(status, RuntimeProfileStatus) and status.status.session_id is not None
        runtime.session(person, status.status.session_id, "human_sign_out")
        assert serve.event() == {"event": "agent_stopped", "reason": "session_ended"}
        assert tree_reaped(record)


def test_a_bearer_line_with_a_duplicate_key_is_refused_before_any_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        serve = _serve(runtime, tmp_path, source)
        serve.send(b'{"bearer": "one-NOT-A-REAL-TOKEN", "bearer": "two-NOT-A-REAL-TOKEN"}\n')
        assert serve.event() == {"event": "agent_refused", "code": "agent_service_failed"}
        assert serve.wait() == 1
        assert not (record / "received.json").exists()
        assert runtime.profiles.logins == []
