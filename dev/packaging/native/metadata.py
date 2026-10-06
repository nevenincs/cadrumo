"""Generate native build identity and Windows resources from canonical inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT

from .identity import identity
from .layout import backend, distribution_target, load_layout


def generate(
    destination: Path, number: int, date: str, tools: Path, channel: str = "stable", *, target: str | None = None
) -> None:
    """Project identity, the existing favicon, and package filenames into resources."""
    version = parse_toml((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    python = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    configured_identity = destination / "identity.json"
    if target is None and configured_identity.is_file():
        configured_target = json.loads(configured_identity.read_text(encoding="utf-8"))["target"]
        if not isinstance(configured_target, str):
            raise ValueError("Configured target must be a string")
        target = configured_target
    layout = load_layout(target)
    product = identity(distribution_target(layout), channel)
    destination.mkdir(parents=True, exist_ok=True)
    metadata = {
        "product": PRODUCT_IDENTITY.display_name,
        "version": version,
        "build_number": number,
        "build_date": date,
        "python": python,
        "layout_abi": layout["abi"],
        "application_id": product.application_id,
        "publisher": product.publisher,
        "channel": product.channel,
        "target": product.target,
        "compatibility_floor": product.compatibility_floor,
    }
    (destination / "build.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    values = {
        "VERSION": version,
        "BUILD_NUMBER": str(number),
        "BUILD_DATE": date,
        "EXECUTABLE": layout["paths"]["executable"],
        **{name.upper(): value for name, value in layout["files"].items()},
    }
    header = "\n".join(f"#define CADRUMO_{name} {json.dumps(value)}" for name, value in values.items())
    (destination / "build_metadata.h").write_text(header + "\n", encoding="utf-8")
    backend(layout).resources(destination, version, number, date, tools, layout["entrypoints"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--number", type=int, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--channel", choices=("stable", "preview"), default="stable")
    parser.add_argument("--target")
    args = parser.parse_args()
    generate(args.destination, args.number, args.date, args.tools, args.channel, target=args.target)
