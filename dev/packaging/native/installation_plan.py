"""Project installer-owned bytes once, independently of generated receipts."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid5
from xml.etree.ElementTree import Element, SubElement, tostring

from .hashing import digest
from .identity import DistributionIdentity
from .layout import ApplicationImage, application_images, load_layout
from .macos_launchagent import author_agent, verify_agent
from .package_inventory import package_inventory


def checksum(contents: bytes) -> str:
    """Hash deterministic generated controls without an intermediate file."""
    return hashlib.sha256(contents).hexdigest()


def output_mode(name: str, mode: int = 0o644) -> int:
    """Match Windows' reported read-only/executable flags, or the POSIX mode."""
    if os.name != "nt":
        return mode
    executable = PurePosixPath(name).suffix.lower() in {".exe", ".bat", ".cmd", ".com"}
    return (0o666 if mode & 0o200 else 0o444) | (0o111 if executable else 0)


@dataclass
class Preparation:
    """Trusted source projection; none of these expectations comes from a receipt."""

    destination: str
    files: dict[str, str]
    modes: dict[str, int]
    controls: dict[str, bytes]
    metadata: dict[str, bytes]
    identity: dict[str, object]


def project(payload: Path, identity_file: Path, desktop: str | None, control_root: Path) -> Preparation:
    """Project an already validated payload and current installation controls."""
    manifest_file = payload / "data/package-manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    value = json.loads(identity_file.read_text(encoding="utf-8"))
    target = value["target"]
    managers = [image for image in application_images(manifest["layout"]) if image.target == "rust_manager"]
    versioned = target.startswith("windows-") and bool(managers)
    definition = manifest["layout"].get("installation", {})
    if versioned:
        if definition != load_layout("windows-x64")["installation"]:
            raise ValueError("Manager payload requires the canonical installation layout; rebuild the package")
        if len(managers) != 1 or managers[0].placement != ".":
            raise ValueError("Versioned installation requires one root-level manager image")
        if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value["version"]):
            raise ValueError("Versioned installation requires a canonical numeric release")
    if target.startswith("linux-"):
        destination = f"opt/{value['package_name']}"
    elif target.startswith("macos-"):
        if desktop is None or not desktop or "/" in desktop:
            raise ValueError("A macOS application bundle requires a root-level desktop executable")
        destination = f"{value['name']}.app/Contents/MacOS"
    elif versioned:
        destination = f"{definition['versions']}/{value['version']}"
    else:
        destination = "app"
    source = {**package_inventory(payload, manifest), "data/package-manifest.json": digest(manifest_file)}
    files = {f"{destination}/{name}": value for name, value in source.items()}
    modes = {f"{destination}/{name}": (payload / name).stat().st_mode & 0o777 for name in source}
    controls: dict[str, bytes] = {}
    metadata: dict[str, bytes] = {}
    license_dir = "docs/licenses" if versioned else f"{destination}/docs/licenses"
    for filename, name in (("LICENSE", "CADRUMO.txt"), ("NOTICE", "NOTICE.txt")):
        controls[f"{license_dir}/{name}"] = (control_root / filename).read_bytes()
    # The installation notice directory normalizes all direct children, including
    # a source-owned CPython notice in non-versioned layouts.
    for name in modes:
        if PurePosixPath(name).parent.as_posix() == license_dir:
            modes[name] = output_mode(name)
    if versioned:
        manager = managers[0]
        contents = (payload / manager.package_path).read_bytes()
        if checksum(contents) != source[manager.package_path]:
            raise ValueError("Shared manager source changed after payload validation")
        controls[manager.package_path] = contents
        modes[manager.package_path] = (payload / manager.package_path).stat().st_mode & 0o777
        controls[definition["marker"]] = (
            json.dumps(
                {
                    "schema": definition["schema"],
                    "application_id": value["application_id"],
                    "channel": value["channel"],
                    "platform": manifest["layout"]["platform"],
                    "abi": manifest["layout"]["abi"],
                    "launch_policy": "portable",
                },
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
    if target.startswith("linux-") and bool(desktop):
        controls[f"usr/share/applications/{value['application_id']}.desktop"] = (
            f"[Desktop Entry]\nType=Application\nVersion=1.5\nName={value['name']}\n"
            f'Exec="/opt/{value["package_name"]}/{desktop}"\n'
            f"Icon={value['application_id']}\nTerminal=false\nCategories=Office;Finance;\n"
            "StartupNotify=true\n"
        ).encode()
        controls[f"usr/share/icons/hicolor/scalable/apps/{value['application_id']}.svg"] = (
            control_root / "docs/_static/cadrumo-favicon.svg"
        ).read_bytes()
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
        controls[f"{value['name']}.app/Contents/Info.plist"] = plistlib.dumps(plist)
        if managers:
            if len(managers) != 1 or managers[0].package_path not in manifest["files"]:
                raise ValueError("A macOS LaunchAgent requires one inventory-owned manager image")
            agent = author_agent(DistributionIdentity(**value), managers[0])
            verify_agent(agent.contents, DistributionIdentity(**value), managers[0])
            controls[f"{value['name']}.app/{agent.destination.as_posix()}"] = agent.contents
    if target.startswith("windows-") and bool(desktop) and not versioned:
        metadata = windows_metadata(value, managers, destination, desktop, versioned)
    for name, contents in controls.items():
        files[name] = checksum(contents)
        modes.setdefault(name, output_mode(name))
    helpers = {
        name: digest(Path(__file__).with_name(name + ".py"))
        for name in (
            "installation",
            "installation_plan",
            "installation_currency",
            "installation_reuse",
            "distribution_prepare",
            "installation_filesystem",
            "installation_windows",
            "hashing",
            "identity",
            "layout",
            "package_inventory",
            "docs_stage",
            "macos_launchagent",
            "linux_desktop_runtime",
        )
    }
    binding = {
        "schema": 1,
        "identity": digest(identity_file),
        "desktop": desktop,
        "payload_manifest": source["data/package-manifest.json"],
        "helpers": helpers,
        "files": files,
        "modes": modes,
        "metadata": {name: checksum(data) for name, data in metadata.items()},
        "layout": load_layout(),
    }
    identity = {
        "schema": 1,
        "inputs": checksum(json.dumps(binding, sort_keys=True).encode("utf-8")),
        "payload_manifest": source["data/package-manifest.json"],
    }
    return Preparation(destination, files, modes, controls, metadata, identity)


def windows_metadata(
    value: dict[str, Any], managers: list[ApplicationImage], destination: str, desktop: str | None, versioned: bool
) -> dict[str, bytes]:
    """Render the one canonical Windows desktop metadata description."""
    metadata: dict[str, bytes] = {}
    wix = Element("Wix", xmlns="http://wixtoolset.org/schemas/v4/wxs")
    fragment = SubElement(wix, "Fragment")
    if desktop is not None and desktop:
        menu = SubElement(fragment, "StandardDirectory", Id="ProgramMenuFolder")
        folder = SubElement(menu, "Directory", Id="CADRUMO_MENU", Name=value["name"])
    else:
        folder = SubElement(fragment, "DirectoryRef", Id="INSTALL_ROOT")
    component = SubElement(
        folder,
        "Component",
        Id="CADRUMO_MENU_COMPONENT",
        Bitness="always64",
        Guid=str(uuid5(UUID(value["upgrade_code"]), "start-menu")).upper(),
    )
    if desktop is not None and desktop:
        shortcut = SubElement(
            component,
            "Shortcut",
            Id="CADRUMO_LAUNCH",
            Name=value["name"],
            Target="[INSTALL_ROOT]" + destination.replace("/", "\\") + "\\" + desktop.replace("/", "\\"),
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
    if desktop is not None and desktop:
        SubElement(component, "RemoveFolder", Id="CADRUMO_REMOVE_MENU", On="uninstall")
    if versioned:
        SubElement(
            component,
            "RegistryValue",
            Root="HKLM",
            Key="Software\\" + value["application_id"],
            Name="EntryPoint",
            Type="string",
            Value="[INSTALL_ROOT]" + managers[0].package_path.replace("/", "\\"),
        )
    metadata["Desktop.wxs"] = tostring(wix, encoding="utf-8", xml_declaration=True)
    patch = Element("CPackWiXPatch")
    feature = SubElement(patch, "CPackWiXFragment", Id="#PRODUCTFEATURE")
    SubElement(feature, "ComponentRef", Id="CADRUMO_MENU_COMPONENT")
    metadata["DesktopPatch.xml"] = tostring(patch, encoding="utf-8", xml_declaration=True)
    return metadata
