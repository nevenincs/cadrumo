"""Inspect generated WiX ownership sources without installing or claiming native acceptance."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import UUID

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

from .test_native_installation import payload_fixture

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
def test_version_data_components_preserve_directory_inventory_and_binary_ownership(tmp_path: Path, scope: str) -> None:
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

    def components(files: dict[str, str]) -> list:
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

    components = [(f"C_{index}", "260", f"R_{index}") for index in range(count)]
    registry = [(f"R_{index}", "1", f"C_{index}") for index in range(count)]
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

    features = [("ProductFeature", "", "0", "1", "24"), ("PayloadFeature0001", "ProductFeature", "0", "1", "26")]
    components = [(f"C_{index}",) for index in range(1601)]
    links = [
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
    from dev.runtime_lifecycle.tests.conftest import _runtime_faults

    path = tmp_path / "faults.log"
    path.write_text(
        "event | "
        + json.dumps({"error_type": "TimeoutError", "error_origin": origin, "password": "private-test-secret"})
        + "\n"
    )
    assert _runtime_faults(path) == [
        {"error_type": "TimeoutError", "origin_owner": owner, "origin_function": function, "origin_line": line}
    ]
    assert "private" not in json.dumps(_runtime_faults(path))


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
    from dev.runtime_lifecycle.tests.conftest import _runtime_faults

    path = tmp_path / "faults.log"
    path.write_text("event | " + json.dumps({"error_type": "TimeoutError", "error_origin": origin}) + "\n")
    assert _runtime_faults(path) == [{"error_type": "TimeoutError"}]


def test_lifecycle_runtime_fault_export_bounds_tail_types_and_fact_count(tmp_path: Path) -> None:
    from dev.runtime_lifecycle.tests.conftest import _runtime_faults

    path = tmp_path / "faults.log"
    assert _runtime_faults(path) == []
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
    assert _runtime_faults(path) == [{"error_type": f"Fault{index}"} for index in range(3, 15)]


def test_lifecycle_failure_evidence_retains_only_bounded_public_driver_facts(tmp_path: Path) -> None:
    from dev.runtime_lifecycle.tests.conftest import _manager_evidence

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
    evidence = _manager_evidence(path)
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
    from dev.runtime_lifecycle.tests.conftest import _manager_evidence

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
    evidence = _manager_evidence(path)
    assert evidence["tail_bounded"] is True
    assert evidence["events"] == [{"kind": "driver_failed"}]
    assert evidence["invalid_lines"] == 2


def test_lifecycle_failure_evidence_records_read_refusal_without_private_paths(tmp_path: Path) -> None:
    from dev.runtime_lifecycle.tests.conftest import _manager_evidence

    assert _manager_evidence(tmp_path / "absent") == {"events": [], "observation": "absent"}
    refused = _manager_evidence(tmp_path)
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
    from dev.runtime_lifecycle.tests.conftest import _manager_evidence

    events = [
        {"kind": "launched", "sequence": 3},
        {"kind": "ready", "sequence": 7},
        {"kind": "driver_failed", "reason": "effects_unsettled"},
    ]
    path = tmp_path / "manager-events.jsonl"
    path.write_text("".join(json.dumps(event) + "\n" for event in events) + '{"kind": "ready"')
    instance = LifecycleHarness(tmp_path / "manager.exe", tmp_path / "package", tmp_path)
    assert instance.events() == events
    assert _manager_evidence(path)["events"] == events


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
    build, identity = _prepared(tmp_path)
    payload = identity.parent / "payload"
    relative = "/".join(["long-source"] * 15 + ["complete-inventory-member.bin"])
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


@pytest.mark.parametrize(
    ("hardware", "native_uuid", "reason"),
    [
        (("QEMU", "CadrumoRuntimeGuest"), "00000000-0000-0000-0000-000000000001", "UUID differs"),
        (("QEMU", "UnselectedModel"), "8fdaec56-4e89-4602-9d44-43053b6a7771", "pinned native QEMU"),
        (("DeveloperMachine", "Workstation"), "8fdaec56-4e89-4602-9d44-43053b6a7771", "pinned native QEMU"),
    ],
)
def test_installed_guest_policy_refuses_unselected_native_hardware_before_any_maintenance(
    monkeypatch: pytest.MonkeyPatch, hardware: tuple[str, str], native_uuid: str, reason: str
) -> None:
    """Policy-only unit evidence: no installation or service operations occur."""
    from types import SimpleNamespace

    import win32com.client

    from cadrumo.core.storage_environment import STORAGE_ROOT
    from dev.runtime_lifecycle.installed import require_installation_guest

    for variable in STORAGE_ROOT.precedence:
        monkeypatch.delenv(variable, raising=False)
    system = SimpleNamespace(Manufacturer=hardware[0], Model=hardware[1])
    product = SimpleNamespace(UUID=native_uuid)
    wmi = SimpleNamespace(ExecQuery=lambda query: [product] if "SystemProduct" in query else [system])
    monkeypatch.setattr(win32com.client, "GetObject", lambda _: wmi)
    with pytest.raises(ValueError, match=reason):
        require_installation_guest(
            UUID("8fdaec56-4e89-4602-9d44-43053b6a7771"), "S-1-5-21-1-2-3-1001", "user", guest_kind="qemu", fresh=False
        )


@pytest.mark.windows_only
def test_installed_guest_policy_refuses_storage_override_before_native_vm_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cadrumo.core.storage_environment import STORAGE_ROOT
    from dev.runtime_lifecycle.installed import require_installation_guest

    monkeypatch.setenv(STORAGE_ROOT.variable, "C:/developer/private-storage")
    with pytest.raises(ValueError, match="refuses storage overrides"):
        require_installation_guest(UUID(int=1), "S-1-5-21-1-2-3-1001", "user", guest_kind="qemu")


@pytest.mark.windows_only
@pytest.mark.parametrize("channel", ["stable", "preview"])
@pytest.mark.parametrize(
    "defect",
    [
        None,
        "different_root",
        "development_alias",
        "base_spoof",
        "missing_build",
        "development_build",
        "missing_bootstrap",
        "damaged_package",
        "foreign_channel",
        "missing_channel",
        "channel_destination_mismatch",
    ],
)
def test_installed_canonical_pin_requires_native_default_and_shipping_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, defect: str | None, channel: str
) -> None:
    """Native observations are policy fixtures, not guest authentication evidence."""
    from types import ModuleType

    from win32com.shell import shell

    from cadrumo.core.storage_environment import STORAGE_ROOT
    from dev.runtime_lifecycle.installed import _canonical_guest_root

    root = tmp_path / STORAGE_ROOT.channel_directory(channel)
    monkeypatch.setattr(shell, "SHGetKnownFolderPath", lambda *_: str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "foreign" if defect == "base_spoof" else tmp_path))
    monkeypatch.delenv(STORAGE_ROOT.development_variable, raising=False)
    monkeypatch.setenv(STORAGE_ROOT.variable, str(tmp_path / "foreign" if defect == "different_root" else root))
    if defect == "development_alias":
        monkeypatch.setenv(STORAGE_ROOT.development_variable, str(root))
    if defect == "missing_build":
        monkeypatch.delattr(sys, "cadrumo_build", raising=False)
    else:
        monkeypatch.setattr(
            sys, "cadrumo_build", {"development": 1 if defect == "development_build" else 0}, raising=False
        )
    bootstrap = ModuleType("_cadrumo_bootstrap")
    package = tmp_path / "shipping-package"
    package.mkdir()
    manifest = package / "package-manifest.json"
    build = {"channel": "foreign" if defect == "foreign_channel" else channel}
    if defect == "missing_channel":
        build.clear()
    if defect == "channel_destination_mismatch":
        build["channel"] = "preview" if channel == "stable" else "stable"
    manifest.write_text(json.dumps({"build": build}), encoding="utf-8")
    monkeypatch.setattr(sys, "executable", str(package / "python.exe"))
    monkeypatch.setattr(
        bootstrap,
        "LAYOUT",
        {"package_root_from_executable": ".", "files": {"package_manifest": manifest.name}},
        raising=False,
    )
    monkeypatch.setattr(bootstrap, "_inside", lambda root, relative: root / relative, raising=False)
    verified = []

    def verify() -> None:
        verified.append(True)
        if defect == "damaged_package":
            raise ImportError("Damaged or mixed bundled file")

    monkeypatch.setattr(bootstrap, "verify", verify, raising=False)
    if defect == "missing_bootstrap":
        monkeypatch.delitem(sys.modules, "_cadrumo_bootstrap", raising=False)
    else:
        monkeypatch.setitem(sys.modules, "_cadrumo_bootstrap", bootstrap)
    if defect is None:
        assert _canonical_guest_root() == root
        assert verified == [True]
    else:
        with pytest.raises((ValueError, ImportError, KeyError)):
            _canonical_guest_root()


@pytest.mark.windows_only
def test_installed_default_destination_uses_real_windows_known_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Observe the actual current-token shell folder; this does not admit a guest."""
    from win32com.shell import shell, shellcon

    from cadrumo.core.storage_environment import STORAGE_ROOT, normalize_storage_path
    from dev.runtime_lifecycle.installed import _canonical_guest_root

    for variable in (*STORAGE_ROOT.precedence, "LOCALAPPDATA"):
        monkeypatch.delenv(variable, raising=False)
    expected = normalize_storage_path(Path(shell.SHGetKnownFolderPath(shellcon.FOLDERID_LocalAppData, 0, None)))
    assert _canonical_guest_root() == expected / STORAGE_ROOT.product_directory


@pytest.mark.windows_only
def test_installed_guest_checks_freshness_before_com_client_import(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fence the actual import boundary that creates pywin32's persistent cache."""
    import builtins

    from dev.runtime_lifecycle import installed

    observed = []
    native_import = builtins.__import__

    def importing(name: str, *args: object, **kwargs: object) -> object:
        if name == "win32com.client":
            observed.append("COM client import")
            raise RuntimeError("Stop before hardware discovery")
        return native_import(name, *args, **kwargs)

    monkeypatch.setattr(installed, "_canonical_guest_root", lambda: tmp_path)
    monkeypatch.setattr(installed, "_require_fresh_root", lambda root: observed.append("freshness"))
    monkeypatch.setattr(builtins, "__import__", importing)
    with pytest.raises(RuntimeError, match="Stop before hardware discovery"):
        installed.require_installation_guest(UUID(int=1), "S-1-5-21-1-2-3-1001", "user", guest_kind="qemu")
    assert observed == ["freshness", "COM client import"]


@pytest.mark.parametrize("contents", ["absent", "empty_root", "empty_native_temp", "foreign", "native_temp_contents"])
def test_installed_fresh_storage_allows_only_empty_native_bootstrap_temp(tmp_path: Path, contents: str) -> None:
    from cadrumo.core.storage_taxonomy import StorageCategory
    from cadrumo.core.storage_taxonomy_locations import storage_location
    from dev.runtime_lifecycle.installed import _require_fresh_root

    root = tmp_path / "canonical"
    temporary = root / storage_location(StorageCategory.TEMPORARY_FILES).relative_path()
    if contents != "absent":
        root.mkdir()
    if contents in ("empty_native_temp", "native_temp_contents"):
        temporary.mkdir()
    if contents == "native_temp_contents":
        (temporary / "existing-operation").write_bytes(b"must never delete")
    if contents == "foreign":
        (root / "existing-profile").mkdir()
    if contents in ("foreign", "native_temp_contents"):
        with pytest.raises(ValueError, match="fresh canonical storage"):
            _require_fresh_root(root)
        assert any(root.iterdir())
    else:
        _require_fresh_root(root)


@pytest.mark.parametrize("exit_code", [0, 1, "timeout", "cleanup_refused", "preflight_refused"])
def test_installed_dispatcher_never_certifies_incomplete_campaign(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, exit_code: int | str
) -> None:
    """Immediate runner result is policy input, never mock installed acceptance evidence."""
    import argparse
    from types import SimpleNamespace

    from dev.packaging.native import windows_msi_build

    build = tmp_path / "build"
    build.mkdir()
    metadata = build / "metadata"
    metadata.mkdir()
    (build / "build-paths.json").write_text(
        json.dumps({"paths": {"installation_metadata": "metadata"}}), encoding="utf-8"
    )
    plan = tmp_path / "plan.json"
    args = argparse.Namespace(
        build=build,
        identity=tmp_path / "identity.json",
        scope="user",
        prefix=tmp_path / "prefix",
        desktop="cadrumo",
        runner=tmp_path / "runner.exe",
        adapter=tmp_path / "adapter.exe",
        installed_vm_id=UUID(int=1),
        installed_account_sid="S-1-5-21-1-2-3-1001",
        installed_guest_kind="qemu",
    )
    monkeypatch.setattr(windows_msi_build, "require_installation_guest", lambda *_, **__: tmp_path / "fresh")
    monkeypatch.setattr(windows_msi_build, "maintenance_plan", lambda *_: plan)
    commands: list[list[str]] = []
    lifecycle: list[str] = []

    class Owner:
        def __init__(self, *_: object) -> None:
            self.resources = SimpleNamespace(close=lambda: lifecycle.append("closed"))

        def preflight(self) -> None:
            lifecycle.append("preflight")
            if exit_code == "preflight_refused":
                raise ValueError("Preexisting owner refused")

        def cleanup_after_outer_exit(self) -> None:
            lifecycle.append("native_owner_cleanup")
            if exit_code == "cleanup_refused":
                raise RuntimeError("Owned native cleanup refused")

    monkeypatch.setattr(windows_msi_build, "InstalledLifecycleHarness", Owner)
    (metadata / "installed-immediate.json").write_text('{"immediate":"passed"}', encoding="utf-8")

    def immediate(command: list[str], **_: object) -> object:
        from subprocess import TimeoutExpired

        commands.append(command)
        if isinstance(exit_code, str):
            raise TimeoutExpired(command, 1800)
        return SimpleNamespace(returncode=exit_code, stdout="", stderr="")

    monkeypatch.setattr(windows_msi_build, "run_command", immediate)
    reason = (
        "incomplete"
        if exit_code == 0
        else "acceptance failed"
        if exit_code == 1
        else "Preexisting owner"
        if exit_code == "preflight_refused"
        else "outer_timeout"
    )
    with pytest.raises(ValueError, match=reason):
        windows_msi_build.check_installation(args)
    receipt = json.loads((metadata / "installed-immediate.json").read_text(encoding="utf-8"))
    assert receipt["immediate"] == ("passed" if exit_code == 0 else "failed")
    assert receipt["full_installation_acceptance"] == "incomplete"
    assert set(receipt["pending"]) == {"machine_boot", "user_login", "scope_coexistence", "upgrade_cutover_rollback"}
    assert receipt["run_id"]
    if exit_code == "preflight_refused":
        assert not commands and lifecycle == ["preflight"] and receipt["cleanup"] == "not_started"
    else:
        assert "pytest" not in commands[0] and "dev.runtime_lifecycle.installed" in commands[0]
    if exit_code in {"timeout", "cleanup_refused"}:
        assert lifecycle == ["preflight", "native_owner_cleanup", "closed"]
        assert receipt["cleanup"] == ("settled" if exit_code == "timeout" else "unsettled")
        assert receipt["failure"] == "outer_timeout"


@pytest.mark.windows_only
@pytest.mark.parametrize(
    ("kind", "lsa_session", "lsa_owner", "admitted"),
    [
        (2, 4, "S-1-5-21-1-2-3-1001", True),
        (3, 4, "S-1-5-21-1-2-3-1001", False),
        (5, 4, "S-1-5-21-1-2-3-1001", False),
        (2, 9, "S-1-5-21-1-2-3-1001", False),
        (2, 4, "S-1-5-21-1-2-3-1002", False),
    ],
)
def test_installed_raw_token_policy_never_substitutes_desktop_context(
    monkeypatch: pytest.MonkeyPatch, kind: int, lsa_session: int, lsa_owner: str, admitted: bool
) -> None:
    import win32api

    from cadrumo.adapters.local_runtime import windows_login_native
    from cadrumo.adapters.local_runtime.windows_login_native import WindowsLogonRecord, WindowsTokenIdentity
    from dev.runtime_lifecycle.installed import require_interactive_token

    owner = "S-1-5-21-1-2-3-1001"
    actual = WindowsTokenIdentity(owner, 100, 4)
    logon = WindowsLogonRecord(kind, lsa_session, lsa_owner, None)
    monkeypatch.setattr(windows_login_native, "read_windows_token_identity", lambda _: actual)
    monkeypatch.setattr(windows_login_native, "read_windows_logon", lambda _: logon)
    if admitted:
        assert require_interactive_token(int(win32api.GetCurrentProcess()), owner) is actual
    else:
        with pytest.raises(ValueError, match="actual interactive"):
            require_interactive_token(int(win32api.GetCurrentProcess()), owner)


@pytest.mark.windows_only
@pytest.mark.parametrize("native_error", [1168, 1312, 5, None])
def test_installed_credential_preflight_requires_nonexistent_target_not_network_failure(
    monkeypatch: pytest.MonkeyPatch, native_error: int | None
) -> None:
    import pywintypes
    import win32cred

    from dev.runtime_lifecycle.installed import require_credential_facility

    targets: list[str] = []

    def read(target: str, kind: int) -> object:
        targets.append(target)
        assert kind == win32cred.CRED_TYPE_GENERIC
        if native_error is not None:
            raise pywintypes.error(native_error, "CredRead", "Policy probe")
        return {}

    monkeypatch.setattr(win32cred, "CredRead", read)
    if native_error == 1168:
        require_credential_facility()
    else:
        with pytest.raises(
            ValueError, match="unexpectedly exists" if native_error is None else f"native_code={native_error}"
        ):
            require_credential_facility()
    assert len(targets) == 1 and targets[0].startswith("CadrumoInstalledAcceptanceMissing/")
    UUID(targets[0].split("/")[1])


@pytest.mark.parametrize("blocked", [None, "manager", "runtime", "unadmitted", "popup", "popup_unregister"])
def test_installed_timeout_cleanup_retains_existing_processes_without_activation_and_waits(
    monkeypatch: pytest.MonkeyPatch, blocked: str | None
) -> None:
    """Cleanup policy checks retained process settlement, never synthetic installation success."""
    from types import SimpleNamespace

    from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
    from dev.runtime_lifecycle.installed import InstalledLifecycleHarness

    owner = object.__new__(InstalledLifecycleHarness)
    owner._preflight_admitted = blocked != "unadmitted"
    owner._installation_attempted = False
    owner._removed = False
    owner.manager_handle = None
    owner.intent = {"scope": "user" if blocked in {"popup", "popup_unregister"} else "machine"}
    calls: list[str] = []
    observation_failure = TimeoutError("popup observation failed")

    def observe_popup() -> None:
        calls.append("popup")
        raise observation_failure

    def maintenance(command: str) -> None:
        calls.append(command)
        if blocked == "popup_unregister":
            raise RuntimeError("private native failure detail")

    def wait(kind: str, timeout: int) -> int:
        calls.append("wait_" + kind)
        assert timeout == 90
        if blocked == kind:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        return 0

    def bind(*, activate: bool, absent_ok: bool) -> None:
        assert activate is False and absent_ok is True
        calls.append("bind_existing")
        owner.manager_handle = object()
        monkeypatch.setattr(
            owner, "process", SimpleNamespace(wait=lambda *, timeout: wait("manager", timeout)), raising=False
        )

    def retain() -> object:
        calls.append("retain_runtime")
        return SimpleNamespace(wait=lambda *, timeout: wait("runtime", timeout))

    monkeypatch.setattr(owner, "start_manager", bind)
    monkeypatch.setattr(owner, "retain_cleanup_runtime", retain)
    monkeypatch.setattr(owner, "maintenance", maintenance)
    monkeypatch.setattr(owner, "observe_cleanup_popup", observe_popup)
    monkeypatch.setattr(owner, "verify_registration", lambda *, absent: calls.append("absent"))
    if blocked == "unadmitted":
        with pytest.raises(ValueError, match="preflight"):
            owner.cleanup_after_outer_exit()
        assert not calls
    elif blocked in {"popup", "popup_unregister"}:
        with pytest.raises(TimeoutError, match="popup observation failed") as failure:
            owner.cleanup_after_outer_exit()
        assert failure.value is observation_failure
        assert calls[:4] == ["bind_existing", "retain_runtime", "popup", "unregister"]
        if blocked == "popup_unregister":
            assert calls == ["bind_existing", "retain_runtime", "popup", "unregister"]
            assert failure.value.__notes__ == ["Installed acceptance cleanup failed: RuntimeError"]
        else:
            assert calls[4:] == ["absent", "wait_manager"]
    elif blocked is not None:
        with pytest.raises(RuntimeRefusalError) as failure:
            owner.cleanup_after_outer_exit()
        assert failure.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
        assert calls[:4] == ["bind_existing", "retain_runtime", "unregister", "absent"]
    else:
        owner.cleanup_after_outer_exit()
        assert calls == ["bind_existing", "retain_runtime", "unregister", "absent", "wait_manager", "wait_runtime"]


@pytest.mark.parametrize("foreign", [None, "vm_id", "account_sid", "scope", "plan_sha256", "runner_sha256", "cleanup"])
def test_installed_campaign_state_rejects_foreign_or_released_ownership(tmp_path: Path, foreign: str | None) -> None:
    """Persisted campaign policy cannot authorize a different guest, artifact or released owner."""
    from dev.runtime_lifecycle.client_probes import campaign_binding, validate_campaign_state

    plan, runner = tmp_path / "plan.json", tmp_path / "runner.exe"
    plan.write_text(json.dumps({"scope": "machine"}), encoding="utf-8")
    runner.write_bytes(b"policy fixture, not a native executable")
    expected = campaign_binding(plan, runner, UUID(int=1), "S-1-5-21-1", "qemu")
    state = {
        "schema": 1,
        "binding": dict(expected),
        "encrypted_profile": "protected",
        "held_boot": "native-boot",
        "held_authentication_id": 1,
        "phases": {"hold": "passed"},
    }
    if foreign == "cleanup":
        state["phases"]["cleanup"] = "passed"
    elif foreign is not None:
        state["binding"][foreign] = "different"
    if foreign is None:
        validate_campaign_state(state, expected)
        runner.write_bytes(b"another artifact")
        with pytest.raises(ValueError, match="does not own"):
            validate_campaign_state(state, campaign_binding(plan, runner, UUID(int=1), "S-1-5-21-1", "qemu"))
    else:
        with pytest.raises(ValueError, match="does not own"):
            validate_campaign_state(state, expected)


@pytest.mark.windows_only
def test_installed_campaign_profile_uses_account_dpapi_and_never_plaintext_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the native DPAPI boundary policy; this is not installed acceptance evidence."""
    import win32crypt

    from dev.runtime_lifecycle.client_probes import _campaign_profile
    from dev.runtime_lifecycle.harness import Profile

    payload: list[tuple[bytes, bytes]] = []

    def protect(body: bytes, description: str, entropy: bytes, reserved: object, prompt: object, flags: int) -> bytes:
        assert flags == 1 and description == "Cadrumo installed test"
        assert reserved is None and prompt is None
        payload.append((body, entropy))
        return b"encrypted-policy-fixture"

    def unprotect(encrypted: bytes, entropy: bytes, reserved: object, prompt: object, flags: int) -> tuple[str, bytes]:
        assert encrypted == b"encrypted-policy-fixture" and entropy == payload[0][1] and flags == 1
        assert reserved is None and prompt is None
        return "Cadrumo installed test", payload[0][0]

    monkeypatch.setattr(win32crypt, "CryptProtectData", protect)
    monkeypatch.setattr(win32crypt, "CryptUnprotectData", unprotect)
    profile = Profile(UUID(int=4), "synthetic-private-test-password")
    state = {"binding": {"vm_id": "selected-native-guest"}}
    _campaign_profile(state, profile=profile)
    assert profile.password not in json.dumps(state) and str(profile.profile_id) not in json.dumps(state)
    assert _campaign_profile(state) == profile


@pytest.mark.parametrize("committed", [False, True])
def test_installed_campaign_failed_hold_preserves_only_committed_cleanup_authority(committed: bool) -> None:
    """A handle-close failure after hold publication must not strand the authentic native owner."""
    from dev.runtime_lifecycle.client_probes import validate_campaign_state

    expected = {"vm_id": "selected", "account_sid": "S-1-5-21-1", "scope": "machine"}
    state = {
        "schema": 1,
        "binding": expected,
        "encrypted_profile": "DPAPI-protected",
        "held_boot": "native",
        "held_authentication_id": 4,
        "ownership_committed": committed,
        "phases": {"hold": "failed"},
    }
    with pytest.raises(ValueError, match="does not own"):
        validate_campaign_state(state, expected)
    if committed:
        validate_campaign_state(state, expected, cleanup=True)
    else:
        with pytest.raises(ValueError, match="does not own"):
            validate_campaign_state(state, expected, cleanup=True)


@pytest.mark.windows_only
@pytest.mark.parametrize("username", ["actual-user", None])
def test_installed_campaign_prelogin_refuses_user_or_undecodable_wts_inventory(
    monkeypatch: pytest.MonkeyPatch,
    username: str | None,
) -> None:
    import win32ts

    from cadrumo.adapters.local_runtime import windows_login_native
    from dev.runtime_lifecycle.client_probes import verify_prelogin_boot
    from dev.runtime_lifecycle.installed import InstalledLifecycleHarness

    monkeypatch.setattr(windows_login_native, "windows_desktop_sessions", lambda: ((3, 0),))
    monkeypatch.setattr(win32ts, "WTSQuerySessionInformation", lambda *args: username)
    owner = object.__new__(InstalledLifecycleHarness)
    owner.intent = {"scope": "machine"}
    with pytest.raises(ValueError, match="user-associated WTS"):
        verify_prelogin_boot(owner, "S-1-5-21-1")


@pytest.mark.windows_only
@pytest.mark.parametrize("kind", [2, 10, 11, 12])
def test_installed_campaign_prelogin_refuses_actual_dedicated_account_lsa_logon(
    monkeypatch: pytest.MonkeyPatch,
    kind: int,
) -> None:
    from types import SimpleNamespace

    from cadrumo.adapters.local_runtime import windows_login_native
    from dev.runtime_lifecycle.client_probes import verify_prelogin_boot
    from dev.runtime_lifecycle.installed import InstalledLifecycleHarness

    monkeypatch.setattr(windows_login_native, "windows_desktop_sessions", lambda: ())
    monkeypatch.setattr(windows_login_native, "windows_logon_ids", lambda: (0x3E7, 44))

    def read(luid: int) -> object:
        assert luid == 44  # Only the documented LocalSystem zero-data sentinel is classified separately.
        return SimpleNamespace(owner="S-1-5-21-1", kind=kind)

    monkeypatch.setattr(windows_login_native, "read_windows_logon", read)
    owner = object.__new__(InstalledLifecycleHarness)
    owner.intent = {"scope": "machine"}
    with pytest.raises(ValueError, match="interactive account logon"):
        verify_prelogin_boot(owner, "S-1-5-21-1")


@pytest.mark.parametrize("defect", [None, "old_sequence", "different_pid", "unconfirmed", "no_heartbeat"])
def test_installed_takeover_requires_post_loss_control_for_the_verified_incarnation(defect: str | None) -> None:
    from dev.runtime_lifecycle.client_probes import takeover_confirmed

    events = [
        {"stage": "supervision", "sequence": sequence, "lifecycle": {"event": fact, "pid": 42}}
        for sequence, fact in enumerate(("launched", "ready", "boot_record_confirmed"), 11)
    ]
    if defect == "old_sequence":
        events[2]["sequence"] = 10
    elif defect == "different_pid":
        events[2]["lifecycle"] = {"event": "boot_record_confirmed", "pid": 43}
    elif defect == "unconfirmed":
        events.pop()
    elif defect == "no_heartbeat":
        events.pop(1)
    assert takeover_confirmed(events, 42, 10) is (defect is None)


@pytest.mark.windows_only
@pytest.mark.parametrize("settled", [True, False])
def test_installed_takeover_cleanup_drains_before_force_and_retains_unsettled_exact_handle(
    monkeypatch: pytest.MonkeyPatch, settled: bool
) -> None:
    from types import SimpleNamespace
    from typing import cast, override

    import win32event
    import win32process

    from cadrumo.adapters.local_runtime.windows_native_io import NativeWindowsHandle
    from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess, WindowsProcessScope
    from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
    from dev.runtime_lifecycle.client_probes import _settle_takeover

    calls = []

    class Handle(NativeWindowsHandle):
        @override
        def __int__(self) -> int:
            return 101

        @override
        def Close(self) -> None:
            calls.append("close")

    def grace(*, timeout: float) -> int:
        assert 0 <= timeout <= 35
        calls.append("grace")
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

    def wait(handle: int, timeout: int) -> int:
        assert handle == 101 and timeout in (0, 10_000)
        return win32event.WAIT_OBJECT_0 if timeout and settled else win32event.WAIT_TIMEOUT

    monkeypatch.setattr(win32event, "WaitForSingleObject", wait)
    monkeypatch.setattr(win32process, "TerminateProcess", lambda handle, code: calls.append(("force", handle, code)))
    owner = cast(WindowsProcessScope, SimpleNamespace(terminate=lambda **_: calls.append("job")))
    desktop = cast(WindowsOwnedProcess, SimpleNamespace(wait=grace))
    original = cast(NativeWindowsHandle, Handle())
    if settled:
        _settle_takeover(owner, desktop, original, True, 0)
        assert calls == ["grace", "job", ("force", 101, 73), "close"]
    else:
        with pytest.raises(AssertionError, match="did not settle") as failure:
            _settle_takeover(owner, desktop, original, True, 0)
        assert failure.value.__dict__["_takeover_runtime_handle"] is original
        assert calls == ["grace", "job", ("force", 101, 73)]


@pytest.mark.parametrize(
    "defect", [None, "same_scope", "same_prefix", "other_version", "other_manifest", "other_contract"]
)
def test_installed_scope_conflict_requires_real_opposite_sibling_cohort(tmp_path: Path, defect: str | None) -> None:
    from dev.runtime_lifecycle.client_probes import validate_conflicting_plan

    original = {
        "scope": "user",
        "prefix": str(tmp_path / "original"),
        "version": "0.6.0",
        "manifest_sha256": "a" * 64,
        "contract": {"identity": "same-canonical-cohort"},
    }
    candidate = {**original, "scope": "machine", "prefix": str(tmp_path / "candidate")}
    if defect == "same_scope":
        candidate["scope"] = original["scope"]
    elif defect == "same_prefix":
        candidate["prefix"] = original["prefix"]
    elif defect == "other_version":
        candidate["version"] = "0.6.1"
    elif defect == "other_manifest":
        candidate["manifest_sha256"] = "b" * 64
    elif defect == "other_contract":
        candidate["contract"] = {"identity": "other"}
    if defect is None:
        validate_conflicting_plan(original, candidate)
    else:
        with pytest.raises(ValueError, match="real opposite-scope"):
            validate_conflicting_plan(original, candidate)


@pytest.mark.parametrize(
    "defect", [None, "success", "unsettled", "wrong_code", "wrong_schema", "restore_failed", "cause"]
)
def test_installed_scope_campaign_requires_actual_settled_native_failure(defect: str | None) -> None:
    from dev.runtime_lifecycle.client_probes import validate_scope_refusal

    receipt = {"schema": 1, "outcome": "native_rolled_back", "code": "native_preparation_refused"}
    code = 2
    if defect == "success":
        code = 0
    elif defect == "unsettled":
        receipt["outcome"] = "native_unsettled"
    elif defect == "wrong_code":
        receipt["code"] = "artifact_or_owner_refused"
    elif defect == "wrong_schema":
        receipt["schema"] = 2
    elif defect == "restore_failed":
        receipt["service_restore"] = "native_service_restart_failed"
    elif defect == "cause":
        receipt["cause"] = "native_custody_refused"
    if defect is None:
        validate_scope_refusal(receipt, code)
    else:
        with pytest.raises(ValueError, match="actual settled admission refusal"):
            validate_scope_refusal(receipt, code)


def test_installed_scope_elevated_machine_attempt_preserves_standard_user_auth_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Policy seam requires the second genuine caller; it never claims a real install passed."""
    from types import SimpleNamespace

    from dev.runtime_lifecycle import client_probes
    from dev.runtime_lifecycle.harness import Profile
    from dev.runtime_lifecycle.installed import InstalledLifecycleHarness

    calls = []
    original = object.__new__(InstalledLifecycleHarness)
    original.intent = {"scope": "user"}
    candidate = object.__new__(InstalledLifecycleHarness)
    candidate.runner = tmp_path / "runner.exe"
    candidate.plan = tmp_path / "machine.json"
    monkeypatch.setattr(candidate, "native_environment", lambda: {})
    monkeypatch.setattr(client_probes, "_scope_products", lambda owner, *, absent: calls.append((owner, absent)))
    monkeypatch.setattr(client_probes, "_scope_observation", lambda owner, profile: {"boot": "actual-policy-fixture"})
    receipt = {"schema": 1, "outcome": "native_rolled_back", "code": "native_preparation_refused"}
    monkeypatch.setattr(
        client_probes, "run_command", lambda *args, **kwargs: SimpleNamespace(returncode=2, stdout=json.dumps(receipt))
    )
    state = {}
    profile = Profile(UUID(int=1), "private-synthetic-policy-password")
    assert (
        client_probes._scope_campaign(original, candidate, profile, state, {"scope": "machine"}, verify_only=False)
        is False
    )
    assert state["scope_attempt"]["receipt"] == receipt
    assert calls == [(original, False), (candidate, True), (candidate, True), (original, False)]
    monkeypatch.setattr(original, "start_manager", lambda *, activate: calls.append(("attach", activate)))
    live = SimpleNamespace(client=SimpleNamespace(login_password=lambda *args, **kwargs: calls.append("password")))
    monkeypatch.setattr(original, "connect", lambda _: live)
    monkeypatch.setattr(client_probes, "installed_protected_read", lambda *args: calls.append("protected"))
    assert (
        client_probes._scope_campaign(original, candidate, profile, state, {"scope": "machine"}, verify_only=True)
        is True
    )
    assert calls[-3:] == [("attach", False), "password", "protected"]
    with pytest.raises(ValueError, match="same real settled attempt"):
        client_probes._scope_campaign(original, candidate, profile, state, {"scope": "foreign"}, verify_only=True)


@pytest.mark.parametrize(
    "changed",
    [None, "scope", "prefix", "contract", "version", "manifest_sha256", "version_product", "registration_product"],
)
def test_installed_upgrade_requires_real_newer_compatible_cohorts(changed: str | None) -> None:
    from copy import deepcopy

    from dev.runtime_lifecycle.client_probes import validate_successor_plan

    original = {
        "scope": "user",
        "prefix": "C:/acceptance/product",
        "contract": {"identity": "genuine-same-family"},
        "version": "0.6.0",
        "manifest_sha256": "old",
        "version_product": {"product_code": "old-version"},
        "registration_product": {"product_code": "old-registration"},
    }
    successor = deepcopy(original)
    successor.update(
        version="0.6.1",
        manifest_sha256="new",
        version_product={"product_code": "new-version"},
        registration_product={"product_code": "new-registration"},
    )
    if changed in {"version", "manifest_sha256", "version_product", "registration_product"}:
        successor[changed] = original[changed]
    elif changed == "scope":
        successor[changed] = "machine"
    elif changed == "prefix":
        successor[changed] = "C:/other/product"
    elif changed == "contract":
        successor[changed] = {"identity": "foreign"}
    if changed is None:
        validate_successor_plan(original, successor)
    else:
        with pytest.raises(ValueError, match="two real newer compatible"):
            validate_successor_plan(original, successor)


@pytest.mark.parametrize("job_owner,member", [("S-1-5-18", True), ("S-1-5-21-1", True), ("S-1-5-18", False)])
def test_installed_cutover_successor_requires_actual_system_owned_service_job(
    monkeypatch: pytest.MonkeyPatch, job_owner: str, member: bool
) -> None:
    from contextlib import nullcontext
    from types import SimpleNamespace

    import win32api
    import win32com.client
    import win32event
    import win32job
    import win32process
    import win32security
    import win32service

    import cadrumo.adapters.local_runtime.windows_native_io as native
    import dev.runtime_lifecycle.installed as installed

    class Handle(int):
        def close(self) -> None:
            pass

        Close = close

    owner = object.__new__(installed.InstalledLifecycleHarness)
    owner.prefix, owner.manager = Path("C:/product"), Path("C:/product/versions/0.6.1/cadrumo-manager.exe")
    owner.registration = {"services": [{"name": "actual-product-manager"}]}
    monkeypatch.setattr(owner, "service", lambda _: nullcontext(1))
    monkeypatch.setattr(installed, "owned_windows_handle", Handle)
    monkeypatch.setattr(win32api, "OpenProcess", lambda *_: 10)
    monkeypatch.setattr(win32api, "CloseHandle", lambda _: None)
    monkeypatch.setattr(
        win32com.client, "GetObject", lambda _: SimpleNamespace(Get=lambda _: SimpleNamespace(ParentProcessId=99))
    )
    monkeypatch.setattr(native, "windows_image_path", lambda _: (owner.prefix / owner.manager.name).resolve())
    monkeypatch.setattr(native, "current_windows_owner_sid", lambda: "S-1-5-21-1")
    monkeypatch.setattr(installed, "require_interactive_token", lambda *_: SimpleNamespace(authentication_id=5))
    monkeypatch.setattr(win32security, "OpenProcessToken", lambda *_: 11)
    monkeypatch.setattr(win32security, "GetTokenInformation", lambda *_: ("S-1-5-18", 0))
    monkeypatch.setattr(win32security, "ConvertSidToStringSid", lambda sid: sid)
    monkeypatch.setattr(
        win32security, "GetSecurityInfo", lambda *_: SimpleNamespace(GetSecurityDescriptorOwner=lambda: job_owner)
    )
    names = []
    monkeypatch.setattr(
        win32job, "OpenJobObject", lambda access, inherit, name: names.append((access, inherit, name)) or 20
    )
    monkeypatch.setattr(win32job, "IsProcessInJob", lambda process, job: process == 30 and job == 20 and member)
    monkeypatch.setattr(win32event, "WaitForSingleObject", lambda *_: win32event.WAIT_TIMEOUT)
    monkeypatch.setattr(win32process, "GetProcessTimes", lambda handle: {"CreationTime": 1 if handle == 10 else 2})
    monkeypatch.setattr(
        win32service, "QueryServiceStatusEx", lambda _: {"CurrentState": win32service.SERVICE_RUNNING, "ProcessId": 7}
    )
    assert owner.worker_of_broker(42, 30) is (job_owner == "S-1-5-18" and member)
    assert names == [
        (
            win32job.JOB_OBJECT_QUERY | 0x20000,
            False,
            "Global\\actual-product-manager.service.S-1-5-21-1.0000000000000005.job",
        )
    ]


def test_installed_upgrade_keeps_old_session_inside_original_dpapi_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib

    import win32crypt

    from dev.runtime_lifecycle.client_probes import _campaign_payload, _campaign_profile
    from dev.runtime_lifecycle.harness import Profile

    state = {"binding": {"plan_sha256": "original", "runner_sha256": "original-owner"}}
    entropy = hashlib.sha256(json.dumps(state["binding"], sort_keys=True).encode("utf-8")).digest()
    private: list[bytes] = []

    def protect(body: bytes, _: str, observed: bytes, *_args: object) -> bytes:
        assert observed == entropy
        private.append(body)
        return b"opaque native protected payload"

    def unprotect(body: bytes, observed: bytes, *_args: object) -> tuple[str, bytes]:
        assert observed == entropy and body == b"opaque native protected payload"
        return "", private[-1]

    monkeypatch.setattr(win32crypt, "CryptProtectData", protect)
    monkeypatch.setattr(win32crypt, "CryptUnprotectData", unprotect)
    profile = Profile(UUID(int=1), "synthetic-private-password")
    continuation = {"session": str(UUID(int=2)), "boot": str(UUID(int=3)), "operation": "a" * 64, "revision": "4"}
    _campaign_profile(state, profile=profile, continuation=continuation)
    assert state["binding"] == {"plan_sha256": "original", "runner_sha256": "original-owner"}
    assert continuation["session"] not in json.dumps(state)
    assert profile.password not in json.dumps(state)
    assert _campaign_profile(state) == profile
    assert _campaign_payload(state)["continuation"] == continuation


@pytest.mark.parametrize(
    "missing", [None, "schema", "phase", "scope", "result", "full_installation_acceptance", "pending"]
)
def test_installed_finalization_requires_actual_complete_same_scope_cleanup_receipt(missing: str | None) -> None:
    from dev.packaging.native.windows_msi_build import validate_cleanup_receipt

    receipt = {
        "schema": 1,
        "phase": "cleanup",
        "scope": "user",
        "result": "passed",
        "full_installation_acceptance": "passed",
        "pending": [],
    }
    if missing is not None:
        receipt.pop(missing)
        with pytest.raises(ValueError, match="Actual campaign cleanup"):
            validate_cleanup_receipt(receipt, "user")
    else:
        validate_cleanup_receipt(receipt, "user")
        with pytest.raises(ValueError, match="same-scope"):
            validate_cleanup_receipt(receipt, "machine")


@pytest.mark.parametrize(
    "phase,result,pending,full",
    [
        ("immediate", "passed", [], "passed"),
        ("cleanup", "failed", [], "passed"),
        ("cleanup", "passed", ["machine_boot"], "passed"),
        ("cleanup", "passed", [], "incomplete"),
    ],
)
def test_installed_finalization_refuses_partial_or_unsettled_receipt(
    phase: str, result: str, pending: list[str], full: str
) -> None:
    from dev.packaging.native.windows_msi_build import validate_cleanup_receipt

    with pytest.raises(ValueError, match="Actual campaign cleanup"):
        validate_cleanup_receipt(
            {
                "schema": 1,
                "phase": phase,
                "scope": "machine",
                "result": result,
                "pending": pending,
                "full_installation_acceptance": full,
            },
            "machine",
        )


@pytest.mark.parametrize("phase", ["gui-stop", "gui-user", "gui-restore"])
@pytest.mark.parametrize(
    "defect", [None, "scope", "login", "scope_refusal", "successor", "order", "boot", "logon", "linked", "session"]
)
def test_installed_ordinary_gui_requires_original_ordered_machine_logon(phase: str, defect: str | None) -> None:
    """Policy evidence fences token-level observations; it never claims real GUI success."""
    from dev.runtime_lifecycle.client_probes import validate_gui_phase

    state = {
        "phases": {"login": "passed", "scope_conflict_refusal": "passed"},
        "gui_boot": "actual-boot",
        "gui_authentication_id": 123,
        "gui_user_authentication_id": 456,
        "gui_session_id": 1,
    }
    if phase != "gui-stop":
        state["phases"]["gui-stop"] = "passed"
    if phase == "gui-restore":
        state["phases"]["gui-user"] = "passed"
    scope, boot = "machine", "actual-boot"
    logon, linked = (456, 123) if phase == "gui-user" else (123, 456)
    session = 1
    if defect == "scope":
        scope = "user"
    elif defect == "login":
        state["phases"]["login"] = "failed"
    elif defect == "scope_refusal":
        state["phases"]["scope_conflict_refusal"] = "attempted"
    elif defect == "successor":
        state["successor"] = {"version": "another-cohort"}
    elif defect == "order":
        if phase == "gui-stop":
            state["phases"]["gui-user"] = "passed"
        else:
            state["phases"].pop("gui-stop" if phase == "gui-user" else "gui-user")
    elif defect == "boot":
        boot = "later-boot"
    elif defect == "logon":
        logon = 789
    elif defect == "linked":
        linked = 789
    elif defect == "session":
        session = 2
    # Stop captures the native context; subsequent phases must match it.
    if defect is None or (phase == "gui-stop" and defect in {"boot", "logon", "linked", "session"}):
        validate_gui_phase(state, scope, phase, boot, logon, linked, session)
    else:
        with pytest.raises(ValueError, match="ordered original machine"):
            validate_gui_phase(state, scope, phase, boot, logon, linked, session)


@pytest.mark.parametrize(
    ("scope", "fresh", "interactive"), [("user", False, True), ("machine", True, True), ("machine", False, False)]
)
def test_installed_least_gui_override_cannot_relax_destructive_or_network_guard(
    scope: str, fresh: bool, interactive: bool
) -> None:
    from dev.runtime_lifecycle.installed import require_installation_guest

    with pytest.raises(ValueError, match="Least-privilege GUI observation"):
        require_installation_guest(
            UUID(int=1), "S-1-5-21-1", scope, fresh=fresh, interactive=interactive, caller_elevation=False
        )


def test_installed_ordinary_gui_body_never_activates_or_controls_machine_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from dev.runtime_lifecycle import client_probes

    calls = []
    owner = SimpleNamespace(verify_stopped_service=lambda: calls.append("stopped"), retain_cleanup_runtime=lambda: None)
    before, after = UUID(int=1), UUID(int=2)
    monkeypatch.setattr(client_probes, "_campaign_payload", lambda _: {"continuation": {"boot": str(before)}})

    def proof(instance: object, profile: object, *, after_boot: UUID) -> UUID:
        assert instance is owner and after_boot == before
        calls.append("actual-shipping-proof")
        return after

    monkeypatch.setattr(client_probes, "exercise_cadrumo_takeover", proof)
    state = {}
    client_probes._gui_campaign(owner, object(), state, "gui-user")
    assert calls == ["stopped", "actual-shipping-proof", "stopped"]
    assert state["gui_runtime_boot"] == str(after)


@pytest.mark.parametrize("elevated", [False, True])
def test_installed_least_gui_guard_requires_actual_unelevated_interactive_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, elevated: bool
) -> None:
    """Native observations are policy inputs here, never actual installed acceptance."""
    from types import SimpleNamespace

    import win32com.client
    import win32security

    from cadrumo.adapters.local_runtime import windows_native_io
    from cadrumo.core import storage_environment
    from dev.runtime_lifecycle import installed

    vm, sid = UUID(int=1), "S-1-5-21-1-2-3-1001"
    for variable in storage_environment.STORAGE_ROOT.precedence:
        monkeypatch.delenv(variable, raising=False)
    system = SimpleNamespace(Manufacturer="QEMU", Model="CadrumoRuntimeGuest")
    product = SimpleNamespace(UUID=str(vm))
    monkeypatch.setattr(
        win32com.client,
        "GetObject",
        lambda _: SimpleNamespace(ExecQuery=lambda query: [product] if "SystemProduct" in query else [system]),
    )
    monkeypatch.setattr(windows_native_io, "current_windows_owner_sid", lambda: sid)
    monkeypatch.setattr(win32security, "OpenProcessToken", lambda *_: SimpleNamespace(Close=lambda: None))
    monkeypatch.setattr(win32security, "GetTokenInformation", lambda *_: elevated)
    calls = []
    monkeypatch.setattr(installed, "require_interactive_token", lambda *_: calls.append("raw-interactive-token"))
    monkeypatch.setattr(installed, "require_credential_facility", lambda: calls.append("nonexistent-CredRead"))
    monkeypatch.setattr(installed, "_canonical_guest_root", lambda: tmp_path)
    if elevated:
        with pytest.raises(ValueError, match="token elevation"):
            installed.require_installation_guest(
                vm, sid, "machine", guest_kind="qemu", fresh=False, caller_elevation=False
            )
        assert not calls
    else:
        assert (
            installed.require_installation_guest(
                vm, sid, "machine", guest_kind="qemu", fresh=False, caller_elevation=False
            )
            == tmp_path
        )
        assert calls == ["raw-interactive-token", "nonexistent-CredRead"]


@pytest.mark.parametrize("defect", [None, "owner", "session", "lsa_kind", "same_elevation", "missing", "unstable"])
def test_installed_gui_counterpart_requires_native_link_and_its_own_lsa_identity(
    monkeypatch: pytest.MonkeyPatch, defect: str | None
) -> None:
    """Native API fixtures test ownership policy only, never real authentication."""
    import win32api
    import win32security

    from cadrumo.adapters.local_runtime import windows_login_native
    from dev.runtime_lifecycle.installed import require_linked_interactive_token

    sid = "S-1-5-21-1-2-3-1001"
    closed, reads = [], {}
    original = windows_login_native.WindowsTokenIdentity(sid, 123, 1)
    counterpart = windows_login_native.WindowsTokenIdentity(
        "S-1-5-21-9" if defect == "owner" else sid, 456, 2 if defect == "session" else 1
    )

    def identity(token: int) -> object:
        reads[token] = reads.get(token, 0) + 1
        if token == 102 and defect == "unstable" and reads[token] > 1:
            return original
        return original if token == 101 else counterpart

    def information(token: int, kind: int) -> object:
        if kind == win32security.TokenLinkedToken:
            if defect == "missing":
                raise ValueError("native linked token unavailable")
            return 102
        assert kind == win32security.TokenElevation
        return token == 101 or defect == "same_elevation"

    monkeypatch.setattr(win32security, "OpenProcessToken", lambda *_: 101)
    monkeypatch.setattr(win32security, "GetTokenInformation", information)
    monkeypatch.setattr(win32api, "CloseHandle", lambda token: closed.append(token))
    monkeypatch.setattr(windows_login_native, "read_windows_token_identity", identity)
    monkeypatch.setattr(
        windows_login_native,
        "read_windows_logon",
        lambda luid: windows_login_native.WindowsLogonRecord(
            3 if defect == "lsa_kind" and luid == 456 else 2,
            1 if luid == 123 else counterpart.session_id,
            sid if luid == 123 else counterpart.owner,
            None,
        ),
    )
    if defect is None:
        assert require_linked_interactive_token(1, sid) == counterpart
        assert counterpart.authentication_id != original.authentication_id
    else:
        with pytest.raises(ValueError):
            require_linked_interactive_token(1, sid)
    assert closed == ([101] if defect == "missing" else [102, 101])


@pytest.mark.parametrize(
    ("rejection", "expected"),
    [
        ({"stage": "inventory", "kind": "incompatible"}, {"stage": "inventory", "kind": "incompatible"}),
        ({"stage": "manifest", "kind": "io_not_found"}, {"stage": "manifest", "kind": "io_not_found"}),
        (
            {"stage": "manager", "kind": "integrity", "member_sha256": "a" * 64, "path": "private-value"},
            {"stage": "manager", "kind": "integrity", "member_sha256": "a" * 64},
        ),
        (
            {
                "stage": "manifest",
                "kind": "io_permission_denied",
                "member_sha256": "private-value",
                "message": "private-value",
            },
            None,
        ),
        ({"stage": "inventory", "kind": "incompatible", "member_sha256": "private-value"}, None),
        ({"stage": "private-value", "kind": "io_not_found"}, None),
        ({"stage": "manifest", "kind": "private-value"}, None),
        ({"stage": ["manifest"], "kind": "io_not_found"}, None),
        ({"stage": "manifest", "kind": {"private": "value"}}, None),
    ],
)
def test_precommit_candidate_diagnostics_preserve_only_native_finite_fields(
    rejection: dict[str, object], expected: dict[str, str] | None
) -> None:
    from dev.runtime_lifecycle.installed import _precommit_receipt, _require_precommit_rollback

    receipt = _precommit_receipt(
        {
            "schema": 1,
            "outcome": "native_rolled_back",
            "code": "version_inventory_failed",
            "candidate_rejection": rejection,
        },
        1,
    )
    assert receipt["candidate_rejection"] == expected
    assert "private-value" not in json.dumps(receipt)
    if expected == {"stage": "inventory", "kind": "incompatible"}:
        _require_precommit_rollback(receipt)
    else:
        with pytest.raises(ValueError, match="did not settle"):
            _require_precommit_rollback(receipt)


@pytest.mark.parametrize("retention_fails", [False, True])
def test_installed_maintenance_retains_native_candidate_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retention_fails: bool
) -> None:
    from types import SimpleNamespace

    from dev.runtime_lifecycle import installed

    instance = object.__new__(installed.InstalledLifecycleHarness)
    instance.plan = (tmp_path / "missing" if retention_fails else tmp_path) / "plan.json"
    instance.runner = tmp_path / "runner.exe"
    monkeypatch.setattr(instance, "native_environment", lambda: {})
    monkeypatch.setattr(
        installed,
        "run_command",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stderr="",
            stdout=json.dumps(
                {
                    "schema": 1,
                    "outcome": "rolled_back_publication_pending",
                    "code": "rollback_publication_fenced",
                    "cause": "version_inventory_failed",
                    "candidate_rejection": {"stage": "manifest", "kind": "io_not_found", "path": "private-value"},
                    "private_error": "private-value",
                }
            ),
        ),
    )
    with pytest.raises(RuntimeError, match="rollback_publication_fenced") as caught:
        instance.maintenance("install")
    assert "io_not_found" in str(caught.value)
    assert "private-value" not in str(caught.value)
    if retention_fails:
        assert caught.value.__notes__ == ["Native failure evidence retention failed: FileNotFoundError"]
    else:
        (evidence,) = tmp_path.glob("native-maintenance-failure-*.json")
        retained = json.loads(evidence.read_text(encoding="utf-8"))
        assert retained["candidate_rejection"] == {"stage": "manifest", "kind": "io_not_found"}
        assert retained["cause"] == "version_inventory_failed"
        assert retained["returncode"] == 1
        assert retained["command"] == "install"
        assert "private-value" not in evidence.read_text(encoding="utf-8")


@pytest.mark.parametrize("spelling", ["upper", "mixed"])
def test_installed_native_launch_derives_own_roots_without_mutating_frontend_pins(
    monkeypatch: pytest.MonkeyPatch, spelling: str
) -> None:
    from cadrumo.core.storage_environment import PROCESS_ENVIRONMENT, STORAGE_ROOT, StoragePlatform
    from dev.runtime_lifecycle.installed import InstalledLifecycleHarness

    declared = (*STORAGE_ROOT.precedence, *PROCESS_ENVIRONMENT.inherited_names(StoragePlatform.WINDOWS))
    pins = {name if spelling == "upper" else name.swapcase(): "frontend-owned-pin" for name in declared}
    ambient = {"SystemRoot": "C:\\Windows", "USERPROFILE": "C:\\Users\\Fixture", "TEMP": "C:\\Temp", **pins}
    monkeypatch.setattr(os, "environ", ambient.copy())
    instance = object.__new__(InstalledLifecycleHarness)
    native = instance.native_environment()
    assert native == {key: value for key, value in ambient.items() if key not in pins}
    assert os.environ == ambient
    assert not {name.upper() for name in native}.intersection(name.upper() for name in declared)


def test_installed_native_timeout_retains_only_bounded_phase_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from dev.runtime_lifecycle import installed

    valid = {"schema": 1, "event": "native_maintenance_phase", "phase": "commit", "transition": "enter", "elapsedMs": 7}
    rows = [
        valid,
        {**valid, "phase": "private-path"},
        {**valid, "elapsedMs": True},
        {**valid, "transition": "private-path"},
        {**valid, "phase": "publication_admission", "elapsedMs": 8, "path": "private-path"},
    ]
    rows.append({**valid, "schema": True})
    nested = "[" * 2000 + "null" + "]" * 2000
    stderr = ("private-path\n" + nested + "\n" + "\n".join(map(json.dumps, rows))).encode()
    error = subprocess.TimeoutExpired(["native-owner"], 900, stderr=stderr)
    instance = object.__new__(installed.InstalledLifecycleHarness)
    instance.plan, instance.runner = tmp_path / "plan.json", tmp_path / "runner.exe"
    monkeypatch.setattr(instance, "native_environment", lambda: {})

    def invoke(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(installed, "run_command", invoke)
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        instance.maintenance("install")
    assert caught.value is error
    (evidence,) = tmp_path.glob("native-maintenance-failure-*.json")
    facts = json.loads(evidence.read_text(encoding="utf-8"))
    assert facts["native_result"] is None
    assert facts["observation"] == "timed_out"
    assert facts["phases"] == [
        {"phase": "commit", "transition": "enter", "elapsedMs": 7},
        {"phase": "publication_admission", "transition": "enter", "elapsedMs": 8},
    ]
    assert "private-path" not in evidence.read_text(encoding="utf-8")
    assert "private-path" not in "\n".join(error.__notes__)
    many = "\n".join(json.dumps({**valid, "elapsedMs": index}) for index in range(100))
    assert len(installed._native_phase_facts(many)) == 32
    assert installed._native_phase_facts(many)[0]["elapsedMs"] == 68
    assert installed._native_phase_facts(b"X" * 70000 + b"\n" + stderr) == facts["phases"]


@pytest.mark.parametrize("entry", [True, False, None])
def test_installed_cleanup_preserves_primary_failure(monkeypatch: pytest.MonkeyPatch, entry: bool | None) -> None:
    from contextlib import ExitStack

    from dev.runtime_lifecycle.installed import InstalledLifecycleHarness

    instance = object.__new__(InstalledLifecycleHarness)
    instance.resources = ExitStack()
    instance.metrics = {}
    primary = RuntimeError("primary native failure")
    closed = []

    def cleanup() -> None:
        closed.append(True)
        raise OSError("private-value")

    def fail(*_args: object) -> None:
        raise primary

    instance.resources.callback(cleanup)
    monkeypatch.setattr(instance, "stop_manager", cleanup)
    if entry:
        monkeypatch.setattr(instance, "preflight", lambda: None)
        monkeypatch.setattr(instance, "maintenance", fail)
        with pytest.raises(RuntimeError) as caught:
            instance.__enter__()
        assert caught.value is primary
    elif entry is False:
        instance.__exit__(RuntimeError, primary, None)
        assert "cleanup_seconds" in instance.metrics
    else:
        with pytest.raises(OSError) as caught:
            instance.__exit__(None, None, None)
        assert len(caught.value.__notes__) == 1
        assert "private-value" not in caught.value.__notes__[0]
        assert len(closed) == 2
        return
    assert len(closed) == 2
    assert len(primary.__notes__) == 2
    assert all("OSError" in note and "private-value" not in note for note in primary.__notes__)


def test_installed_campaign_secondary_cleanup_never_masks_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import ExitStack

    from cadrumo.adapters.persistence.storage.custody import acceleration_receipt
    from dev.runtime_lifecycle import client_probes, installed
    from dev.runtime_lifecycle.harness import Profile

    primary = RuntimeError("primary native failure")
    phases = []
    profile = Profile(UUID(int=9), "synthetic-only")

    def cleanup(*_args: object, **_kwargs: object) -> None:
        raise OSError("private-value")

    class Owner:
        _held = False
        package = tmp_path
        prefix = tmp_path / "installation"
        resources = ExitStack()

        def __enter__(self) -> Owner:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def create_profile(self, *_args: object) -> Profile:
            return profile

    owner = Owner()
    owner.resources.callback(cleanup)
    plan, runner = tmp_path / "plan.json", tmp_path / "runner.exe"
    plan.touch()
    runner.touch()
    monkeypatch.setattr(client_probes.os, "environ", os.environ.copy())
    monkeypatch.setattr(client_probes, "campaign_binding", lambda *_: {"scope": "user"})
    monkeypatch.setattr(installed, "require_installation_guest", lambda *_args, **_kwargs: tmp_path / "storage")
    monkeypatch.setattr(installed, "InstalledLifecycleHarness", lambda *_: owner)
    monkeypatch.setattr(acceleration_receipt, "delete_profile_session", cleanup)

    def publish(_path: Path, state: dict[str, object]) -> None:
        phases.append(state["phases"])
        cleanup()

    def exercise(*_args: object, **_kwargs: object) -> None:
        raise primary

    monkeypatch.setattr(client_probes, "_publish_campaign", publish)
    monkeypatch.setattr(client_probes, "exercise_installed_manager", exercise)
    with pytest.raises(RuntimeError) as caught:
        client_probes.installed_campaign("hold", tmp_path / "state.json", plan, runner, UUID(int=3), "test-SID")
    assert caught.value is primary
    assert phases == [{"hold": "failed"}]
    assert len(primary.__notes__) == 3
    assert all("OSError" in note and "private-value" not in note for note in primary.__notes__)


@pytest.mark.parametrize(
    "defect", [None, "fenced", "state5", "pending", "files", "wrong_rejection", "zero_exit", "observation_error"]
)
def test_installed_precommit_rollback_requires_native_and_publication_settlement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str | None
) -> None:
    from contextlib import ExitStack
    from types import SimpleNamespace

    from dev.runtime_lifecycle import installed

    root, prefix = tmp_path / "storage", tmp_path / "prefix"
    plan, runner, evidence = tmp_path / "plan.json", tmp_path / "runner.exe", tmp_path / "evidence.json"
    intent = {
        "scope": "user",
        "prefix": str(prefix),
        "version": "0.6.2",
        "contract": {"layout": {"abi": 7, "installation": {"publication": "publication", "versions": "versions"}}},
        "version_product": {"product_code": str(UUID(int=1))},
        "registration_product": {"product_code": str(UUID(int=2))},
    }
    original = json.dumps(intent)
    plan.write_text(original, encoding="utf-8")
    runner.touch()
    calls: list[str] = []
    instance = SimpleNamespace(
        intent=intent,
        prefix=prefix,
        package=prefix / "versions/0.6.2",
        resources=ExitStack(),
        preflight=lambda: calls.append("preflight"),
        native_environment=lambda: {},
        verify_registration=lambda **_: calls.append("registration_absent"),
    )
    monkeypatch.setattr(installed, "require_installation_guest", lambda *_args, **_kwargs: root)
    monkeypatch.setattr(installed, "InstalledLifecycleHarness", lambda *_: instance)

    def states(_product: str, scope: str, sid: str) -> dict[int, int | None]:
        assert scope == "user" and sid == "S-1-5-21-1-2-3-1000"
        if "native_install" in calls and _product == str(UUID(int=1)):
            if defect == "observation_error":
                raise OSError("private observation detail")
            if defect in {"state5", "fenced"}:
                return {1: None, 2: 5}
        return {1: None, 2: None}

    monkeypatch.setattr(installed, "exact_msi_product_states", states)

    def invoke(command: list[str], **_kwargs: object) -> SimpleNamespace:
        assert command[:3] == [str(runner), "install", "--plan"]
        negative = json.loads(Path(command[3]).read_text(encoding="utf-8"))
        assert negative["contract"]["layout"]["abi"] == 6
        negative["contract"]["layout"]["abi"] = 7
        assert negative == intent
        calls.append("native_install")
        state = prefix / "publication/state.json"
        state.parent.mkdir(parents=True)
        state.write_text(
            json.dumps(
                {
                    "schema": 2,
                    "versions": {"0.6.2": {"phase": "pending"}}
                    if defect in {"pending", "fenced", "observation_error"}
                    else {},
                    "manager_anchor": None,
                    "desktop_anchor": None,
                    "registration": None,
                }
            ),
            encoding="utf-8",
        )
        if defect == "files":
            instance.package.mkdir(parents=True)
        document = {
            "schema": 1,
            "outcome": "rolled_back_publication_pending"
            if defect in {"fenced", "observation_error"}
            else "native_rolled_back",
            "code": "rollback_publication_fenced"
            if defect in {"fenced", "observation_error"}
            else "version_inventory_failed",
            "candidate_rejection": {
                "stage": "inventory",
                "kind": "missing" if defect == "wrong_rejection" else "incompatible",
            },
            "private_error": "must never enter retained evidence",
        }
        if defect in {"fenced", "observation_error"}:
            document["cause"] = "version_inventory_failed"
        stderr = "\n".join(
            json.dumps(fact)
            for fact in (
                {
                    "schema": 1,
                    "event": "native_maintenance_phase",
                    "phase": "candidate_verification",
                    "transition": "failed",
                    "elapsedMs": 42,
                    "private_error": "must never enter retained evidence",
                },
                {
                    "schema": 1,
                    "event": "native_maintenance_phase",
                    "phase": "unknown_private_phase",
                    "transition": "failed",
                    "elapsedMs": 43,
                },
            )
        )
        return SimpleNamespace(returncode=0 if defect == "zero_exit" else 1, stdout=json.dumps(document), stderr=stderr)

    monkeypatch.setattr(installed, "run_command", invoke)
    arguments = (plan, runner, evidence, UUID(int=3), "S-1-5-21-1-2-3-1000")
    if defect is None:
        receipt = installed.run_precommit_rollback(*arguments)
        assert receipt["precommit_rollback"] == "passed"
        assert calls == ["preflight", "native_install", "registration_absent"]
    else:
        with pytest.raises(ValueError) as caught:
            installed.run_precommit_rollback(*arguments)
        if defect in {"fenced", "observation_error"}:
            assert str(caught.value) == "Precommit rollback did not settle the authentic candidate rejection"
    retained = json.loads(evidence.read_text(encoding="utf-8"))
    assert retained["precommit_rollback"] == ("passed" if defect is None else "failed")
    assert retained["native"]["returncode"] == (0 if defect == "zero_exit" else 1)
    assert retained["candidate_present"] == (defect == "files")
    assert retained["publication"]["versions_empty"] == (defect not in {"pending", "fenced", "observation_error"})
    assert retained["registration_absent"] is True
    assert retained["products"]["registration_product"] == {"1": None, "2": None}
    if defect == "observation_error":
        assert retained["products"]["version_product"] is None
        assert retained["observation_errors"]["version_product"] == "OSError"
        assert all("private" not in note for note in caught.value.__notes__)
    else:
        assert retained["products"]["version_product"] == {
            "1": None,
            "2": 5 if defect in {"state5", "fenced"} else None,
        }
    assert retained["phases"] == [{"phase": "candidate_verification", "transition": "failed", "elapsedMs": 42}]
    assert "must never" not in evidence.read_text(encoding="utf-8")
    assert retained["full_installation_acceptance"] == "incomplete"
    assert plan.read_text(encoding="utf-8") == original


@pytest.mark.windows_only
@pytest.mark.parametrize("scope", ["user", "machine"])
@pytest.mark.parametrize("status", [0, 1605, 1610])
def test_installed_exact_msi_state_observation_binds_native_context(
    monkeypatch: pytest.MonkeyPatch, scope: str, status: int
) -> None:
    import ctypes
    from types import SimpleNamespace
    from typing import Any

    from dev.runtime_lifecycle.installed import exact_msi_product_states

    observed: list[tuple[str, str | None, int, str]] = []

    class Query:
        def __call__(self, code: str, sid: str | None, context: int, name: str, buffer: Any, _size: object) -> int:
            observed.append((code, sid, context, name))
            buffer.value = "5"
            return status

    def library(name: str, *, winmode: int) -> SimpleNamespace:
        assert name == "msi.dll" and winmode == 0x800
        return SimpleNamespace(MsiGetProductInfoExW=Query())

    monkeypatch.setattr(ctypes, "WinDLL", library)
    sid = "S-1-5-21-1-2-3-1000"
    if status == 1610:
        with pytest.raises(ValueError, match="native_code=1610"):
            exact_msi_product_states(str(UUID(int=1)), scope, sid)
    else:
        expected = {context: 5 if status == 0 else None for context in ((1, 2) if scope == "user" else (4,))}
        assert exact_msi_product_states(str(UUID(int=1)), scope, sid) == expected
    contexts = ((1,) if status == 1610 else (1, 2)) if scope == "user" else (4,)
    assert observed == [
        ("{00000000-0000-0000-0000-000000000001}", sid if scope == "user" else None, context, "State")
        for context in contexts
    ]
