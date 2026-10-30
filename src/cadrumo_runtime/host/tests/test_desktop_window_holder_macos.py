"""A desktop window connected over a real local socket is judged on the kernel's own evidence.

The accepting side names no program for a socket peer, so admission reads the
program from the peer's audit token and the start arguments from the kernel.
Real processes connect over a real socket: one the runtime did not start is the
window, one it started is not, and the arguments it reports are the ones its
program was started with.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo_client.contracts.access_vocabulary import AccessScope
from cadrumo_client.contracts.service_access import InstalledParentImage, InstalledServiceDescriptor
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.posix_channel import PosixChannel
from cadrumo_runtime.adapters.service_verification import (
    channel_peer_image,
    native_process_arguments,
    native_process_identity,
)
from cadrumo_runtime.host.desktop_holder_identity import desktop_window_peer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.skipif(sys.platform != "darwin", reason="reads a local socket peer's audit token"),
]


@dataclass
class _Verifier:
    """Admits the desktop image by its path alone; the digest check is the installed verifier's."""

    desktop_image: str

    def installed_parent_image_matches(self, image_path: str, descriptor_path: str, image_digest: str) -> bool:
        del image_digest
        return Path(image_path).resolve() == Path(descriptor_path).resolve() == Path(self.desktop_image).resolve()


def _descriptor(image: str) -> InstalledServiceDescriptor:
    return InstalledServiceDescriptor(
        service_id="desktop-session",
        launch_image=sys.executable,
        launch_module="cadrumo_runtime.host.bootstrap",
        image_digest="1" * 64,
        descriptor_digest="2" * 64,
        record_capabilities=(),
        operation_scope=AccessScope(
            operations=frozenset(),
            actions=frozenset(),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        allowed_parent_images=(InstalledParentImage(launch_image=image, image_digest="3" * 64),),
    )


def _start_peer(how: str, path: str) -> subprocess.Popen[bytes]:
    """Start a peer that connects to ``path`` and holds the connection until the runtime side closes it."""
    environment = {**os.environ, "WINDOW_TEST_SOCKET": path}
    if how == "detached":
        # The peer starts in its own session from a parent that then exits, so it does not descend from here.
        return subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import subprocess, sys\n"
                "subprocess.Popen([sys.executable, '-c', 'import os, socket\\n"
                "s = socket.socket(socket.AF_UNIX)\\n"
                "s.connect(os.environ[\\'WINDOW_TEST_SOCKET\\'])\\n"
                "s.recv(1)\\n'], start_new_session=True, stdin=subprocess.DEVNULL)\n",
            ],
            env=environment,
        )
    if how == "role":
        return subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import os, socket\n"
                "s = socket.socket(socket.AF_UNIX)\n"
                "s.connect(os.environ['WINDOW_TEST_SOCKET'])\n"
                "s.recv(1)\n",
                "--role",
                "runtime",
            ],
            env=environment,
        )
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import os, socket\n"
            "s = socket.socket(socket.AF_UNIX)\n"
            "s.connect(os.environ['WINDOW_TEST_SOCKET'])\n"
            "s.recv(1)\n",
        ],
        env=environment,
    )


@contextmanager
def _accepted(how: str) -> Generator[PosixChannel]:
    """Yield the runtime side of a real socket whose peer is a fresh process."""
    assert sys.platform != "win32"
    with tempfile.TemporaryDirectory(dir="/tmp") as base:
        path = str(Path(base) / "r.sock")
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(path)
        listener.listen(1)
        listener.settimeout(20)
        child = _start_peer(how, path)
        try:
            connection, _ = listener.accept()
            channel = PosixChannel(connection)
            try:
                yield channel
            finally:
                channel.close()
        finally:
            listener.close()
            child.wait(timeout=20)


def _image() -> str:
    assert sys.platform != "win32"
    return native_process_identity(os.getpid(), str(os.getuid())).image


def test_the_socket_names_no_program_so_the_audit_token_names_the_peer_incarnation() -> None:
    with _accepted("child") as channel:
        assert channel.peer.image_path is None and channel.peer.process_id is not None
        image = channel_peer_image(channel)
        assert image is not None
        observed = native_process_identity(channel.peer.process_id, channel.peer.os_owner_id)
        assert Path(image).resolve() == Path(observed.image).resolve()


def test_a_desktop_image_the_runtime_did_not_start_is_the_window() -> None:
    with _accepted("detached") as channel:
        context = ConnectionContext(uuid4(), uuid4(), channel.peer)
        assert desktop_window_peer(_Verifier(_image()), context, channel, _descriptor(_image()))
        assert not desktop_window_peer(_Verifier(_image()), context, channel, _descriptor("/elsewhere/other"))


def test_a_process_this_runtime_started_is_never_the_window() -> None:
    with _accepted("child") as channel:
        context = ConnectionContext(uuid4(), uuid4(), channel.peer)
        assert not desktop_window_peer(_Verifier(_image()), context, channel, _descriptor(_image()))


def test_the_kernel_reports_the_arguments_the_peer_was_started_with() -> None:
    with _accepted("role") as channel:
        assert channel.peer.process_id is not None
        started = native_process_arguments(channel.peer.process_id, channel.peer.os_owner_id)
        assert started[0] == "-c" and started[-2:] == ("--role", "runtime")
