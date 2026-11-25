"""The desktop window's own process is admitted as the desktop holder on the package's evidence.

The window connects to the runtime from its own process. The runtime admits it
as the desktop holder when the peer runs one of the images the package names as
a desktop, by exact bytes, was not started as a role of that image and does not
descend from the runtime. These tests drive the check with this process as the
peer and the image verifier controlled, so no package is needed.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

import pytest

from cadrumo_client.contracts.access_vocabulary import AccessScope
from cadrumo_client.contracts.contracts import ByteChannel, Peer
from cadrumo_client.contracts.service_access import InstalledParentImage, InstalledServiceDescriptor
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_runtime.adapters import service_verification
from cadrumo_runtime.adapters.service_verification import native_process_identity
from cadrumo_runtime.host import desktop_holder_identity
from cadrumo_runtime.host.desktop_holder_identity import desktop_window_peer

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _owner() -> str:
    from cadrumo_client.transport.windows_native_io import current_windows_owner_sid

    return current_windows_owner_sid() if sys.platform == "win32" else str(os.getuid())


@dataclass
class _Verifier:
    """Admits the desktop image by its path alone; the digest check is the installed verifier's."""

    desktop_image: str
    asked: list[tuple[str, str, str]]

    def installed_parent_image_matches(self, image_path: str, descriptor_path: str, image_digest: str) -> bool:
        self.asked.append((image_path, descriptor_path, image_digest))
        return image_path == descriptor_path == self.desktop_image


@dataclass
class _Channel:
    peer: Peer


def _descriptor(*parents: str) -> InstalledServiceDescriptor:
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
        allowed_parent_images=tuple(
            InstalledParentImage(launch_image=parent, image_digest="3" * 64) for parent in parents
        ),
    )


def _peer() -> tuple[ConnectionContext, _Channel]:
    identity = native_process_identity(os.getpid(), _owner())
    peer = Peer(os_owner_id=_owner(), process_id=os.getpid(), image_path=identity.image)
    return ConnectionContext(uuid4(), uuid4(), peer), _Channel(peer)


def _window_peer(context: ConnectionContext, channel: _Channel, descriptor: InstalledServiceDescriptor) -> bool:
    verifier = _Verifier(native_process_identity(os.getpid(), _owner()).image, [])
    return desktop_window_peer(verifier, context, cast(ByteChannel, channel), descriptor)


@pytest.fixture
def not_this_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """The peer is this process, which in the product is never the runtime itself."""
    monkeypatch.setattr(desktop_holder_identity, "descends_from_this_runtime", lambda _identity, _owner: False)


@pytest.mark.usefixtures("not_this_runtime")
def test_the_desktop_image_connected_from_its_window_is_the_holder() -> None:
    context, channel = _peer()
    image = native_process_identity(os.getpid(), _owner()).image
    assert _window_peer(context, channel, _descriptor(image))
    assert _window_peer(context, channel, _descriptor("C:/elsewhere/other.exe", image))


@pytest.mark.usefixtures("not_this_runtime")
def test_an_image_the_package_does_not_name_as_a_desktop_is_not_the_window() -> None:
    context, channel = _peer()
    assert not _window_peer(context, channel, _descriptor("C:/elsewhere/other.exe"))
    assert not _window_peer(context, channel, _descriptor())


@pytest.mark.usefixtures("not_this_runtime")
def test_a_role_of_the_desktop_image_is_a_runtime_child_not_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    context, channel = _peer()
    image = native_process_identity(os.getpid(), _owner()).image
    monkeypatch.setattr(
        service_verification, "native_process_arguments", lambda _pid, _owner: ("--role", "runtime", "session", "hold")
    )
    assert not _window_peer(context, channel, _descriptor(image))
    monkeypatch.setattr(service_verification, "native_process_arguments", lambda _pid, _owner: ("--format", "json"))
    assert _window_peer(context, channel, _descriptor(image))


def test_a_process_this_runtime_started_is_never_the_window() -> None:
    # Without the fixture, the peer is this process and so is the "runtime": a descendant.
    context, channel = _peer()
    image = native_process_identity(os.getpid(), _owner()).image
    assert not _window_peer(context, channel, _descriptor(image))


@pytest.mark.usefixtures("not_this_runtime")
def test_a_peer_whose_channel_or_process_differs_is_refused() -> None:
    context, _channel = _peer()
    image = native_process_identity(os.getpid(), _owner()).image
    other = _Channel(Peer(os_owner_id=_owner(), process_id=os.getpid() + 1, image_path=image))
    assert not _window_peer(context, other, _descriptor(image))
    absent = ConnectionContext(uuid4(), uuid4(), Peer(os_owner_id=_owner(), process_id=None))
    assert not _window_peer(absent, _Channel(absent.peer), _descriptor(image))
    unnamed = Peer(os_owner_id=_owner(), process_id=os.getpid(), image_path=None)
    assert not _window_peer(ConnectionContext(uuid4(), uuid4(), unnamed), _Channel(unnamed), _descriptor(image))
