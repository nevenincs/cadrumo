"""Inspect generated WiX ownership sources without installing or claiming native acceptance."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from uuid import UUID

import pytest
from defusedxml import ElementTree

from dev.packaging.command_execution import run_command
from dev.packaging.native.distribution_prepare import refresh
from dev.packaging.native.hashing import digest
from dev.packaging.native.identity import DistributionIdentity
from dev.packaging.native.windows_msi import MAINTENANCE_GATE, author, reject_combined_manager_msi
from dev.packaging.native.windows_msi_build import compile_products, maintenance_plan, verify_database, verify_products
from dev.packaging.native.windows_msi_identity import msi_identity

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
                if source.name == "native-installation.json":
                    relative = "data/installation.json"
                    native_marker = json.loads(source.read_text(encoding="utf-8"))
                    portable_marker = json.loads((stage / relative).read_text(encoding="utf-8"))
                    assert "publication" not in portable_marker
                    assert native_marker.pop("publication") == "data/installation-state"
                    assert native_marker == portable_marker
                else:
                    relative = source.relative_to(stage).as_posix()
                    assert digest(source) == owned[relative]
                sets[role].add(relative)
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
                assert login.attrib["Value"] == '"[INSTALL_ROOT]cadrumo-manager" --sign-in'
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


def test_optional_native_admission_is_scoped_and_hash_bound_without_opening_installation(tmp_path: Path) -> None:
    build, identity = _prepared(tmp_path)
    adapter = tmp_path / "installer.dll"
    adapter.write_bytes(b"authoring fixture; not a native acceptance payload")
    outputs = author(build, identity, "cadrumo", adapter)
    value = DistributionIdentity(**json.loads(identity.read_text(encoding="utf-8")))
    for scope in ("user", "machine"):
        opposite = "machine" if scope == "user" else "user"
        for role in ("version", "registration"):
            package = ElementTree.parse(outputs[f"{scope}-{role}.wxs"]).find("w:Package", NS)
            assert package is not None
            metadata = package.find("w:Property[@Id='CadrumoAdmission']", NS)
            assert metadata is not None
            request = json.loads(metadata.attrib["Value"])
            assert request["scope"] == scope
            assert request["permitted_families"] == [
                msi_identity(value, scope, item).upgrade_code for item in ("version", "registration")
            ]
            assert request["conflicting_families"] == [
                msi_identity(value, opposite, item).upgrade_code for item in ("version", "registration")
            ] + [value.upgrade_code]
            action = package.find("w:CustomAction[@Id='CadrumoScopeAdmission']", NS)
            assert action is not None
            assert action.attrib["Impersonate"] == ("yes" if scope == "user" else "no")
            assert action.attrib["Execute"] == "deferred"
            assert action.attrib["Return"] == "check"
            launch = package.find("w:Launch", NS)
            assert launch is not None and launch.attrib["Condition"] == "0"
    descriptor = build / "installation/metadata/wix/authoring.json"
    before = descriptor.read_bytes()
    assert json.loads(before)["adapter_sha256"] == digest(adapter)
    adapter.write_bytes(b"changed adapter")
    author(build, identity, "cadrumo", adapter)
    assert descriptor.read_bytes() != before


@pytest.mark.parametrize("defect", ["data", "action", "impersonation", "ignore-failure"])
def test_database_verifier_detects_native_admission_changes(tmp_path: Path, defect: str) -> None:
    build, identity = _prepared(tmp_path)
    adapter = tmp_path / "installer.dll"
    adapter.write_bytes(b"authoring fixture")
    source = author(build, identity, "cadrumo", adapter)["machine-version.wxs"]
    database = tmp_path / "database.wxs"
    content = source.read_text(encoding="utf-8")
    if defect == "data":
        content = content.replace('Id="CadrumoAdmission"', 'Id="MissingAdmission"')
    elif defect == "action":
        content = content.replace('DllEntry="CadrumoScopeAdmission"', 'DllEntry="MissingAdmission"')
    elif defect == "impersonation":
        content = content.replace('Impersonate="no"', 'Impersonate="yes"')
    else:
        content = content.replace('Return="check"', 'Return="ignore"')
    database.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="admission"):
        verify_database(source, database)


@pytest.mark.external_tool
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="Requires the native Windows MSI adapter and compiler")
def test_native_admission_dll_is_embedded_in_all_four_verified_products(tmp_path: Path) -> None:
    wix = shutil.which("wix")
    assert wix is not None, "Put the configured WiX compiler on PATH"
    configured = os.environ.get("CADRUMO_TEST_MSI_ADAPTER")
    assert configured, "Set CADRUMO_TEST_MSI_ADAPTER to the CMake rust_installer output"
    adapter = tmp_path / "adapter.dll"
    shutil.copyfile(Path(configured), adapter)
    runner = Path(configured).with_name("cadrumo-msi-maintenance.exe")
    assert runner.is_file(), "Build the native maintenance runner alongside its DLL"
    build, identity = _prepared(tmp_path)
    paths = build / "build-paths.json"
    document = json.loads(paths.read_text(encoding="utf-8"))
    document["paths"]["packages"] = "packages"
    paths.write_text(json.dumps(document), encoding="utf-8")
    compile_products(build, identity, Path(wix), "cadrumo", adapter, runner)
    verify_products(build, identity, "cadrumo", adapter, runner)
    receipt = json.loads((build / "packages/msi/compiled.json").read_text(encoding="utf-8"))
    assert receipt["installable"] is False
    assert len(receipt["artifacts"]) == 4
    prefix = tmp_path / "never installed"
    plan = maintenance_plan(build, identity, "user", prefix, "cadrumo", adapter, runner)

    def run_plan() -> str:
        result = run_command([str(runner), "install", "--plan", str(plan)], cwd=build, timeout_seconds=30)
        assert result.returncode != 0
        assert not prefix.exists()
        code = json.loads(result.stdout)["code"]
        assert isinstance(code, str)
        return code

    assert run_plan() == "native_owner_protocol_not_admitted"
    request = json.loads(plan.read_text(encoding="utf-8"))
    request["version_product"], request["registration_product"] = (
        request["registration_product"],
        request["version_product"],
    )
    plan.write_text(json.dumps(request), encoding="utf-8")
    assert run_plan() == "artifact_or_owner_refused"
    request["version_product"], request["registration_product"] = (
        request["registration_product"],
        request["version_product"],
    )
    request["contract"]["installation_identity"]["channel"] = "another-channel"
    plan.write_text(json.dumps(request), encoding="utf-8")
    assert run_plan() == "artifact_or_owner_refused"
    adapter.write_bytes(adapter.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="stale payload identity"):
        verify_products(build, identity, "cadrumo", adapter, runner)


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


@pytest.mark.parametrize("defect", ["identity", "gate", "version-removal", "registration-upgrade"])
def test_database_verifier_rejects_ownership_regressions(tmp_path: Path, defect: str) -> None:
    build, identity = _prepared(tmp_path)
    sources = author(build, identity, "cadrumo")
    role = "registration" if defect == "registration-upgrade" else "version"
    source = sources[f"user-{role}.wxs"]
    database = tmp_path / "database.wxs"
    content = source.read_text(encoding="utf-8")
    database.write_text(content, encoding="utf-8")
    verify_database(source, database)
    if defect == "identity":
        package = ElementTree.parse(source).find("w:Package", NS)
        assert package is not None
        content = content.replace(package.attrib["ProductCode"], "00000000-0000-0000-0000-000000000000")
    elif defect == "gate":
        content = content.replace('Condition="0"', 'Condition="1"')
    elif defect == "version-removal":
        content = content.replace(
            "</Package>",
            "<InstallExecuteSequence><RemoveExistingProducts "
            'After="InstallExecute" /></InstallExecuteSequence></Package>',
        )
    else:
        content = content.replace("MajorUpgrade", "MissingUpgrade")
    database.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        verify_database(source, database)


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
