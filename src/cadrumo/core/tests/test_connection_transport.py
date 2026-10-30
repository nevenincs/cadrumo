"""Darwin transport selection without ambient root authority or Settings I/O."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from ...tests.env_scope import isolated_aeat_env
from .. import connection_transport, darwin_transport
from ..config import Settings, settings_override
from ..storage_materialization import ensure_storage_tree
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import storage_location, storage_path, storage_tree_targets

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_native_default_selection_ignores_root_pin(monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
    monkeypatch.setattr(connection_transport.sys, "platform", platform)
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", "/synthetic-or-inherited-root")
    assert connection_transport.uses_darwin_transport() is (platform == "darwin")


def test_settings_are_pure_and_accessor_owns_external_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bool] = []
    external = tmp_path / "native-cache" / "cadrumo"
    in_root = tmp_path / "data" / storage_location(StorageCategory.CONNECTION_SOCKETS).relative_path()

    def resolve(*, create: bool = False) -> Path:
        calls.append(create)
        return external

    monkeypatch.setattr(connection_transport, "uses_darwin_transport", lambda: True)
    monkeypatch.setattr(darwin_transport, "darwin_socket_directory", resolve)
    with isolated_aeat_env(CADRUMO_STORAGE_ROOT=str(tmp_path / "data")):
        settings = Settings()
        assert not calls
        assert storage_path(StorageCategory.CONNECTION_SOCKETS, settings=settings) == external
        assert calls == [False]
        assert external not in storage_tree_targets(settings)
        assert in_root not in storage_tree_targets(settings)
        calls.clear()
        ensure_storage_tree(settings)
        assert not calls
        assert not external.exists()
        assert not in_root.exists()


def test_off_darwin_the_namespace_is_the_member_beneath_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    namespace = tmp_path / "runtime"
    monkeypatch.setattr(connection_transport, "uses_darwin_transport", lambda: False)
    with isolated_aeat_env(CADRUMO_STORAGE_ROOT=str(tmp_path)):
        settings = Settings()
        token = settings_override.set(settings)
        try:
            assert storage_path(StorageCategory.CONNECTION_SOCKETS) == namespace
            assert connection_transport.socket_directory(tmp_path) == (namespace, False)
        finally:
            settings_override.reset(token)


@pytest.mark.skipif(sys.platform == "win32", reason="native no-follow directory descriptors are POSIX")
def test_native_namespace_refuses_permissions_replacement_and_recreation(tmp_path: Path) -> None:
    base = tmp_path.resolve() / "cache"
    base.mkdir(mode=0o700)
    namespace = darwin_transport._Namespace(base)
    try:
        path = namespace.verify(create=False)
        assert not path.exists()
        assert namespace.verify(create=True) == path
        assert path.stat().st_mode & 0o777 == 0o700
        lock = path / "held.sock.lock"
        lock.touch(mode=0o600)
        assert namespace.verify(create=True) == path
        assert lock.exists()
        moved = base / "old"
        path.rename(moved)
        path.mkdir(mode=0o700)
        with pytest.raises(PermissionError, match="replaced"):
            namespace.verify(create=True)
        path.rmdir()
        with pytest.raises(FileNotFoundError):
            namespace.verify(create=True)
        assert not path.exists()
    finally:
        os.close(namespace.base_fd)
        if namespace.directory_fd is not None:
            os.close(namespace.directory_fd)


@pytest.mark.skipif(sys.platform == "win32", reason="native no-follow directory descriptors are POSIX")
def test_native_namespace_refuses_insecure_base_and_symlink(tmp_path: Path) -> None:
    base = tmp_path.resolve() / "cache"
    base.mkdir(mode=0o755)
    with pytest.raises(PermissionError):
        darwin_transport._Namespace(base)
    base.chmod(0o700)
    namespace = darwin_transport._Namespace(base)
    try:
        target = base / "elsewhere"
        target.mkdir(mode=0o700)
        namespace.path.symlink_to(target, target_is_directory=True)
        with pytest.raises(OSError):
            namespace.verify(create=True)
        assert namespace.path.is_symlink()
    finally:
        os.close(namespace.base_fd)


@pytest.mark.skipif(sys.platform == "win32", reason="native no-follow directory descriptors are POSIX")
def test_native_query_is_once_canonical_and_base_replacement_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path.resolve() / "cache"
    base.mkdir(mode=0o700)
    alias = tmp_path.resolve() / "alias"
    alias.symlink_to(base, target_is_directory=True)
    queries: list[int] = []

    def query(name: int) -> str:
        queries.append(name)
        return str(alias)

    monkeypatch.setattr(darwin_transport.os, "confstr", query)
    darwin_transport._namespace.cache_clear()
    namespace = darwin_transport._namespace()
    try:
        path = darwin_transport.darwin_socket_directory(create=True)
        assert path == base / "cadrumo"
        assert darwin_transport.darwin_socket_directory() == path
        assert len(queries) == 1
        base.rename(tmp_path / "removed-cache")
        base.mkdir(mode=0o700)
        with pytest.raises(PermissionError, match="base was replaced"):
            darwin_transport.darwin_socket_directory(create=True)
        assert not (base / "cadrumo").exists()
    finally:
        darwin_transport._namespace.cache_clear()
        os.close(namespace.base_fd)
        if namespace.directory_fd is not None:
            os.close(namespace.directory_fd)
