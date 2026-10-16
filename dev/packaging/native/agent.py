"""Build the private agent wheel and validate its native dependency locks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT

from ..command_execution import run_command
from ..runtime_wheel_selection import active_requirements, marker_environment
from ..runtime_wheelhouse_contract import target_platform
from ..uv_constraints import export_runtime_constraints
from ..wheel_metadata import read_wheel_metadata
from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .build_toolchain import selected_uv
from .hashing import digest
from .product import BUNDLED_EXTRAS, _wheel_input_digest
from .target import uv_platform


def locked_requirements(target: str, python: str, *, lock: Path | None = None) -> dict[str, Requirement]:
    """Refuse unpinned, unhashed or conflicting supplemental dependencies."""
    lock = lock or REPO_ROOT / "native/agent" / f"{target}.txt"
    environment = marker_environment(target_platform(target), python)
    requirements: dict[str, Requirement] = {}
    for row in lock.read_text(encoding="utf-8").replace("\\\n", " ").splitlines():
        row = row.strip()
        if not row or row.startswith("#"):
            continue
        specification, separator, hashes = row.partition(" --hash=")
        requirement = Requirement(specification.strip())
        pins = tuple(requirement.specifier)
        if (
            not separator
            or not re.fullmatch(r"sha256:[0-9a-f]{64}(?:\s+--hash=sha256:[0-9a-f]{64})*", hashes.strip())
            or requirement.url is not None
            or len(pins) != 1
            or pins[0].operator != "=="
            or "*" in pins[0].version
        ):
            raise ValueError(f"Agent dependency must have one exact version and SHA-256 hashes: {specification}")
        if requirement.marker is not None and not requirement.marker.evaluate(environment):
            continue
        name = canonicalize_name(requirement.name)
        if name in requirements:
            raise ValueError(f"Duplicate agent dependency: {name}")
        requirements[name] = requirement
    if not requirements:
        raise ValueError("Agent dependency lock is empty")
    base = active_requirements(REPO_ROOT, target_platform(target), python, extras=BUNDLED_EXTRAS)
    for name in requirements.keys() & base.keys():
        if str(requirements[name].specifier) != str(base[name].specifier):
            raise ValueError(f"Agent dependency conflicts with Cadrumo's lock: {name}")
    return requirements


def build_agent(output: Path, source: Path, uv: str) -> None:
    """Build the configured local project through the native CMake action."""
    source = source.resolve(strict=True)
    project = parse_toml((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if canonicalize_name(project["name"]) != "cadrumo-agent":
        raise ValueError("Configured agent directory must contain cadrumo-agent")
    output.mkdir(parents=True, exist_ok=True)
    wheels = output / "wheels"
    inputs = _wheel_input_digest(source, toolchain={"python": sys.version, "uv": uv})
    input_receipt = output / "agent-inputs.json"
    try:
        prior = json.loads(input_receipt.read_text(encoding="utf-8"))
        if prior == inputs:
            agent_wheel(output)
            return
    except (OSError, ValueError, KeyError):
        pass
    result = run_command(
        [
            uv,
            "build",
            "--python",
            sys.executable,
            "--no-build-isolation",
            "--no-sources",
            "--wheel",
            "--out-dir",
            str(wheels),
            str(source),
        ],
        cwd=REPO_ROOT,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    artifacts = [wheel for wheel in wheels.glob("*.whl") if read_wheel_metadata(wheel)["Version"] == project["version"]]
    if len(artifacts) != 1:
        raise ValueError("Agent build must produce exactly one wheel")
    metadata = read_wheel_metadata(artifacts[0])
    if metadata["Name"] != "cadrumo-agent" or metadata["Version"] != project["version"]:
        raise ValueError("Agent wheel metadata differs from the configured project")
    (output / "agent-wheel.json").write_text(
        json.dumps(
            dict(
                source=str(source),
                version=metadata["Version"],
                wheel=artifacts[0].name,
                wheel_sha256=digest(artifacts[0]),
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for wheel in wheels.glob("*.whl"):
        if wheel != artifacts[0]:
            wheel.unlink()
    input_receipt.write_text(json.dumps(inputs) + "\n", encoding="utf-8")


def agent_wheel(output: Path) -> Path:
    """Verify the built wheel against its recorded artifact checksum."""
    record = json.loads((output / "agent-wheel.json").read_text(encoding="utf-8"))
    name = record["wheel"]
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".whl"):
        raise ValueError("Invalid agent wheel path")
    name = str(name)
    wheel = output / "wheels" / name
    if digest(wheel) != record["wheel_sha256"]:
        raise ValueError("Agent wheel checksum mismatch")
    return wheel


def validate_wheel_dependencies(wheel: Path, target: str, python: str) -> None:
    """Check the actual wheel's active requirements against the native lock."""
    requirements = locked_requirements(target, python)
    environment = marker_environment(target_platform(target), python)
    for value in read_wheel_metadata(wheel).get_all("Requires-Dist", []):
        requirement = Requirement(value)
        if requirement.marker is None or requirement.marker.evaluate(environment):
            locked = requirements.get(canonicalize_name(requirement.name))
            if locked is None or next(iter(locked.specifier)).version not in requirement.specifier:
                raise ValueError(f"Agent wheel dependency differs from native lock: {requirement.name}")


def update_lock(build: Path, target: str) -> None:
    """Resolve a candidate supplemental lock inside the build for author review."""
    target_platform(target)
    paths = build_paths(build)
    receipt = json.loads((paths["agent"] / "agent-wheel.json").read_text(encoding="utf-8"))
    source = Path(receipt["source"])
    requirements = parse_toml((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    work = paths["testing"] / "agent-lock" / target
    work.mkdir(parents=True, exist_ok=True)
    inputs = work / "requirements.in"
    inputs.write_text("\n".join(requirements) + "\n", encoding="utf-8")
    constraints = work / "constraints.txt"
    constraints.write_text(
        "\n".join(export_runtime_constraints(repo_root=REPO_ROOT, extras=BUNDLED_EXTRAS)) + "\n", encoding="utf-8"
    )
    configured = json.loads((paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8"))
    pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    lock = work / "requirements.txt"
    result = run_command(
        [
            selected_uv(configured),
            "pip",
            "compile",
            str(inputs),
            "--constraint",
            str(constraints),
            "--python-version",
            pin,
            "--python-platform",
            uv_platform(target),
            "--only-binary",
            ":all:",
            "--generate-hashes",
            "--no-header",
            "--no-annotate",
            "--output-file",
            str(lock),
        ],
        cwd=REPO_ROOT,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    locked_requirements(target, pin, lock=lock)
    print(f"Candidate agent dependency lock: {lock}; review before updating native/agent/{target}.txt")


def main() -> None:
    """Run explicit lock maintenance or checksum admission from CMake."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("lock", "checksum"))
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    parser.add_argument("--target")
    arguments = parser.parse_args()
    if arguments.action == "lock":
        if arguments.target is None:
            parser.error("lock requires --target")
        update_lock(arguments.build, arguments.target)
    else:
        agent_wheel(build_paths(arguments.build)["agent"])


if __name__ == "__main__":
    main()
