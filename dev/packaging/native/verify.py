"""Dispatch platform acceptance against an assembled package."""

from __future__ import annotations

import argparse
from pathlib import Path

from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .layout import backend, load_layout
from .verification_paths import verification_destination


def verify(
    package: Path,
    *,
    target: str,
    destination: Path | None = None,
    product: bool = False,
    build_root: Path | None = None,
    already_relocated: bool = False,
) -> None:
    """Run the selected platform's native-loader and relocation acceptance."""
    if already_relocated:
        if build_root is None or destination is not None:
            raise ValueError("Already relocated verification needs its owning output root without a destination")
        output_root = build_root
        contract = load_layout(target)
    else:
        if build_root is None:
            raise ValueError("Native package verification requires its owning CMake build directory")
        paths = build_paths(build_root)
        output_root = paths["verification"]
        output_root.mkdir(parents=True, exist_ok=True)
        destination = verification_destination(destination, output_root)
        contract = load_layout(target)
        if contract["backend"] != "windows":
            destination.mkdir(parents=True)
    backend(contract).verify(
        package,
        destination=destination,
        product=product,
        build_root=output_root,
        already_relocated=already_relocated,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--product", action="store_true")
    parser.add_argument("--target", required=True)
    parser.add_argument(
        "--build", type=require_enrolled_build, required=True, help="The owning CMake binary directory."
    )
    args = parser.parse_args()
    verify(
        args.package,
        target=args.target,
        destination=args.destination,
        product=args.product,
        build_root=args.build,
    )
