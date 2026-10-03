"""Real isolated GNOME resource publication without desktop activation."""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Generator
from importlib.resources import files
from pathlib import Path

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.config import override_settings

from .. import linux_gnome_installation
from ..linux_gnome_installation import inspect_gnome_login_producer, install_gnome_login_producer
from ..linux_gnome_lock import GNOME_LOGIN_EXTENSION_UUID
from ..posix import posix_owner_uid

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.skipif(sys.platform != "linux", reason="Real Linux no-follow and no-replace directory primitives"),
]


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    # Every file operation uses the real no-follow/native primitives under the
    # isolated pytest project root; ambient home/XDG values remain irrelevant.
    home = tmp_path
    monkeypatch.setenv("HOME", str(tmp_path / "foreign-home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "foreign-data"))
    with override_settings(cadrumo_local_storage_root=home / "storage"):
        yield home


def _target(home: Path) -> Path:
    return home / "storage/integrations/gnome/extensions" / GNOME_LOGIN_EXTENSION_UUID


def _resources() -> dict[str, bytes]:
    return {
        name: files("cadrumo").joinpath("_data/local_runtime/gnome_login", name).read_bytes()
        for name in ("extension.js", "metadata.json")
    }


def test_inspection_absence_is_read_only_and_installation_is_exact_and_idempotent(isolated_home: Path) -> None:
    assert not inspect_gnome_login_producer()
    assert not (isolated_home / "storage/integrations").exists()
    assert install_gnome_login_producer()
    target = _target(isolated_home)
    assert set(path.name for path in target.iterdir()) == {"extension.js", "metadata.json"}
    assert stat.S_IMODE(target.stat().st_mode) == 0o700
    observations: dict[str, tuple[int, int, int]] = {}
    for name, expected in _resources().items():
        path = target / name
        observed = path.stat()
        assert path.read_bytes() == expected
        assert stat.S_IMODE(observed.st_mode) == 0o600
        assert observed.st_uid == posix_owner_uid() and observed.st_nlink == 1
        observations[name] = (observed.st_dev, observed.st_ino, observed.st_mtime_ns)
    assert inspect_gnome_login_producer()
    assert not install_gnome_login_producer()
    after = {
        name: (path.stat().st_dev, path.stat().st_ino, path.stat().st_mtime_ns)
        for name in _resources()
        if (path := target / name).exists()
    }
    assert after == observations
    assert list(target.parent.iterdir()) == [target]
    assert not (isolated_home / "foreign-home").exists()
    assert not (isolated_home / "foreign-data").exists()


@pytest.mark.parametrize(
    "kind", ["empty", "one-file", "modified", "old-cohort", "extra", "permissions", "hardlink", "symlink"]
)
def test_partial_unsafe_or_conflicting_installation_is_never_replaced(isolated_home: Path, kind: str) -> None:
    target = _target(isolated_home)
    if kind == "empty":
        target.mkdir(mode=0o700, parents=True)
    else:
        assert install_gnome_login_producer()
        if kind == "one-file":
            (target / "metadata.json").unlink()
        elif kind == "modified":
            (target / "extension.js").write_bytes(b"foreign executable code")
        elif kind == "old-cohort":
            (target / "metadata.json").write_bytes(b'{"uuid":"prior-cohort"}')
        elif kind == "extra":
            (target / "foreign.txt").write_bytes(b"unrelated owned data")
        elif kind == "permissions":
            (target / "extension.js").chmod(0o644)
        elif kind == "hardlink":
            os.link(target / "extension.js", isolated_home / "unrelated-link")
        else:
            actual = isolated_home / "foreign-code"
            (target / "extension.js").rename(actual)
            (target / "extension.js").symlink_to(actual)
    before = {path.name: path.read_bytes() for path in target.iterdir()}
    for operation in (inspect_gnome_login_producer, install_gnome_login_producer):
        with pytest.raises(RuntimeRefusalError) as caught:
            operation()
        assert caught.value.reason in {
            RuntimeRefusalCode.UNAVAILABLE,
            RuntimeRefusalCode.VERSION_MISMATCH,
            RuntimeRefusalCode.PEER_UNTRUSTED,
        }
        assert {path.name: path.read_bytes() for path in target.iterdir()} == before
    assert not any(path.name.startswith("." + GNOME_LOGIN_EXTENSION_UUID) for path in target.parent.iterdir())


@pytest.mark.parametrize("component", ["integrations", "gnome", "extensions", GNOME_LOGIN_EXTENSION_UUID])
def test_symlinked_component_refuses_without_touching_foreign_directory(isolated_home: Path, component: str) -> None:
    target = _target(isolated_home)
    parts = ("integrations", "gnome", "extensions", GNOME_LOGIN_EXTENSION_UUID)
    parent = isolated_home / "storage"
    for part in parts:
        if part == component:
            break
        parent /= part
        parent.mkdir(mode=0o700)
    foreign = isolated_home / "unrelated-directory"
    foreign.mkdir(mode=0o700)
    sentinel = foreign / "sentinel"
    sentinel.write_bytes(b"unrelated owned data")
    (parent / component).symlink_to(foreign, target_is_directory=True)
    for operation in (inspect_gnome_login_producer, install_gnome_login_producer):
        with pytest.raises(RuntimeRefusalError):
            operation()
    assert sentinel.read_bytes() == b"unrelated owned data" and list(foreign.iterdir()) == [sentinel]
    if component != GNOME_LOGIN_EXTENSION_UUID:
        assert not target.exists()


def test_writable_configured_storage_root_refuses_without_publishing(isolated_home: Path) -> None:
    storage_root = isolated_home / "storage"
    storage_root.mkdir(mode=0o700)
    storage_root.chmod(0o777)
    try:
        for operation in (inspect_gnome_login_producer, install_gnome_login_producer):
            with pytest.raises(RuntimeRefusalError) as caught:
                operation()
            assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
        assert not (storage_root / "integrations").exists()
    finally:
        storage_root.chmod(0o700)


def test_abandoned_stage_is_preserved_and_never_treated_as_success(isolated_home: Path) -> None:
    parent = _target(isolated_home).parent
    parent.mkdir(mode=0o700, parents=True)
    stage = parent / ("." + GNOME_LOGIN_EXTENSION_UUID + ".stage-abandoned")
    stage.mkdir(mode=0o700)
    partial = stage / "extension.js"
    partial.write_bytes(b"unfinished public producer resource")
    for operation in (inspect_gnome_login_producer, install_gnome_login_producer):
        with pytest.raises(RuntimeRefusalError) as caught:
            operation()
        assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert partial.read_bytes() == b"unfinished public producer resource"
    assert not _target(isolated_home).exists()


def test_real_directory_publication_cannot_clobber_a_concurrent_target(isolated_home: Path) -> None:
    expected = _resources()
    with linux_gnome_installation._extensions_directory(create=True) as parent:
        with (
            pytest.raises(RuntimeRefusalError) as caught,
            linux_gnome_installation._StagedProducer(parent) as staged,
        ):
            for name, payload in expected.items():
                staged.write(name, payload)
            collision = _target(isolated_home)
            collision.mkdir(mode=0o700)
            sentinel = collision / "unrelated.txt"
            sentinel.write_bytes(b"concurrent owned directory")
            staged.publish(expected)
        assert caught.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
    target = _target(isolated_home)
    assert list(target.iterdir()) == [target / "unrelated.txt"]
    assert (target / "unrelated.txt").read_bytes() == b"concurrent owned directory"
    assert list(target.parent.iterdir()) == [target]


def test_preparation_exception_cleans_only_current_owned_stage(isolated_home: Path) -> None:
    class PreparationStoppedError(Exception):
        pass

    with linux_gnome_installation._extensions_directory(create=True) as parent:
        unrelated = _target(isolated_home).parent / "unrelated-extension"
        unrelated.mkdir(mode=0o700)
        with (
            pytest.raises(PreparationStoppedError),
            linux_gnome_installation._StagedProducer(parent) as staged,
        ):
            staged.write("extension.js", _resources()["extension.js"])
            raise PreparationStoppedError
    assert list(_target(isolated_home).parent.iterdir()) == [unrelated]
    assert not _target(isolated_home).exists()
