"""Publish only a rebuilt agent wheel into an existing CMake application stage."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from dev.first_party_source import is_test_source

from ..runtime_wheel_selection import marker_environment
from ..runtime_wheelhouse_contract import target_platform
from ..wheel_metadata import read_wheel_metadata
from .agent import agent_wheel, validate_wheel_dependencies
from .build_paths import build_paths
from .hashing import digest
from .layout import load_layout
from .process_quiescence import quiesce
from .stdlib import bytecode
from .update_images import publish


def wheel_files(wheel: Path, *, version: str, prefix: str) -> dict[str, bytes]:
    """Admit agent-owned members and prepare their checked-hash bytecode in memory."""
    owned = {"cadrumo_agent", f"cadrumo_agent-{version}.dist-info"}
    prepared: dict[str, bytes] = {}
    aliases: set[str] = set()
    with zipfile.ZipFile(wheel) as archive:
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename)
            if (
                not name.parts
                or name.is_absolute()
                or ".." in name.parts
                or ":" in entry.filename
                or "\\" in entry.filename
                or name.parts[0] not in owned
                or (entry.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("Agent wheel contains an unowned or linked member")
            if entry.is_dir() or is_test_source(name) or "__pycache__" in name.parts:
                continue
            member = f"{prefix}/{name}"
            if member.casefold() in aliases:
                raise ValueError("Agent wheel contains duplicate or aliased members")
            aliases.add(member.casefold())
            content = archive.read(entry)
            prepared[member] = content
            if name.suffix == ".py":
                cache = name.parent / "__pycache__" / f"{name.stem}.{sys.implementation.cache_tag}.pyc"
                prepared[f"{prefix}/{cache}"] = bytecode(content, name.as_posix(), prefix=prefix)
    if f"{prefix}/cadrumo_agent/__init__.py" not in prepared:
        raise ValueError("Agent wheel has no package root")
    return prepared


def update(build: Path, config: str) -> None:
    """Update agent-owned files with rollback; preserve every other distribution and image."""
    paths = build_paths(build)
    target = json.loads((paths["generated"] / "identity.json").read_text())["target"]
    contract = load_layout(target)
    root = (paths["stage"] / config / "app").resolve(strict=True)
    if not root.is_relative_to(build.resolve()):
        raise ValueError("Agent update requires a package inside its CMake directory")
    manifest_path = root / contract["files"]["package_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads((paths["agent"] / "agent-wheel.json").read_text(encoding="utf-8"))
    if manifest["layout"] != contract or manifest["distributions"]["cadrumo-agent"] != receipt["version"]:
        raise ValueError("Agent-only update requires the existing layout and distribution version")
    if tuple(map(int, manifest["python"].split("."))) != sys.version_info[:3]:
        raise ValueError("Agent bytecode requires the package's exact Python compiler")
    wheel = agent_wheel(paths["agent"])
    validate_wheel_dependencies(wheel, target, manifest["python"])
    environment = marker_environment(target_platform(target), manifest["python"])
    for value in read_wheel_metadata(wheel).get_all("Requires-Dist", []):
        requirement = Requirement(value)
        if requirement.marker is None or requirement.marker.evaluate(environment):
            installed = manifest["distributions"].get(canonicalize_name(requirement.name))
            if installed is None or installed not in requirement.specifier:
                raise ValueError(f"Agent requires a dependency update: {requirement.name}")
    prefix = contract["paths"]["packages"]
    prepared = wheel_files(wheel, version=receipt["version"], prefix=prefix)
    owned = (f"{prefix}/cadrumo_agent/", f"{prefix}/cadrumo_agent-{receipt['version']}.dist-info/")
    previous = {member for member in manifest["files"] if member.startswith(owned)}
    members = previous | prepared.keys()
    for member in members:
        path = root / member
        if ".." in PurePosixPath(member).parts or not path.resolve().is_relative_to(root):
            raise ValueError("Agent update escapes its package")
        if member in previous and (not path.is_file() or digest(path) != manifest["files"][member]):
            raise ValueError(f"Existing agent file does not match its inventory: {member}")
    changed = {
        member
        for member in members
        if member not in prepared
        or member not in previous
        or hashlib.sha256(prepared[member]).hexdigest() != manifest["files"][member]
    }
    if changed:
        quiesce(build.resolve(), target)
    backups = {member: (root / member).read_bytes() if (root / member).is_file() else None for member in changed}
    try:
        for member in changed:
            path = root / member
            if member in prepared:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(prepared[member])
            else:
                path.unlink()
        for member in previous:
            manifest["files"].pop(member)
        manifest["files"].update({member: hashlib.sha256(content).hexdigest() for member, content in prepared.items()})
        manifest["agent"] = {"bundled": True, **receipt}
        manifest["inputs"]["agent"] = receipt
        publish(manifest_path, manifest)
    except BaseException:
        for member, content in backups.items():
            path = root / member
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        raise
    print(f"Agent files updated: {len(changed)}; application, dependencies and native images preserved", flush=True)


def main() -> None:
    """Run the CMake-owned incremental agent publication."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--config", choices=("Debug", "Release"), required=True)
    arguments = parser.parse_args()
    update(arguments.build, arguments.config)


if __name__ == "__main__":
    main()
