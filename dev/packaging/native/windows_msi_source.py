"""Author scoped MSI ownership sources; native maintenance integration gates installation."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from .hashing import digest
from .identity import DistributionIdentity
from .installation import member
from .layout import load_layout
from .windows_msi_components import add_files, add_machine_service, add_registration
from .windows_msi_contract import MAINTENANCE_GATE, WIX_NAMESPACE
from .windows_msi_identity import InstallationScope, MsiIdentity, ProductRole, msi_identity
from .windows_msi_paths import literal as _literal
from .windows_msi_paths import source_path as _source_path
from .windows_msi_single import OWNER_GATE


def _add_authored_registration(
    package: Element,
    feature: Element,
    root: Element,
    product: MsiIdentity,
    value: DistributionIdentity,
    scope: InstallationScope,
    manager: str,
    desktop: str | None,
    files: dict[str, str],
    stage: Path,
    native_marker: tuple[str, Path, str],
) -> None:
    if scope == "machine":
        components = [
            component
            for component in root.iter("Component")
            if any(file.attrib["Name"] == manager for file in component.findall("File"))
        ]
        if len(components) != 1:
            raise ValueError("Machine service requires one verified stable manager component")
        add_machine_service(components[0], value)
    add_registration(package, feature, root, product, value, manager, desktop)
    description = _registration_description(package, product, value, files, stage, native_marker)
    # Preserve the literal template inside JSON without WiX treating it as a
    # Property-table reference. The native JSON decoder restores the token.
    encoded = json.dumps(description, separators=(",", ":")).replace("[INSTALL_ROOT]", "\\u005bINSTALL_ROOT\\u005d")
    SubElement(package, "Property", Id="CadrumoRegistration", Value=encoded)


def _check_component_budget(package: Element) -> None:
    components = list(package.iter("Component"))
    if (
        len(components)
        + sum(
            any(entry.attrib.get("KeyPath") == "yes" for entry in component.findall("RegistryValue"))
            for component in components
        )
        > 65535
    ):
        raise ValueError("MSI component costing budget exceeds 65535 entries")


def _add_admission(
    package: Element,
    product: MsiIdentity,
    value: DistributionIdentity,
    scope: InstallationScope,
    adapter: Path | None,
    runner: Path | None,
) -> None:
    if adapter is not None:
        _admission(package, value, scope, adapter)
        if runner is not None:
            _owner(package, product, runner, value)


def msi_source(
    stage: Path,
    files: dict[str, str],
    value: DistributionIdentity,
    scope: InstallationScope,
    role: ProductRole,
    manager: str,
    desktop: str | None,
    native_marker: tuple[str, Path, str],
    manifest_sha256: str,
    adapter: Path | None = None,
    runner: Path | None = None,
    product: MsiIdentity | None = None,
) -> bytes:
    """Author one MSI ownership partition as WiX source."""
    product = product or msi_identity(value, scope, role)
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
    # Owned products authenticate through mandatory native callbacks before any
    # file ownership changes. No command-line property can skip those callbacks.
    # Keep unowned/admission-only products unconditionally blocked.
    SubElement(
        package,
        "Launch",
        Condition="1" if runner is not None else "0",
        Message=OWNER_GATE if runner is not None else MAINTENANCE_GATE,
    )
    _add_admission(package, product, value, scope, adapter, runner)
    if role == "registration":
        SubElement(
            package,
            "MajorUpgrade",
            Schedule="afterInstallExecute",
            AllowSameVersionUpgrades="no",
            DowngradeErrorMessage="A later shared registration product is already installed.",
        )
    feature = SubElement(
        package,
        "Feature",
        Id="ProductFeature",
        Title=_literal(value.name),
        Level="1",
        Display="hidden",
        InstallDefault="local",
        AllowAdvertise="no",
        AllowAbsent="no",
    )
    root = add_files(
        package,
        feature,
        product,
        value,
        stage,
        files,
        native_marker,
        {name for name in (manager, desktop) if name is not None},
    )
    if role == "registration":
        _add_authored_registration(
            package, feature, root, product, value, scope, manager, desktop, files, stage, native_marker
        )
    _check_component_budget(package)
    partition_features(feature)
    content = tostring(wix, encoding="utf-8", xml_declaration=True)
    if not isinstance(content, bytes):
        raise TypeError("WiX source serialization did not produce UTF-8 bytes")
    return content


def partition_features(feature: Element) -> None:
    """Keep every mandatory component within MSI's 1600-per-feature limit."""
    references = feature.findall("ComponentRef")
    relocated = set(references[1600:])
    if not relocated:
        return
    feature[:] = [child for child in feature if child not in relocated]
    for offset in range(1600, len(references), 1600):
        child = SubElement(
            feature,
            "Feature",
            Id=f"PayloadFeature{offset // 1600:04d}",
            Level="1",
            Display="hidden",
            InstallDefault="followParent",
            AllowAdvertise="no",
            AllowAbsent="no",
        )
        child.extend(references[offset : offset + 1600])


def _registration_shortcuts(components: list[Element], value: DistributionIdentity) -> list[dict[str, str]]:
    shortcuts: list[dict[str, str]] = []
    for component in components:
        for shortcut in component.findall("Shortcut"):
            properties = {item.attrib["Key"]: item.attrib["Value"] for item in shortcut.findall("ShortcutProperty")}
            shortcuts.append(
                {
                    "component": component.attrib["Guid"],
                    "path": f"{value.name}/{shortcut.attrib['Name']}.lnk",
                    "target": shortcut.attrib["Target"],
                    "arguments": shortcut.attrib.get("Arguments", ""),
                    "working_directory": "[INSTALL_ROOT]",
                    "app_id": properties["System.AppUserModel.ID"],
                }
            )
    return shortcuts


def _registration_registry(components: list[Element]) -> list[dict[str, str]]:
    return [
        {
            "component": component.attrib["Guid"],
            **{key.lower(): entry.attrib[key] for key in ("Key", "Name", "Type", "Value")},
        }
        for component in components
        for entry in component.findall("RegistryValue")
    ]


def _registration_description(
    package: Element,
    product: MsiIdentity,
    value: DistributionIdentity,
    files: dict[str, str],
    stage: Path,
    native_marker: tuple[str, Path, str],
) -> dict[str, object]:
    """Describe the actual authored resources, including the native marker overlay."""
    components = list(package.iter("Component"))
    registry = _registration_registry(components)
    shortcuts = _registration_shortcuts(components, value)
    return {
        "schema": 2,
        "application_id": value.application_id,
        "version": value.version,
        "scope": product.scope,
        "files": {
            name: native_marker[2] if name == native_marker[0] else digest(member(stage, name))
            for name in sorted(files)
        },
        "components": [component.attrib["Guid"] for component in components],
        "registry": registry,
        "services": [
            {
                "component": component.attrib["Guid"],
                "name": service.attrib["Name"],
                "binary": "[INSTALL_ROOT]" + file.attrib["Name"],
                "arguments": service.attrib["Arguments"],
                "account": service.attrib["Account"],
                "start": service.attrib["Start"],
            }
            for component in components
            for service in component.findall("ServiceInstall")
            for file in component.findall("File")
        ],
        "shortcuts": shortcuts,
        "absent_registry": []
        if shortcuts
        else [
            {"key": "Software\\" + value.application_id, "name": name}
            for name in ("DesktopAnchorVersion", "DesktopRegistered")
        ],
        "absent_shortcuts": [] if shortcuts else [f"{value.name}/{value.name}.lnk"],
    }


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
    SubElement(package, "Binary", Id="CadrumoInstaller", SourceFile=_source_path(adapter))
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


def _owner(package: Element, product: MsiIdentity, runner: Path, value: DistributionIdentity) -> None:
    """Cached actions locate an exact live owner through protected native state."""
    metadata = {
        "schema": 2,
        "scope": product.scope,
        "product_code": product.product_code.upper(),
        "role": product.role,
        "runner_sha256": digest(runner),
        "identity": {"application_id": value.application_id, "channel": value.channel, "platform": "windows-x64"},
        "publication": load_layout("windows-x64")["installation"]["publication"],
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
