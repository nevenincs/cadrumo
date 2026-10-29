"""Author scoped MSI ownership sources; native maintenance integration gates installation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast
from xml.etree.ElementTree import Element

from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .hashing import digest
from .identity import DistributionIdentity
from .installation import member, validate_payload, verify_inventory
from .layout import application_images, load_layout
from .windows_msi_components import add_machine_service
from .windows_msi_contract import MAINTENANCE_GATE
from .windows_msi_identity import ProductRole, release_identity
from .windows_msi_single import OWNER_GATE
from .windows_msi_single import source as release_source
from .windows_msi_source import msi_source


def verify_destination_lengths(prefix: PureWindowsPath, members: Iterable[str]) -> None:
    """Admit every installed destination within the legacy MSI path budget."""
    if not prefix.is_absolute() or ".." in prefix.parts:
        raise ValueError("MSI destination requires an absolute Windows installation prefix")
    for relative in members:
        member_path = PurePosixPath(relative)
        if member_path.is_absolute() or ".." in member_path.parts or "\\" in relative or ":" in relative:
            raise ValueError("MSI destination member must remain relative to its installation prefix")
        destination = prefix / member_path
        if len(str(destination).encode("utf-16-le")) // 2 >= 260:
            raise ValueError(f"MSI installed destination exceeds 259 UTF-16 units: {relative}")


def default_installation_prefixes(name: str) -> tuple[PureWindowsPath, PureWindowsPath]:
    """Resolve MSI folder owners; portable authoring checks nominal Windows defaults."""
    if sys.platform == "win32":
        from win32com.shell import shell, shellcon

        user = shell.SHGetKnownFolderPath(shellcon.FOLDERID_LocalAppData, 0, None)
        machine = shell.SHGetKnownFolderPath(shellcon.FOLDERID_ProgramFilesX64, 0, None)
    else:
        # Cross-host authoring cannot attest the eventual account's known folders.
        # Native maintenance must validate its actual selected prefix as well.
        user = "C:/Users/Default/AppData/Local"
        machine = "C:/Program Files"
    return PureWindowsPath(user) / name, PureWindowsPath(machine) / name


def _staged_manifest(build: Path) -> tuple[Path, dict[str, str], Path, dict[str, object]]:
    paths = build_paths(build)
    stage = paths["installation_stage"]
    receipt = member(paths["installation_metadata"], "installation.json")
    verify_inventory(stage, receipt)
    document = cast(dict[str, object], json.loads(receipt.read_text(encoding="utf-8")))
    owned = cast(dict[str, str], document["files"])
    anchors = [
        name for name in owned if name == "data/package-manifest.json" or name.endswith("/data/package-manifest.json")
    ]
    if len(anchors) != 1:
        raise ValueError("MSI stage must identify exactly one verified package")
    manifest = member(stage, anchors[0])
    value = cast(dict[str, object], json.loads(manifest.read_text(encoding="utf-8")))
    if document["application_id"] != cast(dict[str, object], value["build"])["application_id"]:
        raise ValueError("MSI receipt and package identities differ")
    return stage, owned, manifest, value


def reject_combined_manager_msi(build: Path) -> None:
    """Prevent the legacy CPack product from owning a manager version and shared entry."""
    _, _, _, manifest = _staged_manifest(build)
    if any(image.target == "rust_manager" for image in application_images(cast(dict[str, object], manifest["layout"]))):
        raise ValueError("Manager payloads require the authenticated release MSI. " + MAINTENANCE_GATE)


def _validate_installation_tools(adapter: Path | None, runner: Path | None) -> tuple[Path | None, Path | None]:
    if adapter is not None:
        adapter = adapter.resolve(strict=True)
        if not adapter.is_file() or adapter.suffix.lower() != ".dll":
            raise ValueError("MSI adapter must be an existing native installer DLL")
    if runner is not None:
        runner = runner.resolve(strict=True)
        if adapter is None or not runner.is_file() or runner.suffix.lower() != ".exe":
            raise ValueError("MSI owner requires a built runner executable and native installer DLL")
    return adapter, runner


def _previous_authoring(locator: Path) -> tuple[object, dict[str, str]]:
    retired_sources = {}
    previous: object = {}
    try:
        previous = json.loads(locator.read_text(encoding="utf-8"))
        old = {
            **cast(dict[str, dict[str, str]], previous).get("retired_sources", {}),
            **cast(dict[str, dict[str, str]], previous).get("sources", {}),
        }
        retired_sources = {
            name: checksum
            for name, checksum in old.items()
            if name in {f"{scope}-{role}.wxs" for scope in ("user", "machine") for role in ("version", "registration")}
        }
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return previous, retired_sources


def _authoring_identity(
    metadata: Path, identity_file: Path, desktop: str | None, adapter: Path | None, runner: Path | None
) -> dict[str, object]:
    return {
        "installation_sha256": digest(member(metadata, "installation.json")),
        "identity_sha256": digest(identity_file),
        "desktop": desktop,
        "adapter_sha256": digest(adapter) if adapter is not None else None,
        "runner_sha256": digest(runner) if runner is not None else None,
        "helpers": {
            name: digest(Path(__file__).with_name(name + ".py"))
            for name in (
                "windows_msi",
                "windows_msi_components",
                "windows_msi_source",
                "windows_msi_contract",
                "windows_msi_single",
                "windows_msi_identity",
                "windows_msi_paths",
                "identity",
                "layout",
                "installation",
            )
        },
    }


def _can_reuse_authoring(
    previous: object,
    input_identity: dict[str, object],
    output: Path,
    native_marker: Path,
    marker_content: bytes,
    stage: Path,
    metadata: Path,
) -> bool:
    if isinstance(previous, dict) and cast(dict[str, object], previous).get("input_identity") == input_identity:
        try:
            if (
                cast(dict[str, object], previous)["sources"] == {"application.wxs": digest(output)}
                and digest(native_marker) == hashlib.sha256(marker_content).hexdigest()
            ):
                verify_inventory(stage, member(metadata, "installation.json"))
                return True
        except (OSError, KeyError, TypeError):
            pass
    return False


def _validate_manager_layout(layout: dict[str, object], definition: dict[str, object]) -> str:
    managers = [image for image in application_images(layout) if image.target == "rust_manager"]
    if len(managers) != 1 or managers[0].placement != "." or layout.get("installation") != definition:
        raise ValueError("MSI authoring requires the canonical versioned manager layout")
    return managers[0].package_path


def _validate_shared_resources(
    stage: Path, package: Path, shared_files: dict[str, str], manager: str, definition: dict[str, object]
) -> None:
    expected_shared = {
        manager,
        cast(str, definition["marker"]),
        "docs/licenses/CADRUMO.txt",
        "docs/licenses/NOTICE.txt",
    }
    if set(shared_files) != expected_shared or digest(member(stage, manager)) != digest(member(package, manager)):
        raise ValueError("MSI shared resources differ from the canonical registration owner")


def _validate_release_stage(
    stage: Path,
    owned: dict[str, str],
    manifest_file: Path,
    manifest: dict[str, object],
    value: DistributionIdentity,
    identity_file: Path,
    desktop: str | None,
) -> tuple[dict[str, object], dict[str, str], dict[str, str], str]:
    definition = cast(dict[str, object], load_layout("windows-x64")["installation"])
    manager = _validate_manager_layout(cast(dict[str, object], manifest["layout"]), definition)
    prefix = f"{definition['versions']}/{value.version}/"
    package = member(stage, prefix.rstrip("/"))
    if manifest_file != member(package, "data/package-manifest.json"):
        raise ValueError("MSI version files do not belong to the requested release")
    validate_payload(package, identity_file, desktop)
    version_files = {name: checksum for name, checksum in owned.items() if name.startswith(prefix)}
    shared_files = {name: checksum for name, checksum in owned.items() if not name.startswith(prefix)}
    _validate_shared_resources(stage, package, shared_files, manager, definition)
    for destination in default_installation_prefixes(value.name):
        verify_destination_lengths(destination, owned)
    return definition, version_files, shared_files, manager


def _emit_authoring_sources(
    stage: Path,
    version_files: dict[str, str],
    shared_files: dict[str, str],
    value: DistributionIdentity,
    manager: str,
    desktop: str | None,
    definition: dict[str, object],
    native_marker: Path,
    marker_content: bytes,
    manifest_file: Path,
    metadata: Path,
    directory: Path,
    adapter: Path | None,
    runner: Path | None,
) -> dict[str, Path]:
    partitions: list[bytes] = []
    roles: tuple[tuple[ProductRole, dict[str, str]], ...] = (("version", version_files), ("registration", shared_files))
    for role, files in roles:
        partitions.append(
            msi_source(
                stage,
                files,
                value,
                "user",
                role,
                manager,
                desktop,
                (cast(str, definition["marker"]), native_marker, hashlib.sha256(marker_content).hexdigest()),
                digest(manifest_file),
                product=release_identity(value, role),
            )
        )
    service = Element("Component")
    add_machine_service(service, value)
    sources = {
        "application.wxs": release_source(
            partitions[0],
            partitions[1],
            value,
            manager,
            list(service),
            adapter,
            runner,
        )
    }
    verify_inventory(stage, member(metadata, "installation.json"))
    directory.mkdir(exist_ok=True)
    if not native_marker.exists() or native_marker.read_bytes() != marker_content:
        native_marker.write_bytes(marker_content)
    outputs: dict[str, Path] = {}
    for name, content in sources.items():
        output = member(directory, name)
        if not output.exists() or output.read_bytes() != content:
            output.write_bytes(content)
        outputs[name] = output
    return outputs


def _write_authoring_descriptor(
    locator: Path,
    runner: Path | None,
    manifest_file: Path,
    outputs: dict[str, Path],
    input_identity: dict[str, object],
    retired_sources: dict[str, str],
    adapter: Path | None,
    native_marker: Path,
    value: DistributionIdentity,
    desktop: str | None,
    manifest_layout: object,
) -> None:
    descriptor = {
        "installable": False,
        "blocked_by": OWNER_GATE if runner is not None else MAINTENANCE_GATE,
        "manifest_sha256": digest(manifest_file),
        "sources": {name: digest(path) for name, path in outputs.items()},
        "input_identity": input_identity,
        "retired_sources": retired_sources,
        "adapter_sha256": digest(adapter) if adapter is not None else None,
        "runner_sha256": digest(runner) if runner is not None else None,
        "native_marker_sha256": digest(native_marker),
        "maintenance": {
            "version": value.version,
            "manifest_sha256": digest(manifest_file),
            "desktop_present": desktop is not None,
            "contract": {
                "layout": manifest_layout,
                "installation_identity": {"application_id": value.application_id, "channel": value.channel},
            },
            "products": {"application": release_identity(value, "version").product_code},
        },
    }
    content = (json.dumps(descriptor, indent=2) + "\n").encode("utf-8")
    if not locator.exists() or locator.read_bytes() != content:
        locator.write_bytes(content)


def author(
    build: Path,
    identity_file: Path,
    desktop: str | None = None,
    adapter: Path | None = None,
    runner: Path | None = None,
) -> dict[str, Path]:
    """Emit one scope-aware MSI source with independently maintained ownership features."""
    stage, owned, manifest_file, manifest = _staged_manifest(build)
    adapter, runner = _validate_installation_tools(adapter, runner)
    value = DistributionIdentity(**json.loads(identity_file.read_text(encoding="utf-8")))
    if value.target != "windows-x86-64":
        raise ValueError("MSI authoring requires a Windows payload")
    definition, version_files, shared_files, manager = _validate_release_stage(
        stage, owned, manifest_file, manifest, value, identity_file, desktop
    )
    metadata = build_paths(build)["installation_metadata"]
    directory = member(metadata, "wix")
    # Native eligibility is an installer-owned overlay. Archive staging and its
    # immutable inventory remain unchanged and do not acquire this native fence.
    marker = json.loads(member(stage, cast(str, definition["marker"])).read_text(encoding="utf-8"))
    marker["publication"] = definition["publication"]
    marker["launch_policy"] = "native"
    native_marker = member(directory, "native-installation.json")
    marker_content = (json.dumps(marker, indent=2) + "\n").encode("utf-8")
    locator = member(directory, "authoring.json")
    previous, retired_sources = _previous_authoring(locator)
    input_identity = _authoring_identity(metadata, identity_file, desktop, adapter, runner)
    output = member(directory, "application.wxs")
    if _can_reuse_authoring(previous, input_identity, output, native_marker, marker_content, stage, metadata):
        return {"application.wxs": output}
    outputs = _emit_authoring_sources(
        stage,
        version_files,
        shared_files,
        value,
        manager,
        desktop,
        definition,
        native_marker,
        marker_content,
        manifest_file,
        metadata,
        directory,
        adapter,
        runner,
    )
    _write_authoring_descriptor(
        locator,
        runner,
        manifest_file,
        outputs,
        input_identity,
        retired_sources,
        adapter,
        native_marker,
        value,
        desktop,
        manifest["layout"],
    )
    return outputs


def main() -> None:
    """Expose CMake-owned authoring and a guard for direct CPack MSI invocation."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    source = commands.add_parser("author")
    source.add_argument("--build", type=require_enrolled_build, required=True)
    source.add_argument("--identity", type=Path, required=True)
    source.add_argument("--desktop")
    source.add_argument("--adapter", type=Path)
    source.add_argument("--runner", type=Path)
    guard = commands.add_parser("reject-combined")
    guard.add_argument("--build", type=require_enrolled_build, required=True)
    args = parser.parse_args()
    if args.command == "author":
        author(args.build, args.identity, args.desktop, args.adapter, args.runner)
    else:
        reject_combined_manager_msi(args.build)


if __name__ == "__main__":
    main()
