"""The foreground fixture owns readiness, its explicit session policy and cleanup."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from .. import installed_tui_runtime as runtime
from ..cli_contracts import RetencionesInstalledCliError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(("body_fails", "cleanup_fails"), [(False, False), (True, False), (False, True)])
def test_fixture_verifies_readiness_and_joins_owner_even_when_continuation_fails(
    tmp_path: Path,
    monkeypatch,
    body_fails: bool,
    cleanup_fails: bool,
) -> None:
    scripts = tmp_path / "bin"
    scripts.mkdir()
    cli = scripts / "aeat"
    cli.touch()
    (scripts / "cadrumo-runtime").touch()
    observations = []
    boot = uuid4()

    class Endpoint:
        storage_identity = "a" * 64

        def __init__(self, **kwargs):
            observations.append(("endpoint", kwargs))
            self.attempts = 0

        def connect(self, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_NOT_READY)
            return "verified-native-channel"

        def close(self):
            observations.append(("endpoint_closed",))

    class Process:
        returncode = None

        def terminate(self):
            observations.append(("terminate",))

        def kill(self):
            observations.append(("kill",))

        async def wait(self):
            if cleanup_fails:
                observations.append(("join_failed",))
                raise TimeoutError
            observations.append(("joined",))
            return 0

    async def launch(*argv, **kwargs):
        observations.append(("launch", argv, kwargs))
        return Process()

    def handshake(channel, *, expected, deadline):
        assert channel == "verified-native-channel"
        assert expected.storage_identity == "a" * 64
        observations.append(("handshake",))
        return SimpleNamespace(hello=SimpleNamespace(boot_id=boot), close=lambda: None)

    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    monkeypatch.setattr(runtime, "PosixRuntimeEndpoint", Endpoint)
    monkeypatch.setattr(runtime, "VerifiedRuntimeConnection", handshake)
    monkeypatch.setattr(runtime.asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr(runtime, "version", lambda name: "installed-cohort")
    monkeypatch.setenv("CADRUMO_UNRELATED", "ambient-value")

    def continuation():
        with runtime.installed_foreground_runtime(
            cli_executable=cli,
            storage_root=tmp_path,
            authority_root=tmp_path,
            runtime_socket_dir=tmp_path / "r",
        ) as evidence:
            assert evidence["runtime_boot_id"] == str(boot)
            assert evidence["native_desktop_login_claimed"] is False
            assert observations[-1] == ("handshake",)
            if body_fails:
                raise ValueError("continuation_failure")

    if cleanup_fails:
        with pytest.raises(TimeoutError):
            continuation()
    elif body_fails:
        with pytest.raises(ValueError, match="continuation_failure"):
            continuation()
    else:
        continuation()
    launch_evidence = next(value for value in observations if value[0] == "launch")
    environment = launch_evidence[2]["env"]
    assert "CADRUMO_UNRELATED" not in environment
    assert environment["CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE"] == "1"
    assert environment["CADRUMO_RUNTIME_SOCKET_DIR"] == str(tmp_path / "r")
    assert launch_evidence[2]["stdin"] == asyncio.subprocess.DEVNULL
    assert launch_evidence[2]["start_new_session"] is True
    if cleanup_fails:
        assert observations[-5:] == [
            ("terminate",),
            ("join_failed",),
            ("kill",),
            ("join_failed",),
            ("endpoint_closed",),
        ]
    else:
        assert observations[-3:] == [("terminate",), ("joined",), ("endpoint_closed",)]


def test_unsafe_namespace_is_refused_before_launch_without_permission_repair(tmp_path: Path, monkeypatch) -> None:
    cli = tmp_path / "aeat"
    cli.touch()
    (tmp_path / "cadrumo-runtime").touch()

    def unsafe_endpoint(**kwargs):
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)

    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    monkeypatch.setattr(runtime, "PosixRuntimeEndpoint", unsafe_endpoint)
    with (
        pytest.raises(RetencionesInstalledCliError) as refusal,
        runtime.installed_foreground_runtime(
            cli_executable=cli,
            storage_root=tmp_path,
            authority_root=tmp_path,
            runtime_socket_dir=tmp_path / "r",
        ),
    ):
        pytest.fail("unsafe endpoint reached continuation")
    assert refusal.value.stage == "runtime_endpoint"
    assert refusal.value.diagnostic_code == "runtime_endpoint_untrusted"
