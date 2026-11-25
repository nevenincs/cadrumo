"""Transport tests own their namespace and leave the account's transport directory untouched."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

from cadrumo.core.darwin_transport import darwin_socket_directory
from cadrumo.tests.process_support import runtime_namespace_base
from cadrumo_client.transport.posix_endpoint import PosixEndpoint

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.skipif(sys.platform != "darwin", reason="the account transport directory is Darwin's"),
]


def _entries(directory: Path) -> set[str]:
    return {entry.name for entry in directory.iterdir()} if directory.is_dir() else set()


def test_fixture_namespace_base_lies_outside_the_account_transport_directory() -> None:
    account = darwin_socket_directory().resolve()
    assert not runtime_namespace_base().resolve().is_relative_to(account)


def test_a_listening_endpoint_in_a_fixture_namespace_writes_nothing_to_the_account_directory(tmp_path: Path) -> None:
    account = darwin_socket_directory()
    before = _entries(account)
    with tempfile.TemporaryDirectory(prefix="s-", dir=runtime_namespace_base()) as folder:
        namespace = Path(folder) / "ipc"
        endpoint = PosixEndpoint(storage_root=tmp_path, namespace=namespace)
        try:
            endpoint.listen()
            assert endpoint._path.parent == namespace
            assert endpoint._path.exists()
        finally:
            endpoint.close()
        assert (namespace / (endpoint._name.removesuffix(".sock") + ".lock")).is_file()
    assert _entries(account) == before


def test_the_guard_detects_an_entry_written_to_the_directory_it_watches(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    before = _entries(watched)
    (watched / "stray.lock").write_bytes(b"")
    assert _entries(watched) != before
