"""Filesystem inventory and copy-paste observations for authored native code."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT

from .duplication import DuplicationResult, run_duplication_scan


@dataclass(frozen=True)
class LanguageScope:
    """One source population and its jscpd parser."""

    name: str
    root: Path
    suffixes: tuple[str, ...]
    format_name: str


SCOPES: Final = (
    LanguageScope("typescript", Path("native/desktop/frontend"), (".ts",), "typescript"),
    LanguageScope("typescript-tsx", Path("native/desktop/frontend"), (".ts", ".tsx"), "tsx"),
    LanguageScope("css", Path("native/desktop/frontend"), (".css",), "css"),
    LanguageScope("rust", Path("native"), (".rs",), "rust"),
)
EXCLUDED_DIRECTORIES: Final = frozenset({"node_modules", "target", "dist", "build", "generated", ".git"})
_IGNORE: Final = ",".join(f"**/{name}/**" for name in sorted(EXCLUDED_DIRECTORIES))
_GENERATED_HEADER: Final = re.compile(
    r"^\s*(?://[/!]?|#|/\*+|\*)\s*(?:@generated\b|generated (?:by|from)\b|"
    r"this file is generated\b|do not edit\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InventoryEntry:
    """An observed source file and its role in the inspected tree."""

    path: Path
    role: str


def inventory(repo_root: Path, scope: LanguageScope) -> tuple[Path, ...]:
    """List source paths without following links or depending on checkout history."""
    root = repo_root / scope.root
    if not root.is_dir() or root.is_symlink():
        raise OSError(f"source root unavailable: {root}")

    def fail(error: OSError) -> None:
        raise error

    files: list[Path] = []
    for directory, names, filenames in os.walk(root, onerror=fail, followlinks=False):
        parent = Path(directory)
        names[:] = [name for name in names if name not in EXCLUDED_DIRECTORIES]
        for name in names:
            if (parent / name).is_symlink():
                raise OSError(f"source directory is a link: {parent / name}")
        for name in filenames:
            path = parent / name
            if path.suffix in scope.suffixes:
                if path.is_symlink():
                    raise OSError(f"source file is a link: {path}")
                files.append(path.relative_to(repo_root))
    if not files:
        raise OSError(f"no {scope.name} files in {scope.root}")
    return tuple(sorted(files))


def scan(repo_root: Path, scope: LanguageScope) -> DuplicationResult:
    """Measure token clones; aggregate counts alone cannot establish file identity."""
    return run_duplication_scan(
        repo_root,
        source_roots=(scope.root,),
        format_name=scope.format_name,
        ignore=_IGNORE,
    )


def classify(repo_root: Path, path: Path) -> InventoryEntry:
    """Classify an inventoried source by its owner and an explicit generated marker."""
    with (repo_root / path).open(encoding="utf-8") as source:
        generated = False
        for line in islice(source, 12):
            stripped = line.lstrip()
            if stripped and not stripped.startswith(("//", "#", "/*", "*")):
                break
            generated |= _GENERATED_HEADER.search(line) is not None
    parts = path.parts
    name = path.name.casefold()
    if "vendor" in parts or "vendored" in parts:
        role = "vendored"
    elif generated:
        role = "generated"
    elif any(part in {"fixtures", "fixture", "testdata", "_data"} for part in parts):
        role = "data"
    elif (
        any(part in {"tests", "test", "benches"} for part in parts)
        or name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", "_test.rs", "_tests.rs"))
        or (name.startswith("test_") and name.endswith(".rs"))
        or name == "tests.rs"
    ):
        role = "test"
    elif "dev" in parts or ".storybook" in parts or name.endswith(".stories.tsx") or name == "build.rs":
        role = "tooling"
    elif "src" in parts:
        role = "runtime"
    else:
        role = "tooling"
    return InventoryEntry(path, role)


def census(repo_root: Path) -> tuple[InventoryEntry, ...]:
    """List every admitted TS, TSX, CSS and Rust file exactly once."""
    scopes = (SCOPES[1], SCOPES[2], SCOPES[3])
    files = {path for scope in scopes for path in inventory(repo_root, scope)}
    return tuple(classify(repo_root, path) for path in sorted(files))


def main() -> int:
    """Print a reproducible filesystem census without writing an artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        entries = census(REPO_ROOT)
    except (OSError, UnicodeError) as error:
        print(f"native inventory unavailable: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "schema": 1,
                "roots": ["native/desktop/frontend", "native"],
                "excluded_directories": sorted(EXCLUDED_DIRECTORIES),
                "roles": dict(sorted(Counter(entry.role for entry in entries).items())),
                "files": [{"path": entry.path.as_posix(), "role": entry.role} for entry in entries],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
