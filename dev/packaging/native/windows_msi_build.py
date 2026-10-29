"""Build scoped MSI products and run explicit native maintenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from contextlib import suppress
from pathlib import Path, PureWindowsPath
from typing import cast
from uuid import uuid4

from ..command_execution import run_command
from .action_cache import action_lock
from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .hashing import digest
from .installation import member, verify_inventory
from .installation_reuse import public_directory
from .windows_msi import author, verify_destination_lengths
from .windows_msi_database import verify_admission_order, verify_feature_ownership, verify_upgrade_order
from .windows_msi_identity import InstallationScope
from .windows_msi_permissions import public_install_permissions
from .windows_msi_verify import verify_database


def _run(wix: Path, arguments: list[str], directory: Path) -> str:
    result = run_command([str(wix), *arguments], cwd=directory, timeout_seconds=300)
    if result.returncode:
        raise ValueError(f"WiX failed ({result.returncode}): {result.stdout}{result.stderr}")
    return result.stdout.strip()


def compile_products(
    build: Path,
    identity: Path,
    wix: Path,
    desktop: str | None = None,
    adapter: Path | None = None,
    runner: Path | None = None,
) -> None:
    """Serialize the one MSI producer, including direct admitted CLI invocations."""
    with action_lock(build, "msi-products"):
        _compile_products(build, identity, wix, desktop, adapter, runner)


def _read_compilation_receipt(
    receipt: Path,
    compiler: dict[str, str],
    inputs: dict[str, str],
    authoring_hash: str,
    directory: Path,
    sources: dict[str, Path],
    authoring: Path,
) -> tuple[dict[str, object], bool]:
    previous = {}
    try:
        previous = json.loads(receipt.read_text(encoding="utf-8"))
        if (
            previous["compiler"] == compiler
            and previous["sources"] == inputs
            and previous["authoring_sha256"] == authoring_hash
        ):
            _verify_compilation(directory, sources, authoring)
            return cast(dict[str, object], previous), True
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if not isinstance(previous, dict):
        previous = {}
    return cast(dict[str, object], previous), False


def _compile_sources(
    wix: Path, work: Path, sources: dict[str, Path], adapter: Path | None, runner: Path | None
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for name, source in sources.items():
        artifact = work / Path(name).with_suffix(".msi").name
        _run(wix, ["build", "-arch", "x64", "-wx", "-o", str(artifact), str(source)], work)
        database = work / name
        _run(wix, ["msi", "decompile", "-o", str(database), str(artifact)], work)
        verify_database(source, database)
        verify_feature_ownership(artifact)
        verify_upgrade_order(artifact, version_product=source.stem.endswith("-version") or source.stem == "application")
        if adapter is not None:
            verify_admission_order(artifact, owner_required=runner is not None)
        artifacts[artifact.name] = digest(artifact)
    return artifacts


def _check_compilation_inputs(
    paths: dict[str, Path],
    before: dict[str, str],
    stable_inputs: list[Path],
    inputs: dict[str, str],
    sources: dict[str, Path],
    authoring: Path,
    authoring_hash: str,
) -> None:
    # Re-admit bytes without regenerating a second complete WiX document.
    verify_inventory(paths["installation_stage"], member(paths["installation_metadata"], "installation.json"))
    if (
        before != {str(path): digest(path) for path in stable_inputs}
        or inputs != {name: digest(path) for name, path in sources.items()}
        or _authoring_identity(authoring) != authoring_hash
    ):
        raise ValueError("MSI inputs changed during compilation")


def _prepare_retirement(directory: Path, previous: dict[str, object]) -> tuple[Path, dict[str, str], set[str]]:
    retirement = member(directory, "retiring.json")
    retired: dict[str, str] = {}
    with suppress(OSError, ValueError):
        retired = cast(dict[str, str], json.loads(retirement.read_text(encoding="utf-8")))
    legacy = {f"{scope}-{role}.msi" for scope in ("user", "machine") for role in ("version", "registration")}
    previous_artifacts = cast(dict[str, str], previous.get("artifacts", {}))
    retired.update({name: checksum for name, checksum in previous_artifacts.items() if name in legacy})
    if retired:
        retirement.write_text(json.dumps(retired, indent=2) + "\n", encoding="utf-8")
    return retirement, retired, legacy


def _compile_products(
    build: Path,
    identity: Path,
    wix: Path,
    desktop: str | None,
    adapter: Path | None,
    runner: Path | None,
) -> None:
    """Compile the single release MSI and publish its receipt after database verification."""
    wix = wix.resolve(strict=True)
    sources = author(build, identity, desktop, adapter, runner)
    paths = build_paths(build)
    directory = member(paths["packages"], "msi")
    directory.mkdir(parents=True, exist_ok=True)
    receipt = member(directory, "compiled.json")
    version = _run(wix, ["--version"], build)
    if not version.split(".", 1)[0].isdigit() or int(version.split(".", 1)[0]) < 5:
        receipt.unlink(missing_ok=True)
        raise ValueError("Scoped MSI products require WiX 5 or newer")
    inputs = {name: digest(path) for name, path in sources.items()}
    authoring = member(paths["installation_metadata"], "wix/authoring.json")
    authoring_hash = _authoring_identity(authoring)
    compiler = {"path": str(wix), "version": version, "sha256": digest(wix)}
    previous, reusable = _read_compilation_receipt(
        receipt, compiler, inputs, authoring_hash, directory, sources, authoring
    )
    if reusable:
        return
    retirement, retired, legacy = _prepare_retirement(directory, previous)
    # A failed retry must not leave an earlier receipt presenting this run as successful.
    receipt.unlink(missing_ok=True)
    stable_inputs = [identity, member(paths["installation_metadata"], "installation.json")]
    stable_inputs.extend(path for path in (adapter, runner) if path is not None)
    before = {str(path): digest(path) for path in stable_inputs}
    with public_directory(directory, "compile-") as work:
        artifacts = _compile_sources(wix, work, sources, adapter, runner)
        _check_compilation_inputs(paths, before, stable_inputs, inputs, sources, authoring, authoring_hash)
        for name in artifacts:
            os.replace(work / name, member(directory, name))
        _retire(directory, retired, legacy)
        authored = json.loads(authoring.read_text(encoding="utf-8"))
        _retire(
            authoring.parent,
            cast(dict[str, str], authored.get("retired_sources", {})),
            {Path(name).with_suffix(".wxs").name for name in legacy},
        )
        document = {
            "installable": False,
            "compiler": compiler,
            "authoring_sha256": authoring_hash,
            "sources": inputs,
            "artifacts": artifacts,
        }
        pending = work / "compiled.json"
        pending.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        os.replace(pending, receipt)
        retirement.unlink(missing_ok=True)


def _retire(directory: Path, recorded: dict[str, str], permitted: set[str]) -> None:
    """Remove only unchanged outputs whose previous producer recorded ownership."""
    paths: list[Path] = []
    for name, checksum in recorded.items():
        if name not in permitted:
            raise ValueError("Previous MSI receipt contains an unexpected owned output")
        path = member(directory, name)
        if path.exists():
            if digest(path) != checksum:
                raise ValueError(f"Previous MSI output changed; refusing to remove: {name}")
            paths.append(path)
    for path in paths:
        path.unlink()


def _authoring_identity(path: Path) -> str:
    """Bind emitted ownership, without rebuilding MSI for generation-cache bookkeeping."""
    document = json.loads(path.read_text(encoding="utf-8"))
    document.pop("input_identity", None)
    document.pop("retired_sources", None)
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_products(
    build: Path, identity: Path, desktop: str | None = None, adapter: Path | None = None, runner: Path | None = None
) -> None:
    """Reject stale or altered build artifacts against the current admitted payload."""
    sources = author(build, identity, desktop, adapter, runner)
    paths = build_paths(build)
    directory = member(paths["packages"], "msi")
    _verify_compilation(directory, sources, member(paths["installation_metadata"], "wix/authoring.json"))


def _verify_compilation(directory: Path, sources: dict[str, Path], authoring: Path) -> None:
    """Validate one publication against already admitted authoring without regenerating it."""
    receipt = json.loads(member(directory, "compiled.json").read_text(encoding="utf-8"))
    expected = {Path(name).with_suffix(".msi").name for name in sources}
    if receipt["installable"] is not False or set(receipt["artifacts"]) != expected:
        raise ValueError("MSI compilation receipt has invalid ownership or installation state")
    if receipt["sources"] != {name: digest(path) for name, path in sources.items()}:
        raise ValueError("MSI compilation receipt has stale sources")
    if receipt["authoring_sha256"] != _authoring_identity(authoring):
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
    document.update({"schema": 2, "scope": scope, "prefix": str(prefix)})
    for role in ("version", "registration"):
        name = "application"
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
        "schema": 2,
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


def _retired_kit_artifacts(descriptor: Path, sources: dict[str, tuple[Path, str]]) -> dict[str, str]:
    retired = {}
    try:
        previous = cast(dict[str, object], json.loads(descriptor.read_text(encoding="utf-8")))
        legacy = {f"{scope}-{role}.msi" for scope in ("user", "machine") for role in ("version", "registration")}
        retired = {
            artifact["path"]: artifact["sha256"]
            for artifact in cast(dict[str, dict[str, str]], previous.get("artifacts", {})).values()
            if artifact.get("path") in legacy and artifact["path"] not in sources
        }
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        pass
    return retired


def _copy_kit_sources(directory: Path, work: Path, sources: dict[str, tuple[Path, str]]) -> None:
    for name, (original, checksum) in sources.items():
        if digest(original) != checksum:
            raise ValueError("Installation kit source changed during delivery")
        destination = member(directory, name)
        if destination.is_file() and digest(destination) == checksum and public_install_permissions(destination):
            continue
        pending = member(work, name)
        shutil.copyfile(original, pending)
        if digest(pending) != checksum:
            raise ValueError("Installation kit copy differs from its verified source")
        # Identical bytes with private or explicit ACLs are replaced too.
        os.replace(pending, destination)


def _deliver_kit(directory: Path, descriptor: Path, sources: dict[str, tuple[Path, str]], document: str) -> Path:
    """Copy admitted inputs and publish their descriptor only after every hash matches."""
    # mkdtemp's 0700 directory gives Windows artifacts a private, protected DACL.
    # These public installation files must inherit their destination's permissions.
    work = member(directory, f"kit-{uuid4().hex}")
    work.mkdir(mode=0o755)
    retired = _retired_kit_artifacts(descriptor, sources)
    try:
        _copy_kit_sources(directory, work, sources)
        _retire(directory, retired, set(retired))
        # Publish the descriptor last; incomplete or mixed copies cannot pass admission.
        if not (
            descriptor.is_file()
            and descriptor.read_text(encoding="utf-8") == document
            and public_install_permissions(descriptor)
        ):
            pending_descriptor = member(work, descriptor.name)
            pending_descriptor.write_text(document, encoding="utf-8")
            os.replace(pending_descriptor, descriptor)
    finally:
        shutil.rmtree(work)
    return descriptor


def _maintenance_command(args: argparse.Namespace) -> None:
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


def main() -> None:
    """Expose build, verification and authenticated native maintenance commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("build", "verify", "kit", "plan", "install", "remove-version", "unregister"),
    )
    parser.add_argument("--build", type=require_enrolled_build, required=True)
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
        if args.command == "kit":
            if args.payload is None:
                raise ValueError("Desktop provisioning requires the assembled payload")
            bootstrap_kit(
                args.build.resolve(), args.identity, args.payload.resolve(), args.desktop, args.adapter, args.runner
            )
        elif args.command in {"plan", "install", "remove-version", "unregister"}:
            _maintenance_command(args)
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
