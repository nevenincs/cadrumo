"""Darwin external namespace custody survives the POSIX endpoint integration boundary."""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.runtime.contracts import RuntimeRefusalError
from ....core import darwin_transport
from .. import posix_endpoint
from .process_support import runtime_namespace_base

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.skipif(sys.platform == "win32", reason="requires native POSIX directory custody"),
]


@pytest.fixture
def external_namespace(monkeypatch: pytest.MonkeyPatch) -> Iterator[darwin_transport._Namespace]:
    with tempfile.TemporaryDirectory(prefix="d-", dir=runtime_namespace_base()) as scratch:
        namespace = darwin_transport._Namespace(Path(scratch).resolve())
        monkeypatch.setattr(darwin_transport, "_namespace", lambda: namespace)
        try:
            yield namespace
        finally:
            os.close(namespace.base_fd)
            if namespace.directory_fd is not None:
                os.close(namespace.directory_fd)


def test_endpoint_never_recreates_external_namespace_after_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, external_namespace: darwin_transport._Namespace
) -> None:
    def resolve(root: Path, *, create: bool = False) -> tuple[Path, bool]:
        path = external_namespace.verify(create=create)
        path.rmdir()
        return path, True

    monkeypatch.setattr(posix_endpoint, "runtime_socket_directory", resolve)
    with pytest.raises(RuntimeRefusalError):
        posix_endpoint.PosixRuntimeEndpoint(storage_root=tmp_path)
    assert not external_namespace.path.exists()


def test_endpoint_uses_external_namespace_and_retains_lock_on_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, external_namespace: darwin_transport._Namespace
) -> None:
    monkeypatch.setattr(
        posix_endpoint,
        "runtime_socket_directory",
        lambda root, *, create=False: (external_namespace.verify(create=create), True),
    )
    endpoint = posix_endpoint.PosixRuntimeEndpoint(storage_root=tmp_path)
    try:
        endpoint.listen()
        assert endpoint._path.parent == external_namespace.path
        assert endpoint._path.exists()
    finally:
        endpoint.close()
    assert not endpoint._path.exists()
    assert (external_namespace.path / (endpoint._name.removesuffix(".sock") + ".lock")).is_file()
