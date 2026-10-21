"""Resolve output boundaries independently of platform verification dispatch."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4


def relocated_verification_package(package: Path, build_root: Path) -> Path:
    """Admit only an existing isolated extraction owned beneath the verifier root."""
    root = build_root.resolve(strict=True)
    if not package.is_absolute() or not package.is_dir():
        raise ValueError("Relocated verification requires an existing absolute package directory")
    resolved = package.resolve(strict=True)
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("Relocated verification package must be beneath its owning build root")
    lexical = package.absolute()
    if not lexical.is_relative_to(root):
        raise ValueError("Relocated verification package must not use an aliased path")
    for member in (lexical, *lexical.parents):
        if member == root:
            break
        if member.is_symlink() or member.is_junction():
            raise ValueError("Relocated verification package must not use linked directories")
    return resolved


def verification_destination(
    destination: Path | None,
    build_root: Path,
) -> Path:
    """Resolve a fresh verification root beneath the owning build output directory."""
    root = build_root.resolve(strict=True)
    candidate = destination if destination is not None else root / "verification" / f"package-{uuid4().hex}"
    if not candidate.is_absolute():
        candidate = root / candidate
    lexical = candidate.absolute()
    try:
        relative = lexical.relative_to(root)
    except ValueError as error:
        raise ValueError("Verification destination must be beneath its owning build output directory") from error
    if not relative.parts or candidate.exists():
        raise ValueError("Verification needs a fresh destination beneath its owning build output directory")
    member = root
    for part in relative.parts:
        member = member / part
        if member.is_symlink() or member.is_junction():
            raise ValueError("Verification destination must not use linked directories")
    resolved = candidate.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("Verification destination must be beneath its owning build output directory")
    return resolved
