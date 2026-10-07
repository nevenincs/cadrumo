"""Inspect generated WiX ownership sources without installing or claiming native acceptance."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from uuid import UUID

import pytest
from defusedxml import ElementTree

from dev.packaging.command_execution import run_command
from dev.packaging.native.distribution_prepare import refresh
from dev.packaging.native.hashing import digest
from dev.packaging.native.windows_msi import MAINTENANCE_GATE, author, reject_combined_manager_msi

from .test_native_installation import payload_fixture

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
NS = {"w": "http://wixtoolset.org/schemas/v4/wxs"}


def _prepared(tmp_path: Path, *, manager: bool = True, desktop: bool = True) -> tuple[Path, Path]:
    temporary = tmp_path / "relocated ü space"
    temporary.mkdir()
    payload, identity = payload_fixture(temporary, "windows-x86-64", manager=manager)
    build = temporary / "build"
    build.mkdir()
    paths = {f"installation_{name}": f"installation/{name}" for name in ("stage", "metadata", "work", "receipts")}
    (build / "build-paths.json").write_text(json.dumps({"paths": paths}), encoding="utf-8")
    refresh(payload, identity, build, "cadrumo" if desktop else None)
    return build, identity


@pytest.mark.parametrize("desktop", [True, False])
def test_authoring_separates_file_ownership_and_scoped_registration(tmp_path: Path, desktop: bool) -> None:
    build, identity = _prepared(tmp_path, desktop=desktop)
    outputs = author(build, identity, "cadrumo" if desktop else None)
    assert set(outputs) == {
        f"{scope}-{role}.wxs" for scope in ("user", "machine") for role in ("version", "registration")
    }
    stage = build / "installation/stage"
    receipt = build / "installation/metadata/installation.json"
    owned = json.loads(receipt.read_text(encoding="utf-8"))["files"]
    value = json.loads(identity.read_text(encoding="utf-8"))
    version_prefix = f"versions/{value['version']}/"
    products: set[str] = set()
    families: set[str] = set()
    for scope in ("user", "machine"):
        expected_registry = "HKCU" if scope == "user" else "HKLM"
        sets = {}
        components = {}
        for role in ("version", "registration"):
            root = ElementTree.parse(outputs[f"{scope}-{role}.wxs"])
            package = root.find("w:Package", NS)
            assert package is not None
            products.add(package.attrib["ProductCode"])
            families.add(package.attrib["UpgradeCode"])
            assert package.attrib["Scope"] == ("perUser" if scope == "user" else "perMachine")
            assert package.attrib["Version"] == value["version"]
            launch = package.find("w:Launch", NS)
            assert launch is not None and launch.attrib == {"Condition": "0", "Message": MAINTENANCE_GATE}
            properties = {item.attrib["Id"]: item.attrib["Value"] for item in package.findall("w:Property", NS)}
            assert properties["MSIRESTARTMANAGERCONTROL"] == "Disable"
            assert properties["REBOOT"] == "ReallySuppress"
            assert root.find(".//w:ServiceInstall", NS) is None
            assert root.find(".//w:CustomAction", NS) is None
            component_nodes = root.findall(".//w:Component", NS)
            components[role] = {item.attrib["Guid"] for item in component_nodes}
            references = {item.attrib["Id"] for item in root.findall(".//w:ComponentRef", NS)}
            assert references == {item.attrib["Id"] for item in component_nodes}
            registry = root.findall(".//w:RegistryValue", NS)
            assert all(item.attrib["Root"] == expected_registry for item in registry)
            sets[role] = set()
            for file in root.findall(".//w:File", NS):
                source = Path(file.attrib["Source"])
                relative = source.relative_to(stage).as_posix()
                sets[role].add(relative)
                assert digest(source) == owned[relative]
                assert file.attrib["KeyPath"] == ("no" if scope == "user" else "yes")
            if role == "version":
                assert package.attrib["UpgradeStrategy"] == "none"
                assert root.find(".//w:MajorUpgrade", NS) is None
                assert root.find(".//w:RemoveExistingProducts", NS) is None
                assert root.find(".//w:Shortcut", NS) is None
                assert not any(item.attrib["Name"] in {"EntryPoint", "InstallLocation"} for item in registry)
            else:
                assert package.attrib["UpgradeStrategy"] == "majorUpgrade"
                upgrade = package.find("w:MajorUpgrade", NS)
                assert upgrade is not None and upgrade.attrib["Schedule"] == "afterInstallExecute"
                assert upgrade.attrib["AllowSameVersionUpgrades"] == "no"
                entry = next(item for item in registry if item.attrib["Name"] == "EntryPoint")
                assert entry.attrib["Value"] == "[INSTALL_ROOT]cadrumo-manager"
                login = next(item for item in registry if item.attrib["Name"] == value["application_id"])
                assert login.attrib["Key"].endswith("\\CurrentVersion\\Run")
                assert login.attrib["Value"] == '"[INSTALL_ROOT]cadrumo-manager"'
                anchor = next(item for item in registry if item.attrib["Name"] == "ManagerAnchorVersion")
                assert anchor.attrib["Value"] == value["version"]
                shortcut = root.find(".//w:Shortcut", NS)
                if desktop:
                    assert shortcut is not None
                    assert shortcut.attrib["Target"] == f"[INSTALL_ROOT]versions\\{value['version']}\\cadrumo"
                else:
                    assert shortcut is None
        assert sets["version"] == {name for name in owned if name.startswith(version_prefix)}
        assert sets["version"].isdisjoint(sets["registration"])
        assert sets["version"] | sets["registration"] == set(owned)
        assert components["version"].isdisjoint(components["registration"])
    assert len(products) == 4
    assert len(families) == 4
    descriptor = json.loads((build / "installation/metadata/wix/authoring.json").read_text(encoding="utf-8"))
    assert descriptor["installable"] is False
    assert descriptor["sources"] == {name: digest(path) for name, path in outputs.items()}


@pytest.mark.parametrize("manager", [False, True])
def test_legacy_msi_guard_refuses_only_manager_payloads(tmp_path: Path, manager: bool) -> None:
    build, _ = _prepared(tmp_path, manager=manager)
    if manager:
        with pytest.raises(ValueError, match="separate version and registration"):
            reject_combined_manager_msi(build)
    else:
        reject_combined_manager_msi(build)


def test_authoring_is_incremental_and_preserves_stage(tmp_path: Path) -> None:
    build, identity = _prepared(tmp_path)
    receipt = build / "installation/metadata/installation.json"
    before = receipt.read_bytes()
    outputs = author(build, identity, "cadrumo")
    times = {name: path.stat().st_mtime_ns for name, path in outputs.items()}
    assert author(build, identity, "cadrumo") == outputs
    assert {name: path.stat().st_mtime_ns for name, path in outputs.items()} == times
    assert receipt.read_bytes() == before


@pytest.mark.parametrize("operation", ["author", "guard"])
def test_modified_stage_is_refused_before_authoring_or_packaging(tmp_path: Path, operation: str) -> None:
    build, identity = _prepared(tmp_path)
    version = json.loads(identity.read_text(encoding="utf-8"))["version"]
    (build / f"installation/stage/versions/{version}/cadrumo").write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="has changed"):
        if operation == "author":
            author(build, identity, "cadrumo")
        else:
            reject_combined_manager_msi(build)
    assert not (build / "installation/metadata/wix").exists()


def test_shared_manager_must_match_the_version_owner(tmp_path: Path) -> None:
    build, identity = _prepared(tmp_path)
    manager = build / "installation/stage/cadrumo-manager"
    manager.write_bytes(b"different manager bytes")
    receipt = build / "installation/metadata/installation.json"
    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["files"]["cadrumo-manager"] = digest(manager)
    receipt.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical registration owner"):
        author(build, identity)
    assert not (build / "installation/metadata/wix").exists()


def test_wix_preprocessor_metadata_is_refused_before_any_output(tmp_path: Path) -> None:
    build, identity = _prepared(tmp_path)
    value = json.loads(identity.read_text(encoding="utf-8"))
    value["publisher"] = "$(env.UNKNOWN)"
    identity.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="preprocessor expressions"):
        author(build, identity)
    assert not (build / "installation/metadata/wix").exists()


def test_stage_receipt_and_package_identity_must_agree(tmp_path: Path) -> None:
    build, identity = _prepared(tmp_path)
    receipt = build / "installation/metadata/installation.json"
    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["application_id"] = "another.application"
    receipt.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt and package identities differ"):
        author(build, identity)
    with pytest.raises(ValueError, match="receipt and package identities differ"):
        reject_combined_manager_msi(build)
    assert not (build / "installation/metadata/wix").exists()


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="Requires the native Windows MSI validator")
@pytest.mark.parametrize("desktop", [True, False])
def test_native_wix_compiles_all_scopes_and_roles_without_warnings(tmp_path: Path, desktop: bool) -> None:
    wix = shutil.which("wix")
    assert wix is not None, "Put a configured WiX 5 or newer tool on PATH for the native compiler lane"
    build, identity = _prepared(tmp_path, desktop=desktop)
    outputs = author(build, identity, "cadrumo" if desktop else None)
    artifacts = tmp_path / "compiled"
    artifacts.mkdir()
    for source in outputs.values():
        artifact = artifacts / source.with_suffix(".msi").name
        result = run_command(
            [wix, "build", "-arch", "x64", "-wx", "-o", str(artifact), str(source)],
            cwd=tmp_path,
            timeout_seconds=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert artifact.is_file() and artifact.stat().st_size > 0
        decompiled = artifact.with_suffix(".wxs")
        result = run_command(
            [wix, "msi", "decompile", "-o", str(decompiled), str(artifact)], cwd=tmp_path, timeout_seconds=120
        )
        assert result.returncode == 0, result.stdout + result.stderr
        database = ElementTree.parse(decompiled)
        package = database.find("w:Package", NS)
        assert package is not None
        original = ElementTree.parse(source).find("w:Package", NS)
        assert original is not None
        assert UUID(package.attrib["ProductCode"]) == UUID(original.attrib["ProductCode"])
        launch = database.find(".//w:Launch", NS)
        assert launch is not None and launch.attrib == {"Condition": "0", "Message": MAINTENANCE_GATE}
        if "version" in source.stem:
            assert database.find(".//w:MajorUpgrade", NS) is None
            assert database.find(".//w:RemoveExistingProducts", NS) is None
        else:
            assert database.find(".//w:MajorUpgrade", NS) is not None
