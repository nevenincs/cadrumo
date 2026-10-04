"""Validate native payloads and remove only unchanged files owned by a prefix install."""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid5
from xml.etree.ElementTree import Element, SubElement, tostring

from dev._paths import REPO_ROOT

from .hashing import digest
from .installation_filesystem import file_identity, remove_owned_file


def member(root: Path, relative: str) -> Path:
    """Reject traversal, Windows drive paths and symlink/reparse redirection."""
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"Unsafe installation member: {relative}")
    candidate = root.joinpath(*path.parts)
    for parent in (candidate, *candidate.parents):
        if parent.is_symlink() or parent.is_junction():
            raise ValueError(f"Installation path redirects through a link: {parent}")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Installation path escapes prefix: {relative}")
    return candidate


def validate_payload(root: Path, identity_file: Path, desktop: str | None = None) -> None:
    """Require the payload to match the requested target, channel and release."""
    expected = json.loads(identity_file.read_text(encoding="utf-8"))
    if desktop and not re.fullmatch(r"[A-Za-z0-9_./-]+", desktop):
        raise ValueError("Desktop executable must use a safe payload-relative path")
    manifest_file = member(root, "data/package-manifest.json")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    for key in ("application_id", "version", "target", "channel"):
        if manifest["build"].get(key) != expected[key]:
            raise ValueError(f"Payload {key} does not match requested distribution")
    files = manifest["files"]
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(files) | {"data/package-manifest.json"}:
        raise ValueError("Payload inventory differs from its package manifest")
    for name, checksum in files.items():
        file = member(root, name)
        if not file.is_file() or digest(file) != checksum:
            raise ValueError(f"Payload file is missing or modified: {name}")
    if desktop and desktop not in files:
        raise ValueError("Desktop executable must belong to the verified payload inventory")
    for path in root.rglob("*"):
        member(root, path.relative_to(root).as_posix())


def inventory(root: Path, destination: Path, application_id: str) -> None:
    """Capture the staged installation's exact files before native packaging."""
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        checked = member(root, relative)
        if checked.is_file():
            files[relative] = digest(checked)
    destination.write_text(
        json.dumps({"application_id": application_id, "files": files}, indent=2) + "\n", encoding="utf-8"
    )


def verify_inventory(root: Path, receipt: Path) -> None:
    """Refuse stale or tampered staged input immediately before CMake installs it."""
    owned = json.loads(receipt.read_text(encoding="utf-8"))["files"]
    actual = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if member(root, relative).is_file():
            actual.add(relative)
    if actual != set(owned):
        raise ValueError("Staged installation inventory has changed; reconfigure")
    for relative, checksum in owned.items():
        if digest(member(root, relative)) != checksum:
            raise ValueError(f"Staged installation file has changed: {relative}")


def uninstall(prefix: Path, receipt: Path, *, dry_run: bool = False) -> list[str]:
    """Preserve modified/unowned files and never follow directory links."""
    if not prefix.is_absolute() or prefix.resolve() == Path(prefix.anchor):
        raise ValueError("An explicit non-root absolute installation prefix is required")
    owned = json.loads(receipt.read_text(encoding="utf-8"))["files"]
    anchors = [
        name for name in owned if name == "data/package-manifest.json" or name.endswith("/data/package-manifest.json")
    ]
    if len(anchors) != 1:
        raise ValueError("Receipt must identify exactly one native package manifest")
    anchor = member(prefix, anchors[0])
    if not anchor.is_file() or digest(anchor) != owned[anchors[0]]:
        raise ValueError("Prefix does not contain the package identified by this receipt")
    removals = []
    preserved: list[str] = []
    # Preflight the entire receipt before removing anything.
    for relative, checksum in owned.items():
        if not isinstance(relative, str) or not isinstance(checksum, str):
            raise ValueError("Invalid installation receipt entry")
        path = member(prefix, relative)
        if not path.exists():
            continue
        if not path.is_file() or digest(path) != checksum:
            preserved.append(relative)
        else:
            removals.append((relative, checksum, file_identity(path)))
    if not dry_run:
        # Keep the anchor until every other file's retained removal has settled.
        removals.sort(key=lambda item: item[0] == anchors[0])
        for relative, checksum, expected in removals:
            if relative == anchors[0] and preserved:
                continue
            path = member(prefix, relative)
            if not remove_owned_file(path, checksum, expected):
                preserved.append(relative)
        # Empty directories do not belong to the receipt. Preserve them rather
        # than removing a newly replaced/unowned directory by its path name.
    return preserved


def prepare(payload: Path, identity_file: Path, build: Path, desktop: str | None = None) -> Path:
    """Reuse only an unchanged, identical owning stage; never erase existing state."""
    validate_payload(payload, identity_file, desktop)
    build = build.absolute()
    root = member(build, "native-install-tree")
    if root.exists():
        receipt = member(build, "installation.json")
        if not receipt.is_file():
            raise ValueError("Existing native installation stage has no owning receipt; select a fresh build directory")
        verify_inventory(root, receipt)
        with tempfile.TemporaryDirectory(prefix="native-install-candidate-", dir=build) as scratch:
            candidate = Path(scratch)
            _prepare_fresh(payload, identity_file, candidate, desktop)
            expected = json.loads((candidate / "installation.json").read_text(encoding="utf-8"))
            existing = json.loads(receipt.read_text(encoding="utf-8"))
            if existing != expected:
                raise ValueError(
                    "Native installation stage differs from the requested payload; select a fresh build directory"
                )
        # Recheck after construction: another writer may have touched the stage.
        verify_inventory(root, receipt)
        return root
    return _prepare_fresh(payload, identity_file, build, desktop)


def _prepare_fresh(payload: Path, identity_file: Path, build: Path, desktop: str | None = None) -> Path:
    """Create platform installation layout, with desktop registration only for a real entrypoint."""
    validate_payload(payload, identity_file, desktop)
    value = json.loads(identity_file.read_text(encoding="utf-8"))
    build = build.absolute()
    root = member(build, "native-install-tree")
    if payload.resolve().is_relative_to(root) or root.is_relative_to(payload.resolve()):
        raise ValueError("Payload and installer staging directory must not overlap")
    root.mkdir(parents=True, mode=0o700)
    target = value["target"]
    if target.startswith("linux-"):
        destination = root / "opt" / value["package_name"]
    elif target.startswith("macos-"):
        if not desktop or "/" in desktop:
            raise ValueError("A macOS application bundle requires a root-level desktop executable")
        destination = root / f"{value['name']}.app" / "Contents/MacOS"
    else:
        destination = root / "app"
    shutil.copytree(payload, destination, dirs_exist_ok=True)
    validate_payload(destination, identity_file, desktop)
    license_dir = destination / "docs/licenses"
    license_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "LICENSE", license_dir / "CADRUMO.txt")
    shutil.copy2(REPO_ROOT / "NOTICE", license_dir / "NOTICE.txt")
    for file in license_dir.iterdir():
        if file.is_file():
            file.chmod(0o644)
    if target.startswith("linux-") and desktop:
        applications = root / "usr/share/applications"
        applications.mkdir(parents=True)
        (applications / f"{value['application_id']}.desktop").write_text(
            "[Desktop Entry]\nType=Application\nVersion=1.5\n"
            f'Name={value["name"]}\nExec="/opt/{value["package_name"]}/{desktop}"\n'
            f"Icon={value['application_id']}\nTerminal=false\nCategories=Office;Finance;\n"
            "StartupNotify=true\n",
            encoding="utf-8",
        )
        icons = root / "usr/share/icons/hicolor/scalable/apps"
        icons.mkdir(parents=True)
        shutil.copy2(REPO_ROOT / "docs/_static/cadrumo-favicon.svg", icons / f"{value['application_id']}.svg")
    if target.startswith("macos-"):
        plist = {
            "CFBundleIdentifier": value["application_id"],
            "CFBundleName": value["name"],
            "CFBundleDisplayName": value["name"],
            "CFBundleExecutable": desktop,
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": value["version"],
            "CFBundleVersion": value["version"],
            "LSMinimumSystemVersion": value["compatibility_floor"].removeprefix("macos-"),
            "LSApplicationCategoryType": "public.app-category.finance",
            "NSHighResolutionCapable": True,
        }
        (destination.parent / "Info.plist").write_bytes(plistlib.dumps(plist))
    if target.startswith("windows-") and desktop:
        wix = Element("Wix", xmlns="http://wixtoolset.org/schemas/v4/wxs")
        fragment = SubElement(wix, "Fragment")
        menu = SubElement(fragment, "StandardDirectory", Id="ProgramMenuFolder")
        folder = SubElement(menu, "Directory", Id="CADRUMO_MENU", Name=value["name"])
        component = SubElement(
            folder,
            "Component",
            Id="CADRUMO_MENU_COMPONENT",
            Bitness="always64",
            Guid=str(uuid5(UUID(value["upgrade_code"]), "start-menu")).upper(),
        )
        shortcut = SubElement(
            component,
            "Shortcut",
            Id="CADRUMO_LAUNCH",
            Name=value["name"],
            Target="[INSTALL_ROOT]app\\" + desktop.replace("/", "\\"),
            WorkingDirectory="INSTALL_ROOT",
        )
        SubElement(shortcut, "ShortcutProperty", Key="System.AppUserModel.ID", Value=value["application_id"])
        SubElement(
            component,
            "RegistryValue",
            Root="HKLM",
            Key="Software\\" + value["application_id"],
            Name="InstallLocation",
            Type="string",
            Value="[INSTALL_ROOT]",
            KeyPath="yes",
        )
        SubElement(component, "RemoveFolder", Id="CADRUMO_REMOVE_MENU", On="uninstall")
        (build / "Desktop.wxs").write_bytes(tostring(wix, encoding="utf-8", xml_declaration=True))
        patch = Element("CPackWiXPatch")
        feature = SubElement(patch, "CPackWiXFragment", Id="#PRODUCTFEATURE")
        SubElement(feature, "ComponentRef", Id="CADRUMO_MENU_COMPONENT")
        (build / "DesktopPatch.xml").write_bytes(tostring(patch, encoding="utf-8", xml_declaration=True))
    # Receipt lives in the build tree, outside the user's installation and storage.
    inventory(root, build / "installation.json", value["application_id"])
    return root


def main() -> None:
    """Expose configure validation and explicit prefix uninstall operations."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--payload", type=Path, required=True)
    validate.add_argument("--identity", type=Path, required=True)
    validate.add_argument("--desktop")
    stage = commands.add_parser("prepare")
    stage.add_argument("--payload", type=Path, required=True)
    stage.add_argument("--identity", type=Path, required=True)
    stage.add_argument("--build", type=Path, required=True)
    stage.add_argument("--desktop")
    capture = commands.add_parser("inventory")
    capture.add_argument("--root", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--application-id", required=True)
    verify = commands.add_parser("verify-inventory")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--receipt", type=Path, required=True)
    remove = commands.add_parser("uninstall")
    remove.add_argument("--prefix", type=Path, required=True)
    remove.add_argument("--receipt", type=Path, required=True)
    remove.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        validate_payload(args.payload, args.identity, args.desktop)
    elif args.command == "prepare":
        prepare(args.payload, args.identity, args.build, args.desktop)
    elif args.command == "inventory":
        inventory(args.root, args.output, args.application_id)
    elif args.command == "verify-inventory":
        verify_inventory(args.root, args.receipt)
    else:
        preserved = uninstall(args.prefix, args.receipt, dry_run=args.dry_run)
        print(json.dumps({"preserved_modified_files": preserved, "dry_run": args.dry_run}))


if __name__ == "__main__":
    main()
