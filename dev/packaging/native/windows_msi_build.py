"""Build scoped MSI products and run explicit native maintenance/guest acceptance."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from subprocess import TimeoutExpired
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from ...runtime_lifecycle.installed import InstalledLifecycleHarness, require_installation_guest
from ..command_execution import run_command
from .build_paths import build_paths
from .hashing import digest
from .installation import member, verify_inventory
from .windows_msi import MAINTENANCE_GATE, OWNER_GATE, WIX_NAMESPACE, author, verify_destination_lengths
from .windows_msi_database import verify_admission_order, verify_feature_ownership, verify_upgrade_order
from .windows_msi_identity import InstallationScope

_NS = {"w": WIX_NAMESPACE}


def check_installation(args: argparse.Namespace) -> None:
    """Execute immediate installed checks; refuse to certify unobserved boot/login/upgrade obligations."""
    receipt = member(build_paths(args.build)["installation_metadata"], "installed-immediate.json")
    evidence = {
        "schema": 1,
        "run_id": str(uuid4()),
        "scope": args.scope,
        "vm_id": str(args.installed_vm_id),
        "guest_kind": args.installed_guest_kind,
        "immediate": "failed",
        "full_installation_acceptance": "incomplete",
        "cleanup": "not_started",
        "pending": ["machine_boot", "user_login", "scope_coexistence", "upgrade_cutover_rollback"],
    }

    def publish() -> None:
        receipt.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    publish()
    if args.installed_vm_id is None or args.installed_account_sid is None or args.scope is None or args.prefix is None:
        raise ValueError(
            "Select a disposable guest with --installed-vm-id, --installed-account-sid, --scope and --prefix"
        )
    campaign = getattr(args, "installed_campaign_state", None)
    root = require_installation_guest(
        args.installed_vm_id,
        args.installed_account_sid,
        args.scope,
        guest_kind=args.installed_guest_kind,
        fresh=campaign is None,
    )
    if args.runner is None or args.adapter is None or args.desktop is None:
        raise ValueError("Installed acceptance requires the actual native runner, adapter and desktop")
    plan = maintenance_plan(args.build, args.identity, args.scope, args.prefix, args.desktop, args.adapter, args.runner)
    owner = InstalledLifecycleHarness(plan, args.runner, root)
    if campaign is None:
        owner.preflight()
    else:
        from ...runtime_lifecycle.client_probes import (
            campaign_binding,
            validate_campaign_state,
            validate_successor_plan,
        )

        state = json.loads(campaign.read_text(encoding="utf-8"))
        validate_campaign_state(
            state,
            campaign_binding(
                plan, args.runner, args.installed_vm_id, args.installed_account_sid, args.installed_guest_kind
            ),
            cleanup=True,
        )
        successor_plan = getattr(args, "installed_successor_plan", None)
        successor_runner = getattr(args, "installed_successor_runner", None)
        if successor_plan is None or successor_runner is None:
            raise ValueError("Campaign finalization requires both immutable successor artifacts")
        successor = InstalledLifecycleHarness(successor_plan, successor_runner, root)
        validate_successor_plan(owner.intent, successor.intent)
        if state.get("successor") != campaign_binding(
            successor_plan,
            successor_runner,
            args.installed_vm_id,
            args.installed_account_sid,
            args.installed_guest_kind,
        ):
            raise ValueError("Campaign successor artifacts differ from committed ownership")
        import win32com.client

        if (
            win32com.client.Dispatch("WindowsInstaller.Installer").ProductState(
                successor.intent["registration_product"]["product_code"]
            )
            == 5
        ):
            owner = successor
        owner._preflight_admitted = True
    source = Path(__file__).resolve().parents[3]
    evidence["immediate"] = "running"
    publish()
    try:
        command = [
            sys.executable,
            "-B",
            "-m",
            "dev.runtime_lifecycle.installed",
            "--plan",
            str(plan),
            "--runner",
            str(args.runner),
            "--installed-vm-id",
            str(args.installed_vm_id),
            "--installed-account-sid",
            args.installed_account_sid,
            "--installed-guest-kind",
            args.installed_guest_kind,
        ]
        if campaign is not None:
            command.extend(
                (
                    "--phase",
                    "cleanup",
                    "--campaign-state",
                    str(campaign),
                    "--successor-plan",
                    str(args.installed_successor_plan),
                    "--successor-runner",
                    str(args.installed_successor_runner),
                )
            )
        result = run_command(
            command,
            cwd=source,
            timeout_seconds=1800,
        )
    except (TimeoutExpired, OSError) as error:
        evidence["immediate"] = "failed"
        evidence["failure"] = "outer_timeout" if isinstance(error, TimeoutExpired) else "outer_launch_failure"
        # Fresh native absence was observed before launch. The authentic native
        # transaction owns SCM/workers; descendant tree termination does not.
        try:
            owner.cleanup_after_outer_exit()
        except Exception as cleanup:
            evidence["cleanup"] = "unsettled"
            evidence["cleanup_error_type"] = type(cleanup).__name__
        else:
            evidence["cleanup"] = "settled"
        finally:
            try:
                owner.resources.close()
            except Exception as cleanup:
                evidence["cleanup"] = "unsettled"
                evidence["cleanup_error_type"] = type(cleanup).__name__
            finally:
                publish()
        raise ValueError(f"Installed acceptance {evidence['failure']}; cleanup={evidence['cleanup']}") from None
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    evidence["immediate"] = "passed" if result.returncode == 0 else "failed"
    evidence["cleanup"] = "scenario_completed" if result.returncode == 0 else "scenario_failed"
    publish()
    if result.returncode:
        raise ValueError("Real installed manager acceptance failed; see the test failure and immediate receipt")
    if campaign is not None:
        validate_cleanup_receipt(json.loads(result.stdout), args.scope)
        evidence["full_installation_acceptance"] = "passed"
        evidence["cleanup"] = "settled"
        evidence["pending"] = []
        publish()
        return
    raise ValueError(
        "Immediate installed checks passed; boot/login, scope coexistence and "
        "two-release upgrade acceptance remain incomplete"
    )


def validate_cleanup_receipt(receipt: Mapping[str, object], scope: str) -> None:
    """Accept only this actually executed same-scope cleanup's complete existing receipt."""
    if (
        receipt.get("schema") != 1
        or receipt.get("phase") != "cleanup"
        or receipt.get("scope") != scope
        or receipt.get("result") != "passed"
        or receipt.get("full_installation_acceptance") != "passed"
        or receipt.get("pending") != []
    ):
        raise ValueError("Actual campaign cleanup did not establish complete same-scope installation acceptance")


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
            verify_feature_ownership(artifact)
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
        verify_feature_ownership(member(directory, name))


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
    paths = build_paths(build)
    inventory_path = member(paths["installation_metadata"], "installation.json")
    verify_inventory(paths["installation_stage"], inventory_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    verify_destination_lengths(PureWindowsPath(prefix), inventory["files"])
    verify_products(build, identity, desktop, adapter, runner)
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
    # mkdtemp's 0700 directory gives Windows artifacts a private, protected DACL.
    # These public installation files must inherit their destination's permissions.
    work = member(directory, f"kit-{uuid4().hex}")
    work.mkdir(mode=0o755)
    try:
        for name, (original, checksum) in sources.items():
            if digest(original) != checksum:
                raise ValueError("Installation kit source changed during delivery")
            pending = member(work, name)
            shutil.copyfile(original, pending)
            if digest(pending) != checksum:
                raise ValueError("Installation kit copy differs from its verified source")
            destination = member(directory, name)
            # Replace identical bytes too: an earlier publication may have retained
            # the private staging DACL, which copying into this directory repairs.
            os.replace(pending, destination)
        # Publish the descriptor last; incomplete or mixed copies cannot pass admission.
        pending_descriptor = member(work, descriptor.name)
        pending_descriptor.write_text(document, encoding="utf-8")
        os.replace(pending_descriptor, descriptor)
    finally:
        shutil.rmtree(work)
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
    parser.add_argument("--installed-vm-id", type=UUID, help="Explicitly selected disposable guest native UUID")
    parser.add_argument(
        "--installed-account-sid", help="Dedicated guest account whose native token must run acceptance"
    )
    parser.add_argument("--installed-guest-kind", choices=("hyperv", "qemu"), default="hyperv")
    parser.add_argument("--installed-campaign-state", type=Path)
    parser.add_argument("--installed-successor-plan", type=Path)
    parser.add_argument("--installed-successor-runner", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "check-installation":
            check_installation(args)
        elif args.command == "kit":
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
