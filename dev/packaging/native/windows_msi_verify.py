"""Build scoped MSI products and run explicit native maintenance."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import ElementTree as XMLTree

from defusedxml import ElementTree

from .windows_msi_contract import MAINTENANCE_GATE, WIX_NAMESPACE
from .windows_msi_single import OWNER_GATE

_NS = {"w": WIX_NAMESPACE}


def _verify_database_registration(original: Element, package: Element) -> None:
    registration = original.find("w:Property[@Id='CadrumoRegistration']", _NS)
    observed_registration = package.find("w:Property[@Id='CadrumoRegistration']", _NS)
    if registration is None:
        if observed_registration is not None:
            raise ValueError("Version MSI acquired unexpected registration resources")
    elif observed_registration is None or registration.attrib.get("Value") != observed_registration.attrib.get("Value"):
        raise ValueError("MSI database immutable registration resources differ from its source")
    for scope in ("User", "Machine"):
        for prefix in ("CadrumoRegistration", "CadrumoAdmission"):
            name = prefix + scope
            expected = original.find(f"w:Property[@Id='{name}']", _NS)
            actual = package.find(f"w:Property[@Id='{name}']", _NS)
            if expected is not None and (actual is None or expected.attrib.get("Value") != actual.attrib.get("Value")):
                raise ValueError("MSI database altered scope-specific registration ownership or admission")


def _verify_database_identity(original: Element, package: Element) -> None:
    for key in ("ProductCode", "UpgradeCode"):
        if UUID(package.attrib[key]) != UUID(original.attrib[key]):
            raise ValueError(f"MSI database {key} differs from its source")
    if package.attrib["Version"] != original.attrib["Version"]:
        raise ValueError("MSI database version differs from its source")
    ownership = original.find("w:Property[@Id='CadrumoPackage']", _NS)
    observed_ownership = package.find("w:Property[@Id='CadrumoPackage']", _NS)
    if (
        ownership is None
        or observed_ownership is None
        or ownership.attrib.get("Value") != observed_ownership.attrib.get("Value")
    ):
        raise ValueError("MSI database immutable package ownership differs from its source")
    _verify_database_registration(original, package)


def _verify_database_services(original: Element, package: Element) -> None:
    for element, defaults in (
        (
            "ServiceInstall",
            {
                "Type": "ownProcess",
                "Start": "demand",
                "ErrorControl": "normal",
                "Account": "LocalSystem",
                "Arguments": "",
                "Vital": "yes",
            },
        ),
        ("ServiceControl", {"Start": "", "Stop": "", "Remove": "", "Wait": "yes"}),
    ):

        def services(node: Element, element: str, defaults: dict[str, str]) -> dict[tuple[str, str], dict[str, str]]:
            return {
                (str(UUID(component.attrib["Guid"])), service.attrib["Name"]): {
                    key: service.attrib.get(key, default) for key, default in defaults.items()
                }
                for component in node.findall(".//w:Component", _NS)
                for service in component.findall(f"w:{element}", _NS)
            }

        if services(original, element, defaults) != services(package, element, defaults):
            raise ValueError(f"MSI database altered {element} ownership or lifecycle")


def _verify_upgrade(original: Element, tree: XMLTree) -> None:
    upgrade = tree.find(".//w:MajorUpgrade", _NS)
    if original.attrib["UpgradeStrategy"] == "none":
        if upgrade is not None or tree.find(".//w:RemoveExistingProducts", _NS) is not None:
            raise ValueError("Version MSI schedules removal of another product")
    elif upgrade is None:
        raise ValueError("Registration MSI lost its major upgrade")


def _verify_database_gate(original: Element, tree: XMLTree) -> Element | None:
    conditions = tree.findall(".//w:Launch", _NS)
    owner = original.find("w:Property[@Id='CadrumoOwner']", _NS)
    gate = (
        {"Condition": "1", "Message": OWNER_GATE}
        if owner is not None
        else {
            "Condition": "0",
            "Message": MAINTENANCE_GATE,
        }
    )
    if not any(item.attrib == gate for item in conditions):
        raise ValueError("MSI database lost its native installation gate")
    if owner is not None and any(item.attrib.get("Condition") == "0" for item in conditions):
        raise ValueError("MSI database blocks its authenticated native owner")
    _verify_upgrade(original, tree)
    return owner


def _verify_owner_scopes(original: Element, tree: XMLTree) -> None:
    for scope in ("User", "Machine"):
        name = "CadrumoAuthenticateOwner" + scope
        expected = original.find(f".//w:InstallExecuteSequence/w:Custom[@Action='{name}']", _NS)
        actual = tree.find(f".//w:InstallExecuteSequence/w:Custom[@Action='{name}']", _NS)
        if (
            expected is None
            or actual is None
            or actual.attrib.get("Condition", "") != expected.attrib.get("Condition", "")
        ):
            raise ValueError("MSI database lost scope-bound native owner authentication")


def _verify_database_owner(original: Element, package: Element, tree: XMLTree, owner: Element | None) -> None:
    if owner is not None:
        observed_owner = package.find("w:Property[@Id='CadrumoOwner']", _NS)
        if observed_owner is None or observed_owner.attrib.get("Value") != owner.attrib["Value"]:
            raise ValueError("MSI database lost immutable native owner authentication metadata")
        combined = original.find("w:Property[@Id='CadrumoAdmissionUser']", _NS) is not None
        names = ("CadrumoPrepareOwner",) if combined else ("CadrumoPrepareOwner", "CadrumoAuthenticateOwner")
        for name in names:
            scheduled = tree.find(f".//w:InstallExecuteSequence/w:Custom[@Action='{name}']", _NS)
            if scheduled is None or scheduled.attrib.get("Condition", ""):
                raise ValueError("MSI database lost unconditional native owner authentication")
        if combined:
            _verify_owner_scopes(original, tree)


def _verify_database_admission(original: Element, package: Element) -> None:
    admission = original.find("w:Property[@Id='CadrumoAdmission']", _NS)
    if admission is not None or original.find("w:Property[@Id='CadrumoAdmissionUser']", _NS) is not None:
        if admission is not None:
            observed = package.find("w:Property[@Id='CadrumoAdmission']", _NS)
            if observed is None or observed.attrib.get("Value") != admission.attrib["Value"]:
                raise ValueError("MSI database lost its immutable scope admission data")
        for action in original.findall("w:CustomAction", _NS):
            actual = package.find(f"w:CustomAction[@Id='{action.attrib['Id']}']", _NS)
            if actual is None:
                raise ValueError("MSI database lost its native admission action")
            defaults = {"Execute": "immediate", "Return": "check", "Impersonate": "yes", "HideTarget": "no"}
            for key in ("BinaryRef", "DllEntry", *defaults):
                if actual.attrib.get(key, defaults.get(key)) != action.attrib.get(key, defaults.get(key)):
                    raise ValueError(f"MSI database altered native admission {key}")


def verify_database(source: Path, database: Path) -> None:
    """Check actual decompiled MSI identity, installation gate and upgrade ownership."""
    original = ElementTree.parse(source).find("w:Package", _NS)
    tree = ElementTree.parse(database)
    package = tree.find("w:Package", _NS)
    if original is None or package is None:
        raise ValueError("MSI database lacks its package identity")
    _verify_database_identity(original, package)
    _verify_database_services(original, package)
    owner = _verify_database_gate(original, tree)
    _verify_database_owner(original, package, tree, owner)
    _verify_database_admission(original, package)
