"""Fixture namespace roots follow pytest's controlled temporary directory."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.tests import process_support
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.posix_endpoint import PosixEndpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_posix_namespace_base_uses_pinned_temp_without_an_extra_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(process_support, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    assert process_support.runtime_namespace_base.__wrapped__() == tmp_path.resolve()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(sys.platform == "win32", reason="requires a native POSIX endpoint")
def test_controlled_namespace_still_refuses_an_overlong_socket_path(tmp_path: Path) -> None:
    namespace = tmp_path / ("n" * 110)
    with pytest.raises(RefusalError) as error:
        PosixEndpoint(storage_root=tmp_path, namespace=namespace)
    assert error.value.reason == RefusalCode.UNAVAILABLE
    assert not list(namespace.glob("*.sock"))
