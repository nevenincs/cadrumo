"""Combine disjoint release features into one authenticated scope-aware MSI source."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Literal, cast
from xml.etree.ElementTree import Element, SubElement, tostring

from defusedxml import ElementTree

from .hashing import digest
from .identity import DistributionIdentity
from .layout import load_layout
from .windows_msi_identity import MsiIdentity, msi_identity, release_identity
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
    destination, shared_root, registration_feature = _merge_feature_roots(package, shared)
    ownership = package.find("w:Property[@Id='CadrumoPackage']", _NS)
    if ownership is None:
        raise ValueError("Release feature has no immutable package ownership")
    document = json.loads(ownership.attrib["Value"])
    document.update(schema=2, role="application")
    ownership.attrib["Value"] = json.dumps(document, separators=(",", ":"))
    user_description, machine_description = _registration_descriptions(
        shared, shared_root, destination, registration_feature, value, manager, service_resources
    )
    for scope, resources in (("User", user_description), ("Machine", machine_description)):
        _property(package, "CadrumoRegistration" + scope, resources)
    launch = package.find("w:Launch", _NS)
    if launch is None:
        raise ValueError("Release feature has no native installation gate")
    launch.attrib["Condition"] = "1" if runner is not None else "0"
    if runner is not None:
        launch.attrib["Message"] = OWNER_GATE
    _install_admission_actions(package, value, product, adapter, runner)
    # ElementTree's generated ns0 prefix is a namespace serialization detail;
    # WiX parses the same single Package and receives each payload member once.
    content = tostring(root, encoding="utf-8", xml_declaration=True)
    if not isinstance(content, bytes):
        raise TypeError("Release WiX source serialization did not produce bytes")
    return content


def _merge_feature_roots(package: Element, shared: Element) -> tuple[Element, Element, Element]:
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
    return destination, shared_root, registration_feature


def _registration_descriptions(
    shared: Element,
    shared_root: Element,
    destination: Element,
    registration_feature: Element,
    value: DistributionIdentity,
    manager: str,
    service_resources: list[Element],
) -> tuple[dict[str, object], dict[str, object]]:
    description = shared.find("w:Property[@Id='CadrumoRegistration']", _NS)
    if description is None:
        raise ValueError("Release registration has no immutable resource inventory")
    user_description = cast("dict[str, object]", json.loads(description.attrib["Value"]))
    user_manager, machine_manager, service_guid = _install_machine_manager(
        shared_root, destination, registration_feature, value, manager, service_resources
    )
    machine_description = copy.deepcopy(user_description)
    machine_description["scope"] = "machine"
    login_guids = _condition_user_login_components(shared_root)
    machine_description["components"] = [
        service_guid if component == user_manager.attrib["Guid"] else component
        for component in cast("list[str]", machine_description["components"])
        if component not in login_guids
    ]
    machine_description["registry"] = [
        entry
        for entry in cast("list[dict[str, str]]", machine_description["registry"])
        if entry["component"] not in login_guids
    ]
    for registry in machine_description["registry"]:
        if registry["component"] == user_manager.attrib["Guid"]:
            registry["component"] = service_guid
            registry["key"] = registry["key"].replace(user_manager.attrib["Id"], machine_manager.attrib["Id"])
    machine_description["services"] = _machine_services(service_resources, service_guid, manager)
    return user_description, machine_description


def _machine_services(service_resources: list[Element], service_guid: str, manager: str) -> list[dict[str, str]]:
    return [
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


def _condition_user_login_components(shared_root: Element) -> set[str]:
    login_guids: set[str] = set()
    for component in shared_root.iter(_URI + "Component"):
        if any(
            entry.attrib["Key"] == "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
            for entry in component.findall("w:RegistryValue", _NS)
        ):
            component.attrib["Condition"] = "NOT ALLUSERS"
            login_guids.add(component.attrib["Guid"])
    return login_guids


def _install_machine_manager(
    shared_root: Element,
    destination: Element,
    registration_feature: Element,
    value: DistributionIdentity,
    manager: str,
    service_resources: list[Element],
) -> tuple[Element, Element, str]:
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
    return user_manager, machine_manager, service_guid


def _install_admission_actions(
    package: Element, value: DistributionIdentity, product: MsiIdentity, adapter: Path | None, runner: Path | None
) -> None:
    if adapter is not None:
        _element(package, "Binary", Id="CadrumoInstaller", SourceFile=source_path(adapter.resolve(strict=True)))
        sequence = _element(package, "InstallExecuteSequence")
        for scope in ("user", "machine"):
            _scope_admission_actions(package, sequence, value, product, scope, runner)
        _immediate_admission_actions(package, sequence, runner)
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


def _scope_admission_actions(
    package: Element,
    sequence: Element,
    value: DistributionIdentity,
    product: MsiIdentity,
    scope: Literal["user", "machine"],
    runner: Path | None,
) -> None:
    suffix = scope.title()
    _property(
        package,
        "CadrumoAdmission" + suffix,
        {
            "schema": 2,
            "scope": scope,
            "permitted_families": [product.upgrade_code],
            "conflicting_families": _conflicting_families(value),
        },
    )
    condition = _scope_condition(scope)
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


def _immediate_admission_actions(package: Element, sequence: Element, runner: Path | None) -> None:
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


def _conflicting_families(value: DistributionIdentity) -> list[str]:
    return [
        msi_identity(value, old_scope, role).upgrade_code
        for old_scope in ("user", "machine")
        for role in ("version", "registration")
    ] + [value.upgrade_code]


def _scope_condition(scope: Literal["user", "machine"]) -> str:
    return 'ALLUSERS = "1"' if scope == "machine" else "NOT ALLUSERS"
