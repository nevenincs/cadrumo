"""Author scoped MSI ownership sources; native maintenance integration gates installation."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from xml.etree.ElementTree import Element, SubElement

from .identity import DistributionIdentity
from .installation import member
from .windows_msi_identity import MsiIdentity
from .windows_msi_paths import literal as _literal
from .windows_msi_paths import source_path as _source_path


def add_component(parent: Element, feature: Element, product: MsiIdentity, resource: str) -> Element:
    """Add a component and its owning feature reference."""
    code = product.component_code(resource)
    component_id = "C_" + code.replace("-", "")
    component = SubElement(parent, "Component", Id=component_id, Guid=code, Bitness="always64")
    SubElement(feature, "ComponentRef", Id=component_id)
    return component


def _group_resources(members: dict[str, str], product: MsiIdentity, individual_names: set[str]) -> dict[str, list[str]]:
    seen: set[str] = set()
    groups: dict[str, list[str]] = {}
    separate_extensions = {".exe", ".dll", ".pyd", ".ocx", ".sys", ".drv", ".com", ".scr", ".cpl", ".hlp", ".chm"}
    for relative in sorted(members):
        if relative.casefold() in seen:
            raise ValueError("MSI resources collide in the Windows filename namespace")
        seen.add(relative.casefold())
        path = PurePosixPath(relative)
        grouped = (
            product.scope == "user"
            and product.role == "version"
            and path.name not in individual_names
            and path.suffix.lower() not in separate_extensions
        )
        groups.setdefault("directory/" + str(path.parent) if grouped else "file/" + relative, []).append(relative)
    return groups


def _resource_parent(
    root: Element, directories: dict[str, Element], path: PurePosixPath, product: MsiIdentity
) -> Element:
    parent = root
    for index, name in enumerate(path.parts[:-1]):
        directory = "/".join(path.parts[: index + 1])
        if directory not in directories:
            code = product.component_code(directory)
            directories[directory] = SubElement(
                parent, "Directory", Id="D_" + code.replace("-", ""), Name=_literal(name)
            )
        parent = directories[directory]
    return parent


def _add_resource_files(
    component: Element,
    relatives: list[str],
    product: MsiIdentity,
    value: DistributionIdentity,
    stage: Path,
    native_marker: tuple[str, Path, str],
) -> None:
    for relative in relatives:
        resource = (
            relative.removeprefix(f"{product.version_directory}/{value.version}/")
            if product.role == "version"
            else relative
        )
        file_id = "F_" + product.component_code(resource).replace("-", "")
        SubElement(
            component,
            "File",
            Id=file_id,
            Name=_literal(PurePosixPath(relative).name),
            Source=_source_path(native_marker[1] if relative == native_marker[0] else member(stage, relative)),
            KeyPath="no" if product.scope == "user" else "yes",
        )


def add_files(
    package: Element,
    feature: Element,
    product: MsiIdentity,
    value: DistributionIdentity,
    stage: Path,
    members: dict[str, str],
    native_marker: tuple[str, Path, str],
    individual_names: set[str],
) -> Element:
    """Author the ordered MSI file components and directories."""
    standard = SubElement(package, "StandardDirectory", Id=product.root_directory)
    root = SubElement(standard, "Directory", Id="INSTALL_ROOT", Name=_literal(value.name))
    directories = {"": root}
    groups = _group_resources(members, product, individual_names)
    for relatives in groups.values():
        path = PurePosixPath(relatives[0])
        parent = _resource_parent(root, directories, path, product)
        resource = relatives[0]
        if product.role == "version":
            resource = resource.removeprefix(f"{product.version_directory}/{value.version}/")
        if len(relatives) > 1:
            inventory = "\0".join(relative.casefold() for relative in relatives).encode("utf-8")
            resource = f"msi-directory-data/{PurePosixPath(resource).parent}/{hashlib.sha256(inventory).hexdigest()}"
        component = add_component(parent, feature, product, resource)
        _add_resource_files(component, relatives, product, value, stage, native_marker)
        if product.scope == "user":
            SubElement(
                component,
                "RegistryValue",
                Root=product.registry_root,
                Key=f"Software\\{value.application_id}\\Installer\\Components\\{component.attrib['Id']}",
                Name="Installed",
                Type="integer",
                Value="1",
                KeyPath="yes",
            )
    return root


def add_machine_service(component: Element, value: DistributionIdentity) -> None:
    """Author the machine manager service and its lifecycle."""
    SubElement(
        component,
        "ServiceInstall",
        Id="CadrumoMachineManager",
        Name=value.manager_id,
        DisplayName=_literal(value.manager_name),
        Description="Starts and supervises Cadrumo managers in their real user logons.",
        Type="ownProcess",
        Start="auto",
        ErrorControl="normal",
        Account="LocalSystem",
        Arguments="--service",
        Vital="yes",
    )
    SubElement(
        component,
        "ServiceControl",
        Id="CadrumoMachineManagerControl",
        Name=value.manager_id,
        Start="install",
        Stop="both",
        Remove="uninstall",
        Wait="yes",
    )


def add_registration(
    package: Element,
    feature: Element,
    root: Element,
    product: MsiIdentity,
    value: DistributionIdentity,
    manager: str,
    desktop: str | None,
) -> None:
    """Author shared registration and user launch resources."""
    component = add_component(root, feature, product, "registry/registration")
    values = {
        "InstallLocation": "[INSTALL_ROOT]",
        "EntryPoint": "[INSTALL_ROOT]" + manager,
        "ManagerAnchorVersion": value.version,
    }
    if desktop is not None and desktop:
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
    if product.scope == "user":
        login = add_component(root, feature, product, "registry/login")
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
    if desktop is not None and desktop:
        menu = SubElement(package, "StandardDirectory", Id="ProgramMenuFolder")
        folder = SubElement(menu, "Directory", Id="CADRUMO_MENU", Name=_literal(value.name))
        shortcut_component = add_component(folder, feature, product, "menu/desktop")
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
