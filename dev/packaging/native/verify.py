"""Dispatch platform acceptance against an assembled package."""

from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

from dev._paths import REPO_ROOT

from .layout import backend, load_layout


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


def verify(
    package: Path, *, destination: Path | None = None, product: bool = False, build_root: Path | None = None
) -> None:
    """Run the selected platform's native-loader and relocation acceptance."""
    backend(load_layout()).verify(package, destination=destination, product=product, build_root=build_root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--product", action="store_true")
    args = parser.parse_args()
    verify(args.package, destination=args.destination, product=args.product)
