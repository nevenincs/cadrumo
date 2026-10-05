"""Resolve output boundaries independently of platform verification dispatch."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from dev._paths import REPO_ROOT


def verification_destination(
    destination: Path | None,
    build_root: Path,
    *,
    repository_root: Path = REPO_ROOT,
) -> Path:
    """Resolve a fresh verification root within the declared caller boundaries."""
    candidate = destination or Path("verification") / f"package-{uuid4().hex}"
    if destination is not None and candidate.is_absolute():
        resolved = candidate.resolve()
        if resolved.is_relative_to(repository_root.resolve()) or resolved.exists():
            raise ValueError("An explicit absolute verification destination must be fresh and outside the checkout")
        return resolved
    resolved = (build_root / candidate).resolve()
    root = build_root.resolve()
    if resolved == root or not resolved.is_relative_to(root) or resolved.exists():
        raise ValueError("Verification needs a fresh destination beneath CADRUMO_NATIVE_BUILD_ROOT")
    return resolved
