"""Bounded cleanup of named CMake artifact classes; never remove source or install prefixes."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from dev._paths import REPO_ROOT

GROUPS = {
    "stage": ("stage", "verification", "testing"),
    "packages": ("packages", "_CPack_Packages"),
    "dependencies": ("_deps", "product"),
    "native": ("bin", "lib", "symbols", "cargo", "generated"),
}


def clean(build: Path, group: str) -> None:
    """Delete only selected generated children of an identified native CMake build."""
    build = build.resolve(strict=True)
    cache = build / "CMakeCache.txt"
    if build == REPO_ROOT or not cache.is_file():
        raise ValueError("Cleanup requires an existing out-of-source CMake binary directory")
    owner = f"CMAKE_HOME_DIRECTORY:INTERNAL={REPO_ROOT.as_posix()}"
    if owner not in cache.read_text(encoding="utf-8"):
        raise ValueError("Build directory belongs to another project")
    groups = GROUPS.values() if group == "all" else (GROUPS[group],)
    for paths in groups:
        for relative in paths:
            target = (build / relative).resolve()
            if target == build or not target.is_relative_to(build):
                raise ValueError(f"Cleanup target escapes the binary directory: {relative}")
            if target.exists():
                shutil.rmtree(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("group", choices=(*GROUPS, "all"))
    args = parser.parse_args()
    clean(args.build, args.group)
