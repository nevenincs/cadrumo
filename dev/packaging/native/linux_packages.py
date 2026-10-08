"""Gate and inspect current Linux manager packages without installing them."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Literal

from ..command_execution import run_command
from .build_paths import build_paths
from .hashing import digest
from .identity import DistributionIdentity
from .installation import member, verify_inventory
from .linux_desktop_runtime import validate_payload as validate_desktop_payload
from .linux_desktop_runtime import verify_requirements

PackageFormat = Literal["deb", "rpm"]
MAINTENANCE_GATE = (
    "CADRUMO Linux installation is disabled: version ownership, publication, scope admission, "
    "in-use removal and native login acceptance remain unverified."
)
PREINSTALL = f"#!/bin/sh\nprintf '%s\\n' '{MAINTENANCE_GATE}' >&2\nexit 1\n"


def _identity(path: Path) -> DistributionIdentity:
    value = DistributionIdentity(**json.loads(path.read_text(encoding="utf-8")))
    if not value.target.startswith("linux-"):
        raise ValueError("Linux package inspection requires a Linux identity")
    return value


def author_gates(build: Path, identity_file: Path) -> dict[str, Path]:
    """Create native pre-install script inputs in the CMake-owned metadata directory."""
    _identity(identity_file)
    paths = build_paths(build)
    directory = member(paths["installation_metadata"], "linux-gate")
    directory.mkdir(parents=True, exist_ok=True)
    result = {}
    for name in ("preinst", "rpm-preinstall.sh"):
        path = member(directory, name)
        with NamedTemporaryFile(dir=directory, delete=False) as output:
            output.write(PREINSTALL.encode("utf-8"))
            temporary = Path(output.name)
        try:
            temporary.chmod(0o755)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        result[name] = path
    return result


def _run(tool: Path, arguments: list[str], directory: Path) -> str:
    if not tool.is_absolute() or not tool.is_file():
        raise ValueError("Native package inspector must be an explicit tool path")
    result = run_command([str(tool), *arguments], cwd=directory, timeout_seconds=120)
    if result.returncode:
        raise ValueError(f"Native package inspection failed ({result.returncode}): {result.stderr}")
    if len(result.stdout) > 32 * 1024 * 1024:
        raise ValueError("Native package inventory exceeds its inspection bound")
    return result.stdout


def _path(raw: str) -> str:
    value = raw.removeprefix("./")
    path = PurePosixPath("/" + value.lstrip("/"))
    if ".." in path.parts or "\\" in value or any(ord(char) < 32 for char in value):
        raise ValueError("Native package contains a noncanonical member")
    return str(path)


def deb_files(listing: str) -> set[str]:
    """Read dpkg-deb's native tar listing without extracting any package member."""
    files = set()
    for row in listing.splitlines():
        fields = row.split(maxsplit=5)
        if len(fields) != 6 or fields[0][0] not in {"-", "d"}:
            raise ValueError("DEB payload contains unsupported or malformed ownership")
        if fields[0][0] == "-":
            path = _path(fields[5])
            if path in files:
                raise ValueError("DEB payload owns a file more than once")
            files.add(path)
    return files


def rpm_files(listing: str) -> set[str]:
    """Classify native RPM file modes; symbolic links cannot bypass inventory checks."""
    files = set()
    for row in listing.splitlines():
        mode, separator, name = row.partition(" ")
        if not separator:
            raise ValueError("RPM payload ownership row is malformed")
        kind = int(mode, 8) & 0o170000
        if kind not in {0o100000, 0o40000}:
            raise ValueError("RPM payload contains unsupported ownership")
        if kind == 0o100000:
            path = _path(name)
            if path in files:
                raise ValueError("RPM payload owns a file more than once")
            files.add(path)
    return files


def inspect_artifact(
    build: Path, identity_file: Path, artifact: Path, package_format: PackageFormat, tool: Path
) -> Path:
    """Inspect metadata and file ownership; this does not prove extracted payload bytes."""
    if package_format not in {"deb", "rpm"}:
        raise ValueError("Unsupported Linux package format")
    paths = build_paths(build)
    directory = member(paths["packages"], "linux-inspection")
    directory.mkdir(parents=True, exist_ok=True)
    receipt = member(directory, f"{package_format}.json")
    receipt.unlink(missing_ok=True)
    value = _identity(identity_file)
    stage = paths["installation_stage"]
    verify_inventory(stage, member(paths["installation_metadata"], "installation.json"))
    artifact = member(paths["packages"], artifact.absolute().relative_to(paths["packages"]).as_posix())
    artifact_hash = digest(artifact)

    def run(arguments: list[str]) -> str:
        return _run(tool, arguments, build)

    arch = {"linux-x86-64": ("amd64", "x86_64"), "linux-aarch64": ("arm64", "aarch64")}[value.target]
    if package_format == "deb":
        observed = run(["--show", "--showformat=${Package}\n${Version}\n${Architecture}\n", str(artifact)])
        expected = f"{value.package_name}\n{value.version}\n{arch[0]}\n"
        gate = run(["--info", str(artifact), "preinst"])
        owned = deb_files(run(["--contents", str(artifact)]))
    elif package_format == "rpm":
        observed = run(["-qp", "--queryformat", "%{NAME}\n%{VERSION}\n%{ARCH}\n", str(artifact)])
        expected = f"{value.package_name}\n{value.version}\n{arch[1]}\n"
        gate = run(["-qp", "--queryformat", "%{PREIN}", str(artifact)])
        interpreter = run(["-qp", "--queryformat", "%{PREINPROG}", str(artifact)]).strip()
        if interpreter != "/bin/sh":
            raise ValueError("RPM pre-install gate does not use its declared shell")
        owned = rpm_files(run(["-qp", "--queryformat", "[%{FILEMODES:octal} %{FILENAMES}\n]", str(artifact)]))
    else:
        raise ValueError("Unsupported Linux package format")
    if observed != expected:
        raise ValueError("Native package identity differs from the CMake identity projection")
    if gate.strip() != PREINSTALL.strip():
        raise ValueError("Linux manager package lost its unconditional installation gate")
    desktop_requirements: str | None = None
    for manifest_file in stage.rglob("data/package-manifest.json"):
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if validate_desktop_payload(manifest_file.parent.parent, manifest):
            requirements = (
                run(["--show", "--showformat=${Depends}", str(artifact)])
                if package_format == "deb"
                else run(["-qp", "--requires", str(artifact)])
            )
            verify_requirements(requirements, package_format)
            desktop_requirements = requirements
    expected_files = {"/" + path.relative_to(stage).as_posix() for path in stage.rglob("*") if path.is_file()}
    if owned != expected_files:
        raise ValueError("Native package ownership differs from verified installation staging")
    if digest(artifact) != artifact_hash:
        raise ValueError("Native package changed during inspection")
    receipt.write_text(
        json.dumps(
            {
                "schema": 1,
                "desktop_runtime_dependencies": desktop_requirements,
                "format": package_format,
                "application_id": value.application_id,
                "channel": value.channel,
                "version": value.version,
                "target": value.target,
                "artifact": artifact.name,
                "sha256": artifact_hash,
                "owned_files": sorted(owned),
                "installable": False,
                "payload_bytes_verified": False,
                "blocker": MAINTENANCE_GATE,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return receipt


def main() -> None:
    """Expose native artifact checks to the CMake distribution graph."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("author-gates", "inspect", "check-installation"))
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--format", choices=("deb", "rpm"))
    parser.add_argument("--tool", type=Path)
    arguments = parser.parse_args()
    if arguments.action == "author-gates":
        author_gates(arguments.build, arguments.identity)
    elif arguments.action == "check-installation":
        raise SystemExit(MAINTENANCE_GATE)
    elif arguments.artifact is None or arguments.format is None or arguments.tool is None:
        parser.error("inspect requires --artifact, --format and --tool")
    else:
        inspect_artifact(arguments.build, arguments.identity, arguments.artifact, arguments.format, arguments.tool)


if __name__ == "__main__":
    main()
