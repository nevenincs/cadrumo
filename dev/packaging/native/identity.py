"""Project canonical product metadata into cross-platform distribution identities."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT
from dev.packaging.runtime_wheelhouse_contract import SUPPORTED_TARGETS

PREVIEW_NAME_SUFFIX = " Preview"
"""User-facing suffix that separates the preview installation family from stable."""
MANAGER_NAME_SUFFIX = " Background Services"
"""User-facing suffix that names the per-user runtime manager after the channel's name."""
MANAGER_COMPONENT = "manager"
"""Reverse-DNS component under the channel's application identifier for the runtime manager."""


@dataclass(frozen=True)
class DistributionIdentity:
    """Stable installation family, separated from release and build identities."""

    name: str
    application_id: str
    package_name: str
    publisher: str
    contact: str
    description: str
    homepage: str
    license: str
    version: str
    channel: str
    target: str
    compatibility_floor: str
    upgrade_code: str
    manager_id: str
    manager_name: str


def identity(target: str, channel: str = "stable", *, project_file: Path | None = None) -> DistributionIdentity:
    """Use a version-independent UUIDv5 family; never regenerate it randomly."""
    if channel not in {"stable", "preview"}:
        raise ValueError(f"Unsupported release channel: {channel}")
    platform = next((item for item in SUPPORTED_TARGETS if item.name == target), None)
    if platform is None:
        raise ValueError(f"Unsupported distribution target: {target}")
    project = tomllib.loads((project_file or REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("Native releases require a numeric major.minor.patch version; use the preview channel")
    major, minor, patch = map(int, version.split("."))
    if major > 255 or minor > 255 or patch > 65535:
        raise ValueError("Version exceeds the MSI ProductVersion limits (255.255.65535)")
    suffix = "" if channel == "stable" else f".{channel}"
    app_id = PRODUCT_IDENTITY.application_id + suffix
    author = project["authors"][0]
    name = PRODUCT_IDENTITY.display_name + ("" if channel == "stable" else PREVIEW_NAME_SUFFIX)
    return DistributionIdentity(
        name=name,
        application_id=app_id,
        package_name=PRODUCT_IDENTITY.distribution + ("" if channel == "stable" else f"-{channel}"),
        publisher=author["name"],
        contact=author["email"],
        description=project["description"],
        homepage=project["urls"]["Homepage"],
        license=project["license"],
        version=version,
        channel=channel,
        target=platform.name,
        compatibility_floor=platform.floor,
        upgrade_code=str(uuid5(NAMESPACE_DNS, f"{app_id}/{platform.name}/machine")).upper(),
        manager_id=f"{app_id}.{MANAGER_COMPONENT}",
        manager_name=name + MANAGER_NAME_SUFFIX,
    )


def cmake_projection(value: DistributionIdentity) -> str:
    """Bracket quoting keeps metadata literal, including CMake interpolation syntax."""
    lines = []
    for key, item in asdict(value).items():
        delimiter = "="
        while f"]{delimiter}]" in item:
            delimiter += "="
        lines.append(f"set(CADRUMO_ID_{key.upper()} [{delimiter}[{item}]{delimiter}])")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Emit inspectable JSON and a literal CMake projection for configure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=[item.name for item in SUPPORTED_TARGETS])
    parser.add_argument("--channel", default="stable", choices=("stable", "preview"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = identity(args.target, args.channel)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in {
        "identity.json": json.dumps(asdict(value), indent=2) + "\n",
        "Identity.cmake": cmake_projection(value),
    }.items():
        destination = args.output / name
        if not destination.exists() or destination.read_text(encoding="utf-8") != content:
            destination.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
