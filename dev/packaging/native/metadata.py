"""Generate native build identity and Windows resources from canonical inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT

from .build_directory import require_enrolled_output
from .build_stamp import BuildStamp, display_version, load_identity
from .identity import identity
from .layout import backend, bundled_images, distribution_target, load_layout
from .stable_output import write_text


def generate(
    destination: Path,
    stamp: BuildStamp,
    tools: Path,
    channel: str = "stable",
    *,
    target: str | None = None,
    identity_destination: Path | None = None,
) -> None:
    """Project identity, the interpreter hosts' build identity, the favicon and package filenames into resources.

    ``stamp`` is the identity of the interpreter component: the hosts, console entrypoints,
    bundled images and CPython bridge compiled from these outputs. The package's own identity
    belongs to staging, so ``build.json`` here records only the interpreter's, which the staged
    record repeats for the bootstrap's mixed-build check.

    Outputs that carry no build identity (``build_layout.h``, the icon and the process
    manifests) go to ``destination``. Those that do (``build_metadata.h``, the version
    resources and ``build.json``) go to ``identity_destination``, one directory per CMake
    configuration, so Debug and Release built from different sources never share one; both
    display versions are written and each image selects its own through ``CADRUMO_BUILD_DEBUG``.
    """
    identity_destination = destination if identity_destination is None else identity_destination
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
    identity_destination.mkdir(parents=True, exist_ok=True)
    metadata = {
        "product": product.name,
        "version": version,
        "python": python,
        "layout_abi": layout["abi"],
        "application_id": product.application_id,
        "publisher": product.publisher,
        "channel": product.channel,
        "target": product.target,
        "compatibility_floor": product.compatibility_floor,
        "interpreter": {
            "build_id": stamp.build_id,
            "build_sequence": stamp.build_sequence,
            "build_number": stamp.build_sequence,
            "build_date": stamp.build_date,
        },
    }
    write_text(identity_destination / "build.json", json.dumps(metadata, indent=2))
    layout_values = {
        "VERSION": version,
        "EXECUTABLE": layout["paths"]["executable"],
        **{name.upper(): value for name, value in layout["files"].items()},
    }
    write_text(destination / LAYOUT_HEADER, _header(layout_values))
    write_text(identity_destination / "build_metadata.h", identity_header(version, stamp))
    images = {**layout["entrypoints"], **{name: entry["description"] for name, entry in bundled_images(layout).items()}}
    backend(layout).resources(identity_destination, version, stamp, tools, images, product, shared=destination)


LAYOUT_HEADER = "build_layout.h"
"""The package layout and product version the C hosts compile in, identical for every build."""


def _header(values: dict[str, str]) -> str:
    return "\n".join(f"#define CADRUMO_{name} {json.dumps(value)}" for name, value in values.items()) + "\n"


def identity_header(version: str, stamp: BuildStamp) -> str:
    """Return ``build_metadata.h``: one image's build identity over the shared layout header."""
    values = {
        "BUILD_ID": stamp.build_id,
        "BUILD_SEQUENCE": str(stamp.build_sequence),
        "BUILD_NUMBER": str(stamp.build_sequence),
        "BUILD_DATE": stamp.build_date,
        "DISPLAY_VERSION_RELEASE": display_version(version, stamp.build_id, "release"),
        "DISPLAY_VERSION_DEBUG": display_version(version, stamp.build_id, "debug"),
    }
    return f'#include "{LAYOUT_HEADER}"\n' + _header(values) + _BUILD_TYPE_SELECTION


# Each configuration has its own header, which still lets the compiler name the build type.
_BUILD_TYPE_SELECTION = """#ifndef CADRUMO_BUILD_DEBUG
#error "Define CADRUMO_BUILD_DEBUG to 1 for a Debug build and 0 otherwise"
#endif
#if CADRUMO_BUILD_DEBUG
#define CADRUMO_BUILD_TYPE "debug"
#define CADRUMO_DISPLAY_VERSION CADRUMO_DISPLAY_VERSION_DEBUG
#else
#define CADRUMO_BUILD_TYPE "release"
#define CADRUMO_DISPLAY_VERSION CADRUMO_DISPLAY_VERSION_RELEASE
#endif
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=require_enrolled_output)
    parser.add_argument("--identity", type=Path, required=True, help="the interpreter component's published identity")
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--channel", choices=("stable", "preview"), default="stable")
    parser.add_argument("--target")
    parser.add_argument(
        "--identity-destination", type=require_enrolled_output, help="the configuration's identity output directory"
    )
    args = parser.parse_args()
    generate(
        args.destination,
        load_identity(args.identity, "interpreter").stamp,
        args.tools,
        args.channel,
        target=args.target,
        identity_destination=args.identity_destination,
    )
