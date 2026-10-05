"""Read output ownership declared by CMake."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath


def build_paths(build: Path) -> dict[str, Path]:
    """Validate every declared directory before returning any output paths."""
    build = build.resolve(strict=True)
    document = json.loads((build / "build-paths.json").read_text(encoding="utf-8"))
    paths: dict[str, Path] = {}
    for key, relative in document["paths"].items():
        if not isinstance(key, str) or not isinstance(relative, str):
            raise ValueError("CMake output names and directories must be strings")
        member = PurePosixPath(relative)
        if not member.parts or member.is_absolute() or ".." in member.parts or ":" in relative or "\\" in relative:
            raise ValueError(f"Invalid CMake output directory: {relative}")
        target = build
        for part in member.parts:
            target /= part
            if target.is_symlink() or target.is_junction():
                raise ValueError(f"Linked CMake output directory: {target}")
        target = target.resolve()
        if target == build or not target.is_relative_to(build):
            raise ValueError(f"CMake output directory escapes binary directory: {relative}")
        paths[key] = target
    return paths
