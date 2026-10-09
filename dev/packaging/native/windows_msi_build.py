"""Compile and inspect scoped MSI products without installing them."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from defusedxml import ElementTree

from ..command_execution import run_command
from .build_paths import build_paths
from .hashing import digest
from .installation import member
from .windows_msi import MAINTENANCE_GATE, OWNER_GATE, WIX_NAMESPACE, author
from .windows_msi_database import verify_admission_order, verify_upgrade_order
from .windows_msi_identity import InstallationScope

_NS = {"w": WIX_NAMESPACE}


def _run(wix: Path, arguments: list[str], directory: Path) -> str:
    result = run_command([str(wix), *arguments], cwd=directory, timeout_seconds=300)
    if result.returncode:
        raise ValueError(f"WiX failed ({result.returncode}): {result.stdout}{result.stderr}")
    return result.stdout.strip()


def verify_database(source: Path, database: Path) -> None:
    """Check actual decompiled MSI identity, installation gate and upgrade ownership."""
    original = ElementTree.parse(source).find("w:Package", _NS)
    tree = ElementTree.parse(database)
    package = tree.find("w:Package", _NS)
    if original is None or package is None:
        raise ValueError("MSI database lacks its package identity")
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
    registration = original.find("w:Property[@Id='CadrumoRegistration']", _NS)
    observed_registration = package.find("w:Property[@Id='CadrumoRegistration']", _NS)
    if registration is None:
        if observed_registration is not None:
            raise ValueError("Version MSI acquired unexpected registration resources")
    elif observed_registration is None or registration.attrib.get("Value") != observed_registration.attrib.get("Value"):
        raise ValueError("MSI database immutable registration resources differ from its source")
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
    upgrade = tree.find(".//w:MajorUpgrade", _NS)
    if original.attrib["UpgradeStrategy"] == "none":
        if upgrade is not None or tree.find(".//w:RemoveExistingProducts", _NS) is not None:
            raise ValueError("Version MSI schedules removal of another product")
    elif upgrade is None:
        raise ValueError("Registration MSI lost its major upgrade")
    admission = original.find("w:Property[@Id='CadrumoAdmission']", _NS)
    if owner is not None:
        observed_owner = package.find("w:Property[@Id='CadrumoOwner']", _NS)
        if observed_owner is None or observed_owner.attrib.get("Value") != owner.attrib["Value"]:
            raise ValueError("MSI database lost immutable native owner authentication metadata")
        for name in ("CadrumoPrepareOwner", "CadrumoAuthenticateOwner"):
            scheduled = tree.find(f".//w:InstallExecuteSequence/w:Custom[@Action='{name}']", _NS)
            if scheduled is None or scheduled.attrib.get("Condition", ""):
                raise ValueError("MSI database lost unconditional native owner authentication")
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


def compile_products(
    build: Path,
    identity: Path,
    wix: Path,
    desktop: str | None = None,
    adapter: Path | None = None,
    runner: Path | None = None,
) -> None:
    """Publish four gated products and a hash receipt only after all databases pass."""
    wix = wix.resolve(strict=True)
    sources = author(build, identity, desktop, adapter, runner)
    paths = build_paths(build)
    directory = member(paths["packages"], "msi")
    directory.mkdir(parents=True, exist_ok=True)
    receipt = member(directory, "compiled.json")
    # A failed retry must not leave an earlier receipt presenting this run as successful.
    receipt.unlink(missing_ok=True)
    version = _run(wix, ["--version"], build)
    if not version.split(".", 1)[0].isdigit() or int(version.split(".", 1)[0]) < 5:
        raise ValueError("Scoped MSI products require WiX 5 or newer")
    inputs = {name: digest(path) for name, path in sources.items()}
    authoring = member(paths["installation_metadata"], "wix/authoring.json")
    authoring_hash = digest(authoring)
    with TemporaryDirectory(prefix="compile-", dir=directory) as temporary:
        work = Path(temporary)
        artifacts = {}
        for name, source in sources.items():
            artifact = work / Path(name).with_suffix(".msi").name
            _run(wix, ["build", "-arch", "x64", "-wx", "-o", str(artifact), str(source)], work)
            database = work / name
            _run(wix, ["msi", "decompile", "-o", str(database), str(artifact)], work)
            verify_database(source, database)
            verify_upgrade_order(artifact, version_product=source.stem.endswith("-version"))
            if adapter is not None:
                verify_admission_order(artifact, owner_required=runner is not None)
            artifacts[artifact.name] = digest(artifact)
        # Re-admit the payload after compilation, detecting a concurrently changed stage.
        author(build, identity, desktop, adapter, runner)
        if inputs != {name: digest(path) for name, path in sources.items()} or digest(authoring) != authoring_hash:
            raise ValueError("MSI inputs changed during compilation")
        for name in artifacts:
            os.replace(work / name, member(directory, name))
        document = {
            "installable": False,
            "compiler": {"path": str(wix), "version": version},
            "authoring_sha256": authoring_hash,
            "sources": inputs,
            "artifacts": artifacts,
        }
        pending = work / "compiled.json"
        pending.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        os.replace(pending, receipt)


def verify_products(
    build: Path, identity: Path, desktop: str | None = None, adapter: Path | None = None, runner: Path | None = None
) -> None:
    """Reject stale or altered build artifacts against the current admitted payload."""
    sources = author(build, identity, desktop, adapter, runner)
    paths = build_paths(build)
    directory = member(paths["packages"], "msi")
    receipt = json.loads(member(directory, "compiled.json").read_text(encoding="utf-8"))
    expected = {Path(name).with_suffix(".msi").name for name in sources}
    if receipt["installable"] is not False or set(receipt["artifacts"]) != expected:
        raise ValueError("MSI compilation receipt has invalid ownership or installation state")
    if receipt["sources"] != {name: digest(path) for name, path in sources.items()}:
        raise ValueError("MSI compilation receipt has stale sources")
    if receipt["authoring_sha256"] != digest(member(paths["installation_metadata"], "wix/authoring.json")):
        raise ValueError("MSI compilation receipt has stale payload identity")
    for name, checksum in receipt["artifacts"].items():
        if digest(member(directory, name)) != checksum:
            raise ValueError(f"MSI artifact has changed: {name}")


def maintenance_plan(
    build: Path,
    identity: Path,
    scope: InstallationScope,
    prefix: Path,
    desktop: str | None = None,
    adapter: Path | None = None,
    runner: Path | None = None,
) -> Path:
    """Bind an explicit installation intent to the verified pair of native artifacts."""
    if scope not in {"user", "machine"} or not prefix.is_absolute():
        raise ValueError("Native MSI maintenance requires an explicit scope and absolute prefix")
    verify_products(build, identity, desktop, adapter, runner)
    paths = build_paths(build)
    authoring = json.loads(member(paths["installation_metadata"], "wix/authoring.json").read_text(encoding="utf-8"))
    compilation = json.loads(member(paths["packages"], "msi/compiled.json").read_text(encoding="utf-8"))
    source = authoring["maintenance"]
    document = {key: source[key] for key in ("version", "manifest_sha256", "desktop_present", "contract")}
    document.update({"schema": 1, "scope": scope, "prefix": str(prefix)})
    for role in ("version", "registration"):
        name = f"{scope}-{role}"
        document[f"{role}_product"] = {
            "path": str(member(paths["packages"], f"msi/{name}.msi")),
            "sha256": compilation["artifacts"][f"{name}.msi"],
            "product_code": source["products"][name],
        }
    destination = member(paths["installation_metadata"], f"maintenance-{scope}.json")
    destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return destination


def bootstrap_kit(
    build: Path,
    identity: Path,
    payload: Path,
    desktop: str | None = None,
    adapter: Path | None = None,
    runner: Path | None = None,
) -> Path:
    """Deliver portable desktop provisioning beside the immutable application package."""
    if runner is None or adapter is None or desktop is None:
        raise ValueError("Desktop provisioning requires the authenticated runner, adapter and desktop")
    verify_products(build, identity, desktop, adapter, runner)
    paths = build_paths(build)
    authored = json.loads(member(paths["installation_metadata"], "wix/authoring.json").read_text(encoding="utf-8"))
    compiled = json.loads(member(paths["packages"], "msi/compiled.json").read_text(encoding="utf-8"))
    source = authored["maintenance"]
    manifest = json.loads(member(payload, "data/package-manifest.json").read_text(encoding="utf-8"))
    if digest(member(payload, "data/package-manifest.json")) != source["manifest_sha256"]:
        raise ValueError("Desktop package differs from the MSI installation kit")
    definition = manifest["layout"]["installation"]["bootstrap"]
    directory = member(payload.parent, definition["directory"])
    directory.mkdir(parents=True, exist_ok=True)
    descriptor = member(directory, definition["manifest"])
    artifacts = {
        name: {
            "path": f"{name}.msi",
            "sha256": compiled["artifacts"][f"{name}.msi"],
            "product_code": code,
        }
        for name, code in source["products"].items()
    }
    document = {
        "schema": 1,
        "runner": {"path": runner.name, "sha256": authored["runner_sha256"]},
        "maintenance": {key: source[key] for key in ("version", "manifest_sha256", "desktop_present", "contract")},
        "artifacts": artifacts,
    }
    sources = {runner.name: (runner, authored["runner_sha256"])}
    sources.update(
        {
            f"{name}.msi": (member(paths["packages"], f"msi/{name}.msi"), compiled["artifacts"][f"{name}.msi"])
            for name in artifacts
        }
    )
    return _deliver_kit(directory, descriptor, sources, json.dumps(document, indent=2) + "\n")


def _deliver_kit(directory: Path, descriptor: Path, sources: dict[str, tuple[Path, str]], document: str) -> Path:
    """Copy admitted inputs and publish their descriptor only after every hash matches."""
    with TemporaryDirectory(prefix="kit-", dir=directory) as temporary:
        work = Path(temporary)
        for name, (original, checksum) in sources.items():
            if digest(original) != checksum:
                raise ValueError("Installation kit source changed during delivery")
            pending = member(work, name)
            shutil.copyfile(original, pending)
            if digest(pending) != checksum:
                raise ValueError("Installation kit copy differs from its verified source")
            destination = member(directory, name)
            if destination.exists() and digest(destination) == checksum:
                continue
            os.replace(pending, destination)
        # Publish the descriptor last; incomplete or mixed copies cannot pass admission.
        pending_descriptor = member(work, descriptor.name)
        pending_descriptor.write_text(document, encoding="utf-8")
        os.replace(pending_descriptor, descriptor)
    return descriptor


def main() -> None:
    """Expose build, verification and authenticated native maintenance commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("build", "verify", "kit", "plan", "install", "remove-version", "unregister", "check-installation"),
    )
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--desktop")
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--runner", type=Path)
    parser.add_argument("--scope", choices=("user", "machine"))
    parser.add_argument("--prefix", type=Path)
    parser.add_argument("--version", help="Exact installed release to remove; anchors and live use refuse")
    parser.add_argument("--wix", type=Path)
    parser.add_argument("--payload", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "check-installation":
            raise ValueError(
                f"{MAINTENANCE_GATE} Required: transaction publication, scope-conflict admission, "
                "same-version integrity, anchor retention, safe in-use removal; manager IPC/readiness, "
                "cutover/rollback, login opt-out and uninstall detection. Acceptance requires a disposable "
                "interactive Windows runner and two genuinely built distinct releases; Session 0 is insufficient. "
                "Signing remains a release prerequisite."
            )
        if args.command == "kit":
            if args.payload is None:
                raise ValueError("Desktop provisioning requires the assembled payload")
            bootstrap_kit(
                args.build.resolve(), args.identity, args.payload.resolve(), args.desktop, args.adapter, args.runner
            )
        elif args.command in {"plan", "install", "remove-version", "unregister"}:
            if args.scope is None or args.prefix is None:
                raise ValueError("Set CADRUMO_MSI_SCOPE and CADRUMO_MSI_PREFIX for explicit native maintenance")
            plan = maintenance_plan(
                args.build.resolve(), args.identity, args.scope, args.prefix, args.desktop, args.adapter, args.runner
            )
            if args.command != "plan":
                if args.runner is None or not args.runner.is_file():
                    raise ValueError("Set CADRUMO_MSI_RUNNER to the CMake-built native maintenance runner")
                command = [str(args.runner), args.command, "--plan", str(plan)]
                if args.command == "remove-version":
                    if not args.version:
                        raise ValueError("Set CADRUMO_MSI_REMOVE_VERSION to the exact installed release")
                    command.extend(("--version", args.version))
                elif args.version is not None:
                    raise ValueError("--version is valid only for remove-version")
                result = run_command(command, cwd=args.build, timeout_seconds=900)
                print(result.stdout, end="")
                if result.returncode:
                    raise ValueError("Native maintenance refused or did not complete; see its typed result")
        elif args.command == "build":
            if args.wix is None or not args.wix.is_file():
                raise ValueError("Set CADRUMO_WIX_EXECUTABLE to an installed WiX 5+ executable")
            compile_products(args.build.resolve(), args.identity, args.wix, args.desktop, args.adapter, args.runner)
        else:
            verify_products(args.build.resolve(), args.identity, args.desktop, args.adapter, args.runner)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
