"""Author scoped MSI ownership sources; native maintenance integration gates installation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from .build_paths import build_paths
from .hashing import digest
from .identity import DistributionIdentity
from .installation import member, validate_payload, verify_inventory
from .layout import application_images, load_layout
from .windows_msi_identity import InstallationScope, MsiIdentity, ProductRole, msi_identity

WIX_NAMESPACE = "http://wixtoolset.org/schemas/v4/wxs"
MAINTENANCE_GATE = "Native MSI transaction, scope admission and safe maintenance are not yet integrated."


def _staged_manifest(build: Path) -> tuple[Path, dict[str, str], Path, dict[str, Any]]:
    paths = build_paths(build)
    stage = paths["installation_stage"]
    receipt = member(paths["installation_metadata"], "installation.json")
    verify_inventory(stage, receipt)
    document = json.loads(receipt.read_text(encoding="utf-8"))
    owned = document["files"]
    anchors = [
        name for name in owned if name == "data/package-manifest.json" or name.endswith("/data/package-manifest.json")
    ]
    if len(anchors) != 1:
        raise ValueError("MSI stage must identify exactly one verified package")
    manifest = member(stage, anchors[0])
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if document["application_id"] != value["build"]["application_id"]:
        raise ValueError("MSI receipt and package identities differ")
    return stage, owned, manifest, value


def reject_combined_manager_msi(build: Path) -> None:
    """Prevent the legacy CPack product from owning a manager version and shared entry."""
    _, _, _, manifest = _staged_manifest(build)
    if any(image.target == "rust_manager" for image in application_images(manifest["layout"])):
        raise ValueError("Manager payloads require separate version and registration MSI products. " + MAINTENANCE_GATE)


def _literal(value: str) -> str:
    # WiX preprocessing must never interpret metadata or source paths as expressions.
    if "$" in value:
        raise ValueError("MSI authoring cannot admit WiX preprocessor expressions in literal inputs")
    return value


def _component(parent: Element, feature: Element, product: MsiIdentity, resource: str) -> Element:
    code = product.component_code(resource)
    component_id = "C_" + code.replace("-", "")
    component = SubElement(parent, "Component", Id=component_id, Guid=code, Bitness="always64")
    SubElement(feature, "ComponentRef", Id=component_id)
    return component


def _files(
    package: Element,
    feature: Element,
    product: MsiIdentity,
    value: DistributionIdentity,
    stage: Path,
    members: dict[str, str],
    native_marker: tuple[str, Path],
) -> Element:
    standard = SubElement(package, "StandardDirectory", Id=product.root_directory)
    root = SubElement(standard, "Directory", Id="INSTALL_ROOT", Name=_literal(value.name))
    directories = {"": root}
    seen: set[str] = set()
    for relative in sorted(members):
        if relative.casefold() in seen:
            raise ValueError("MSI resources collide in the Windows filename namespace")
        seen.add(relative.casefold())
        path = PurePosixPath(relative)
        parent = root
        for index, name in enumerate(path.parts[:-1]):
            directory = "/".join(path.parts[: index + 1])
            if directory not in directories:
                code = product.component_code(directory)
                directories[directory] = SubElement(
                    parent, "Directory", Id="D_" + code.replace("-", ""), Name=_literal(name)
                )
            parent = directories[directory]
        resource = relative
        if product.role == "version":
            resource = relative.removeprefix(f"{product.version_directory}/{value.version}/")
        component = _component(parent, feature, product, resource)
        file_id = "F_" + component.attrib["Id"][2:]
        SubElement(
            component,
            "File",
            Id=file_id,
            Name=_literal(path.name),
            Source=_literal((native_marker[1] if relative == native_marker[0] else member(stage, relative)).as_posix()),
            KeyPath="no" if product.scope == "user" else "yes",
        )
        if product.scope == "user":
            SubElement(
                component,
                "RegistryValue",
                Root="HKCU",
                Key=f"Software\\{value.application_id}\\Installer\\Components\\{component.attrib['Id']}",
                Name="Installed",
                Type="integer",
                Value="1",
                KeyPath="yes",
            )
    return root


def _registration(
    package: Element,
    feature: Element,
    root: Element,
    product: MsiIdentity,
    value: DistributionIdentity,
    manager: str,
    desktop: str | None,
) -> None:
    component = _component(root, feature, product, "registry/registration")
    values = {
        "InstallLocation": "[INSTALL_ROOT]",
        "EntryPoint": "[INSTALL_ROOT]" + manager,
        "ManagerAnchorVersion": value.version,
    }
    if desktop:
        values["DesktopAnchorVersion"] = value.version
    for name, text in values.items():
        SubElement(
            component,
            "RegistryValue",
            Root=product.registry_root,
            Key="Software\\" + value.application_id,
            Name=name,
            Type="string",
            Value=text,
            KeyPath="yes" if name == "InstallLocation" else "no",
        )
    login = _component(root, feature, product, "registry/login")
    SubElement(
        login,
        "RegistryValue",
        Root=product.registry_root,
        Key="Software\\Microsoft\\Windows\\CurrentVersion\\Run",
        Name=value.application_id,
        Type="string",
        Value='"[INSTALL_ROOT]' + manager + '" --sign-in',
        KeyPath="yes",
    )
    if desktop:
        menu = SubElement(package, "StandardDirectory", Id="ProgramMenuFolder")
        folder = SubElement(menu, "Directory", Id="CADRUMO_MENU", Name=_literal(value.name))
        shortcut_component = _component(folder, feature, product, "menu/desktop")
        shortcut = SubElement(
            shortcut_component,
            "Shortcut",
            Id="CADRUMO_LAUNCH",
            Name=_literal(value.name),
            Target=f"[INSTALL_ROOT]{product.version_directory}\\{value.version}\\" + desktop.replace("/", "\\"),
            WorkingDirectory="INSTALL_ROOT",
        )
        SubElement(shortcut, "ShortcutProperty", Key="System.AppUserModel.ID", Value=value.application_id)
        SubElement(shortcut_component, "RemoveFolder", Id="CADRUMO_REMOVE_MENU", On="uninstall")
        SubElement(
            shortcut_component,
            "RegistryValue",
            Root=product.registry_root,
            Key="Software\\" + value.application_id,
            Name="DesktopRegistered",
            Type="integer",
            Value="1",
            KeyPath="yes",
        )


def _source(
    stage: Path,
    files: dict[str, str],
    value: DistributionIdentity,
    scope: InstallationScope,
    role: ProductRole,
    manager: str,
    desktop: str | None,
    native_marker: tuple[str, Path],
    manifest_sha256: str,
    adapter: Path | None = None,
    runner: Path | None = None,
) -> bytes:
    product = msi_identity(value, scope, role)
    wix = Element("Wix", xmlns=WIX_NAMESPACE, RequiredVersion="5.0")
    package = SubElement(
        wix,
        "Package",
        Name=_literal(f"{value.name} {value.version} {role} ({scope})"),
        Manufacturer=_literal(value.publisher),
        Version=value.version,
        ProductCode=product.product_code,
        UpgradeCode=product.upgrade_code,
        Scope=product.install_scope,
        UpgradeStrategy="none" if role == "version" else "majorUpgrade",
        InstallerVersion="500",
        Language="1033",
        Compressed="yes",
    )
    SubElement(package, "MediaTemplate", EmbedCab="yes")
    SubElement(package, "Property", Id="MSIRESTARTMANAGERCONTROL", Value="Disable")
    SubElement(package, "Property", Id="REBOOT", Value="ReallySuppress")
    ownership = {
        "schema": 1,
        "application_id": value.application_id,
        "channel": value.channel,
        "platform": "windows-x64",
        "version": value.version,
        "role": role,
        "manifest_sha256": manifest_sha256,
    }
    SubElement(package, "Property", Id="CadrumoPackage", Value=json.dumps(ownership, separators=(",", ":")))
    # Native product evidence must identify the resolved relocated prefix, not an
    # unevaluated directory token or a registry value belonging to another role.
    SubElement(
        package,
        "SetProperty",
        Id="ARPINSTALLLOCATION",
        Value="[INSTALL_ROOT]",
        After="CostFinalize",
        Sequence="execute",
    )
    # Literal false cannot be bypassed with an MSI command-line property. Replace
    # it only when native transactional admission/maintenance is implemented.
    SubElement(package, "Launch", Condition="0", Message=MAINTENANCE_GATE)
    if adapter is not None:
        _admission(package, value, scope, adapter)
        if runner is not None:
            _owner(package, product, runner)
    if role == "registration":
        SubElement(
            package,
            "MajorUpgrade",
            Schedule="afterInstallExecute",
            AllowSameVersionUpgrades="no",
            DowngradeErrorMessage="A later shared registration product is already installed.",
        )
    feature = SubElement(package, "Feature", Id="ProductFeature", Title=_literal(value.name), Level="1")
    root = _files(package, feature, product, value, stage, files, native_marker)
    if role == "registration":
        _registration(package, feature, root, product, value, manager, desktop)
    content = tostring(wix, encoding="utf-8", xml_declaration=True)
    if not isinstance(content, bytes):
        raise TypeError("WiX source serialization did not produce UTF-8 bytes")
    return content


def _admission(package: Element, value: DistributionIdentity, scope: InstallationScope, adapter: Path) -> None:
    """Enroll checked native admission without claiming transactional maintenance is complete."""
    opposite: InstallationScope = "machine" if scope == "user" else "user"
    request = {
        "schema": 1,
        "scope": scope,
        "permitted_families": [msi_identity(value, scope, role).upgrade_code for role in ("version", "registration")],
        "conflicting_families": [
            msi_identity(value, opposite, role).upgrade_code for role in ("version", "registration")
        ]
        + [value.upgrade_code],
    }
    SubElement(package, "Property", Id="CadrumoAdmission", Value=json.dumps(request, separators=(",", ":")))
    SubElement(package, "Binary", Id="CadrumoInstaller", SourceFile=_literal(adapter.as_posix()))
    SubElement(
        package,
        "CustomAction",
        Id="CadrumoPrepareAdmission",
        BinaryRef="CadrumoInstaller",
        DllEntry="CadrumoPrepareAdmission",
        Execute="immediate",
        Return="check",
    )
    SubElement(
        package,
        "CustomAction",
        Id="CadrumoScopeAdmission",
        BinaryRef="CadrumoInstaller",
        DllEntry="CadrumoScopeAdmission",
        Execute="deferred",
        Impersonate="no" if scope == "machine" else "yes",
        HideTarget="yes",
        Return="check",
    )
    sequence = SubElement(package, "InstallExecuteSequence")
    # Removing a conflicting product must remain possible. Never run maintenance
    # from the UI sequence, whose token/scope differs from the execute transaction.
    condition = 'NOT (REMOVE ~= "ALL")'
    SubElement(sequence, "Custom", Action="CadrumoPrepareAdmission", Before="InstallInitialize", Condition=condition)
    SubElement(sequence, "Custom", Action="CadrumoScopeAdmission", After="InstallInitialize", Condition=condition)


def _owner(package: Element, product: MsiIdentity, runner: Path) -> None:
    """The public endpoint locates a server; native image/token checks grant authority."""
    metadata = {
        "schema": 1,
        "scope": product.scope,
        "product_code": product.product_code.upper(),
        "role": product.role,
        "runner_sha256": digest(runner),
    }
    SubElement(package, "Property", Id="CadrumoOwner", Value=json.dumps(metadata, separators=(",", ":")))
    SubElement(package, "Property", Id="CADRUMO_MSI_OWNER", Secure="yes", Hidden="yes")
    for name, execution in (("CadrumoPrepareOwner", "immediate"), ("CadrumoAuthenticateOwner", "deferred")):
        attributes = {
            "Id": name,
            "BinaryRef": "CadrumoInstaller",
            "DllEntry": name,
            "Execute": execution,
            "Return": "check",
        }
        if execution == "deferred":
            attributes.update({"Impersonate": "no" if product.scope == "machine" else "yes", "HideTarget": "yes"})
        SubElement(package, "CustomAction", attributes)
    sequence = package.find("InstallExecuteSequence")
    if sequence is None:
        raise ValueError("Native owner requires enrolled scope admission")
    SubElement(sequence, "Custom", Action="CadrumoPrepareOwner", Before="CadrumoPrepareAdmission")
    SubElement(sequence, "Custom", Action="CadrumoAuthenticateOwner", After="CadrumoScopeAdmission")


def author(
    build: Path,
    identity_file: Path,
    desktop: str | None = None,
    adapter: Path | None = None,
    runner: Path | None = None,
) -> dict[str, Path]:
    """Emit four ownership sources from the verified stage without producing installable MSIs."""
    stage, owned, manifest_file, manifest = _staged_manifest(build)
    if adapter is not None:
        adapter = adapter.resolve(strict=True)
        if not adapter.is_file() or adapter.suffix.lower() != ".dll":
            raise ValueError("MSI adapter must be an existing native installer DLL")
    if runner is not None:
        runner = runner.resolve(strict=True)
        if adapter is None or not runner.is_file() or runner.suffix.lower() != ".exe":
            raise ValueError("MSI owner requires a built runner executable and native installer DLL")
    value = DistributionIdentity(**json.loads(identity_file.read_text(encoding="utf-8")))
    if value.target != "windows-x86-64":
        raise ValueError("MSI authoring requires a Windows payload")
    definition = load_layout("windows-x64")["installation"]
    managers = [image for image in application_images(manifest["layout"]) if image.target == "rust_manager"]
    if len(managers) != 1 or managers[0].placement != "." or manifest["layout"].get("installation") != definition:
        raise ValueError("MSI authoring requires the canonical versioned manager layout")
    prefix = f"{definition['versions']}/{value.version}/"
    package = member(stage, prefix.rstrip("/"))
    if manifest_file != member(package, "data/package-manifest.json"):
        raise ValueError("MSI version files do not belong to the requested release")
    validate_payload(package, identity_file, desktop)
    version_files = {name: checksum for name, checksum in owned.items() if name.startswith(prefix)}
    shared_files = {name: checksum for name, checksum in owned.items() if not name.startswith(prefix)}
    manager = managers[0].package_path
    expected_shared = {manager, definition["marker"], "docs/licenses/CADRUMO.txt", "docs/licenses/NOTICE.txt"}
    if set(shared_files) != expected_shared or digest(member(stage, manager)) != digest(member(package, manager)):
        raise ValueError("MSI shared resources differ from the canonical registration owner")
    metadata = build_paths(build)["installation_metadata"]
    directory = member(metadata, "wix")
    # Native eligibility is an installer-owned overlay. Archive staging and its
    # immutable inventory remain unchanged and do not acquire this native fence.
    marker = json.loads(member(stage, definition["marker"]).read_text(encoding="utf-8"))
    marker["publication"] = definition["publication"]
    native_marker = member(directory, "native-installation.json")
    marker_content = (json.dumps(marker, indent=2) + "\n").encode("utf-8")
    sources = {}
    for scope in ("user", "machine"):
        for role, files in (("version", version_files), ("registration", shared_files)):
            name = f"{scope}-{role}.wxs"
            sources[name] = _source(
                stage,
                files,
                value,
                scope,
                role,
                manager,
                desktop,
                (definition["marker"], native_marker),
                digest(manifest_file),
                adapter,
                runner,
            )
    verify_inventory(stage, member(metadata, "installation.json"))
    directory.mkdir(exist_ok=True)
    if not native_marker.exists() or native_marker.read_bytes() != marker_content:
        native_marker.write_bytes(marker_content)
    outputs = {}
    for name, content in sources.items():
        output = member(directory, name)
        if not output.exists() or output.read_bytes() != content:
            output.write_bytes(content)
        outputs[name] = output
    descriptor = {
        "installable": False,
        "blocked_by": MAINTENANCE_GATE,
        "manifest_sha256": digest(manifest_file),
        "sources": {name: digest(path) for name, path in outputs.items()},
        "adapter_sha256": digest(adapter) if adapter is not None else None,
        "runner_sha256": digest(runner) if runner is not None else None,
        "native_marker_sha256": digest(native_marker),
        "maintenance": {
            "version": value.version,
            "manifest_sha256": digest(manifest_file),
            "desktop_present": desktop is not None,
            "contract": {
                "layout": manifest["layout"],
                "installation_identity": {"application_id": value.application_id, "channel": value.channel},
            },
            "products": {
                f"{scope}-{role}": msi_identity(value, scope, role).product_code
                for scope in ("user", "machine")
                for role in ("version", "registration")
            },
        },
    }
    locator = member(directory, "authoring.json")
    content = (json.dumps(descriptor, indent=2) + "\n").encode("utf-8")
    if not locator.exists() or locator.read_bytes() != content:
        locator.write_bytes(content)
    return outputs


def main() -> None:
    """Expose CMake-owned authoring and a guard for direct CPack MSI invocation."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    source = commands.add_parser("author")
    source.add_argument("--build", type=Path, required=True)
    source.add_argument("--identity", type=Path, required=True)
    source.add_argument("--desktop")
    source.add_argument("--adapter", type=Path)
    source.add_argument("--runner", type=Path)
    guard = commands.add_parser("reject-combined")
    guard.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "author":
        author(args.build, args.identity, args.desktop, args.adapter, args.runner)
    else:
        reject_combined_manager_msi(args.build)


if __name__ == "__main__":
    main()
