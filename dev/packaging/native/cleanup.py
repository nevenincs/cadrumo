"""Bounded cleanup of named CMake artifact classes; never remove source or install prefixes."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from dev._paths import REPO_ROOT

from .build_paths import build_paths


def clean(build: Path, group: str) -> None:
    """Delete only selected generated children of an identified native CMake build."""
    build = build.resolve(strict=True)
    cache = build / "CMakeCache.txt"
    if build == REPO_ROOT or not cache.is_file():
        raise ValueError("Cleanup requires an existing out-of-source CMake binary directory")
    owner = f"CMAKE_HOME_DIRECTORY:INTERNAL={REPO_ROOT.as_posix()}"
    if owner not in cache.read_text(encoding="utf-8"):
        raise ValueError("Build directory belongs to another project")
    paths = build_paths(build)
    definitions = json.loads((build / "build-paths.json").read_text(encoding="utf-8"))["cleanup"]
    groups = definitions.values() if group == "all" else (definitions[group],)
    targets = [paths[key] for keys in groups for key in keys]
    for target in targets:
        if target.exists():
            shutil.rmtree(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("group", help="CMake-defined cleanup group or all")
    args = parser.parse_args()
    clean(args.build, args.group)
