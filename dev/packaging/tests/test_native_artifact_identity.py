"""Reject replaced native archives before discarding prior acceptance evidence."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from dev.packaging.command_execution import CommandResult, run_command
from dev.packaging.native import artifact_verify
from dev.packaging.native.artifact_verify import check
from dev.packaging.native.hashing import digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_replaced_archive_preserves_previous_acceptance(tmp_path: Path) -> None:
    """A same-name replacement must not inherit the original package's identity."""
    archive = tmp_path / "product.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("app/content.txt", "original")
    locator = {"archive": str(archive), "archive_sha256": digest(archive)}
    (tmp_path / "artifacts-Release.json").write_text(json.dumps(locator), encoding="utf-8")
    previous = tmp_path / "verification/Release/result.json"
    previous.parent.mkdir(parents=True)
    previous.write_text("previous evidence", encoding="utf-8")
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("app/content.txt", "replaced")

    with pytest.raises(AssertionError, match="ZIP differs from the packaged artifact locator"):
        check(tmp_path, "Release")

    assert previous.read_text(encoding="utf-8") == "previous evidence"


@pytest.mark.parametrize("returncode", [0, 7, 10])
def test_application_probe_receives_extracted_root_and_controls_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int
) -> None:
    """A real probe subprocess must test this ZIP and fail the combined acceptance on error."""
    manifest = {
        "build": {
            "version": "1.0",
            "build_number": "42",
            "build_date": "2026-10-04",
            "target": "windows-x86-64",
            "python": "3.13.11",
            "channel": "stable",
        },
        "layout": {
            "paths": {"executable": "python.exe"},
            "files": {"development_executable": "python_d.exe"},
            "platform": "windows-x64",
            "abi": 1,
        },
        "python": "3.13.11",
        "distributions": {"fixture-product": "1.0"},
    }
    (tmp_path / "build-paths.json").write_text(
        json.dumps({"paths": {"verification": "verification"}}), encoding="utf-8"
    )
    manifest_bytes = json.dumps(manifest).encode()
    archive = tmp_path / "product.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("app/data/package-manifest.json", manifest_bytes)
    locator = {
        "archive": str(archive),
        "archive_sha256": digest(archive),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "development_binary": False,
        "target": "windows-x86-64",
        "release": {
            "target": "windows-x86-64",
            "platform": "windows-x64",
            "abi": 1,
            "python": "3.13.11",
            "version": "1.0",
            "channel": "stable",
            "cohort": ["fixture-product"],
        },
    }
    (tmp_path / "artifacts-Release.json").write_text(json.dumps(locator), encoding="utf-8")
    monkeypatch.setattr(
        artifact_verify, "load_layout", lambda target: {"files": {"package_manifest": "data/package-manifest.json"}}
    )
    monkeypatch.setattr(artifact_verify, "backend", lambda _: SimpleNamespace(external_probe=lambda _: ["fixture"]))
    monkeypatch.setattr(artifact_verify, "verify", lambda *args, **kwargs: None)
    monkeypatch.setenv("CADRUMO_TEST_PACKAGE_ROOT", str(tmp_path / "wrong-staged-package"))

    def dispatch(
        argv: list[str], *, cwd: Path, environment: Mapping[str, str], timeout_seconds: float
    ) -> CommandResult:
        if argv[0] == sys.executable:
            return run_command(argv, cwd=cwd, environment=environment, timeout_seconds=timeout_seconds)
        now = datetime.now(UTC)
        return CommandResult(tuple(argv), str(tmp_path), now, now, 0, 0, json.dumps(manifest["build"]), "")

    monkeypatch.setattr(artifact_verify, "run_command", dispatch)
    observed = tmp_path / "observed-root.txt"
    command = [
        sys.executable,
        "-c",
        "import os,pathlib,sys; "
        "pathlib.Path(sys.argv[1]).write_text(os.environ['CADRUMO_TEST_PACKAGE_ROOT'],encoding='utf-8'); "
        "code=int(sys.argv[2]); "
        "manifest=pathlib.Path(os.environ['CADRUMO_TEST_PACKAGE_ROOT'])/'data/package-manifest.json'; "
        "manifest.write_bytes(manifest.read_bytes()+b' ') if code==10 else None; "
        "sys.exit(0 if code==10 else code)",
        str(observed),
        str(returncode),
    ]
    result_path = tmp_path / "verification/Release/result.json"
    if returncode:
        failure = "ZIP manifest changed" if returncode == 10 else "Rust package compatibility failed"
        with pytest.raises(AssertionError, match=failure):
            check(tmp_path, "Release", command)
        assert not result_path.exists()
    else:
        check(tmp_path, "Release", command)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        assert result["application_probe"] == "passed"
        assert result["package_root"] == observed.read_text(encoding="utf-8")
    assert (
        Path(observed.read_text(encoding="utf-8"))
        == (tmp_path / "verification/Release/ZIP espacio á 漢字/app").resolve()
    )
