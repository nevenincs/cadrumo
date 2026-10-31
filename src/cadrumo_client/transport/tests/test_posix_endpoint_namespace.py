"""The POSIX transport refuses a namespace that cannot fit a socket path."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ..posix_endpoint import PosixEndpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.skipif(sys.platform == "win32", reason="requires a native POSIX endpoint")
def test_controlled_namespace_still_refuses_an_overlong_socket_path(tmp_path: Path) -> None:
    namespace = tmp_path / ("n" * 110)
    with pytest.raises(RefusalError) as error:
        PosixEndpoint(storage_root=tmp_path, namespace=namespace)
    assert error.value.reason == RefusalCode.UNAVAILABLE
    assert not list(namespace.glob("*.sock"))
