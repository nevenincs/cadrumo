"""Installed service verification over a real native pipe peer."""

from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import AccessScope
from cadrumo.core.hashing import sha256_hex
from cadrumo_client.contracts.contracts import ByteChannel
from cadrumo_client.contracts.service_access import InstalledServiceDescriptor
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.windows import WindowsEndpoint

from .. import service_verification
from ..service_verification import InstalledNativeServiceVerifier

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows named pipes and process identity"),
]


@contextmanager
def _peer_channel(root: Path) -> Generator[ByteChannel]:
    """Yield the runtime side of a pipe whose kernel peer is this test process."""
    endpoint = WindowsEndpoint(storage_root=root)
    endpoint.listen()
    try:
        client = endpoint.connect()
        server = endpoint.accept(timeout=2)
        try:
            yield server
        finally:
            client.close()
            server.close()
    finally:
        endpoint.close()


def _descriptor(image: Path) -> InstalledServiceDescriptor:
    return InstalledServiceDescriptor(
        service_id="synthetic-service",
        launch_image=str(image),
        launch_module="synthetic.service",
        image_digest=sha256_hex(image.read_bytes()),
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
    )


def test_a_verified_peer_is_rechecked_by_incarnation_and_image_without_hashing_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _peer_channel(tmp_path) as channel:
        assert channel.peer.image_path is not None
        image = Path(channel.peer.image_path).resolve(strict=True)
        context = ConnectionContext(uuid4(), uuid4(), channel.peer)
        verifier = InstalledNativeServiceVerifier()

        peer = verifier.verify_service(context, channel, _descriptor(image))

        assert peer is not None
        assert peer.image_path == str(image)
        stat = image.stat()
        assert peer.image_identity == f"{stat.st_dev}:{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}"

        def no_hash(_payload: bytes) -> str:
            raise AssertionError("a recheck must not hash the image")

        monkeypatch.setattr(service_verification, "sha256_hex", no_hash)
        assert verifier.recheck_service(context, channel, peer)
        assert not verifier.recheck_service(context, channel, replace(peer, process_incarnation="1"))
        assert not verifier.recheck_service(context, channel, replace(peer, image_identity="0:0:0:0"))
        assert not verifier.recheck_service(context, channel, replace(peer, image_path=str(tmp_path / "other.exe")))
        other = ConnectionContext(uuid4(), context.runtime_boot_id, channel.peer)
        assert not verifier.recheck_service(other, channel, peer)


def test_an_image_that_does_not_match_its_digest_is_not_verified(tmp_path: Path) -> None:
    with _peer_channel(tmp_path) as channel:
        assert channel.peer.image_path is not None
        image = Path(channel.peer.image_path).resolve(strict=True)
        context = ConnectionContext(uuid4(), uuid4(), channel.peer)
        descriptor = _descriptor(image).model_copy(update={"image_digest": "0" * 64})

        assert InstalledNativeServiceVerifier().verify_service(context, channel, descriptor) is None
