"""Filesystem inventory and copy-paste observations for authored native code."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .duplication import DuplicationOutcome, DuplicationResult, run_duplication_scan


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


def scan(repo_root: Path, scope: LanguageScope, files: tuple[Path, ...]) -> DuplicationResult:
    """Reject scanner evidence that cannot belong to the inventoried population."""
    result = run_duplication_scan(
        repo_root,
        source_roots=(scope.root,),
        format_name=scope.format_name,
        ignore=_IGNORE,
    )
    if result.outcome is not DuplicationOutcome.UNAVAILABLE and result.files_analyzed > len(files):
        return DuplicationResult.unavailable(
            f"{scope.name} inventory has {len(files)} files but jscpd analysed {result.files_analyzed}"
        )
    return result
