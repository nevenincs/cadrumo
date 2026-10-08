"""Linux native ownership inspection and pre-install refusal."""

from __future__ import annotations

import json
import shlex
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from dev.packaging.command_execution import run_command

from ..hashing import digest
from ..identity import identity
from ..linux_packages import PREINSTALL, author_gates, deb_files, inspect_artifact, rpm_files
from .test_distribution_prepare import _cmake, _configure_distribution

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_native_file_lists_reject_links_traversal_duplicates_and_non_file_nodes() -> None:
    assert deb_files("-rw-r--r-- root/root 5 2026-10-08 00:00 ./opt/name with space\n") == {"/opt/name with space"}
    assert rpm_files("100644 /opt/name with space\n40755 /opt\n") == {"/opt/name with space"}
    for listing in [
        "lrwxrwxrwx root/root 5 2026-10-08 00:00 ./link -> /etc/passwd\n",
        "-rw-r--r-- root/root 5 2026-10-08 00:00 ./../outside\n",
    ]:
        with pytest.raises(ValueError):
            deb_files(listing)
    for listing in ["120777 /link\n", "20600 /device\n", "100644 /file\n100644 /file\n"]:
        with pytest.raises(ValueError):
            rpm_files(listing)


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    build = tmp_path / "build"
    build.mkdir()
    paths = {"installation_stage": "stage", "installation_metadata": "metadata", "packages": "packages"}
    (build / "build-paths.json").write_text(json.dumps({"paths": paths}), encoding="utf-8")
    value = identity("linux-x86-64")
    identity_file = tmp_path / "identity.json"
    identity_file.write_text(json.dumps(asdict(value)), encoding="utf-8")
    stage = build / "stage"
    payload = stage / "opt" / value.package_name / "cadrumo-manager"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"native-package-fixture")
    (build / "metadata").mkdir()
    (build / "metadata/installation.json").write_text(
        json.dumps(
            {"application_id": value.application_id, "files": {payload.relative_to(stage).as_posix(): digest(payload)}}
        ),
        encoding="utf-8",
    )
    (build / "packages").mkdir()
    return build, identity_file


def test_gate_authoring_preserves_lf_and_never_registers_login(tmp_path: Path) -> None:
    build, identity_file = _fixture(tmp_path)
    gates = author_gates(build, identity_file)
    assert set(gates) == {"preinst", "rpm-preinstall.sh"}
    for path in gates.values():
        assert path.read_bytes() == PREINSTALL.encode("utf-8")
        shell = shutil.which("sh") if sys.platform == "linux" else None
        if shell is not None:
            refused = run_command([shell, str(path)], cwd=tmp_path, timeout_seconds=5)
            assert refused.returncode == 1
            assert "Linux installation is disabled" in refused.stderr
    assert not (build / "stage/etc").exists()


def test_real_deb_metadata_guard_and_ownership_are_inspected(tmp_path: Path) -> None:
    native = shutil.which("dpkg-deb")
    if native is None:
        pytest.skip("native dpkg-deb runner required")
    build, identity_file = _fixture(tmp_path)
    value = identity("linux-x86-64")
    gates = author_gates(build, identity_file)
    package = tmp_path / "deb-root"
    shutil.copytree(build / "stage", package)
    control = package / "DEBIAN"
    control.mkdir()
    (control / "control").write_text(
        f"Package: {value.package_name}\nVersion: {value.version}\nArchitecture: amd64\n"
        "Maintainer: Fixture <fixture@example.invalid>\nDescription: disposable package inspection fixture\n",
        encoding="utf-8",
        newline="\n",
    )
    shutil.copy2(gates["preinst"], control / "preinst")
    artifact = build / "packages/fixture.deb"
    result = run_command([native, "--build", str(package), str(artifact)], cwd=tmp_path, timeout_seconds=30)
    assert result.returncode == 0, result.stderr
    receipt = inspect_artifact(build, identity_file, artifact, "deb", Path(native))
    observed = json.loads(receipt.read_text(encoding="utf-8"))
    assert observed["installable"] is False
    assert observed["sha256"] == digest(artifact)
    assert observed["owned_files"] == [f"/opt/{value.package_name}/cadrumo-manager"]
    # A rebuilt artifact with a permissive maintainer script must not receive evidence.
    (control / "preinst").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    result = run_command([native, "--build", str(package), str(artifact)], cwd=tmp_path, timeout_seconds=30)
    assert result.returncode == 0, result.stderr
    with pytest.raises(ValueError, match="lost its unconditional installation gate"):
        inspect_artifact(build, identity_file, artifact, "deb", Path(native))
    assert not receipt.exists()


def test_real_rpm_metadata_guard_and_ownership_are_inspected(tmp_path: Path) -> None:
    native, compiler = shutil.which("rpm"), shutil.which("rpmbuild")
    if native is None or compiler is None:
        pytest.skip("native rpm/rpmbuild runner required")
    build, identity_file = _fixture(tmp_path)
    value = identity("linux-x86-64")
    top = tmp_path / "rpm-build"
    top.mkdir()
    payload = build / "stage/opt" / value.package_name / "cadrumo-manager"
    spec = top / "fixture.spec"
    body = (
        f"Name: {value.package_name}\nVersion: {value.version}\nRelease: 1\nSummary: Fixture\n"
        "License: MIT\nBuildArch: x86_64\nAutoReqProv: no\n"
        "%description\nDisposable native ownership inspection fixture.\n"
        "%install\n"
        f"install -D -m644 {shlex.quote(str(payload))} '%{{buildroot}}/opt/{value.package_name}/cadrumo-manager'\n"
        "%pre\n" + PREINSTALL.replace("%", "%%") + "\n"
        f"%files\n/opt/{value.package_name}/cadrumo-manager\n"
    )
    spec.write_text(body, encoding="utf-8", newline="\n")
    result = run_command([compiler, "--define", f"_topdir {top}", "-bb", str(spec)], cwd=tmp_path, timeout_seconds=60)
    assert result.returncode == 0, result.stderr
    artifacts = list((top / "RPMS").rglob("*.rpm"))
    assert len(artifacts) == 1
    artifact = build / "packages/fixture.rpm"
    shutil.copy2(artifacts[0], artifact)
    receipt = inspect_artifact(build, identity_file, artifact, "rpm", Path(native))
    observed = json.loads(receipt.read_text(encoding="utf-8"))
    assert observed["installable"] is False
    assert observed["sha256"] == digest(artifact)
    assert observed["owned_files"] == [f"/opt/{value.package_name}/cadrumo-manager"]


def test_real_cmake_linux_targets_build_inspected_gated_native_packages(tmp_path: Path) -> None:
    if sys.platform != "linux" or any(shutil.which(tool) is None for tool in ("dpkg-deb", "rpm", "rpmbuild")):
        pytest.skip("native Linux package build tools required")
    _, source, build = _configure_distribution(tmp_path, "linux-x86-64", manager=True)
    _cmake(source, "--build", str(build), "--target", "native-package")
    for package_format in ("deb", "rpm"):
        receipt = json.loads((build / f"packages/linux-inspection/{package_format}.json").read_text(encoding="utf-8"))
        assert receipt["installable"] is False
        assert receipt["payload_bytes_verified"] is False
    cmake = shutil.which("cmake")
    assert cmake is not None
    refused = run_command([cmake, "--build", str(build), "--target", "check-linux-installation"], cwd=source)
    assert refused.returncode != 0
    assert "Linux installation is disabled" in refused.stdout + refused.stderr
