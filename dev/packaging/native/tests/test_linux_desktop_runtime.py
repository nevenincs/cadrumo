"""Desktop API exceptions stay image-bound, inventoried and enforced by native metadata."""

from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path
from typing import Literal

import pytest

from dev.packaging.command_execution import run_command
from dev.packaging.tests.test_native_installation import payload_fixture

from ..distribution_prepare import refresh
from ..hashing import digest
from ..identity import identity
from ..layout import load_layout
from ..linux_desktop_runtime import (
    DEPENDENCY_INPUTS,
    MANIFEST,
    declaration,
    desktop_path,
    package_requirements,
    validate_dependency_inputs,
    validate_payload,
    verify_requirements,
)
from ..linux_packages import PREINSTALL, author_gates, inspect_artifact
from ..platforms import linux
from ..platforms.tests.test_posix import _elf
from .test_distribution_prepare import _configure_distribution, _paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("target", ["linux-x86-64", "linux-aarch64"])
def test_generated_native_package_dependencies_use_same_payload_policy(tmp_path: Path, target: str) -> None:
    payload, _, build = _configure_distribution(tmp_path, target)
    manifest = json.loads((payload / "data/package-manifest.json").read_text(encoding="utf-8"))
    assert validate_payload(payload, manifest)
    policy = json.loads((payload / MANIFEST).read_text(encoding="utf-8"))
    assert policy["platform"] == target
    assert policy["minimum_host_verified"] is False
    assert "dbus-api-history" in policy["pending_evidence"]
    configuration = (build / "CPackConfig.cmake").read_text(encoding="utf-8")
    for package_format in ("deb", "rpm"):
        assert ", ".join(package_requirements(package_format)) in configuration


@pytest.mark.parametrize("mutation", ["missing", "changed", "rehashed", "wrong-target", "unenrolled"])
def test_prerequisite_manifest_cannot_be_omitted_or_redefined(tmp_path: Path, mutation: str) -> None:
    root, _ = payload_fixture(tmp_path, "linux-x86-64")
    manifest = json.loads((root / "data/package-manifest.json").read_text(encoding="utf-8"))
    if mutation == "missing":
        (root / MANIFEST).unlink()
    elif mutation == "wrong-target":
        manifest["layout"]["platform"] = "linux-aarch64"
    elif mutation == "unenrolled":
        del manifest["layout"]["linux_desktop_runtime"]
    else:
        (root / MANIFEST).write_text("{}", encoding="utf-8")
        if mutation == "rehashed":
            manifest["files"][MANIFEST] = digest(root / MANIFEST)
    with pytest.raises(ValueError, match=r"prerequisite|runtime policy"):
        validate_payload(root, manifest)


def test_runtime_only_payload_does_not_carry_desktop_requirements(tmp_path: Path) -> None:
    root, _ = payload_fixture(tmp_path, "linux-x86-64")
    manifest = json.loads((root / "data/package-manifest.json").read_text(encoding="utf-8"))
    del manifest["files"]["cadrumo"]
    (root / "cadrumo").unlink()
    with pytest.raises(ValueError, match="Runtime-only"):
        validate_payload(root, manifest)
    del manifest["files"][MANIFEST]
    (root / MANIFEST).unlink()
    assert not validate_payload(root, manifest)


@pytest.mark.parametrize(
    "field,value", [("name", "cadrumo-manager"), ("target", "rust_manager"), ("artifact", "OTHER")]
)
def test_copied_desktop_flag_cannot_admit_another_image(field: str, value: str) -> None:
    layout = load_layout("linux-x86-64")
    layout["application_images"] = [layout["application_images"][0]]
    layout["application_images"][0][field] = value
    with pytest.raises(ValueError, match="canonical desktop"):
        desktop_path(layout)
    with pytest.raises(ValueError):
        declaration(dict(layout, linux_desktop_runtime="unknown"))


@pytest.mark.parametrize("requester", ["python", "cadrumo-manager", "extension.so", "other/cadrumo"])
def test_desktop_external_dependency_never_admits_another_requester(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, requester: str
) -> None:
    desktop = _elf(tmp_path / "cadrumo")
    other = tmp_path / requester
    other.parent.mkdir(exist_ok=True)
    _elf(other)
    layout = load_layout("linux-x86-64")
    layout["native_tools"] = {"readelf": "readelf", "patchelf": "patchelf"}
    monkeypatch.setattr(
        linux, "command", lambda tool, *args: "GLIBC_2.28" if args[0] == "--version-info" else "libgtk-3.so.0"
    )
    with pytest.raises(ValueError, match="Unresolved ELF"):
        linux.relocate([other, desktop], tmp_path, layout)


def test_desktop_accepts_exact_external_libraries_and_erases_build_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desktop = _elf(tmp_path / "cadrumo")
    layout = load_layout("linux-x86-64")
    layout["native_tools"] = {"readelf": "readelf", "patchelf": "patchelf"}
    rpath = "/builder/private/lib"

    def tool(_tool: str, *args: str) -> str:
        nonlocal rpath
        if args[0] == "--version-info":
            return "GLIBC_2.28"
        if args[0] == "--print-needed":
            return "libgtk-3.so.0\nlibwebkit2gtk-4.1.so.0\nlibc.so.6"
        if args[0] == "--remove-rpath":
            rpath = ""
        return rpath

    monkeypatch.setattr(linux, "command", tool)
    linux.relocate([desktop], tmp_path, layout)
    assert not rpath
    shadow = _elf(tmp_path / "libgtk-3.so.0")
    with pytest.raises(ValueError, match="shadows"):
        linux.relocate([desktop, shadow], tmp_path, layout)


@pytest.mark.parametrize("package_format", ["deb", "rpm"])
def test_dependency_metadata_cannot_drop_or_weaken_explicit_policy(package_format: Literal["deb", "rpm"]) -> None:
    separator = ", " if package_format == "deb" else "\n"
    expected = separator.join(package_requirements(package_format))
    verify_requirements(expected + separator + "additional-provider", package_format)
    for changed in [expected.replace("3.24", "3.22"), expected.replace("2.42", "2.40"), "libc6"]:
        with pytest.raises(ValueError, match="lacks canonical"):
            verify_requirements(changed, package_format)
    if package_format == "deb":
        with pytest.raises(ValueError, match="lacks canonical"):
            verify_requirements(expected.replace("libgtk-3-0t64 (>= 3.24)", "unrelated-package"), "deb")


@pytest.mark.parametrize("package_format", ["deb", "rpm"])
def test_real_native_artifact_requires_its_inventory_bound_desktop_policy(
    tmp_path: Path, package_format: Literal["deb", "rpm"]
) -> None:
    inspector = shutil.which("dpkg-deb" if package_format == "deb" else "rpm")
    compiler = inspector if package_format == "deb" else shutil.which("rpmbuild")
    if inspector is None or compiler is None:
        pytest.skip("native package tools required")
    payload, identity_file = payload_fixture(tmp_path, "linux-x86-64")
    build = tmp_path / "build"
    _paths(build)
    refresh(payload, identity_file, build)
    stage = build / "installation/stage"
    (build / "packages").mkdir()
    gates = author_gates(build, identity_file)
    value = identity("linux-x86-64")
    artifact = build / f"packages/desktop.{package_format}"
    package_root = tmp_path / "native-root"
    shutil.copytree(stage, package_root)
    top = tmp_path / "rpm-build"
    top.mkdir()
    for weakened in (False, True):
        requirements = ", ".join(package_requirements(package_format))
        if weakened:
            requirements = requirements.replace("3.24", "3.22")
        if package_format == "deb":
            control = package_root / "DEBIAN"
            control.mkdir(exist_ok=True)
            (control / "control").write_text(
                f"Package: {value.package_name}\nVersion: {value.version}\nArchitecture: amd64\n"
                f"Depends: {requirements}\nMaintainer: Fixture <fixture@example.invalid>\n"
                "Description: disposable dependency inspection fixture\n",
                encoding="utf-8",
                newline="\n",
            )
            shutil.copy2(gates["preinst"], control / "preinst")
            command = [compiler, "--build", str(package_root), str(artifact)]
        else:
            spec = top / "fixture.spec"
            files = "\n".join("/" + file.relative_to(stage).as_posix() for file in stage.rglob("*") if file.is_file())
            spec.write_text(
                f"Name: {value.package_name}\nVersion: {value.version}\nRelease: 1\nSummary: Fixture\n"
                f"License: MIT\nBuildArch: x86_64\nAutoReqProv: no\nRequires: {requirements}\n"
                "%description\nDisposable desktop dependency fixture.\n%install\n"
                f"mkdir -p '%{{buildroot}}'\ncp -a {shlex.quote(str(stage))}/. '%{{buildroot}}/'\n"
                "%pre\n" + PREINSTALL.replace("%", "%%") + "\n%files\n" + files + "\n",
                encoding="utf-8",
                newline="\n",
            )
            command = [compiler, "--define", f"_topdir {top}", "-bb", str(spec)]
        result = run_command(command, cwd=tmp_path, timeout_seconds=60)
        assert result.returncode == 0, result.stderr
        if package_format == "rpm":
            shutil.copy2(next((top / "RPMS").rglob("*.rpm")), artifact)
        if weakened:
            with pytest.raises(ValueError, match="lacks canonical"):
                inspect_artifact(build, identity_file, artifact, package_format, Path(inspector))
            assert not (build / f"packages/linux-inspection/{package_format}.json").exists()
        else:
            receipt = inspect_artifact(build, identity_file, artifact, package_format, Path(inspector))
            assert json.loads(receipt.read_text(encoding="utf-8"))["desktop_runtime_dependencies"]


@pytest.mark.parametrize("member", tuple(DEPENDENCY_INPUTS))
def test_dependency_evidence_refuses_lock_and_owned_feature_drift(tmp_path: Path, member: str) -> None:
    from dev._paths import REPO_ROOT

    for name in DEPENDENCY_INPUTS:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / name, target)
    validate_dependency_inputs(tmp_path)
    target = tmp_path / member
    target.write_text(target.read_text(encoding="utf-8") + "\n# Formatting is not feature drift.\n", encoding="utf-8")
    validate_dependency_inputs(tmp_path)
    target.write_text(target.read_text(encoding="utf-8").replace('version = "', 'version = "99.', 1), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence requires refresh"):
        validate_dependency_inputs(tmp_path)
