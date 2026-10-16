"""One compiler input retains independently authenticated native ownership features."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree

from ...command_execution import run_command
from ..hashing import digest
from ..identity import DistributionIdentity
from ..windows_msi import _machine_service, _source, author
from ..windows_msi_build import _retire, verify_database
from ..windows_msi_database import verify_admission_order, verify_feature_ownership
from ..windows_msi_identity import release_identity
from ..windows_msi_single import source
from .test_windows_msi import _prepared

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
_NS = {"w": "http://wixtoolset.org/schemas/v4/wxs"}


def _release_source(tmp_path: Path, *, owned: bool = False) -> bytes:
    build, identity = _prepared(tmp_path)
    author(build, identity, "cadrumo")
    value = DistributionIdentity(**json.loads(identity.read_text(encoding="utf-8")))
    stage = build / "installation/stage"
    files = json.loads((build / "installation/metadata/installation.json").read_text(encoding="utf-8"))["files"]
    prefix = f"versions/{value.version}/"
    marker = build / "installation/metadata/wix/native-installation.json"
    manifest = stage / prefix / "data/package-manifest.json"
    service = Element("Component")
    _machine_service(service, value)
    partitions = []
    for role in ("version", "registration"):
        partitions.append(
            _source(
                stage,
                {name: checksum for name, checksum in files.items() if name.startswith(prefix) == (role == "version")},
                value,
                "user",
                role,
                "cadrumo-manager",
                "cadrumo",
                ("installation.json", marker, digest(marker)),
                digest(manifest),
                product=release_identity(value, role),
            )
        )
    adapter = tmp_path / "adapter.dll" if owned else None
    runner = tmp_path / "runner.exe" if owned else None
    if adapter is not None and runner is not None:
        adapter.write_bytes(b"compiler fixture only; never installed")
        runner.write_bytes(b"compiler fixture only; never executed")
    return source(partitions[0], partitions[1], value, "cadrumo-manager", list(service), adapter, runner)


def test_release_source_has_one_scope_aware_package_and_independent_features(tmp_path: Path) -> None:
    document = ElementTree.fromstring(_release_source(tmp_path))
    packages = document.findall("w:Package", _NS)
    assert len(packages) == 1
    package = packages[0]
    assert package.attrib["Scope"] == "perUserOrMachine"
    assert {feature.attrib["Id"] for feature in package.findall("w:Feature", _NS)} == {
        "VersionFiles",
        "SharedRegistration",
    }
    assert package.find("w:MajorUpgrade", _NS) is None
    assert len(package.findall(".//w:ServiceInstall", _NS)) == 1
    login = [
        component
        for component in package.findall(".//w:Component", _NS)
        if any(
            entry.attrib["Key"] == "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
            for entry in component.findall("w:RegistryValue", _NS)
        )
    ]
    assert len(login) == 1 and login[0].attrib["Condition"] == "NOT ALLUSERS"
    for scope in ("User", "Machine"):
        entry = package.find(f"w:Property[@Id='CadrumoRegistration{scope}']", _NS)
        assert entry is not None
        description = json.loads(entry.attrib["Value"])
        assert (login[0].attrib["Guid"] in description["components"]) == (scope == "User")
        assert any(
            row["key"] == "Software\\Microsoft\\Windows\\CurrentVersion\\Run" for row in description["registry"]
        ) == (scope == "User")


def test_author_reuses_verified_source_but_refuses_changed_output_currency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from .. import windows_msi

    build, identity = _prepared(tmp_path)
    generated = author(build, identity, "cadrumo")

    def unexpected_generation(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("source regeneration requested")

    monkeypatch.setattr(windows_msi, "_source", unexpected_generation)
    assert author(build, identity, "cadrumo") == generated
    generated["application.wxs"].write_bytes(b"changed generated source")
    with pytest.raises(AssertionError, match="regeneration"):
        author(build, identity, "cadrumo")


@pytest.mark.parametrize("modified", [False, True])
def test_retirement_removes_only_unchanged_recorded_outputs_after_complete_preflight(
    tmp_path: Path,
    modified: bool,
) -> None:
    first = tmp_path / "user-version.msi"
    second = tmp_path / "machine-version.msi"
    current = tmp_path / "application.msi"
    foreign = tmp_path / "user-registration.msi"
    for path in (first, second, current, foreign):
        path.write_bytes(path.name.encode())
    recorded = {path.name: digest(path) for path in (first, second)}
    if modified:
        second.write_bytes(b"changed after previous producer receipt")
        with pytest.raises(ValueError, match="refusing to remove"):
            _retire(tmp_path, recorded, set(recorded))
        assert first.is_file() and second.is_file()
    else:
        _retire(tmp_path, recorded, set(recorded))
        assert not first.exists() and not second.exists()
    assert current.read_bytes() == current.name.encode()
    assert foreign.read_bytes() == foreign.name.encode()


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="Requires the native WiX compiler")
@pytest.mark.parametrize("owned", [False, True])
def test_release_source_compiles_with_one_wix_build_invocation(tmp_path: Path, owned: bool) -> None:
    wix = shutil.which("wix")
    assert wix is not None
    generated = tmp_path / "application.wxs"
    generated.write_bytes(_release_source(tmp_path, owned=owned))
    compiled = run_command(
        [wix, "build", "-arch", "x64", "-wx", "-o", str(tmp_path / "application.msi"), str(generated)], cwd=tmp_path
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    verify_feature_ownership(tmp_path / "application.msi")
    if owned:
        verify_admission_order(tmp_path / "application.msi", owner_required=True)
    database = tmp_path / "decompiled.wxs"
    decompiled = run_command(
        [wix, "msi", "decompile", "-o", str(database), str(tmp_path / "application.msi")], cwd=tmp_path
    )
    assert decompiled.returncode == 0, decompiled.stdout + decompiled.stderr
    verify_database(generated, database)
