"""Project installer-owned bytes once, independently of generated receipts."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast
from uuid import UUID, uuid5
from xml.etree.ElementTree import Element, SubElement, tostring

from .hashing import digest
from .identity import DistributionIdentity
from .layout import ApplicationBundle, ApplicationImage, application_bundle, application_images, load_layout
from .macos_bundle import BundleSealer, sealed_members
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


@dataclass(frozen=True)
class BundleInputs:
    """Build artifacts an application wrapper needs beyond the payload it nests, and its sealer."""

    launcher: Path
    icon: Path
    sealer: BundleSealer


@dataclass(frozen=True)
class BundleSeal:
    """The stage-relative application bundle that is sealed after every other member is written.

    ``sealed`` names the members the seal rewrites or creates. Their bytes come from
    the seal over the projected members, not from the projection itself.
    """

    application: str
    main_executable: str
    application_id: str
    sealed: frozenset[str]
    sealer: BundleSealer


@dataclass
class Preparation:
    """Trusted source projection; none of these expectations comes from a receipt."""

    destination: str
    files: dict[str, str]
    modes: dict[str, int]
    controls: dict[str, bytes]
    metadata: dict[str, bytes]
    identity: dict[str, object]
    seal: BundleSeal | None = None

    def admits(self, files: Mapping[str, str]) -> bool:
        """Return whether an actual stage inventory is this projection, sealed when declared.

        Unsealed members must match their projected bytes exactly. The bundle seal's
        own members must all be present; the seal verification proves their bytes.
        """
        if self.seal is None:
            return dict(files) == self.files
        sealed = self.seal.sealed
        projected = {name: value for name, value in self.files.items() if name not in sealed}
        actual = {name: value for name, value in files.items() if name not in sealed}
        return actual == projected and sealed <= files.keys()


def project(
    payload: Path,
    identity_file: Path,
    desktop: str | None,
    control_root: Path,
    bundle: BundleInputs | None = None,
) -> Preparation:
    """Project an already validated payload and current installation controls."""
    manifest_file = payload / "data/package-manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    value = json.loads(identity_file.read_text(encoding="utf-8"))
    target = value["target"]
    managers = [image for image in application_images(manifest["layout"]) if image.target == "rust_manager"]
    versioned = target.startswith("windows-") and bool(managers)
    definition = manifest["layout"].get("installation", {})
    wrapper = application_bundle(manifest["layout"]) if target.startswith("macos-") else None
    destination = _installation_destination(target, value, definition, managers, desktop, versioned, wrapper)
    source = {**package_inventory(payload, manifest), "data/package-manifest.json": digest(manifest_file)}
    files, modes = _payload_projection(payload, destination, source)
    controls: dict[str, bytes] = {}
    _license_controls(versioned, destination, control_root, controls, modes)
    if versioned:
        _versioned_controls(
            payload,
            managers[0],
            source,
            definition,
            value,
            manifest["layout"]["platform"],
            manifest["layout"]["abi"],
            controls,
            modes,
        )
    _linux_controls(target, desktop, value, control_root, controls)
    seal = None
    if wrapper is not None and desktop is not None:
        if bundle is None:
            raise ValueError("A macOS application bundle requires its main executable and icon")
        _macos_controls(wrapper, bundle, desktop, value, managers, manifest["files"], controls, modes)
        application = f"{value['name']}.app"
        seal = BundleSeal(
            application,
            f"{application}/{wrapper.executable_directory}/{desktop}",
            value["application_id"],
            sealed_members(application, wrapper, desktop),
            bundle.sealer,
        )
    metadata = _legacy_windows_metadata(target, desktop, versioned, value, managers, destination)
    _include_controls(controls, files, modes)
    helpers = _installation_helper_hashes()
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
        "seal": None if seal is None else seal.sealer.binding(),
    }
    identity: dict[str, object] = {
        "schema": 1,
        "inputs": checksum(json.dumps(binding, sort_keys=True).encode("utf-8")),
        "payload_manifest": source["data/package-manifest.json"],
    }
    return Preparation(destination, files, modes, controls, metadata, identity, seal)


def _legacy_windows_metadata(
    target: str,
    desktop: str | None,
    versioned: bool,
    value: dict[str, Any],
    managers: list[ApplicationImage],
    destination: str,
) -> dict[str, bytes]:
    if target.startswith("windows-") and bool(desktop) and not versioned:
        return windows_metadata(value, managers, destination, desktop, versioned)
    return {}


def _license_controls(
    versioned: bool, destination: str, control_root: Path, controls: dict[str, bytes], modes: dict[str, int]
) -> None:
    license_dir = "docs/licenses" if versioned else f"{destination}/docs/licenses"
    for filename, name in (("LICENSE", "CADRUMO.txt"), ("NOTICE", "NOTICE.txt")):
        controls[f"{license_dir}/{name}"] = (control_root / filename).read_bytes()
    # The installation notice directory normalizes all direct children, including
    # a source-owned CPython notice in non-versioned layouts.
    for name in modes:
        if PurePosixPath(name).parent.as_posix() == license_dir:
            modes[name] = output_mode(name)


def _installation_helper_hashes() -> dict[str, str]:
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
            "macos_bundle",
            "linux_desktop_runtime",
        )
    }
    return helpers


def _include_controls(controls: Mapping[str, bytes], files: dict[str, str], modes: dict[str, int]) -> None:
    for name, contents in controls.items():
        files[name] = checksum(contents)
        modes.setdefault(name, output_mode(name))


def _payload_projection(
    payload: Path, destination: str, source: Mapping[str, str]
) -> tuple[dict[str, str], dict[str, int]]:
    files = {f"{destination}/{name}": value for name, value in source.items()}
    modes = {f"{destination}/{name}": (payload / name).stat().st_mode & 0o777 for name in source}
    return files, modes


def _versioned_controls(
    payload: Path,
    manager: ApplicationImage,
    source: Mapping[str, str],
    definition: Mapping[str, str | int],
    value: Mapping[str, str],
    platform: str,
    abi: str,
    controls: dict[str, bytes],
    modes: dict[str, int],
) -> None:
    contents = (payload / manager.package_path).read_bytes()
    if checksum(contents) != source[manager.package_path]:
        raise ValueError("Shared manager source changed after payload validation")
    controls[manager.package_path] = contents
    modes[manager.package_path] = (payload / manager.package_path).stat().st_mode & 0o777
    controls[cast("str", definition["marker"])] = (
        json.dumps(
            {
                "schema": definition["schema"],
                "application_id": value["application_id"],
                "channel": value["channel"],
                "platform": platform,
                "abi": abi,
                "launch_policy": "portable",
            },
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _linux_controls(
    target: str, desktop: str | None, value: Mapping[str, str], control_root: Path, controls: dict[str, bytes]
) -> None:
    if target.startswith("linux-") and bool(desktop):
        controls[f"usr/share/applications/{value['application_id']}.desktop"] = (
            f"[Desktop Entry]\nType=Application\nVersion=1.5\nName={value['name']}\n"
            f'Exec="/opt/{value["package_name"]}/{desktop}"\n'
            f"Icon={value['application_id']}\nTerminal=false\nCategories=Office;Finance;\n"
            "StartupNotify=true\n"
        ).encode()
        controls[f"usr/share/icons/hicolor/scalable/apps/{value['application_id']}.svg"] = (
            control_root / "docs/_static/cadrumo-icon.svg"
        ).read_bytes()


def _macos_controls(
    wrapper: ApplicationBundle,
    bundle: BundleInputs,
    desktop: str,
    value: Mapping[str, str],
    managers: list[ApplicationImage],
    files: Mapping[str, object],
    controls: dict[str, bytes],
    modes: dict[str, int],
) -> None:
    application = f"{value['name']}.app"
    icon = f"{PurePosixPath(desktop).name}.icns"
    plist = {
        "CFBundleIdentifier": value["application_id"],
        "CFBundleName": value["name"],
        "CFBundleDisplayName": value["name"],
        "CFBundleExecutable": desktop,
        "CFBundleIconFile": icon,
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": value["version"],
        "CFBundleVersion": value["version"],
        "LSMinimumSystemVersion": value["compatibility_floor"].removeprefix("macos-"),
        "LSApplicationCategoryType": "public.app-category.finance",
        # The desktop is an ordinary windowed application with a Dock presence.
        "LSUIElement": False,
        "NSHighResolutionCapable": True,
    }
    controls[f"{application}/Contents/Info.plist"] = plistlib.dumps(plist, sort_keys=True)
    launcher = f"{application}/{wrapper.executable_directory}/{desktop}"
    controls[launcher] = bundle.launcher.read_bytes()
    modes[launcher] = output_mode(launcher, 0o755)
    controls[f"{application}/{wrapper.resources}/{icon}"] = bundle.icon.read_bytes()
    if managers:
        if len(managers) != 1 or managers[0].package_path not in files:
            raise ValueError("A macOS LaunchAgent requires one inventory-owned manager image")
        agent = author_agent(DistributionIdentity(**value), managers[0], wrapper)
        verify_agent(agent.contents, DistributionIdentity(**value), managers[0], wrapper)
        controls[f"{application}/{agent.destination.as_posix()}"] = agent.contents


def _installation_destination(
    target: str,
    value: Mapping[str, str],
    definition: Mapping[str, object],
    managers: list[ApplicationImage],
    desktop: str | None,
    versioned: bool,
    wrapper: ApplicationBundle | None,
) -> str:
    if versioned:
        _require_versioned_layout(definition, managers, value["version"])
    if target.startswith("linux-"):
        destination = f"opt/{value['package_name']}"
    elif target.startswith("macos-"):
        if desktop is None or not desktop or "/" in desktop:
            raise ValueError("A macOS application bundle requires a root-level desktop executable")
        if wrapper is None:
            raise ValueError("The macOS platform mapping must declare its application bundle")
        destination = f"{value['name']}.app/{wrapper.payload}"
    elif versioned:
        destination = f"{definition['versions']}/{value['version']}"
    else:
        destination = "app"
    return destination


def _require_versioned_layout(definition: Mapping[str, object], managers: list[ApplicationImage], version: str) -> None:
    if definition != load_layout("windows-x64")["installation"]:
        raise ValueError("Manager payload requires the canonical installation layout; rebuild the package")
    if len(managers) != 1 or managers[0].placement != ".":
        raise ValueError("Versioned installation requires one root-level manager image")
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("Versioned installation requires a canonical numeric release")


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
