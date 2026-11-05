"""Shared assertions for the generated WiX source and compiled MSI ownership tests."""

from __future__ import annotations

import ctypes
import json
import shutil
import sys
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import ElementTree as Tree

import pytest

from ...command_execution import run_command
from .. import windows_msi_build
from ..hashing import digest
from ..windows_msi_build import bootstrap_kit, compile_products, maintenance_plan
from ..windows_msi_contract import MAINTENANCE_GATE
from ..windows_msi_database import table_rows, verify_admission_order
from ..windows_msi_paths import source_path

NS = {"w": "http://wixtoolset.org/schemas/v4/wxs"}


def assert_scope_registration(
    tree: Tree, shared_components: list[Element], scope: str, build: Path, *, desktop: bool
) -> None:
    """Compare one scope's registration description with the authored components."""
    property_node = tree.find(f".//w:Property[@Id='CadrumoRegistration{scope.title()}']", NS)
    assert property_node is not None
    description = json.loads(property_node.attrib["Value"])
    assert description["scope"] == scope
    assert description["schema"] == 2
    assert len(description["services"]) == int(scope == "machine")
    excluded = 'ALLUSERS = "1"' if scope == "user" else "NOT ALLUSERS"
    components = [node for node in shared_components if node.attrib.get("Condition", "") != excluded]
    assert set(description["components"]) == {item.attrib["Guid"] for item in components}
    actual_registry = [
        {
            "component": component.attrib["Guid"],
            **{key.lower(): entry.attrib[key] for key in ("Key", "Name", "Type", "Value")},
        }
        for component in components
        for entry in component.findall("w:RegistryValue", NS)
    ]
    assert len(description["registry"]) == len(actual_registry)
    assert {json.dumps(row, sort_keys=True) for row in description["registry"]} == {
        json.dumps(row, sort_keys=True) for row in actual_registry
    }
    assert len(description["files"]) == 4
    for component in components:
        for file in component.findall("w:File", NS):
            assert digest(Path(file.attrib["Source"])) in description["files"].values()
    marker = next(name for name in description["files"] if name.endswith("installation.json"))
    assert description["files"][marker] == digest(build / "installation/metadata/wix/native-installation.json")
    assert bool(description["shortcuts"]) == desktop
    assert bool(description["absent_shortcuts"]) != desktop
    assert {entry["name"] for entry in description["absent_registry"]} == (
        set() if desktop else {"DesktopRegistered", "DesktopAnchorVersion"}
    )


def assert_package_attributes(root: Tree, package: Element, version: str) -> None:
    assert package.attrib["Scope"] == "perUserOrMachine"
    assert package.attrib["Version"] == version
    assert package.attrib["UpgradeStrategy"] == "none"
    assert root.find(".//w:MajorUpgrade", NS) is None
    assert root.find(".//w:RemoveExistingProducts", NS) is None
    launch = package.find("w:Launch", NS)
    assert launch is not None and launch.attrib == {"Condition": "0", "Message": MAINTENANCE_GATE}
    properties = {node.attrib["Id"]: node.attrib.get("Value") for node in package.findall("w:Property", NS)}
    assert properties["MSIRESTARTMANAGERCONTROL"] == "Disable"
    assert properties["REBOOT"] == "ReallySuppress"
    ownership_property = properties["CadrumoPackage"]
    assert ownership_property is not None
    assert json.loads(ownership_property)["role"] == "application"


def feature_ownership(
    package: Element, components: dict[str, Element], stage: Path, owned: dict[str, str]
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return installed-file names and component ids owned by each feature role."""
    ownership: dict[str, set[str]] = {}
    component_sets: dict[str, set[str]] = {}
    for role in ("VersionFiles", "SharedRegistration"):
        feature = package.find(f"w:Feature[@Id='{role}']", NS)
        assert feature is not None and feature.attrib["AllowAbsent"] == "yes"
        references = {node.attrib["Id"] for node in feature.findall(".//w:ComponentRef", NS)}
        component_sets[role] = references
        members = set()
        for key in references:
            for file in components[key].findall("w:File", NS):
                source = Path(file.attrib["Source"])
                relative = (
                    "data/installation.json"
                    if source.name == "native-installation.json"
                    else source.relative_to(Path(source_path(stage))).as_posix()
                )
                if source.name != "native-installation.json":
                    assert digest(source) == owned[relative]
                members.add(relative)
        ownership[role] = members
    return ownership, component_sets


def assert_manager_components(root: Tree, components: dict[str, Element], shared: set[str], manager_id: str) -> None:
    manager_components = [
        node
        for key, node in components.items()
        if key in shared
        if any(file.attrib["Name"] == "cadrumo-manager" for file in node.findall("w:File", NS))
    ]
    # One stable destination has mutually exclusive scope-specific ownership.
    assert {node.attrib["Condition"] for node in manager_components} == {"NOT ALLUSERS", 'ALLUSERS = "1"'}
    for component in manager_components:
        machine = component.attrib["Condition"] != "NOT ALLUSERS"
        services = component.findall("w:ServiceInstall", NS)
        assert len(services) == int(machine)
        if machine:
            assert services[0].attrib["Name"] == manager_id
            assert services[0].attrib["Account"] == "LocalSystem"
            assert services[0].attrib["Start"] == "auto"
            assert services[0].attrib["Arguments"] == "--service"
            control = component.find("w:ServiceControl", NS)
            assert control is not None and control.attrib["Stop"] == "both" and control.attrib["Remove"] == "uninstall"
        file = component.find("w:File", NS)
        assert file is not None and file.attrib["KeyPath"] == ("yes" if machine else "no")


def assert_compiled_ownership_tables(build: Path, receipt: dict[str, Any]) -> None:
    for name in receipt["artifacts"]:
        compiled = build / "packages/msi" / name
        file_rows = table_rows(compiled, "SELECT `File`, `Component_` FROM `File`", 2)
        component_rows = table_rows(compiled, "SELECT `Component`, `Attributes`, `KeyPath` FROM `Component`", 3)
        assert len(file_rows) == len({row[0] for row in file_rows})
        counts = {row[0]: sum(file[1] == row[0] for file in file_rows) for row in component_rows}
        assert max(counts.values()) > 1
        keys = {
            row[0]: row[1:]
            for row in table_rows(compiled, "SELECT `Registry`, `Root`, `Component_` FROM `Registry`", 3)
        }
        files = {row[0]: row[1] for row in file_rows}
        for component, attributes, keypath in component_rows:
            if int(attributes) & 4:
                assert keys[keypath] == ("-1", component)
            else:
                assert files[keypath] == component


def change_database(artifact: Path, statement: str) -> None:
    """Apply one SQL statement to a compiled MSI through the Windows Installer API."""
    assert sys.platform == "win32"
    msi = ctypes.WinDLL("msi.dll", winmode=0x00000800)
    handle = ctypes.c_uint32
    for name, arguments in {
        "MsiOpenDatabaseW": [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.POINTER(handle)],
        "MsiDatabaseOpenViewW": [handle, ctypes.c_wchar_p, ctypes.POINTER(handle)],
        "MsiViewExecute": [handle, handle],
        "MsiDatabaseCommit": [handle],
        "MsiCloseHandle": [handle],
    }.items():
        function = getattr(msi, name)
        function.argtypes = arguments
        function.restype = handle
    database, view = handle(), handle()
    assert msi.MsiOpenDatabaseW(str(artifact), ctypes.c_void_p(1), ctypes.byref(database)) == 0
    try:
        assert msi.MsiDatabaseOpenViewW(database, statement, ctypes.byref(view)) == 0
        try:
            assert msi.MsiViewExecute(view, 0) == 0
        finally:
            msi.MsiCloseHandle(view)
        assert msi.MsiDatabaseCommit(database) == 0
    finally:
        msi.MsiCloseHandle(database)


def assert_changed_artifact_is_refused(
    build: Path, identity: Path, artifact: Path, unpublished: Path, adapter: Path, runner: Path
) -> None:
    original = artifact.read_bytes()
    artifact.write_bytes(original + b"changed")
    try:
        with pytest.raises(ValueError, match=r"MSI artifact has changed: application\.msi"):
            bootstrap_kit(build, identity, unpublished / "app", "cadrumo", adapter, runner)
        assert not unpublished.exists()
    finally:
        artifact.write_bytes(original)


def assert_modified_stage_is_refused(
    monkeypatch: pytest.MonkeyPatch, build: Path, identity: Path, wix: Path, adapter: Path, runner: Path
) -> None:
    published = {
        path: path.read_bytes()
        for directory in (build / "packages/msi", build / "installation/metadata/wix")
        for path in directory.iterdir()
        if path.is_file()
    }
    manager = build / "installation/stage/cadrumo-manager"
    original_manager = manager.read_bytes()

    def compiler_not_entered(wix: Path, arguments: list[str], cwd: Path) -> str:
        raise AssertionError("WiX must not run for a modified installation stage")

    manager.write_bytes(original_manager + b"changed")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(windows_msi_build, "run", compiler_not_entered)
            with pytest.raises(ValueError, match=r"^Staged installation file has changed: cadrumo-manager$"):
                compile_products(build, identity, wix, "cadrumo", adapter, runner)
        assert {path: path.read_bytes() for path in published} == published
    finally:
        manager.write_bytes(original_manager)


def assert_maintenance_plan_refusals(build: Path, identity: Path, prefix: Path, adapter: Path, runner: Path) -> None:
    """Invoke only requests the native runner refuses before any mutation."""
    plan = maintenance_plan(build, identity, "user", prefix, "cadrumo", adapter, runner)

    def run_plan(operation: str = "install", *arguments: str) -> str:
        result = run_command([str(runner), operation, "--plan", str(plan), *arguments], cwd=build)
        assert result.returncode != 0
        assert not prefix.exists()
        code = json.loads(result.stdout)["code"]
        assert isinstance(code, str)
        return code

    # Valid plans are installation-capable now. This development-host lane
    # invokes only requests that are refused before any native mutation.
    assert run_plan("remove-version", "--version", "../escape") == "invalid_release"
    # The plan is rewritten through its place in the build's own layout; the
    # runner location read from the environment never names a write target.
    published_plan = build / "installation/metadata/maintenance-user.json"
    assert published_plan.resolve() == plan.resolve()
    request = json.loads(published_plan.read_text(encoding="utf-8"))
    original_product = request["version_product"]["product_code"]
    request["version_product"]["product_code"] = "00000000-0000-0000-0000-000000000000"
    published_plan.write_text(json.dumps(request), encoding="utf-8")
    assert run_plan() == "invalid_plan"
    assert run_plan("unregister") == "invalid_plan"
    assert run_plan("remove-version", "--version", "0.5.1") == "invalid_plan"
    request["registration_product"]["product_code"] = request["version_product"]["product_code"]
    published_plan.write_text(json.dumps(request), encoding="utf-8")
    assert run_plan() == "artifact_or_owner_refused"
    assert run_plan("unregister") == "artifact_or_owner_refused"
    assert run_plan("remove-version", "--version", "0.5.1") == "artifact_or_owner_refused"
    request["version_product"]["product_code"] = original_product
    request["registration_product"]["product_code"] = original_product
    request["contract"]["installation_identity"]["channel"] = "another-channel"
    published_plan.write_text(json.dumps(request), encoding="utf-8")
    assert run_plan() == "artifact_or_owner_refused"


def assert_conditional_owner_is_refused(artifact: Path, conditional_msi: Path) -> None:
    # Alter the actual action table without a second compilation or install session.
    shutil.copyfile(artifact, conditional_msi)
    change_database(
        conditional_msi,
        "UPDATE `InstallExecuteSequence` SET `Condition` = 'NOT SKIP_OWNER' "
        "WHERE `Action` = 'CadrumoAuthenticateOwnerMachine'",
    )
    with pytest.raises(ValueError, match="owner authentication can be bypassed"):
        verify_admission_order(conditional_msi, owner_required=True)
