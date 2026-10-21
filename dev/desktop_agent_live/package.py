"""Mirror the staged package with the remote-debugging test host as its desktop image.

The desktop supervises its runtime only when it runs as the installed image of the
package it is pointed at, so the lane cannot start the test host from its Cargo
directory. It runs it from a mirror of the staged package instead, rebound to the
host's bytes the way a native image update rebinds the stage: the package manifest
records the host's digest and the service descriptors admit it as the desktop.
The staged package itself is never changed.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from ..packaging.native.hashing import digest
from ..packaging.native.layout import desktop_image
from ..packaging.native.service_descriptors import refresh_service_image_digests


def _files(root: Path) -> dict[str, os.stat_result]:
    found: dict[str, os.stat_result] = {}
    for directory, names, files in os.walk(root):
        base = Path(directory)
        for name in [*names, *files]:
            path = base / name
            if path.is_symlink() or path.is_junction():
                raise ValueError(f"linked member in a package: {path}")
        for name in files:
            path = base / name
            found[path.relative_to(root).as_posix()] = path.stat()
    return found


def mirror(source: Path, destination: Path, *, rebound: frozenset[str]) -> int:
    """Make ``destination`` hold exactly ``source``'s files; return how many were copied.

    A file is copied when its size or modification time differs, so a copy cut
    short is copied again; ``rebound`` members are always copied fresh.
    """
    wanted = _files(source)
    destination.mkdir(parents=True, exist_ok=True)
    present = _files(destination)
    for member in present.keys() - wanted.keys():
        (destination / member).unlink()
    for directory, names, _files_here in os.walk(destination, topdown=False):
        for name in names:
            path = Path(directory) / name
            if not (source / path.relative_to(destination)).is_dir():
                path.rmdir()
    copied = 0
    for member, status in wanted.items():
        current = present.get(member)
        if (
            member in rebound
            or current is None
            or current.st_size != status.st_size
            or current.st_mtime_ns != status.st_mtime_ns
        ):
            target = destination / member
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / member, target)
            copied += 1
    return copied


def stage_lane_package(layout: dict[str, Any], staged: Path, host: Path, destination: Path) -> Path:
    """Mirror ``staged`` into ``destination`` with ``host`` as its desktop image; return the image."""
    members = layout["files"]
    manifest_member, descriptor_member = members["package_manifest"], members["service_descriptors"]
    manifest: dict[str, Any] = json.loads((staged / manifest_member).read_text(encoding="utf-8"))
    if manifest.get("layout") != layout:
        raise ValueError("the staged package was assembled from another layout; stage it again")
    image = desktop_image(layout)
    if image is None:
        raise ValueError("the package layout declares no desktop image")
    if manifest["files"].get(descriptor_member) != digest(staged / descriptor_member):
        raise ValueError("the staged service descriptors differ from the package manifest")
    mirror(staged, destination, rebound=frozenset({image.package_path, descriptor_member, manifest_member}))
    shutil.copy2(host, destination / image.package_path)
    refresh_service_image_digests(destination, descriptor_member)
    manifest["files"][image.package_path] = digest(destination / image.package_path)
    manifest["files"][descriptor_member] = digest(destination / descriptor_member)
    (destination / manifest_member).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination / image.package_path
