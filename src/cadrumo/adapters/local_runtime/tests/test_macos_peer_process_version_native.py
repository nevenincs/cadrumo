"""Opt-in native exec race during Unix peer identity capture, with no credentials."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import overload, override

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from ..macos_login import macos_peer_audit_token
from ..macos_process import MacosProcessWatch, read_macos_process
from . import macos_peer_exec_fixture

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.external_tool,
    pytest.mark.serial,
    pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS Unix peers"),
]


class _ExecRaceSocket(socket.socket):
    def __init__(self, descriptor: int) -> None:
        super().__init__(fileno=descriptor)
        self.armed = False
        self.audit_reads = 0

    @overload
    def getsockopt(self, level: int, optname: int) -> int: ...

    @overload
    def getsockopt(self, level: int, optname: int, buflen: int) -> bytes: ...

    @override
    def getsockopt(self, level: int, optname: int, buflen: int | None = None) -> int | bytes:
        value = super().getsockopt(level, optname) if buflen is None else super().getsockopt(level, optname, buflen)
        if self.armed and (level, optname) == (0, 6):
            self.audit_reads += 1
            if self.audit_reads == 2:
                # Return the actual kernel result captured just before exec.
                # The production validator and subsequent native calls run
                # unchanged; only this OS scheduling point is controlled.
                self.sendall(b"exec")
                assert self.recv(8) == b"again"
                self.armed = False
        return value


def test_native_exec_during_peer_capture_refuses_stale_version_and_accepts_fresh_capture(tmp_path: Path) -> None:
    selected = os.environ.get("CADRUMO_TEST_MACOS_PEER_VERSION")
    if selected is None:
        pytest.skip("requires explicit synthetic native peer acceptance selection")
    if selected != "1":
        pytest.fail("native peer acceptance selector must be 1", pytrace=False)
    peer_path = tmp_path / "peer.sock"
    channel: _ExecRaceSocket | None = None
    watch: MacosProcessWatch | None = None
    children: list[subprocess.Popen[bytes]] = []
    owner = str(os.getuid())
    with socket.socket(socket.AF_UNIX) as listener:
        listener.settimeout(5)
        listener.bind(str(peer_path))
        listener.listen(1)
        try:
            child = subprocess.Popen(  # noqa: S603 - fixed isolated Python and the owning synthetic fixture
                [sys.executable, "-I", str(Path(macos_peer_exec_fixture.__file__).resolve()), str(peer_path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                close_fds=True,
                start_new_session=True,
            )
            children.append(child)
            accepted, _address = listener.accept()
            channel = _ExecRaceSocket(accepted.detach())
            channel.settimeout(5)
            assert channel.recv(8) == b"ready"
            original = macos_peer_audit_token(channel, expected_owner=owner)
            assert original.process_id == child.pid
            observation = read_macos_process(child.pid, expected_owner=owner)
            watch = MacosProcessWatch(observation)
            channel.armed = True
            with pytest.raises(RuntimeRefusalError) as caught:
                macos_peer_audit_token(channel, expected_owner=owner)
            assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
            assert read_macos_process(child.pid, expected_owner=owner) == observation and not watch.exited
            fresh = macos_peer_audit_token(channel, expected_owner=owner)
            assert fresh.process_id == original.process_id and fresh.process_version != original.process_version
            assert fresh.effective_user_id == original.effective_user_id
            channel.sendall(b"done")
            assert child.wait(timeout=5) == 0 and watch.wait(timeout=5)
        finally:
            if channel is not None:
                channel.close()
            for held in children:
                if held.poll() is None:
                    held.kill()
                    held.wait(timeout=5)
            if watch is not None:
                watch.close()
            peer_path.unlink(missing_ok=True)
