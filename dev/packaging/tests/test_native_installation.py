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
from dev.packaging.native.distribution_prepare import refresh
from dev.packaging.native.hashing import digest
from dev.packaging.native.identity import identity
from dev.packaging.native.installation import inventory, member, prepare, uninstall, validate_payload, verify_inventory
from dev.packaging.native.installation_plan import BundleInputs
from dev.packaging.native.layout import load_layout
from dev.packaging.native.linux_desktop_runtime import MANIFEST
from dev.packaging.native.linux_desktop_runtime import stage as stage_desktop_runtime
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


class DigestSeal:
    """Pure stand-in for codesign: rewrites the main executable and hashes every other member.

    It isolates the staging order and receipt admission from the native tool, which
    ``test_macos_bundle`` exercises for real.
    """

    def __init__(self) -> None:
        self.sealed: list[dict[str, str]] = []

    def binding(self) -> dict[str, str]:
        return {"identity": "-"}

    @staticmethod
    def _members(bundle: Path) -> dict[str, str]:
        return {
            path.relative_to(bundle).as_posix(): digest(path)
            for path in sorted(bundle.rglob("*"))
            if path.is_file() and path.parent.name != "_CodeSignature"
        }

    def seal(self, bundle: Path, main_executable: Path, application_id: str) -> None:
        main_executable.write_bytes(main_executable.read_bytes() + b" sealed:" + application_id.encode())
        members = self._members(bundle)
        self.sealed.append(members)
        (bundle / "Contents/_CodeSignature").mkdir()
        (bundle / "Contents/_CodeSignature/CodeResources").write_text(json.dumps(members), encoding="utf-8")

    def verify(self, bundle: Path, application_id: str) -> None:
        recorded = json.loads((bundle / "Contents/_CodeSignature/CodeResources").read_text(encoding="utf-8"))
        if recorded != self._members(bundle):
            raise ValueError("synthetic seal is broken")


def bundle_fixture(tmp_path: Path, sealer: DigestSeal | None = None) -> BundleInputs:
    """Synthetic stand-ins for the source build's bundle main executable, icon and sealer."""
    inputs = tmp_path / "bundle-inputs"
    inputs.mkdir(exist_ok=True)
    (inputs / "bundle-launcher").write_bytes(b"synthetic bundle launcher")
    (inputs / "icon.icns").write_bytes(b"synthetic icon")
    return BundleInputs(inputs / "bundle-launcher", inputs / "icon.icns", sealer or DigestSeal())


def bundle_for(tmp_path: Path, target: str) -> BundleInputs | None:
    return bundle_fixture(tmp_path) if target.startswith("macos-") else None


def payload_fixture(tmp_path: Path, target: str, *, manager: bool = False) -> tuple[Path, Path]:
    value = asdict(identity(target))
    identity_file = tmp_path / "identity.json"
    identity_file.write_text(json.dumps(value), encoding="utf-8")
    root = tmp_path / "payload"
    (root / "data").mkdir(parents=True)
    (root / "cadrumo").write_text("synthetic test executable", encoding="utf-8")
    # Desktop payloads require bundled documentation, inventoried by its own hashed manifest.
    (root / "docs/user").mkdir(parents=True)
    (root / "docs/user/index.html").write_text("synthetic documentation", encoding="utf-8")
    docs = {"files": {"index.html": digest(root / "docs/user/index.html")}}
    (root / "docs/user/manifest.json").write_text(json.dumps(docs), encoding="utf-8")
    manifest = {
        "build": value,
        "files": {
            "cadrumo": digest(root / "cadrumo"),
            "docs/user/manifest.json": digest(root / "docs/user/manifest.json"),
        },
        "delegated_inventories": {"docs/user": "docs/user/manifest.json"},
        "user_docs": {"directory": "docs/user", "bundled": True},
        # Only the image the platform mapping declares as the desktop application is registered.
        "layout": {
            "paths": {"docs": "docs"},
            "files": {"package_manifest": "data/package-manifest.json"},
            "entrypoints": {},
            "entrypoint_suffix": "",
            "application_images": [
                {
                    "name": "cadrumo",
                    "placement": ".",
                    "target": "desktop-host-build",
                    "artifact": "CADRUMO_DESKTOP_HOST_EXECUTABLE",
                    "desktop": True,
                    "signed": True,
                    "version_arguments": ["--version"],
                }
            ],
        },
    }
    if manager:
        layout = load_layout("windows-x64")
        manifest["layout"].update({key: layout[key] for key in ("abi", "platform", "installation")})
        manager_image = next(image for image in layout["application_images"] if image["target"] == "rust_manager")
        manifest["layout"]["application_images"].append(dict(manager_image))
        (root / "cadrumo-manager").write_bytes(b"synthetic manager fixture")
        manifest["files"]["cadrumo-manager"] = digest(root / "cadrumo-manager")
    if target.startswith("macos-"):
        manifest["layout"]["application_bundle"] = load_layout(target)["application_bundle"]
    if target.startswith("linux-"):
        linux_layout = load_layout(target)
        manifest["layout"].update({key: linux_layout[key] for key in ("platform", "linux_desktop_runtime")})
        stage_desktop_runtime(root, manifest["layout"])
        manifest["files"][MANIFEST] = digest(root / MANIFEST)
    (root / "data/package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root, identity_file


@pytest.mark.parametrize("target", [item.name for item in SUPPORTED_TARGETS])
def test_native_layout_projects_registration(tmp_path: Path, target: str) -> None:
    payload, identity_file = payload_fixture(tmp_path, target)
    bundle = bundle_for(tmp_path, target)
    root = prepare(payload, identity_file, tmp_path / "build", "cadrumo", bundle=bundle)
    if target.startswith("linux-"):
        assert (root / "opt/cadrumo/cadrumo").is_file()
        desktop = (root / "usr/share/applications/md.neve.cadrumo.desktop").read_text(encoding="utf-8")
        assert 'Exec="/opt/cadrumo/cadrumo"' in desktop
        assert (root / "usr/share/icons/hicolor/scalable/apps/md.neve.cadrumo.svg").is_file()
    elif target.startswith("macos-"):
        assert bundle is not None
        contents = member(root, f"{identity(target).name}.app/Contents")
        metadata = plistlib.loads((contents / "Info.plist").read_bytes())
        assert metadata["CFBundleIdentifier"] == "md.neve.cadrumo"
        assert metadata["LSMinimumSystemVersion"] == "14.0"
        assert metadata["CFBundleExecutable"] == "cadrumo"
        assert metadata["CFBundleIconFile"] == "cadrumo.icns"
        assert metadata["LSUIElement"] is False
        # The main executable is the wrapper; the payload stays whole beneath the resources.
        assert (contents / "MacOS/cadrumo").read_bytes().startswith(bundle.launcher.read_bytes() + b" sealed:")
        assert (contents / "_CodeSignature/CodeResources").is_file()
        # Windows exposes only the read-only bit, not POSIX executable permissions.
        expected_mode = 0o666 if os.name == "nt" else 0o755
        assert (contents / "MacOS/cadrumo").stat().st_mode & 0o777 == expected_mode
        assert (contents / "Resources/cadrumo.icns").read_bytes() == bundle.icon.read_bytes()
        assert sorted(path.name for path in (contents / "MacOS").iterdir()) == ["cadrumo"]
        assert (contents / "Resources/app/cadrumo").read_bytes() == (payload / "cadrumo").read_bytes()
        assert (contents / "Resources/app/data/package-manifest.json").is_file()
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


def test_macos_bundle_refuses_missing_wrapper_inputs(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "macos-arm64")
    with pytest.raises(ValueError, match="main executable and icon"):
        prepare(payload, identity_file, tmp_path / "build", "cadrumo")


def test_macos_bundle_tracks_wrapper_input_changes(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "macos-arm64")
    paths = json.loads((tmp_path / "build/build-paths.json").read_text(encoding="utf-8"))
    paths["paths"]["installation_receipts"] = "installation/receipts"
    (tmp_path / "build/build-paths.json").write_text(json.dumps(paths), encoding="utf-8")
    bundle = bundle_fixture(tmp_path)
    root = prepare(payload, identity_file, tmp_path / "build", "cadrumo", bundle=bundle)
    launcher = member(root, f"{identity('macos-arm64').name}.app/Contents/MacOS/cadrumo")
    bundle.launcher.write_bytes(b"rebuilt bundle launcher")
    with pytest.raises(ValueError, match="differs from the requested payload"):
        prepare(payload, identity_file, tmp_path / "build", "cadrumo", bundle=bundle)
    refresh(payload, identity_file, tmp_path / "build", "cadrumo", bundle)
    assert launcher.read_bytes().startswith(b"rebuilt bundle launcher sealed:")


def test_macos_bundle_seal_is_the_last_write_and_binds_the_receipt(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "macos-arm64")
    sealer = DigestSeal()
    bundle = bundle_fixture(tmp_path, sealer)
    root = prepare(payload, identity_file, tmp_path / "build", "cadrumo", bundle=bundle)
    application = member(root, f"{identity('macos-arm64').name}.app")
    # The seal saw every member that the stage finally holds, so nothing was written after it.
    assert sealer.sealed == [DigestSeal._members(application)]
    assert "Contents/Info.plist" in sealer.sealed[0]
    assert "Contents/Resources/app/data/package-manifest.json" in sealer.sealed[0]
    receipt = json.loads((tmp_path / "build/installation/metadata/installation.json").read_text(encoding="utf-8"))
    sealed = f"{application.name}/Contents/_CodeSignature/CodeResources"
    assert receipt["files"][sealed] == digest(member(root, sealed))
    # The receipt lives outside the bundle it describes.
    assert not any(path.name == "installation.json" for path in application.rglob("*"))
    # An unchanged stage is admitted again only while its seal still verifies.
    assert prepare(payload, identity_file, tmp_path / "build", "cadrumo", bundle=bundle) == root
    assert len(sealer.sealed) == 1
    (application / "Contents/_CodeSignature/CodeResources").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="synthetic seal is broken"):
        prepare(payload, identity_file, tmp_path / "build", "cadrumo", bundle=bundle)


@pytest.mark.parametrize("desktop", [True, False])
def test_windows_manager_stage_has_stable_entry_and_unmodified_version_inventory(tmp_path: Path, desktop: bool) -> None:
    payload, identity_file = payload_fixture(tmp_path, "windows-x86-64", manager=True)
    desktop_entry = "cadrumo" if desktop else None
    root = prepare(payload, identity_file, tmp_path / "build", desktop_entry)
    version = json.loads(identity_file.read_text(encoding="utf-8"))["version"]
    package = root / "versions" / version
    validate_payload(package, identity_file, "cadrumo")
    assert (root / "cadrumo-manager").read_bytes() == (package / "cadrumo-manager").read_bytes()
    assert (package / "cadrumo").is_file()
    assert (root / "docs/licenses/CADRUMO.txt").is_file()
    assert not (package / "docs/licenses/CADRUMO.txt").exists()
    marker = json.loads((root / "data/installation.json").read_text(encoding="utf-8"))
    assert marker == {
        "schema": 1,
        "application_id": "md.neve.cadrumo",
        "channel": "stable",
        "platform": "windows-x64",
        "abi": 1,
        "launch_policy": "portable",
    }
    assert not (tmp_path / "build/installation/metadata/Desktop.wxs").exists()
    assert not (tmp_path / "build/installation/metadata/DesktopPatch.xml").exists()
    assert prepare(payload, identity_file, tmp_path / "build", desktop_entry) == root
    # A receipt for one version cannot remove entry points shared by another version.
    other = root / "versions/0.0.1/data"
    other.mkdir(parents=True)
    (other / "package-manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Multiple installed versions"):
        uninstall(root, tmp_path / "build/installation/metadata/installation.json")
    assert (root / "cadrumo-manager").is_file()
    assert (package / "cadrumo").is_file()


def test_payload_rejects_modified_and_unowned_files(tmp_path: Path) -> None:
    root, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    (root / "unowned").touch()
    with pytest.raises(ValueError, match="inventory"):
        validate_payload(root, identity_file)
    (root / "unowned").unlink()
    (root / "cadrumo").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="modified"):
        validate_payload(root, identity_file)


def test_only_the_declared_desktop_image_receives_registration(tmp_path: Path) -> None:
    root, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    validate_payload(root, identity_file, "cadrumo")
    with pytest.raises(ValueError, match="declares receives desktop registration"):
        validate_payload(root, identity_file, "docs/user/manifest.json")
    manifest_file = root / "data/package-manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest["layout"]["application_images"][0]["desktop"] = False
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="declares receives desktop registration"):
        validate_payload(root, identity_file, "cadrumo")


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
