"""Unchanged installation staging performs no copying and preserves admission guards."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from dev.packaging.command_execution import run_command
from dev.packaging.tests.test_native_installation import payload_fixture

from .. import distribution_prepare, installation
from ..hashing import digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path, Path]:
    controls = tmp_path / "controls"
    controls.mkdir()
    for name in ("LICENSE", "NOTICE"):
        (controls / name).write_bytes((installation.REPO_ROOT / name).read_bytes())
    monkeypatch.setattr(installation, "REPO_ROOT", controls)
    payload, identity = payload_fixture(tmp_path, "windows-x86-64", manager=True)
    build = tmp_path / "build"
    build.mkdir()
    paths = {f"installation_{name}": f"installation/{name}" for name in ("stage", "metadata", "work", "receipts")}
    (build / "build-paths.json").write_text(json.dumps({"paths": paths}), encoding="utf-8")
    distribution_prepare.refresh(payload, identity, build, "cadrumo")
    return payload, identity, build, controls


def _state(build: Path) -> dict[str, tuple[int, int, int, bytes | None]]:
    result = {}
    for name in ("stage", "metadata", "receipts"):
        root = build / "installation" / name
        for path in (root, *sorted(root.rglob("*"))):
            if not path.exists():
                continue
            metadata = path.stat()
            result[path.relative_to(build).as_posix()] = (
                metadata.st_ino,
                metadata.st_mtime_ns,
                stat.S_IMODE(metadata.st_mode),
                path.read_bytes() if path.is_file() else None,
            )
    return result


def _invoke(action: str, payload: Path, identity: Path, build: Path) -> None:
    if action == "prepare":
        assert installation.prepare(payload, identity, build, "cadrumo") == build / "installation/stage"
    else:
        distribution_prepare.refresh(payload, identity, build, "cadrumo")


def _forbid_materialization(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("An unchanged or refused stage must not copy or construct a candidate")

    monkeypatch.setattr(installation, "_prepare_fresh", forbidden)
    monkeypatch.setattr(installation.shutil, "copytree", forbidden)
    monkeypatch.setattr(installation.shutil, "copy2", forbidden)
    monkeypatch.setattr(distribution_prepare, "public_directory", forbidden)


@pytest.mark.parametrize("action", ["prepare", "refresh"])
def test_unchanged_staging_preserves_every_member_without_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    payload, identity, build, _ = _prepared(tmp_path, monkeypatch)
    assert not (build / "installation/metadata/Desktop.wxs").exists()
    assert not (build / "installation/metadata/DesktopPatch.xml").exists()
    before = _state(build)
    _forbid_materialization(monkeypatch)

    _invoke(action, payload, identity, build)
    _invoke(action, payload, identity, build)

    assert _state(build) == before
    assert not list((build / "installation/work").glob("candidate-*"))


@pytest.mark.parametrize("action", ["prepare", "refresh"])
@pytest.mark.parametrize("change", ["payload", "membership", "control", "identity"])
def test_changed_inputs_invalidate_staging_currency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str, change: str
) -> None:
    payload, identity, build, controls = _prepared(tmp_path, monkeypatch)
    before = _state(build)
    manifest_path = payload / "data/package-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if change in {"payload", "membership"}:
        relative = "cadrumo" if change == "payload" else "new-module.py"
        member = payload / relative
        member.write_bytes(b"changed verified payload")
        manifest["files"][relative] = digest(member)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif change == "control":
        (controls / "LICENSE").write_bytes(b"changed owner notice")
    else:
        value = json.loads(identity.read_text(encoding="utf-8"))
        value["name"] = "Currency Fixture"
        identity.write_text(json.dumps(value), encoding="utf-8")

    if action == "prepare":
        with pytest.raises(ValueError, match="differs"):
            _invoke(action, payload, identity, build)
        assert _state(build) == before
    else:
        _invoke(action, payload, identity, build)
        assert _state(build) != before
        refreshed = _state(build)
        _forbid_materialization(monkeypatch)
        _invoke(action, payload, identity, build)
        assert _state(build) == refreshed


@pytest.mark.parametrize("action", ["prepare", "refresh"])
@pytest.mark.parametrize(
    "fault",
    [
        "content",
        "membership",
        "forged-content",
        "forged-membership",
        "forged-manager",
        "forged-notice",
        "forged-marker",
        "obsolete-desktop-source",
        "obsolete-desktop-patch",
        "metadata-membership",
        "receipt-application-id",
        "receipt-staging-generation",
        "permissions",
    ],
)
def test_currency_does_not_admit_changed_or_self_consistently_forged_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str, fault: str
) -> None:
    payload, identity, build, _ = _prepared(tmp_path, monkeypatch)
    stage = build / "installation/stage"
    version = json.loads(identity.read_text(encoding="utf-8"))["version"]
    package = stage / "versions" / version
    executable = package / "cadrumo"
    original_mode = executable.stat().st_mode
    receipt = build / "installation/metadata/installation.json"
    record = json.loads(receipt.read_text(encoding="utf-8"))
    if fault in {"receipt-application-id", "receipt-staging-generation"}:
        if fault == "receipt-application-id":
            record["application_id"] = "org.example.foreign"
        else:
            record["staging_generation"] = 2
        receipt.write_text(json.dumps(record), encoding="utf-8")
    elif fault in {"obsolete-desktop-source", "obsolete-desktop-patch", "metadata-membership"}:
        name = {
            "obsolete-desktop-source": "Desktop.wxs",
            "obsolete-desktop-patch": "DesktopPatch.xml",
            "metadata-membership": "Unexpected.wxs",
        }[fault]
        (receipt.parent / name).write_bytes(b"changed registration metadata")
    elif fault == "permissions":
        executable.chmod(original_mode & ~stat.S_IWUSR)
    elif fault in {"forged-manager", "forged-notice", "forged-marker"}:
        manifest = json.loads((payload / "data/package-manifest.json").read_text(encoding="utf-8"))
        relative = {
            "forged-manager": "cadrumo-manager",
            "forged-notice": "docs/licenses/CADRUMO.txt",
            "forged-marker": manifest["layout"]["installation"]["marker"],
        }[fault]
        changed = stage / relative
        changed.write_bytes(b"forged installer-owned control")
        record["files"][relative] = digest(changed)
        receipt.write_text(json.dumps(record), encoding="utf-8")
    else:
        changed = package / "unexpected.py" if fault in {"membership", "forged-membership"} else executable
        changed.write_bytes(b"stage alteration")
        if fault.startswith("forged-"):
            # Both inventories agree with the altered stage. The current source
            # package must still independently govern stage admission.
            manifest_path = package / "data/package-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][changed.relative_to(package).as_posix()] = digest(changed)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            for path in (changed, manifest_path):
                record["files"][path.relative_to(stage).as_posix()] = digest(path)
            receipt.write_text(json.dumps(record), encoding="utf-8")
    before = _state(build)
    _forbid_materialization(monkeypatch)
    try:
        with pytest.raises(ValueError):
            _invoke(action, payload, identity, build)
        assert _state(build) == before
    finally:
        executable.chmod(original_mode)


@pytest.mark.parametrize("action", ["prepare", "refresh"])
def test_currency_refuses_unverified_source_before_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    payload, identity, build, _ = _prepared(tmp_path, monkeypatch)
    before = _state(build)
    (payload / "cadrumo").write_bytes(b"source bytes no longer match the admitted manifest")
    _forbid_materialization(monkeypatch)

    with pytest.raises(ValueError):
        _invoke(action, payload, identity, build)

    assert _state(build) == before


@pytest.mark.parametrize("action", ["prepare", "refresh"])
def test_currency_refuses_linked_stage_children_before_copying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    payload, identity, build, _ = _prepared(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "unchanged"
    marker.write_bytes(b"outside the stage")
    linked = build / "installation/stage/linked"
    if os.name == "nt":
        result = run_command(
            [
                str(Path(os.environ["SYSTEMROOT"]) / "System32/cmd.exe"),
                "/d",
                "/c",
                "mklink",
                "/J",
                str(linked),
                str(outside),
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
    else:
        linked.symlink_to(outside, target_is_directory=True)
    _forbid_materialization(monkeypatch)
    try:
        with pytest.raises(ValueError, match=r"link|redirect"):
            _invoke(action, payload, identity, build)
        assert marker.read_bytes() == b"outside the stage"
    finally:
        if os.name == "nt":
            linked.rmdir()
        else:
            linked.unlink()
