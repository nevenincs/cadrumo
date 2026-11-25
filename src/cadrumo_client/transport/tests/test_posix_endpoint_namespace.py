"""The POSIX transport names its socket through the directory it holds, whatever the root's length."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from cadrumo.core.connection_transport import SOCKET_PATH_LIMIT
from cadrumo_client.contracts.contracts import EndpointPresence, RefusalCode, RefusalError

from ..posix_endpoint import PosixEndpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _overlong_namespace(root: Path) -> Path:
    namespace = root / ("n" * 110)
    assert len(os.fsencode(namespace / ("0" * 32 + ".sock"))) > SOCKET_PATH_LIMIT
    return namespace


@pytest.mark.skipif(sys.platform != "linux", reason="Linux names the socket through procfs")
def test_an_endpoint_under_an_overlong_root_listens_and_is_reached_on_linux(tmp_path: Path) -> None:
    namespace = _overlong_namespace(tmp_path)
    owner = PosixEndpoint(storage_root=tmp_path, namespace=namespace)
    client = PosixEndpoint(storage_root=tmp_path, namespace=namespace, create_namespace=False)
    try:
        owner.listen()
        sockets = list(namespace.glob("*.sock"))
        assert len(sockets) == 1
        held = sockets[0].lstat()
        assert stat.S_ISSOCK(held.st_mode)
        assert stat.S_IMODE(held.st_mode) == 0o600
        assert client.presence() is EndpointPresence.HELD
        channel = client.connect(timeout=2.0)
        channel.close()
    finally:
        client.close()
        owner.close()


@pytest.mark.skipif(sys.platform in ("win32", "linux"), reason="requires a POSIX endpoint without procfs addressing")
def test_controlled_namespace_still_refuses_an_overlong_socket_path_without_procfs(tmp_path: Path) -> None:
    namespace = _overlong_namespace(tmp_path)
    with pytest.raises(RefusalError) as error:
        PosixEndpoint(storage_root=tmp_path, namespace=namespace)
    assert error.value.reason == RefusalCode.UNAVAILABLE
    assert not list(namespace.glob("*.sock"))
