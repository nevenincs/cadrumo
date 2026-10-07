"""Bounded cleanup of named CMake artifact classes; never remove source or install prefixes."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from dev._paths import REPO_ROOT

from .build_paths import build_paths


def _build_directory(build: Path, source: Path) -> Path:
    build = build.resolve(strict=True)
    source = source.resolve(strict=True)
    cache = build / "CMakeCache.txt"
    if build == source or source.is_relative_to(build) or not cache.is_file():
        raise ValueError("Cleanup requires an existing out-of-source CMake binary directory")
    owner = f"CMAKE_HOME_DIRECTORY:INTERNAL={source.as_posix()}"
    if owner not in cache.read_text(encoding="utf-8").splitlines():
        raise ValueError("Build directory belongs to another project")
    return build


def _bounded_path(build: Path, value: str) -> Path:
    target = Path(value)
    if not target.is_absolute():
        target = build / target
    if ".." in target.parts or target == build or not target.is_relative_to(build):
        raise ValueError(f"Cleanup path escapes binary directory: {value}")
    current = build
    for part in target.relative_to(build).parts:
        current /= part
        if current.is_symlink() or current.is_junction():
            raise ValueError(f"Linked cleanup path: {current}")
    return target


def _remove(build: Path, values: list[str]) -> None:
    # Validate the complete request before making any filesystem changes.
    targets = [_bounded_path(build, value) for value in values]
    for target in targets:
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def clean_target(build: Path, target: str, config: str) -> None:
    """Remove only the configured outputs owned by one target and enrolled children."""
    if any(character in config for character in ("/", "\\", ":")) or config in {".", ".."}:
        raise ValueError("Invalid cleanup configuration")
    document = json.loads((build / f"cleanup-{config}.json").read_text(encoding="utf-8"))
    build = _build_directory(build, Path(document["source"]))
    definitions = document["targets"]
    visited: set[str] = set()
    paths: list[str] = []

    def collect(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        definition = definitions[name]
        paths.extend(definition["paths"])
        for dependency in definition["depends"]:
            collect(dependency)

    collect(target)
    _remove(build, paths)


def clean(build: Path, group: str) -> None:
    """Delete only selected generated children of an identified native CMake build."""
    document = json.loads((build / "build-paths.json").read_text(encoding="utf-8"))
    build = _build_directory(build, Path(document.get("source", REPO_ROOT)))
    paths = build_paths(build)
    definitions = json.loads((build / "build-paths.json").read_text(encoding="utf-8"))["cleanup"]
    groups = definitions.values() if group == "all" else (definitions[group],)
    targets = [paths[key] for keys in groups for key in keys]
    if group == "all":
        # Explicit clean-all also works with generators that do not implement
        # ADDITIONAL_CLEAN_FILES, and covers every configured build configuration.
        for manifest in sorted(build.glob("cleanup-*.json")):
            ownership = json.loads(manifest.read_text(encoding="utf-8"))
            _build_directory(build, Path(ownership["source"]))
            targets.extend(Path(path) for target in ownership["targets"].values() for path in target["paths"])
    _remove(build, [str(target) for target in targets])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("group", help="CMake-defined cleanup group or all")
    parser.add_argument("--target", action="store_true", help="Clean an individual enrolled target")
    parser.add_argument("--config", default="", help="CMake build configuration")
    args = parser.parse_args()
    if args.target:
        clean_target(args.build, args.group, args.config)
    else:
        clean(args.build, args.group)
