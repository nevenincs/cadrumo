"""Combine disjoint release features into one authenticated scope-aware MSI source."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from defusedxml import ElementTree

from .hashing import digest
from .identity import DistributionIdentity
from .layout import load_layout
from .windows_msi_identity import msi_identity, release_identity
from .windows_msi_paths import literal, source_path

_NS = {"w": "http://wixtoolset.org/schemas/v4/wxs"}
_URI = "{" + _NS["w"] + "}"
OWNER_GATE = "Installation requires the authenticated native maintenance owner."


def _element(parent: Element, name: str, **attributes: str) -> Element:
    return SubElement(parent, _URI + name, attributes)


def _property(package: Element, name: str, document: object) -> None:
    encoded = json.dumps(document, separators=(",", ":")).replace("[INSTALL_ROOT]", "\\u005bINSTALL_ROOT\\u005d")
    _element(package, "Property", Id=name, Value=encoded)


def _feature(package: Element, name: str) -> Element:
    feature = package.find("w:Feature", _NS)
    if feature is None:
        raise ValueError("Release ownership has no feature root")
    for child in feature.iter(_URI + "Feature"):
        child.attrib["Id"] = child.attrib["Id"].replace("ProductFeature", name)
        child.attrib["AllowAbsent"] = "yes"
    return feature


def source(
    version: bytes,
    registration: bytes,
    value: DistributionIdentity,
    manager: str,
    service_resources: list[Element],
    adapter: Path | None,
    runner: Path | None,
) -> bytes:
    """Generate each payload owner once; scopes select authenticated native features."""
    root = ElementTree.fromstring(version)
    package = root.find("w:Package", _NS)
    shared = ElementTree.fromstring(registration).find("w:Package", _NS)
    if package is None or shared is None:
        raise ValueError("Release features require complete WiX packages")
    product = release_identity(value, "version")
    package.attrib["Name"] = literal(f"{value.name} {value.version}")
    package.attrib["Scope"] = "perUserOrMachine"
    package.attrib["UpgradeStrategy"] = "none"
    _feature(package, "VersionFiles")
    registration_feature = _feature(shared, "SharedRegistration")
    package.append(registration_feature)
    destination = package.find(".//w:Directory[@Id='INSTALL_ROOT']", _NS)
    shared_root = shared.find(".//w:Directory[@Id='INSTALL_ROOT']", _NS)
    if destination is None or shared_root is None:
        raise ValueError("Release features have no common installation root")
    for child in list(shared_root):
        destination.append(child)
    # Program menu resources are outside INSTALL_ROOT. They still belong only to
    # the shared feature and use Windows Installer's selected user/machine context.
    for directory in shared.findall("w:StandardDirectory", _NS):
        if directory.find("w:Directory[@Id='INSTALL_ROOT']", _NS) is None:
            package.append(directory)
    ownership = package.find("w:Property[@Id='CadrumoPackage']", _NS)
    if ownership is None:
        raise ValueError("Release feature has no immutable package ownership")
    document = json.loads(ownership.attrib["Value"])
    document.update(schema=2, role="application")
    ownership.attrib["Value"] = json.dumps(document, separators=(",", ":"))
    description = shared.find("w:Property[@Id='CadrumoRegistration']", _NS)
    if description is None:
        raise ValueError("Release registration has no immutable resource inventory")
    user_description = json.loads(description.attrib["Value"])
    managers = [
        component
        for component in shared_root.iter(_URI + "Component")
        if any(file.attrib["Name"] == manager for file in component.findall("w:File", _NS))
    ]
    if len(managers) != 1:
        raise ValueError("Release registration requires one stable manager component")
    user_manager = managers[0]
    user_manager.attrib["Condition"] = "NOT ALLUSERS"
    for file in user_manager.findall("w:File", _NS):
        file.attrib["ShortName"] = "cmuser.exe"
    machine_manager = copy.deepcopy(user_manager)
    machine_manager.attrib["Condition"] = 'ALLUSERS = "1"'
    service_guid = release_identity(value, "registration").component_code("service/manager")
    machine_manager.attrib.update(Id="C_" + service_guid.replace("-", ""), Guid=service_guid)
    for file in machine_manager.findall("w:File", _NS):
        file.attrib.update(Id="F_" + service_guid.replace("-", ""), KeyPath="yes", ShortName="cmmach.exe")
    for registry in machine_manager.findall("w:RegistryValue", _NS):
        registry.attrib["KeyPath"] = "no"
        registry.attrib["Key"] = registry.attrib["Key"].replace(user_manager.attrib["Id"], machine_manager.attrib["Id"])
    for resource in service_resources:
        resource = copy.deepcopy(resource)
        resource.tag = _URI + resource.tag.rsplit("}", 1)[-1]
        machine_manager.append(resource)
    destination.append(machine_manager)
    _element(registration_feature, "ComponentRef", Id=machine_manager.attrib["Id"])
    machine_description = copy.deepcopy(user_description)
    machine_description["scope"] = "machine"
    login_guids = set()
    for component in shared_root.iter(_URI + "Component"):
        if any(
            entry.attrib["Key"] == "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
            for entry in component.findall("w:RegistryValue", _NS)
        ):
            component.attrib["Condition"] = "NOT ALLUSERS"
            login_guids.add(component.attrib["Guid"])
    machine_description["components"] = [
        service_guid if component == user_manager.attrib["Guid"] else component
        for component in machine_description["components"]
        if component not in login_guids
    ]
    machine_description["registry"] = [
        entry for entry in machine_description["registry"] if entry["component"] not in login_guids
    ]
    for registry in machine_description["registry"]:
        if registry["component"] == user_manager.attrib["Guid"]:
            registry["component"] = service_guid
            registry["key"] = registry["key"].replace(user_manager.attrib["Id"], machine_manager.attrib["Id"])
    machine_description["services"] = [
        {
            "component": service_guid,
            "name": service.attrib["Name"],
            "binary": "[INSTALL_ROOT]" + manager,
            "arguments": service.attrib["Arguments"],
            "account": service.attrib["Account"],
            "start": service.attrib["Start"],
        }
        for service in service_resources
        if service.tag.rsplit("}", 1)[-1] == "ServiceInstall"
    ]
    for scope, resources in (("User", user_description), ("Machine", machine_description)):
        _property(package, "CadrumoRegistration" + scope, resources)
    launch = package.find("w:Launch", _NS)
    if launch is None:
        raise ValueError("Release feature has no native installation gate")
    launch.attrib["Condition"] = "1" if runner is not None else "0"
    if runner is not None:
        launch.attrib["Message"] = OWNER_GATE
    if adapter is not None:
        _element(package, "Binary", Id="CadrumoInstaller", SourceFile=source_path(adapter.resolve(strict=True)))
        sequence = _element(package, "InstallExecuteSequence")
        for scope in ("user", "machine"):
            suffix = scope.title()
            _property(
                package,
                "CadrumoAdmission" + suffix,
                {
                    "schema": 2,
                    "scope": scope,
                    "permitted_families": [product.upgrade_code],
                    "conflicting_families": [
                        msi_identity(value, old_scope, role).upgrade_code
                        for old_scope in ("user", "machine")
                        for role in ("version", "registration")
                    ]
                    + [value.upgrade_code],
                },
            )
            condition = 'ALLUSERS = "1"' if scope == "machine" else "NOT ALLUSERS"
            for kind in ("Owner", "Admission"):
                if kind == "Owner" and runner is None:
                    continue
                entry = "CadrumoAuthenticateOwner" if kind == "Owner" else "CadrumoScopeAdmission"
                _element(
                    package,
                    "CustomAction",
                    Id=entry + suffix,
                    BinaryRef="CadrumoInstaller",
                    DllEntry=entry,
                    Execute="deferred",
                    Return="check",
                    Impersonate="no" if scope == "machine" else "yes",
                    HideTarget="yes",
                )
                _element(
                    sequence,
                    "Custom",
                    Action=entry + suffix,
                    After="CadrumoScopeAdmission" + suffix if kind == "Owner" else "InstallInitialize",
                    Condition=condition if kind == "Owner" else f"({condition}) AND NOT REMOVE",
                )
        for kind in ("Admission", "Owner"):
            if kind == "Owner" and runner is None:
                continue
            entry = "CadrumoPrepare" + kind
            _element(
                package,
                "CustomAction",
                Id=entry,
                BinaryRef="CadrumoInstaller",
                DllEntry=entry,
                Execute="immediate",
                Return="check",
            )
            _element(
                sequence,
                "Custom",
                Action=entry,
                Before="CadrumoPrepareAdmission" if kind == "Owner" else "InstallInitialize",
                **({"Condition": "NOT REMOVE"} if kind == "Admission" else {}),
            )
        if runner is not None:
            _property(
                package,
                "CadrumoOwner",
                {
                    "schema": 3,
                    "product_code": product.product_code,
                    "role": "application",
                    "runner_sha256": digest(runner),
                    "identity": {
                        "application_id": value.application_id,
                        "channel": value.channel,
                        "platform": "windows-x64",
                    },
                    "publication": load_layout("windows-x64")["installation"]["publication"],
                },
            )
            _element(package, "Property", Id="CADRUMO_MSI_OWNER", Secure="yes", Hidden="yes")
            _element(package, "Property", Id="CADRUMO_MSI_FEATURE", Secure="yes")
            _element(package, "Property", Id="INSTALL_ROOT", Secure="yes")
    # ElementTree's generated ns0 prefix is a namespace serialization detail;
    # WiX parses the same single Package and receives each payload member once.
    content = tostring(root, encoding="utf-8", xml_declaration=True)
    if not isinstance(content, bytes):
        raise TypeError("Release WiX source serialization did not produce bytes")
    return content
