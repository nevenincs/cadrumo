"""The lane refuses a staged package or test host older than a source it is built from."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from .. import lane
from ..freshness import built_from, newer_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUILT = 1_800_000_000_000_000_000
_SECOND = 1_000_000_000


def _write(path: Path, *, at: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    os.utime(path, ns=(at, at))
    return path


@pytest.mark.parametrize(
    ("relative", "built"),
    [
        ("native/desktop/src-tauri/src/manager.rs", True),
        ("native/desktop/frontend/src/App.tsx", True),
        ("Y:/code/agent/src/cadrumo_agent/service.py", True),
        ("native/desktop/src-tauri/src/manager/tests.rs", False),
        ("native/desktop/src-tauri/src/shell/setup/track_tests.rs", False),
        ("native/desktop/frontend/tests/live/attach.live.ts", False),
        ("native/desktop/frontend/src/components/Rail.stories.tsx", False),
        ("native/desktop/frontend/src/shell/agentCatalog.test.ts", False),
        ("src/cadrumo/core/tests/test_hashing.py", False),
    ],
)
def test_only_files_built_into_the_product_count_as_its_sources(relative: str, built: bool) -> None:
    assert built_from(relative) is built


def test_the_newest_source_changed_after_the_artifact_is_named(tmp_path: Path) -> None:
    artifact = _write(tmp_path / "ready", at=_BUILT)
    older = _write(tmp_path / "a.py", at=_BUILT - _SECOND)
    newer = _write(tmp_path / "b.py", at=_BUILT + _SECOND)
    newest = _write(tmp_path / "c.py", at=_BUILT + 2 * _SECOND)
    assert newer_source(artifact, [older]) is None
    stale = newer_source(artifact, [older, newer, newest, tmp_path / "removed.py"])
    assert stale is not None
    assert stale.source == newest


def _layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    package_source: int,
    host_source: int,
    staged: int = _BUILT,
) -> lane.TestHost:
    build, repository = tmp_path / "build", tmp_path / "checkout"
    monkeypatch.setattr(lane, "_BUILD", build)
    monkeypatch.setattr(lane, "_STAGE", build / "stage")
    monkeypatch.setattr(lane, "_REPOSITORY", repository)
    _write(build / "stage" / "Debug" / "ready", at=staged)
    product = _write(repository / "src" / "cadrumo" / "module.py", at=package_source)
    _write(build / "stage" / "Debug" / "app" / "cadrumo.exe", at=_BUILT)
    (build / "inputs-product.txt").write_text(f"{product.as_posix()}\n", encoding="utf-8")
    _write(repository / "native" / "desktop" / "src-tauri" / "src" / "main.rs", at=host_source)
    _write(repository / "native" / "desktop" / "src-tauri" / "src" / "tests.rs", at=_BUILT + 50 * _SECOND)
    record = _write(build / "desktop" / "testing" / "packaged" / "host.json", at=_BUILT)
    return lane.TestHost(record.parent / "cadrumo.exe", "http://tauri.localhost/index.html", "Debug", record)


def test_current_builds_pass_even_when_only_a_test_changed_since(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host = _layout(tmp_path, monkeypatch, package_source=_BUILT - 10 * _SECOND, host_source=_BUILT - 10 * _SECOND)
    lane.require_current(host)


def test_a_package_older_than_a_declared_input_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = _layout(tmp_path, monkeypatch, package_source=_BUILT + 10 * _SECOND, host_source=_BUILT - 10 * _SECOND)
    with pytest.raises(lane.UnavailableError, match=r"module\.py.*just build-native Debug bundle"):
        lane.require_current(host)


def test_a_package_older_than_the_desktop_crate_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = _layout(tmp_path, monkeypatch, package_source=_BUILT - 10 * _SECOND, host_source=_BUILT + 10 * _SECOND)
    with pytest.raises(lane.UnavailableError, match=r"ready is older than .*main\.rs.*just build-native Debug bundle"):
        lane.require_current(host)


def test_a_test_host_older_than_its_crate_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = _layout(
        tmp_path,
        monkeypatch,
        package_source=_BUILT - 10 * _SECOND,
        host_source=_BUILT + 10 * _SECOND,
        staged=_BUILT + 20 * _SECOND,
    )
    with pytest.raises(lane.UnavailableError, match=r"host\.json is older than .*main\.rs.*desktop-packaged-host"):
        lane.require_current(host)


def test_a_package_staged_without_completing_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = _layout(tmp_path, monkeypatch, package_source=_BUILT - 10 * _SECOND, host_source=_BUILT - 10 * _SECOND)
    (tmp_path / "build" / "stage" / "Debug" / "ready").unlink()
    with pytest.raises(lane.UnavailableError, match="not staged to completion"):
        lane.require_current(host)
