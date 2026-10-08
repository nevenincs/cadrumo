"""Stable source, candidate, and publication fingerprints for collapse verification."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from dev._paths import REPO_ROOT
from dev.packaging.authority_staging import authoring_authority_root

from .registry_collapse_models import FingerprintEntry


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint_tree(root: Path) -> tuple[FingerprintEntry, ...]:
    """Fingerprint every file beneath ``root`` in deterministic path order."""
    resolved = root.resolve(strict=True)
    return tuple(
        FingerprintEntry(path.relative_to(resolved).as_posix(), _sha256(path), path.stat().st_size)
        for path in sorted(item for item in resolved.rglob("*") if item.is_file())
    )


def fingerprint_optional_tree(root: Path) -> tuple[FingerprintEntry, ...]:
    """Fingerprint ``root`` when it exists; an unpublished checkout has no tree.

    A missing directory is a legitimate state for source repair, and it still
    detects mutation: a verifier run that creates the tree changes the result.
    """
    return fingerprint_tree(root) if root.exists() else ()


def published_authority_root(authority_root: Path | None = None) -> Path:
    """Return the published authority a verification run must leave untouched.

    The authority is generated output kept outside the packaged source tree, so
    the default is the working tree's own publication rather than any path
    under the registry source root.
    """
    return (authority_root if authority_root is not None else authoring_authority_root(REPO_ROOT)).resolve()


def fingerprint_paths(paths: Iterable[Path], *, relative_to: Path) -> tuple[FingerprintEntry, ...]:
    """Fingerprint explicit files, retaining a stable repository-relative identity."""
    root = relative_to.resolve(strict=True)
    return tuple(
        FingerprintEntry(path.resolve(strict=True).relative_to(root).as_posix(), _sha256(path), path.stat().st_size)
        for path in sorted({item.resolve(strict=True) for item in paths})
    )


def fingerprint_digest(entries: Iterable[FingerprintEntry]) -> str:
    """Return one digest that commits to file names, sizes, and contents."""
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry.path.encode())
        digest.update(b"\0")
        digest.update(str(entry.bytes).encode())
        digest.update(b"\0")
        digest.update(entry.sha256.encode())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _file_change_count(before: tuple[FingerprintEntry, ...], after: tuple[FingerprintEntry, ...]) -> int:
    left = {item.path: item.sha256 for item in before}
    right = {item.path: item.sha256 for item in after}
    return sum(left.get(path) != right.get(path) for path in set(left) | set(right))
