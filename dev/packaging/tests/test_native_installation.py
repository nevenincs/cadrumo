"""Package layout and prefix removal safety, using explicitly synthetic payloads."""

from __future__ import annotations

import json
import os
import plistlib
from dataclasses import asdict
from pathlib import Path

import pytest
from defusedxml import ElementTree

from dev.packaging.native import installation, installation_filesystem
from dev.packaging.native.hashing import digest
from dev.packaging.native.identity import identity
from dev.packaging.native.installation import inventory, member, prepare, uninstall, validate_payload, verify_inventory
from dev.packaging.runtime_wheelhouse_contract import SUPPORTED_TARGETS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(autouse=True)
def cmake_paths(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir()
    (build / "build-paths.json").write_text(
        json.dumps(
            {
                "paths": {
                    "installation_stage": "installation/stage",
                    "installation_metadata": "installation/metadata",
                    "installation_work": "installation/work",
                }
            }
        ),
        encoding="utf-8",
    )


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
        wix = ElementTree.parse(tmp_path / "build/installation/metadata/Desktop.wxs")
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
    receipt = tmp_path / "build/installation/metadata/installation.json"
    verify_inventory(root, receipt)
    (root / "opt/cadrumo/cadrumo").write_text("replaced", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        verify_inventory(root, receipt)


def test_uninstall_refuses_a_different_installation(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    root = prepare(payload, identity_file, tmp_path / "build", "cadrumo")
    (root / "app/data/package-manifest.json").write_text("another version", encoding="utf-8")
    with pytest.raises(ValueError, match="does not contain"):
        uninstall(root, tmp_path / "build/installation/metadata/installation.json")
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


def test_prepare_refuses_a_preexisting_unowned_stage_without_deleting_it(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    root = tmp_path / "build/installation/stage"
    root.mkdir(parents=True)
    sentinel = root / "user-owned"
    sentinel.write_text("preserve me", encoding="utf-8")
    with pytest.raises(ValueError, match="no owning receipt"):
        prepare(payload, identity_file, tmp_path / "build", "cadrumo")
    assert sentinel.read_text(encoding="utf-8") == "preserve me"


@pytest.mark.parametrize("change", ["modified", "unowned"])
def test_prepare_preserves_intervening_stage_changes(tmp_path: Path, change: str) -> None:
    payload, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    root = prepare(payload, identity_file, tmp_path / "build", "cadrumo")
    path = root / ("app/cadrumo" if change == "modified" else "user-owned")
    path.write_text("preserve me", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        prepare(payload, identity_file, tmp_path / "build", "cadrumo")
    assert path.read_text(encoding="utf-8") == "preserve me"


def test_prepare_reuses_an_identical_owned_stage_without_replacing_files(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    root = prepare(payload, identity_file, tmp_path / "build", "cadrumo")
    before = (root / "app/cadrumo").stat()
    assert prepare(payload, identity_file, tmp_path / "build", "cadrumo") == root
    after = (root / "app/cadrumo").stat()
    assert (after.st_dev, after.st_ino, after.st_mtime_ns) == (before.st_dev, before.st_ino, before.st_mtime_ns)


def test_prepare_refuses_a_different_requested_payload_without_erasing_old_stage(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    root = prepare(payload, identity_file, tmp_path / "build", "cadrumo")
    before = (root / "app/cadrumo").read_bytes()
    (payload / "cadrumo").write_text("new release", encoding="utf-8")
    manifest_path = payload / "data/package-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["cadrumo"] = digest(payload / "cadrumo")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from the requested payload"):
        prepare(payload, identity_file, tmp_path / "build", "cadrumo")
    assert (root / "app/cadrumo").read_bytes() == before


def test_uninstall_preserves_a_file_changed_after_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "installation"
    (root / "data").mkdir(parents=True)
    (root / "data/package-manifest.json").write_text("anchor", encoding="utf-8")
    owned = root / "owned"
    owned.write_text("original", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    inventory(root, receipt, "md.neve.cadrumo")
    original = installation.digest

    def intervene(path: Path) -> str:
        checksum = original(path)
        if path == owned:
            owned.write_text("intervening user edit", encoding="utf-8")
        return checksum

    monkeypatch.setattr(installation, "digest", intervene)
    assert uninstall(root, receipt) == ["owned"]
    assert owned.read_text(encoding="utf-8") == "intervening user edit"
    assert (root / "data/package-manifest.json").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX no-replace claim interleaving")
def test_posix_claim_restores_an_intervening_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    owned = tmp_path / "owned"
    owned.write_text("original", encoding="utf-8")
    checksum = digest(owned)
    expected = installation_filesystem.file_identity(owned)
    original = installation_filesystem.rename_noreplace_at
    replaced = False

    def intervene(*, source_fd: int, source_name: str, destination_fd: int, destination_name: str) -> None:
        nonlocal replaced
        if not replaced:
            replaced = True
            owned.rename(tmp_path / "earlier-owned")
            owned.write_text("replacement belongs to a different owner", encoding="utf-8")
        original(
            source_fd=source_fd,
            source_name=source_name,
            destination_fd=destination_fd,
            destination_name=destination_name,
        )

    monkeypatch.setattr(installation_filesystem, "rename_noreplace_at", intervene)
    assert installation_filesystem.remove_owned_file(owned, checksum, expected) is False
    assert owned.read_text(encoding="utf-8") == "replacement belongs to a different owner"


@pytest.mark.skipif(os.name == "nt", reason="POSIX retained directory descriptor interleaving")
def test_posix_parent_redirection_preserves_the_claim_and_outside_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "program"
    parent.mkdir()
    owned = parent / "owned"
    owned.write_text("original", encoding="utf-8")
    checksum = digest(owned)
    expected = installation_filesystem.file_identity(owned)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "owned").write_text("outside data", encoding="utf-8")
    original = installation_filesystem.rename_noreplace_at
    redirected = False

    def intervene(*, source_fd: int, source_name: str, destination_fd: int, destination_name: str) -> None:
        nonlocal redirected
        if not redirected:
            redirected = True
            parent.rename(tmp_path / "earlier-program")
            parent.symlink_to(outside, target_is_directory=True)
        original(
            source_fd=source_fd,
            source_name=source_name,
            destination_fd=destination_fd,
            destination_name=destination_name,
        )

    monkeypatch.setattr(installation_filesystem, "rename_noreplace_at", intervene)
    assert installation_filesystem.remove_owned_file(owned, checksum, expected) is False
    assert (outside / "owned").read_text(encoding="utf-8") == "outside data"
    assert (tmp_path / "earlier-program/owned").read_text(encoding="utf-8") == "original"
