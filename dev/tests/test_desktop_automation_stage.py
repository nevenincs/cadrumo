"""Automation staging refuses foreign paths, changed hosts and broken package snapshots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from .. import desktop_automation_stage
from ..desktop_agent_live.freshness import STAGED_COMPONENTS
from ..packaging.native import build_directory, build_stamp
from ..packaging.native.layout import desktop_image, load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _json(path: Path, value: object) -> None:
    _write(path, json.dumps(value).encode())


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@pytest.fixture
def staged_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _json(root / "CMakePresets.json", {"configurePresets": [{"name": "macos-arm64"}]})
    _json(root / "native/cmake/distribution/CMakePresets.json", {"configurePresets": []})
    build = root / "build/macos-arm64"
    _json(
        build / "build-paths.json",
        {
            "source": str(root),
            "paths": {"generated": "generated", "stage": "stage", "desktop_testing": "desktop/testing"},
        },
    )
    _write(
        build / "CMakeCache.txt",
        f"CMAKE_HOME_DIRECTORY:INTERNAL={root}\nCMAKE_CACHEFILE_DIR:INTERNAL={build}\n".encode(),
    )
    _json(build / "generated/identity.json", {"target": "macos-arm64"})
    monkeypatch.setattr(build_directory, "REPO_ROOT", root)
    # These tests exercise recorded artifact integrity, independent of source discovery.
    monkeypatch.setattr(build_stamp, "changed_inputs", lambda _build, _component: [])
    package = build / "stage/Debug/app"
    layout = load_layout("macos-arm64")
    desktop = desktop_image(layout)
    assert desktop is not None
    files = {desktop.package_path: b"shipped desktop", "lib/payload.py": b"payload"}
    files[layout["files"]["service_descriptors"]] = b"[]"
    manifest = {"layout": layout, "files": {member: _sha(content) for member, content in files.items()}}
    files[layout["files"]["package_manifest"]] = json.dumps(manifest).encode()
    for member, content in files.items():
        _write(package / member, content)
    host = build / "desktop/testing/packaged/cargo/debug/cadrumo"
    _write(host, b"native automation host")
    _json(
        build / "desktop/testing/packaged/host.json",
        {
            "executable": str(host),
            "configuration": "Debug",
            "features": ["native-automation"],
            "variant": "packaged",
            "shell": None,
            "sha256": _sha(host.read_bytes()),
        },
    )
    for component in STAGED_COMPONENTS:
        record_package = package
        artifacts = {member: _sha(content) for member, content in files.items()}
        if component == "desktop-test-host":
            record_package = host.parent
            artifacts = {host.name: _sha(host.read_bytes())}
        _json(
            build / f"generated/build-identity/{component}.json",
            {
                "schema": 1,
                "component": component,
                "state": "settled",
                "fingerprint": "a" * 64,
                "inputs": f"{component}.inputs.json",
                "build_id": "202611020",
                "staged": {"Debug": {"package": record_package.relative_to(build).as_posix(), "artifacts": artifacts}},
            },
        )
    return build


def _host_record(build: Path, **updates: Any) -> None:
    record = build / "desktop/testing/packaged/host.json"
    value = json.loads(record.read_text())
    value.update(updates)
    _json(record, value)


def test_stages_the_mac_host_without_changing_source_package(staged_build: Path) -> None:
    source = staged_build / "stage/Debug/app"
    before = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    result = desktop_automation_stage.stage_automation_package(staged_build, "Debug")
    expected = staged_build / "desktop/testing/automation/package/Debug/app"
    assert result == {"package": str(expected), "executable": str(expected / "cadrumo")}
    assert (expected / "cadrumo").read_bytes() == b"native automation host"
    assert (expected / "lib/payload.py").read_bytes() == b"payload"
    assert {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"configuration": "Release"}, "not built for Debug"),
        ({"features": []}, "native-automation"),
        ({"executable": "relative/cadrumo"}, "absolute executable"),
        ({"variant": "served"}, "embedded packaged shell"),
        ({"sha256": "0" * 64}, "changed after its build"),
    ],
)
def test_refuses_invalid_host_records_before_creating_mirror(
    staged_build: Path, updates: dict[str, object], reason: str
) -> None:
    _host_record(staged_build, **updates)
    with pytest.raises(ValueError, match=reason):
        desktop_automation_stage.stage_automation_package(staged_build, "Debug")
    assert not (staged_build / "desktop/testing/automation").exists()


def test_refuses_another_builds_host(staged_build: Path) -> None:
    _host_record(staged_build, executable=str(staged_build / "stage/Debug/app/cadrumo"))
    with pytest.raises(ValueError, match="outside its packaged Cargo configuration"):
        desktop_automation_stage.stage_automation_package(staged_build, "Debug")


def test_does_not_repair_broken_staged_package(staged_build: Path) -> None:
    payload = staged_build / "stage/Debug/app/lib/payload.py"
    payload.write_bytes(b"unexpected replacement")
    with pytest.raises(ValueError, match="staged bytes are not the ones"):
        desktop_automation_stage.stage_automation_package(staged_build, "Debug")
    assert payload.read_bytes() == b"unexpected replacement"
    assert not (staged_build / "desktop/testing/automation").exists()


def test_refuses_linked_mirror_destination(staged_build: Path) -> None:
    link = staged_build / "desktop/testing/automation"
    link.symlink_to(staged_build / "stage", target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks or junctions"):
        desktop_automation_stage.stage_automation_package(staged_build, "Debug")


def test_requires_an_absolute_enrolled_build(staged_build: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        desktop_automation_stage.stage_automation_package(Path("build/macos-arm64"), "Debug")
    with pytest.raises(ValueError, match="visible configure preset"):
        desktop_automation_stage.stage_automation_package(staged_build.parent / "arbitrary", "Debug")


def test_main_prints_one_json_result(staged_build: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert desktop_automation_stage.main(["--build", str(staged_build), "--config", "Debug"]) == 0
    output = capsys.readouterr()
    assert len(output.out.splitlines()) == 1
    assert Path(json.loads(output.out)["package"]).parts[-4:] == ("automation", "package", "Debug", "app")
    assert output.err == ""
