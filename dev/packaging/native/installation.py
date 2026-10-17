"""Validate native payloads and remove only unchanged files owned by a prefix install."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from dev._paths import REPO_ROOT

from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .hashing import digest
from .installation_filesystem import file_identity, remove_owned_file
from .layout import desktop_image, load_layout
from .linux_desktop_runtime import validate_payload as validate_linux_desktop_runtime
from .package_inventory import package_inventory


def member(root: Path, relative: str) -> Path:
    """Reject traversal, Windows drive paths and symlink/reparse redirection."""
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"Unsafe installation member: {relative}")
    candidate = root.joinpath(*path.parts)
    for parent in (candidate, *candidate.parents):
        if parent.is_symlink() or parent.is_junction():
            raise ValueError(f"Installation path redirects through a link: {parent}")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Installation path escapes prefix: {relative}")
    return candidate


def validate_payload(root: Path, identity_file: Path, desktop: str | None = None) -> None:
    """Require the payload to match the requested target, channel and release."""
    expected = json.loads(identity_file.read_text(encoding="utf-8"))
    if (desktop is not None and desktop) and not re.fullmatch(r"[A-Za-z0-9_./-]+", desktop):
        raise ValueError("Desktop executable must use a safe payload-relative path")
    manifest_file = member(root, "data/package-manifest.json")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    validate_linux_desktop_runtime(root, manifest)
    for key in ("application_id", "version", "target", "channel"):
        if manifest["build"].get(key) != expected[key]:
            raise ValueError(f"Payload {key} does not match requested distribution")
    files = package_inventory(root, manifest)
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(files) | {"data/package-manifest.json"}:
        raise ValueError("Payload inventory differs from its package manifest")
    for name, checksum in files.items():
        file = member(root, name)
        if not file.is_file() or digest(file) != checksum:
            raise ValueError(f"Payload file is missing or modified: {name}")
    if (desktop is not None and desktop) and desktop not in manifest["files"]:
        raise ValueError("Desktop executable must belong to the verified payload inventory")
    declared = desktop_image(manifest["layout"]) if (desktop is not None and desktop) else None
    if (desktop is not None and desktop) and (declared is None or desktop != declared.package_path):
        raise ValueError(
            "Only the desktop application image the payload's platform mapping declares receives desktop registration"
        )
    for path in root.rglob("*"):
        member(root, path.relative_to(root).as_posix())


def inventory(root: Path, destination: Path, application_id: str, *, staging_generation: int | None = None) -> None:
    """Capture the staged installation's exact files before native packaging."""
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        checked = member(root, relative)
        if checked.is_file():
            files[relative] = digest(checked)
    document: dict[str, object] = {"application_id": application_id, "files": files}
    if staging_generation is not None:
        document["staging_generation"] = staging_generation
    destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def verify_inventory(root: Path, receipt: Path) -> None:
    """Refuse stale or tampered staged input immediately before CMake installs it."""
    owned = json.loads(receipt.read_text(encoding="utf-8"))["files"]
    actual = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if member(root, relative).is_file():
            actual.add(relative)
    if actual != set(owned):
        raise ValueError("Staged installation inventory has changed; reconfigure")
    for relative, checksum in owned.items():
        if digest(member(root, relative)) != checksum:
            raise ValueError(f"Staged installation file has changed: {relative}")


def uninstall(prefix: Path, receipt: Path, *, dry_run: bool = False) -> list[str]:
    """Preserve modified/unowned files and never follow directory links."""
    if not prefix.is_absolute() or prefix.resolve() == Path(prefix.anchor):
        raise ValueError("An explicit non-root absolute installation prefix is required")
    owned = json.loads(receipt.read_text(encoding="utf-8"))["files"]
    anchors = [
        name for name in owned if name == "data/package-manifest.json" or name.endswith("/data/package-manifest.json")
    ]
    if len(anchors) != 1:
        raise ValueError("Receipt must identify exactly one native package manifest")
    anchor = member(prefix, anchors[0])
    if not anchor.is_file() or digest(anchor) != owned[anchors[0]]:
        raise ValueError("Prefix does not contain the package identified by this receipt")
    definition = load_layout("windows-x64")["installation"]
    if anchors[0].startswith(definition["versions"] + "/"):
        versions = member(prefix, definition["versions"])
        for candidate in versions.iterdir():
            candidate = member(prefix, candidate.relative_to(prefix).as_posix())
            other_manifest = member(candidate, "data/package-manifest.json")
            if other_manifest != anchor and other_manifest.exists():
                raise ValueError(
                    "Multiple installed versions share this prefix; version removal requires its package owner"
                )
    removals = []
    preserved: list[str] = []
    # Preflight the entire receipt before removing anything.
    for relative, checksum in owned.items():
        if not isinstance(relative, str) or not isinstance(checksum, str):
            raise ValueError("Invalid installation receipt entry")
        path = member(prefix, relative)
        if not path.exists():
            continue
        if not path.is_file() or digest(path) != checksum:
            preserved.append(relative)
        else:
            removals.append((relative, checksum, file_identity(path)))
    if not dry_run:
        # Keep the anchor until every other file's retained removal has settled.
        removals.sort(key=lambda item: item[0] == anchors[0])
        for relative, checksum, expected in removals:
            if relative == anchors[0] and preserved:
                continue
            path = member(prefix, relative)
            if not remove_owned_file(path, checksum, expected):
                preserved.append(relative)
        # Empty directories do not belong to the receipt. Preserve them rather
        # than removing a newly replaced/unowned directory by its path name.
    return preserved


def prepare(
    payload: Path,
    identity_file: Path,
    build: Path,
    desktop: str | None = None,
    *,
    copy_file: Callable[[str | Path, str | Path], str | Path] | None = None,
) -> Path:
    """Reuse only an unchanged, identical owning stage; never erase existing state."""
    build = build.absolute()
    paths = build_paths(build)
    root = paths["installation_stage"]
    metadata = paths["installation_metadata"]
    if root.exists():
        from .installation_currency import existing

        if existing(payload, identity_file, root, metadata, desktop, REPO_ROOT, allow_change=False):
            return root
        # Legacy/mismatched helper generations migrate through the same admitted
        # candidate and rollback publication path; never scratch-copy to compare.
        from .distribution_prepare import refresh

        refresh(payload, identity_file, build, desktop)
        return root
    return _prepare_fresh(payload, identity_file, root, metadata, desktop, copy_file=copy_file)


def _prepare_fresh(
    payload: Path,
    identity_file: Path,
    root: Path,
    build: Path,
    desktop: str | None = None,
    *,
    copy_file: Callable[[str | Path, str | Path], str | Path] | None = None,
) -> Path:
    """Create platform installation layout, with desktop registration only for a real entrypoint."""
    validate_payload(payload, identity_file, desktop)
    from .installation_plan import project

    plan = project(payload, identity_file, desktop, REPO_ROOT)
    build = build.absolute()
    build.mkdir(parents=True, exist_ok=True)
    if payload.resolve().is_relative_to(root) or root.is_relative_to(payload.resolve()):
        raise ValueError("Payload and installer staging directory must not overlap")
    root.mkdir(parents=True, mode=0o755 if os.name == "nt" else 0o700)
    destination = member(root, plan.destination)
    shutil.copytree(payload, destination, dirs_exist_ok=True, copy_function=copy_file or shutil.copy2)
    validate_payload(destination, identity_file, desktop)
    for name, contents in plan.controls.items():
        output = member(root, name)
        output.parent.mkdir(parents=True, exist_ok=True)
        # A reused member may still share the admitted previous stage's inode.
        output.unlink(missing_ok=True)
        output.write_bytes(contents)
        output.chmod(plan.modes[name])
    for name, mode in plan.modes.items():
        output = member(root, name)
        if output.stat().st_mode & 0o777 != mode:
            output.chmod(mode)
    for name, contents in plan.metadata.items():
        output = member(build, name)
        output.write_bytes(contents)
        output.chmod(0o644)
    value = json.loads(identity_file.read_text(encoding="utf-8"))
    inventory(root, build / "installation.json", value["application_id"], staging_generation=1)
    receipt_file = build / "installation.json"
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    if receipt["files"] != plan.files:
        raise ValueError("Installation candidate differs from current payload and controls")
    receipt["preparation"] = plan.identity
    receipt_file.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return root


def main() -> None:
    """Expose configure validation and explicit prefix uninstall operations."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--payload", type=Path, required=True)
    validate.add_argument("--identity", type=Path, required=True)
    validate.add_argument("--desktop")
    stage = commands.add_parser("prepare")
    stage.add_argument("--payload", type=Path, required=True)
    stage.add_argument("--identity", type=Path, required=True)
    stage.add_argument("--build", type=require_enrolled_build, required=True)
    stage.add_argument("--desktop")
    capture = commands.add_parser("inventory")
    capture.add_argument("--root", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--application-id", required=True)
    verify = commands.add_parser("verify-inventory")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--receipt", type=Path, required=True)
    remove = commands.add_parser("uninstall")
    remove.add_argument("--prefix", type=Path, required=True)
    remove.add_argument("--receipt", type=Path, required=True)
    remove.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        validate_payload(args.payload, args.identity, args.desktop)
    elif args.command == "prepare":
        prepare(args.payload, args.identity, args.build, args.desktop)
    elif args.command == "inventory":
        inventory(args.root, args.output, args.application_id)
    elif args.command == "verify-inventory":
        verify_inventory(args.root, args.receipt)
    else:
        preserved = uninstall(args.prefix, args.receipt, dry_run=args.dry_run)
        print(json.dumps({"preserved_modified_files": preserved, "dry_run": args.dry_run}))


if __name__ == "__main__":
    main()
