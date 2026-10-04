"""Package layout and prefix removal safety, using explicitly synthetic payloads."""

from __future__ import annotations

import json
import plistlib
from dataclasses import asdict
from pathlib import Path

import pytest
from defusedxml import ElementTree

from dev.packaging.native.hashing import digest
from dev.packaging.native.identity import identity
from dev.packaging.native.installation import inventory, member, prepare, uninstall, validate_payload, verify_inventory
from dev.packaging.runtime_wheelhouse_contract import SUPPORTED_TARGETS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def payload_fixture(tmp_path: Path, target: str) -> tuple[Path, Path]:
    value = asdict(identity(target))
    identity_file = tmp_path / "identity.json"
    identity_file.write_text(json.dumps(value), encoding="utf-8")
    root = tmp_path / "payload"
    (root / "data").mkdir(parents=True)
    (root / "cadrumo").write_text("synthetic test executable", encoding="utf-8")
    manifest = {"build": value, "files": {"cadrumo": digest(root / "cadrumo")}}
    (root / "data/package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root, identity_file


@pytest.mark.parametrize("target", [item.name for item in SUPPORTED_TARGETS])
def test_native_layout_projects_registration(tmp_path: Path, target: str) -> None:
    payload, identity_file = payload_fixture(tmp_path, target)
    root = prepare(payload, identity_file, tmp_path / "build", "cadrumo")
    if target.startswith("linux-"):
        assert (root / "opt/cadrumo/cadrumo").is_file()
        desktop = (root / "usr/share/applications/md.neve.cadrumo.desktop").read_text(encoding="utf-8")
        assert 'Exec="/opt/cadrumo/cadrumo"' in desktop
        assert (root / "usr/share/icons/hicolor/scalable/apps/md.neve.cadrumo.svg").is_file()
    elif target.startswith("macos-"):
        contents = root / "CADRUMO.app/Contents"
        metadata = plistlib.loads((contents / "Info.plist").read_bytes())
        assert metadata["CFBundleIdentifier"] == "md.neve.cadrumo"
        assert metadata["LSMinimumSystemVersion"] == "14.0"
        assert (contents / "MacOS/cadrumo").is_file()
    else:
        assert (root / "app/cadrumo").is_file()
        wix = ElementTree.parse(tmp_path / "build/Desktop.wxs")
        namespaces = {"w": "http://wixtoolset.org/schemas/v4/wxs"}
        shortcut_identity = wix.find(".//w:ShortcutProperty", namespaces)
        assert shortcut_identity is not None
        assert shortcut_identity.attrib == {"Key": "System.AppUserModel.ID", "Value": "md.neve.cadrumo"}
        registry = wix.find(".//w:RegistryValue", namespaces)
        assert registry is not None
        assert registry.attrib["Root"] == "HKLM"
        assert registry.attrib["Key"] == "Software\\md.neve.cadrumo"


def test_payload_rejects_modified_and_unowned_files(tmp_path: Path) -> None:
    root, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    (root / "unowned").touch()
    with pytest.raises(ValueError, match="inventory"):
        validate_payload(root, identity_file)
    (root / "unowned").unlink()
    (root / "cadrumo").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="modified"):
        validate_payload(root, identity_file)


def test_payload_rejects_wrong_target(tmp_path: Path) -> None:
    root, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    identity_file.write_text(json.dumps(asdict(identity("linux-aarch64"))), encoding="utf-8")
    with pytest.raises(ValueError, match="target"):
        validate_payload(root, identity_file)


def test_uninstall_preserves_modified_and_unowned_files(tmp_path: Path) -> None:
    root = tmp_path / "installation"
    root.mkdir()
    (root / "data").mkdir()
    (root / "data/package-manifest.json").write_text("installation anchor", encoding="utf-8")
    (root / "owned").write_text("original", encoding="utf-8")
    (root / "modified").write_text("original", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    inventory(root, receipt, "md.neve.cadrumo")
    (root / "modified").write_text("user edit", encoding="utf-8")
    (root / "unowned").write_text("user data", encoding="utf-8")
    assert uninstall(root, receipt, dry_run=True) == ["modified"]
    assert (root / "owned").exists()
    assert uninstall(root, receipt) == ["modified"]
    assert not (root / "owned").exists()
    assert (root / "modified").read_text(encoding="utf-8") == "user edit"
    assert (root / "unowned").read_text(encoding="utf-8") == "user data"


@pytest.mark.parametrize("relative", ["../escape", "/absolute", "C:/drive", "a\\b", "."])
def test_installation_paths_cannot_escape(tmp_path: Path, relative: str) -> None:
    with pytest.raises(ValueError):
        member(tmp_path, relative)


def test_uninstall_preflights_all_paths(tmp_path: Path) -> None:
    (tmp_path / "owned").write_text("keep", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/package-manifest.json").write_text("anchor", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "files": {
                    "owned": digest(tmp_path / "owned"),
                    "../escape": "bad",
                    "data/package-manifest.json": digest(tmp_path / "data/package-manifest.json"),
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        uninstall(tmp_path, receipt)
    assert (tmp_path / "owned").exists()


def test_install_refuses_staged_content_changed_after_configure(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "linux-x86-64")
    root = prepare(payload, identity_file, tmp_path / "build", "cadrumo")
    receipt = tmp_path / "build/installation.json"
    verify_inventory(root, receipt)
    (root / "opt/cadrumo/cadrumo").write_text("replaced", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        verify_inventory(root, receipt)


def test_uninstall_refuses_a_different_installation(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    root = prepare(payload, identity_file, tmp_path / "build", "cadrumo")
    (root / "app/data/package-manifest.json").write_text("another version", encoding="utf-8")
    with pytest.raises(ValueError, match="does not contain"):
        uninstall(root, tmp_path / "build/installation.json")
    assert (root / "app/cadrumo").exists()


def test_symlinked_prefix_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    redirected = tmp_path / "redirected"
    try:
        redirected.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit unprivileged symlinks")
    with pytest.raises(ValueError, match="link"):
        member(redirected, "file")
