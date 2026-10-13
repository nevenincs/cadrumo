"""Inspect generated WiX ownership sources without installing or claiming native acceptance."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal
from uuid import UUID
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree

from dev.packaging.command_execution import run_command
from dev.packaging.native.distribution_prepare import refresh
from dev.packaging.native.hashing import digest
from dev.packaging.native.identity import DistributionIdentity
from dev.packaging.native.windows_msi import MAINTENANCE_GATE, _source_path, author, reject_combined_manager_msi
from dev.packaging.native.windows_msi_build import (
    bootstrap_kit,
    compile_products,
    maintenance_plan,
    verify_database,
    verify_products,
)
from dev.packaging.native.windows_msi_database import verify_admission_order, verify_feature_ownership
from dev.packaging.native.windows_msi_identity import msi_identity
from dev.packaging.tests.test_native_installation import payload_fixture

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
NS = {"w": "http://wixtoolset.org/schemas/v4/wxs"}


@pytest.mark.parametrize("count", [1600, 1601, 3201])
def test_msi_authoring_partitions_complete_mandatory_component_ownership(tmp_path: Path, count: int) -> None:
    from xml.etree.ElementTree import Element, SubElement, tostring

    from dev.packaging.native.windows_msi import _partition_features, _source

    _, identity = _prepared(tmp_path)
    value = DistributionIdentity(**json.loads(identity.read_text(encoding="utf-8")))
    files = {f"versions/{value.version}/payload/{index}.dll": "0" * 64 for index in range(count)}
    source = _source(
        tmp_path,
        files,
        value,
        "user",
        "version",
        "cadrumo-manager",
        None,
        ("unused", tmp_path / "unused", "0" * 64),
        "0" * 64,
    )
    package = ElementTree.fromstring(source).find("w:Package", NS)
    assert package is not None
    features = package.findall(".//w:Feature", NS)
    assert [len(feature.findall("w:ComponentRef", NS)) for feature in features] == [
        min(1600, count - offset) for offset in range(0, count, 1600)
    ]
    references = [reference.attrib["Id"] for feature in features for reference in feature.findall("w:ComponentRef", NS)]
    components = package.findall(".//w:Component", NS)
    assert len(set(references)) == count
    assert set(references) == {component.attrib["Id"] for component in components}
    for index, feature in enumerate(features):
        assert feature.attrib["InstallDefault"] == ("local" if index == 0 else "followParent")
        assert feature.attrib["Level"] == "1"
        assert feature.attrib["Display"] == "hidden"
        assert feature.attrib["AllowAbsent"] == feature.attrib["AllowAdvertise"] == "no"
    product = msi_identity(value, "user", "version")
    assert {component.attrib["Guid"] for component in components} == {
        product.component_code(f"payload/{index}.dll") for index in range(count)
    }
    feature = Element("Feature")
    ordered = [SubElement(feature, "ComponentRef", Id=f"C_{index}") for index in range(count)]
    existing = Element("Feature", Id="ExistingFeature")
    feature.insert(1, existing)
    _partition_features(feature)
    assert list(feature)[:2] == [ordered[0], existing]
    assert feature.findall("ComponentRef") == ordered[:1600]
    assert [
        reference for child in feature.findall("Feature") for reference in child.findall("ComponentRef")
    ] == ordered[1600:]
    grouped = tostring(feature)
    _partition_features(feature)
    assert tostring(feature) == grouped


@pytest.mark.parametrize("scope", ["user", "machine"])
def test_version_data_components_preserve_directory_inventory_and_binary_ownership(
    tmp_path: Path, scope: Literal["user", "machine"]
) -> None:
    from dev.packaging.native.windows_msi import _source

    _, identity = _prepared(tmp_path)
    value = DistributionIdentity(**json.loads(identity.read_text(encoding="utf-8")))
    names = (
        "data/a.json",
        "data/b.json",
        "other/c.json",
        "other/d.json",
        "data/native.dll",
        "data/native.pyd",
        "data/helper.exe",
        "cadrumo-manager",
        "cadrumo-desktop",
        "root.json",
    )
    members = {f"versions/{value.version}/{name}": "0" * 64 for name in names}

    def components(files: dict[str, str]) -> list[Element]:
        source = _source(
            tmp_path,
            files,
            value,
            scope,
            "version",
            "cadrumo-manager",
            "cadrumo-desktop",
            ("unused", tmp_path / "unused", "0" * 64),
            "0" * 64,
        )
        return ElementTree.fromstring(source).findall(".//w:Component", NS)

    authored = components(members)
    assert len(authored) == (8 if scope == "user" else 10)
    files = [file for component in authored for file in component.findall("w:File", NS)]
    assert len(files) == len({file.attrib["Id"] for file in files}) == len(members)
    product = msi_identity(value, scope, "version")
    assert {file.attrib["Id"] for file in files} == {
        "F_" + product.component_code(name).replace("-", "") for name in names
    }
    for component in authored:
        owned = component.findall("w:File", NS)
        if any(
            file.attrib["Name"] in {"native.dll", "native.pyd", "helper.exe", "cadrumo-manager", "cadrumo-desktop"}
            for file in owned
        ):
            assert len(owned) == 1
        if scope == "user":
            keys = component.findall("w:RegistryValue", NS)
            assert len(keys) == 1 and keys[0].attrib["Root"] == "HKCU" and keys[0].attrib["KeyPath"] == "yes"
            assert all(file.attrib["KeyPath"] == "no" for file in owned)
        else:
            assert len(owned) == 1 and owned[0].attrib["KeyPath"] == "yes"
    by_files = {
        tuple(file.attrib["Name"] for file in component.findall("w:File", NS)): component.attrib["Guid"]
        for component in authored
    }
    assert by_files == {
        tuple(file.attrib["Name"] for file in component.findall("w:File", NS)): component.attrib["Guid"]
        for component in components(dict(reversed(list(members.items()))))
    }
    if scope == "user":
        assert ("a.json", "b.json") in by_files and ("c.json", "d.json") in by_files
        assert by_files[("a.json", "b.json")] not in {
            product.component_code("data/a.json"),
            product.component_code("data/b.json"),
        }
        changed = dict(members)
        changed[f"versions/{value.version}/data/e.json"] = "0" * 64
        changed_ids = {component.attrib["Guid"] for component in components(changed)}
        assert by_files[("a.json", "b.json")] not in changed_ids
        assert by_files[("c.json", "d.json")] in changed_ids


@pytest.mark.parametrize("count", [32767, 32768])
def test_msi_component_costing_budget_accounts_for_registry_expansion(count: int) -> None:
    from dev.packaging.native.windows_msi_database import _verify_component_rows

    components: list[tuple[str, ...]] = [(f"C_{index}", "260", f"R_{index}") for index in range(count)]
    registry: list[tuple[str, ...]] = [(f"R_{index}", "1", f"C_{index}") for index in range(count)]
    if count == 32767:
        components.append(("C_File", "256", "F_File"))
        _verify_component_rows(components, registry)
    else:
        with pytest.raises(ValueError, match="component costing budget"):
            _verify_component_rows(components, registry)


@pytest.mark.parametrize(
    "fault", ["oversized", "detached", "unknown", "repeated", "cycle", "parent", "disabled", "advertised"]
)
def test_msi_feature_table_inventory_refuses_invalid_or_unselected_ownership(fault: str) -> None:
    from dev.packaging.native.windows_msi_database import _verify_feature_rows

    features: list[tuple[str, ...]] = [
        ("ProductFeature", "", "0", "1", "24"),
        ("PayloadFeature0001", "ProductFeature", "0", "1", "26"),
    ]
    components: list[tuple[str, ...]] = [(f"C_{index}",) for index in range(1601)]
    links: list[tuple[str, ...]] = [
        ("ProductFeature" if index < 1600 else "PayloadFeature0001", component[0])
        for index, component in enumerate(components)
    ]
    _verify_feature_rows(features, components, links)
    if fault == "oversized":
        links[-1] = ("ProductFeature", components[-1][0])
    elif fault == "detached":
        links.pop()
    elif fault == "unknown":
        links[-1] = ("foreign", components[-1][0])
    elif fault == "repeated":
        links[-1] = ("PayloadFeature0001", components[0][0])
    elif fault in {"cycle", "parent"}:
        features[1] = ("PayloadFeature0001", "PayloadFeature0001" if fault == "cycle" else "foreign", "0", "1", "26")
    else:
        features[1] = (
            "PayloadFeature0001",
            "ProductFeature",
            "0",
            "0" if fault == "disabled" else "1",
            "22" if fault == "advertised" else "26",
        )
    with pytest.raises(ValueError, match=r"MSI feature|MSI components"):
        _verify_feature_rows(features, components, links)


@pytest.mark.parametrize("unicode_name", [False, True])
def test_msi_destination_budget_counts_absolute_utf16_units(unicode_name: bool) -> None:
    from dev.packaging.native.windows_msi import verify_destination_lengths

    prefix = PureWindowsPath("C:/product")
    stem = "\U0001f600" * 120 if unicode_name else "a" * 240
    available = 259 - len(str(prefix)) - 1
    filename = stem + "a" * (available - len(stem.encode("utf-16-le")) // 2)
    verify_destination_lengths(prefix, [filename])
    with pytest.raises(ValueError, match="259 UTF-16"):
        verify_destination_lengths(prefix, [filename + "a"])


@pytest.mark.parametrize("relative", ["../outside", "/outside", "C:/outside", "a\\b"])
def test_msi_destination_budget_refuses_escape(relative: str) -> None:
    from dev.packaging.native.windows_msi import verify_destination_lengths

    with pytest.raises(ValueError, match="relative"):
        verify_destination_lengths(PureWindowsPath("C:/product"), [relative])


def test_msi_authoring_refuses_default_destination_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dev.packaging.native import windows_msi

    build, identity = _prepared(tmp_path)
    directory = build / "installation/metadata/wix"
    oversized = PureWindowsPath("C:/" + "a" * 245)
    monkeypatch.setattr(windows_msi, "default_installation_prefixes", lambda _: (oversized, oversized))
    with pytest.raises(ValueError, match="259 UTF-16"):
        author(build, identity, "cadrumo")
    assert not directory.exists()


def test_msi_maintenance_plan_refuses_selected_destination_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dev.packaging.native import windows_msi_build

    build, identity = _prepared(tmp_path)
    author(build, identity, "cadrumo")
    owned = build / "installation/metadata/wix"
    before = {path.name: path.read_bytes() for path in owned.iterdir() if path.is_file()}

    def not_entered(*_: object) -> None:
        raise AssertionError("Artifact verification may author files and must follow destination admission")

    monkeypatch.setattr(windows_msi_build, "verify_products", not_entered)
    prefix = tmp_path / ("a" * 245)
    with pytest.raises(ValueError, match="259 UTF-16"):
        maintenance_plan(build, identity, "user", prefix, "cadrumo")
    assert not (build / "installation/metadata/maintenance-user.json").exists()
    assert not prefix.exists()
    assert before == {path.name: path.read_bytes() for path in owned.iterdir() if path.is_file()}


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="Requires native Windows known folders")
def test_msi_default_prefixes_use_native_known_folders(monkeypatch: pytest.MonkeyPatch) -> None:
    from win32com.shell import shell, shellcon

    from dev.packaging.native.windows_msi import default_installation_prefixes

    monkeypatch.setenv("LOCALAPPDATA", "C:/foreign")
    monkeypatch.setenv("ProgramFiles", "C:/foreign")
    assert default_installation_prefixes("CADRUMO") == (
        PureWindowsPath(shell.SHGetKnownFolderPath(shellcon.FOLDERID_LocalAppData, 0, None)) / "CADRUMO",
        PureWindowsPath(shell.SHGetKnownFolderPath(shellcon.FOLDERID_ProgramFilesX64, 0, None)) / "CADRUMO",
    )


@pytest.mark.parametrize(
    ("origin", "owner", "function", "line"),
    [
        (
            r"C:\private\package\cadrumo\adapters\local_runtime\windows_native_io.py:146:finish_windows_io",
            "windows_native_io",
            "finish_windows_io",
            146,
        ),
        (
            "/private/cadrumo/adapters/local_runtime/windows_native_io.py:133:windows_deadline_milliseconds",
            "windows_native_io",
            "windows_deadline_milliseconds",
            133,
        ),
        ("cadrumo/adapters/local_runtime/windows_channel.py:167:read_exact", "windows_channel", "read_exact", 167),
        ("cadrumo/adapters/local_runtime/windows_channel.py:203:write_all", "windows_channel", "write_all", 203),
        (r"C:\private\python\Lib\site-packages\filelock\_api.py:1054:acquire", "filelock_api", "acquire", 1054),
        (
            "cadrumo/application/runtime/deadline_budget.py:51:remaining_budget",
            "deadline_budget",
            "remaining_budget",
            51,
        ),
    ],
)
def test_lifecycle_runtime_fault_origin_keeps_only_known_coordinates(
    tmp_path: Path, origin: str, owner: str, function: str, line: int
) -> None:
    from dev.runtime_lifecycle.tests.evidence import runtime_faults

    path = tmp_path / "faults.log"
    path.write_text(
        "event | "
        + json.dumps({"error_type": "TimeoutError", "error_origin": origin, "password": "private-test-secret"})
        + "\n"
    )
    assert runtime_faults(path) == [
        {"error_type": "TimeoutError", "origin_owner": owner, "origin_function": function, "origin_line": line}
    ]
    assert "private" not in json.dumps(runtime_faults(path))


@pytest.mark.parametrize(
    "origin",
    [
        None,
        42,
        "private exception",
        "private.py:1:acquire",
        "windows_channel.py:1:read_exact",
        "cadrumo/adapters/local_runtime/windows_channel.py:1:private_function",
        "filelock/_api.py:0:acquire",
        "filelock/_api.py:-1:acquire",
        "filelock/_api.py:1000001:acquire",
        "filelock/_api.py:\u0661:acquire",
        "filelock/_api.py:1.5:acquire",
        "x" * 513 + "/filelock/_api.py:1:acquire",
    ],
)
def test_lifecycle_runtime_fault_origin_omits_unknown_malformed_or_unbounded_values(
    tmp_path: Path, origin: object
) -> None:
    from dev.runtime_lifecycle.tests.evidence import runtime_faults

    path = tmp_path / "faults.log"
    path.write_text("event | " + json.dumps({"error_type": "TimeoutError", "error_origin": origin}) + "\n")
    assert runtime_faults(path) == [{"error_type": "TimeoutError"}]


def test_lifecycle_runtime_fault_export_bounds_tail_types_and_fact_count(tmp_path: Path) -> None:
    from dev.runtime_lifecycle.tests.evidence import runtime_faults

    path = tmp_path / "faults.log"
    assert runtime_faults(path) == []
    rows = [
        "event | " + json.dumps({"error_type": "EarlyError"}) + "\n",
        "x" * 32768 + "\n",
        "event | broken\n",
        "event | []\n",
    ]
    rows.extend(
        "event | " + json.dumps({"error_type": value}) + "\n" for value in ("private message", "érror", "x" * 129, 42)
    )
    rows.extend("event | " + json.dumps({"error_type": f"Fault{index}"}) + "\n" for index in range(15))
    path.write_text("".join(rows))
    assert runtime_faults(path) == [{"error_type": f"Fault{index}"} for index in range(3, 15)]


def test_lifecycle_failure_evidence_retains_only_bounded_public_driver_facts(tmp_path: Path) -> None:
    from dev.runtime_lifecycle.tests.evidence import manager_evidence

    path = tmp_path / "events.jsonl"
    event = {
        "kind": "driver_failed",
        "pid": 42,
        "seconds": 1.5,
        "manager_status": "unavailable",
        "error_kind": "PermissionDenied",
        "raw_native_code": 5,
        "reason": "driver_io_failure",
        "stage": "supervision",
        "password": "private",
        "message": "private path",
        "profile_id": "private",
    }
    path.write_text((json.dumps(event) + "\n") * 80 + '{"kind": "ready"}', encoding="utf-8")
    evidence = manager_evidence(path)
    assert len(evidence["events"]) == 64
    assert evidence["events"][-1] == {
        key: value
        for key, value in event.items()
        if key
        not in (
            "password",
            "message",
            "profile_id",
        )
    }
    assert "private" not in json.dumps(evidence)


def test_lifecycle_failure_evidence_discards_partial_utf8_and_untrusted_fields(tmp_path: Path) -> None:
    from dev.runtime_lifecycle.tests.evidence import manager_evidence

    path = tmp_path / "events.jsonl"
    path.write_bytes(
        b"x" * 65537
        + b"\xc3\n"
        + json.dumps(
            {
                "kind": "driver_failed",
                "error_kind": {"private": "data"},
                "manager_status": [],
                "raw_native_code": True,
                "seconds": float("nan"),
                "stage": "private",
            }
        ).encode()
        + b"\n"
        + b"{invalid}\n"
        + b'{"kind": []}\n'
    )
    evidence = manager_evidence(path)
    assert evidence["tail_bounded"] is True
    assert evidence["events"] == [{"kind": "driver_failed"}]
    assert evidence["invalid_lines"] == 2


def test_lifecycle_failure_evidence_records_read_refusal_without_private_paths(tmp_path: Path) -> None:
    from dev.runtime_lifecycle.tests.evidence import manager_evidence

    assert manager_evidence(tmp_path / "absent") == {"events": [], "observation": "absent"}
    refused = manager_evidence(tmp_path)
    assert refused["observation"] == "read_failed"
    assert isinstance(refused["error_type"], str)
    assert str(tmp_path) not in json.dumps(refused)


@pytest.mark.parametrize("sequences", [(1, 1), (2, 1), (None,), (True,), (0,), (2**64,)])
def test_lifecycle_event_history_refuses_missing_duplicate_or_noncanonical_sequence(
    tmp_path: Path, sequences: tuple[int | None, ...]
) -> None:
    from dev.runtime_lifecycle.harness import LifecycleHarness

    path = tmp_path / "manager-events.jsonl"
    path.write_text("".join(json.dumps({"kind": "ready", "sequence": value}) + "\n" for value in sequences))
    instance = LifecycleHarness(tmp_path / "manager.exe", tmp_path / "package", tmp_path)
    with pytest.raises(RuntimeError, match="strictly increasing canonical sequence"):
        instance.events()


def test_lifecycle_event_history_preserves_actual_sequence_and_separate_driver_failure(tmp_path: Path) -> None:
    from dev.runtime_lifecycle.harness import LifecycleHarness
    from dev.runtime_lifecycle.tests.evidence import manager_evidence

    events = [
        {"kind": "launched", "sequence": 3},
        {"kind": "ready", "sequence": 7},
        {"kind": "driver_failed", "reason": "effects_unsettled"},
    ]
    path = tmp_path / "manager-events.jsonl"
    path.write_text("".join(json.dumps(event) + "\n" for event in events) + '{"kind": "ready"')
    instance = LifecycleHarness(tmp_path / "manager.exe", tmp_path / "package", tmp_path)
    assert instance.events() == events
    assert manager_evidence(path)["events"] == events


@pytest.mark.parametrize(
    "events",
    [
        [{"kind": "driver_failed", "sequence": 2}],
        [{"kind": "driver_failed", "sequence": None}],
        [{"kind": "driver_failed"}, {"kind": "ready", "sequence": 3}],
        [{"kind": "driver_failed"}, {"kind": "driver_failed"}],
    ],
)
def test_lifecycle_event_history_refuses_fabricated_or_nonterminal_driver_failure(
    tmp_path: Path, events: list[dict[str, object]]
) -> None:
    from dev.runtime_lifecycle.harness import LifecycleHarness

    (tmp_path / "manager-events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    instance = LifecycleHarness(tmp_path / "manager.exe", tmp_path / "package", tmp_path)
    with pytest.raises(RuntimeError, match=r"canonical sequence|after the terminal"):
        instance.events()


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (PureWindowsPath("C:/build/payload/file.bin"), "\\\\?\\C:\\build\\payload\\file.bin"),
        (PureWindowsPath("//server/share/payload/file.bin"), "\\\\?\\UNC\\server\\share\\payload\\file.bin"),
        (PureWindowsPath("\\\\?\\C:\\build\\file.bin"), "\\\\?\\C:\\build\\file.bin"),
        (PureWindowsPath("\\\\?\\UNC\\server\\share\\file.bin"), "\\\\?\\UNC\\server\\share\\file.bin"),
        (PurePosixPath("/portable/fixture/file.bin"), "/portable/fixture/file.bin"),
    ],
)
def test_wix_source_paths_preserve_native_local_unc_and_existing_extended_paths(
    source: PureWindowsPath | PurePosixPath, expected: str
) -> None:
    assert _source_path(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "relative/file",
        "C:relative",
        "C:/root/../file",
        "//./PhysicalDrive0",
        "//?/GLOBALROOT/device",
        "C:/$(env.SECRET)/file",
    ],
)
def test_wix_source_paths_refuse_ambiguous_or_interpreted_paths(source: str) -> None:
    with pytest.raises(ValueError):
        _source_path(PureWindowsPath(source))


@pytest.mark.parametrize("desktop", [True, False])
def test_registration_description_matches_authored_resources(tmp_path: Path, desktop: bool) -> None:
    build, identity = _prepared(tmp_path, desktop=desktop)
    outputs = author(build, identity, "cadrumo" if desktop else None)
    for scope in ("user", "machine"):
        tree = ElementTree.parse(outputs[f"{scope}-registration.wxs"])
        property_node = tree.find(".//w:Property[@Id='CadrumoRegistration']", NS)
        assert property_node is not None
        description = json.loads(property_node.attrib["Value"])
        assert description["scope"] == scope
        assert description["schema"] == 2
        assert len(description["services"]) == int(scope == "machine")
        components = tree.findall(".//w:Component", NS)
        assert description["components"] == [item.attrib["Guid"] for item in components]
        actual_registry = [
            {
                "component": component.attrib["Guid"],
                **{key.lower(): entry.attrib[key] for key in ("Key", "Name", "Type", "Value")},
            }
            for component in components
            for entry in component.findall("w:RegistryValue", NS)
        ]
        assert description["registry"] == actual_registry
        assert len(description["files"]) == 4
        for file in tree.findall(".//w:File", NS):
            expected = digest(Path(file.attrib["Source"]))
            assert expected in description["files"].values()
        marker = next(path for path in description["files"] if path.endswith("installation.json"))
        assert description["files"][marker] == digest(build / "installation/metadata/wix/native-installation.json")
        assert bool(description["shortcuts"]) == desktop
        assert bool(description["absent_shortcuts"]) != desktop
        assert {entry["name"] for entry in description["absent_registry"]} == (
            set() if desktop else {"DesktopRegistered", "DesktopAnchorVersion"}
        )
        version = ElementTree.parse(outputs[f"{scope}-version.wxs"])
        assert version.find(".//w:Property[@Id='CadrumoRegistration']", NS) is None


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
            service = root.find(".//w:ServiceInstall", NS)
            control = root.find(".//w:ServiceControl", NS)
            if role == "registration" and scope == "machine":
                assert service is not None and control is not None
                assert service.attrib["Name"] == value["manager_id"]
                assert service.attrib["Account"] == "LocalSystem"
                assert service.attrib["Start"] == "auto"
                assert service.attrib["Type"] == "ownProcess"
                assert service.attrib["Arguments"] == "--service"
                assert control.attrib["Start"] == "install"
                assert control.attrib["Stop"] == "both"
                assert control.attrib["Remove"] == "uninstall"
            else:
                assert service is None and control is None
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
                    assert native_marker.pop("launch_policy") == "native"
                    assert portable_marker.pop("launch_policy") == "portable"
                    assert native_marker == portable_marker
                else:
                    relative = source.relative_to(Path(_source_path(stage))).as_posix()
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
                login = [item for item in registry if item.attrib["Key"].endswith("\\CurrentVersion\\Run")]
                if scope == "user":
                    assert len(login) == 1
                    assert login[0].attrib["Value"] == '"[INSTALL_ROOT]cadrumo-manager" --sign-in'
                else:
                    assert not login
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


def test_cached_owner_protocol_binds_native_identity_and_publication_for_owned_installation(tmp_path: Path) -> None:
    build, identity = _prepared(tmp_path)
    adapter = tmp_path / "installer.dll"
    runner = tmp_path / "maintenance.exe"
    adapter.write_bytes(b"authoring fixture")
    runner.write_bytes(b"authoring fixture, never executed")
    outputs = author(build, identity, "cadrumo", adapter, runner)
    value = DistributionIdentity(**json.loads(identity.read_text(encoding="utf-8")))
    for scope in ("user", "machine"):
        for role in ("version", "registration"):
            package = ElementTree.parse(outputs[f"{scope}-{role}.wxs"]).find("w:Package", NS)
            assert package is not None
            metadata = package.find("w:Property[@Id='CadrumoOwner']", NS)
            assert metadata is not None
            assert json.loads(metadata.attrib["Value"]) == {
                "schema": 2,
                "scope": scope,
                "product_code": msi_identity(value, scope, role).product_code,
                "role": role,
                "runner_sha256": digest(runner),
                "identity": {
                    "application_id": value.application_id,
                    "channel": value.channel,
                    "platform": "windows-x64",
                },
                "publication": "data/installation-state",
            }
            launch = package.find("w:Launch", NS)
            assert launch is not None and launch.attrib["Condition"] == "1"
            for name in ("CadrumoPrepareOwner", "CadrumoAuthenticateOwner"):
                action = package.find(f"w:CustomAction[@Id='{name}']", NS)
                assert action is not None and action.attrib["Return"] == "check"
                sequence = package.find(f"w:InstallExecuteSequence/w:Custom[@Action='{name}']", NS)
                assert sequence is not None and "Condition" not in sequence.attrib


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


@pytest.mark.parametrize("defect", ["blocked", "missing-owner", "conditional-owner", "ignore-failure"])
def test_database_verifier_refuses_broken_native_owner_admission(tmp_path: Path, defect: str) -> None:
    build, identity = _prepared(tmp_path)
    adapter = tmp_path / "installer.dll"
    runner = tmp_path / "maintenance.exe"
    adapter.write_bytes(b"authoring fixture")
    runner.write_bytes(b"authoring fixture, never executed")
    source = author(build, identity, "cadrumo", adapter, runner)["machine-version.wxs"]
    tree = ElementTree.parse(source)
    package = tree.find("w:Package", NS)
    assert package is not None
    if defect == "blocked":
        launch = package.find("w:Launch", NS)
        assert launch is not None
        launch.set("Condition", "0")
    elif defect == "ignore-failure":
        action = package.find("w:CustomAction[@Id='CadrumoAuthenticateOwner']", NS)
        assert action is not None
        action.set("Return", "ignore")
    else:
        sequence = package.find("w:InstallExecuteSequence", NS)
        assert sequence is not None
        action = sequence.find("w:Custom[@Action='CadrumoAuthenticateOwner']", NS)
        assert action is not None
        if defect == "missing-owner":
            sequence.remove(action)
        else:
            action.set("Condition", "NOT SKIP_OWNER")
    database = tmp_path / "database.wxs"
    tree.write(database, encoding="utf-8")
    with pytest.raises(ValueError, match=r"native installation gate|native owner authentication|native admission"):
        verify_database(source, database)


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
def test_native_admission_dll_is_embedded_in_all_four_verified_products(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dev.packaging.native import windows_msi_build

    wix = shutil.which("wix")
    assert wix is not None, "Put the configured WiX compiler on PATH"
    configured = os.environ.get("CADRUMO_TEST_MSI_ADAPTER")
    assert configured is not None and configured, "Set CADRUMO_TEST_MSI_ADAPTER to the CMake rust_installer output"
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
    from dev.packaging.native.windows_msi_database import _table_rows

    for name in receipt["artifacts"]:
        compiled = build / "packages/msi" / name
        file_rows = _table_rows(compiled, "SELECT `File`, `Component_` FROM `File`", 2)
        component_rows = _table_rows(compiled, "SELECT `Component`, `Attributes`, `KeyPath` FROM `Component`", 3)
        assert len(file_rows) == len({row[0] for row in file_rows})
        counts = {row[0]: sum(file[1] == row[0] for file in file_rows) for row in component_rows}
        if name == "user-version.msi":
            assert max(counts.values()) > 1
            keys = {
                row[0]: row[1:]
                for row in _table_rows(compiled, "SELECT `Registry`, `Root`, `Component_` FROM `Registry`", 3)
            }
            assert all(
                int(attributes) & 4 and keys[keypath] == ("1", component)
                for component, attributes, keypath in component_rows
            )
        else:
            assert max(counts.values()) == 1
    artifact = build / "packages/msi/user-version.msi"
    # Alter the real compiled feature table, without installing or recompiling.
    # Artifact hash checks alone cannot prove mandatory component selection.
    import ctypes

    disabled = tmp_path / "disabled-feature.msi"
    shutil.copyfile(artifact, disabled)
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
    assert msi.MsiOpenDatabaseW(str(disabled), ctypes.c_void_p(1), ctypes.byref(database)) == 0
    try:
        assert (
            msi.MsiDatabaseOpenViewW(
                database, "UPDATE `Feature` SET `Level` = 0 WHERE `Feature` = 'ProductFeature'", ctypes.byref(view)
            )
            == 0
        )
        try:
            assert msi.MsiViewExecute(view, 0) == 0
        finally:
            msi.MsiCloseHandle(view)
        assert msi.MsiDatabaseCommit(database) == 0
    finally:
        msi.MsiCloseHandle(database)
    with pytest.raises(ValueError, match="can be deselected"):
        verify_feature_ownership(disabled)
    original = artifact.read_bytes()
    unpublished = tmp_path / "unpublished"
    artifact.write_bytes(original + b"changed")
    try:
        with pytest.raises(ValueError, match=r"MSI artifact has changed: user-version\.msi"):
            bootstrap_kit(build, identity, unpublished / "app", "cadrumo", adapter, runner)
        assert not unpublished.exists()
    finally:
        artifact.write_bytes(original)
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
            patch.setattr(windows_msi_build, "_run", compiler_not_entered)
            with pytest.raises(ValueError, match=r"^Staged installation file has changed: cadrumo-manager$"):
                compile_products(build, identity, Path(wix), "cadrumo", adapter, runner)
        assert {path: path.read_bytes() for path in published} == published
    finally:
        manager.write_bytes(original_manager)
    prefix = tmp_path / "never installed"
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
    request = json.loads(plan.read_text(encoding="utf-8"))
    request["version_product"], request["registration_product"] = (
        request["registration_product"],
        request["version_product"],
    )
    plan.write_text(json.dumps(request), encoding="utf-8")
    assert run_plan() == "artifact_or_owner_refused"
    assert run_plan("unregister") == "artifact_or_owner_refused"
    assert run_plan("remove-version", "--version", "0.5.1") == "artifact_or_owner_refused"
    request["version_product"], request["registration_product"] = (
        request["registration_product"],
        request["version_product"],
    )
    request["contract"]["installation_identity"]["channel"] = "another-channel"
    plan.write_text(json.dumps(request), encoding="utf-8")
    assert run_plan() == "artifact_or_owner_refused"
    # Read the actual conditional action row in a deliberately broken MSI;
    # compilation and database inspection create no installation session.
    source = build / "installation/metadata/wix/machine-version.wxs"
    tree = ElementTree.parse(source)
    action = tree.find("w:Package/w:InstallExecuteSequence/w:Custom[@Action='CadrumoAuthenticateOwner']", NS)
    assert action is not None
    action.set("Condition", "NOT SKIP_OWNER")
    conditional_source = tmp_path / "conditional.wxs"
    tree.write(conditional_source, encoding="utf-8")
    conditional_msi = tmp_path / "conditional.msi"
    result = run_command(
        [str(wix), "build", "-arch", "x64", "-wx", "-o", str(conditional_msi), str(conditional_source)], cwd=build
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with pytest.raises(ValueError, match="can be skipped by a condition"):
        verify_admission_order(conditional_msi, owner_required=True)
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


@pytest.mark.parametrize(
    "defect",
    [
        "identity",
        "gate",
        "version-removal",
        "registration-upgrade",
        "registration-missing",
        "registration-changed",
        "version-registration",
    ],
)
def test_database_verifier_rejects_ownership_regressions(tmp_path: Path, defect: str) -> None:
    build, identity = _prepared(tmp_path)
    sources = author(build, identity, "cadrumo")
    role = "registration" if defect.startswith("registration-") else "version"
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
    elif defect == "registration-upgrade":
        content = content.replace("MajorUpgrade", "MissingUpgrade")
    elif defect == "registration-missing":
        content = content.replace('Id="CadrumoRegistration"', 'Id="MissingRegistration"')
    elif defect == "registration-changed":
        content = content.replace('Id="CadrumoRegistration" Value="', 'Id="CadrumoRegistration" Value="changed')
    else:
        content = content.replace("</Package>", '<Property Id="CadrumoRegistration" Value="{}" /></Package>')
    database.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        verify_database(source, database)


@pytest.mark.parametrize(
    ("defect", "replacement"),
    [
        ("ServiceInstall", "MissingServiceInstall"),
        ("ServiceControl", "MissingServiceControl"),
        ('Start="auto"', 'Start="demand"'),
        ('Account="LocalSystem"', 'Account="LocalService"'),
        ('Arguments="--service"', 'Arguments="--retry"'),
    ],
)
def test_database_verifier_refuses_missing_or_altered_machine_service(
    tmp_path: Path, defect: str, replacement: str
) -> None:
    build, identity = _prepared(tmp_path)
    source = author(build, identity, "cadrumo")["machine-registration.wxs"]
    database = tmp_path / "machine.wxs"
    content = source.read_text(encoding="utf-8")
    database.write_text(content, encoding="utf-8")
    verify_database(source, database)
    database.write_text(content.replace(defect, replacement), encoding="utf-8")
    with pytest.raises(ValueError, match="Service"):
        verify_database(source, database)


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="Requires the native Windows MSI validator")
def test_native_wix_cabinets_preserve_long_source_bytes_and_install_destinations(tmp_path: Path) -> None:
    wix = shutil.which("wix")
    assert wix is not None, "Put a configured WiX 5 or newer tool on PATH for the native compiler lane"
    source_root = tmp_path.joinpath(*(["long-source-directory" * 2] * 4))
    source_root.mkdir(parents=True)
    build, identity = _prepared(source_root)
    payload = identity.parent / "payload"
    relative = "cabinet/complete-inventory-member.bin"
    original = payload / relative
    original.parent.mkdir(parents=True)
    original.write_bytes(b"long source cabinet integrity fixture")
    manifest_path = payload / "data/package-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][relative] = digest(original)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    refresh(payload, identity, build, "cadrumo")
    sources = author(build, identity, "cadrumo")
    source = sources["machine-version.wxs"]
    authored = ElementTree.parse(source)
    long_file = next(item for item in authored.findall(".//w:File", NS) if item.attrib["Name"] == original.name)
    actual_source = Path(long_file.attrib["Source"])
    assert len(str(actual_source)) > 260
    assert str(actual_source).startswith("\\\\?\\")
    expected_digest = digest(actual_source)
    artifact = tmp_path / "long-source.msi"
    compiled = run_command([wix, "build", "-arch", "x64", "-wx", "-o", str(artifact), str(source)], cwd=tmp_path)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    exported = tmp_path / "exported"
    database = tmp_path / "long-source.wxs"
    decompiled = run_command(
        [wix, "msi", "decompile", "-x", str(exported), "-o", str(database), str(artifact)], cwd=tmp_path
    )
    assert decompiled.returncode == 0, decompiled.stdout + decompiled.stderr
    verify_database(source, database)
    observed = ElementTree.parse(database)
    installed_file = observed.find(f".//w:File[@Id='{long_file.attrib['Id']}']", NS)
    assert installed_file is not None and installed_file.attrib["Name"] == original.name
    original_directories = {item.attrib["Id"]: item.attrib["Name"] for item in authored.findall(".//w:Directory", NS)}
    observed_directories = {item.attrib["Id"]: item.attrib["Name"] for item in observed.findall(".//w:Directory", NS)}
    assert original_directories.items() <= observed_directories.items()
    assert any(digest(path) == expected_digest for path in exported.rglob("*") if path.is_file())
    assert digest(actual_source) == expected_digest == digest(original)


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
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert artifact.is_file() and artifact.stat().st_size > 0
        decompiled = artifact.with_suffix(".wxs")
        result = run_command([wix, "msi", "decompile", "-o", str(decompiled), str(artifact)], cwd=tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        database = ElementTree.parse(decompiled)
        package = database.find("w:Package", NS)
        assert package is not None
        original = ElementTree.parse(source).find("w:Package", NS)
        assert original is not None
        assert UUID(package.attrib["ProductCode"]) == UUID(original.attrib["ProductCode"])
        verify_database(source, decompiled)
        launch = database.find(".//w:Launch", NS)
        assert launch is not None and launch.attrib == {"Condition": "0", "Message": MAINTENANCE_GATE}
        if "version" in source.stem:
            assert database.find(".//w:MajorUpgrade", NS) is None
            assert database.find(".//w:RemoveExistingProducts", NS) is None
        else:
            assert database.find(".//w:MajorUpgrade", NS) is not None
