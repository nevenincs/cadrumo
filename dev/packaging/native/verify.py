"""Dispatch platform acceptance against an assembled package."""

from __future__ import annotations

import argparse
from pathlib import Path

from .layout import backend, load_layout


def verify(
    package: Path,
    *,
    target: str,
    destination: Path | None = None,
    product: bool = False,
    build_root: Path | None = None,
) -> None:
    """Run the selected platform's native-loader and relocation acceptance."""
    backend(load_layout(target)).verify(package, destination=destination, product=product, build_root=build_root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--product", action="store_true")
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    verify(args.package, target=args.target, destination=args.destination, product=args.product)
