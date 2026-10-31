"""Build the existing Python product wheels in a stable native-build snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from contextlib import nullcontext
from email.message import Message
from importlib.metadata import version
from pathlib import Path
from typing import cast

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.toml import parse_toml
from dev._paths import AUTHORITY_ROOT_ENV, REPO_ROOT

from ..authority_staging import selected_published_authority
from ..command_execution import run_command
from ..google_oauth import GOOGLE_OAUTH_ENV, build_client_json
from ..wheel_metadata import installed_wheel_matches, read_wheel_metadata
from .build_directory import require_enrolled_output
from .build_log import BuildLog, display_path
from .build_timing import BuildTimings
from .build_toolchain import selected_uv
from .hashing import digest, digest_cache
from .product_hatch_types import HatchWheelBuilder
from .product_snapshot import capture_product_source_snapshot
from .target import uv_environment, uv_platform

BUNDLED_EXTRAS: tuple[str, ...] = ("browser",)
"""Optional extras the native application ships with its core closure.

The application serves the AEAT browser sessions, which refuse without
``browser``. Playwright's Node driver ships with it; the Chromium builds are
provisioned into profile storage on demand. The wheel's core install stays
without the extra.
"""


def _include_hook_metadata(hook_path: Path, directory: Path, metadata: dict[str, str]) -> None:
    if hook_path.is_file():
        metadata[hook_path.relative_to(directory).as_posix()] = digest(hook_path)


def _wheel_input_digest(directory: Path, *, toolchain: Mapping[str, object] | None) -> str:
    """Name the actual Hatch selection, including hook-owned payloads and metadata."""
    from hatchling.builders.wheel import WheelBuilder

    builder = cast(HatchWheelBuilder, WheelBuilder(str(directory)))
    data = builder.get_default_build_data()
    builder.set_build_data_defaults(data)
    hooks = list(builder.get_build_hooks(str(directory.parent)).values())
    try:
        for hook in hooks:
            hook.initialize("standard", data)
        with builder.config.set_build_data(data):
            members = sorted(
                (item.distribution_path, digest(Path(item.path))) for item in builder.recurse_included_files()
            )
        # Metadata and hook implementations affect the archive even when they
        # aren't themselves selected as wheel members.
        metadata_paths = {directory / "pyproject.toml"}
        if bool(builder.metadata.core.readme_path):
            metadata_paths.add(directory / builder.metadata.core.readme_path)
        for pattern in builder.metadata.core.license_files:
            metadata_paths.update(path for path in directory.glob(pattern) if path.is_file())
        metadata = {path.relative_to(directory).as_posix(): digest(path) for path in metadata_paths}
        for hook in hooks:
            hook_path = directory / hook.config.get("path", "hatch_build.py")
            _include_hook_metadata(hook_path, directory, metadata)
        configuration = dict(members=members, metadata=metadata, backend=version("hatchling"), toolchain=toolchain)
        return hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    finally:
        for hook in hooks:
            hook.finalize("standard", data, "")


def _validate_authority_destination(destination: Path) -> None:
    if destination.is_symlink() or destination.is_junction():
        raise ValueError("Product authority snapshot cannot be linked")
    destination.mkdir(parents=True, exist_ok=True)
    for member in destination.iterdir():
        if member.is_symlink() or member.is_junction() or not member.is_file():
            raise ValueError("Product authority snapshot must contain only regular files")


def _capture_authority(
    root: Path,
    source: Path,
    destination: Path,
    originals: tuple[Path, ...],
    expected: dict[str, str],
    changed: list[Path],
) -> None:
    with tempfile.TemporaryDirectory(prefix=".authority-capture-", dir=source) as temporary:
        candidate = Path(temporary)
        for original in changed:
            shutil.copy2(original, candidate / original.name)
            if digest(candidate / original.name) != expected[original.name]:
                raise RuntimeError("Published authority changed during product snapshot capture")
        if tuple(path.name for path in selected_published_authority(root)) != tuple(
            path.name for path in originals
        ) or any(digest(path) != expected[path.name] for path in originals):
            raise RuntimeError("Published authority changed during product snapshot capture")
        # Content-addressed databases enter first; the descriptor then selects
        # their complete bytes atomically. Failed capture never touches the pair.
        for original in sorted(changed, key=lambda path: path.name == "authority.current.json"):
            (candidate / original.name).replace(destination / original.name)


def _stage_product_authority(root: Path, source: Path) -> None:
    """Capture the selected pair before publication and retire old snapshot generations."""
    originals = selected_published_authority(root)
    expected = {path.name: digest(path) for path in originals}
    destination = source / ".authority"
    _validate_authority_destination(destination)
    changed = [
        path
        for path in originals
        if not (destination / path.name).is_file() or digest(destination / path.name) != expected[path.name]
    ]
    _capture_authority(root, source, destination, originals, expected, changed)
    for member in destination.iterdir():
        if member.name not in expected:
            member.unlink()


def _require_host_python(python: Path) -> str:
    pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    observed = run_command(
        [str(python), "-I", "-c", "import platform; print(platform.python_version())"], cwd=REPO_ROOT
    )
    actual = tuple(int(part) for part in observed.stdout.strip().split(".")) if not observed.returncode else ()
    minimum = tuple(int(part) for part in pin.split("."))
    if actual[:2] != minimum[:2] or actual < minimum:
        raise ValueError(
            f"Product construction requires host CPython {minimum[0]}.{minimum[1]} >= {pin}: {observed.stdout.strip()}"
        )
    return pin


def _wheel_identity(
    directory: Path, source: Path, python: Path, uv: str, build_toolchain: Mapping[str, object] | None
) -> str:
    prior_authority = os.environ.get(AUTHORITY_ROOT_ENV)
    os.environ[AUTHORITY_ROOT_ENV] = str(source / ".authority")
    try:
        identity = _wheel_input_digest(
            directory,
            toolchain={
                "python": digest(python),
                "python_version": sys.version,
                "uv": cast(Mapping[str, object], build_toolchain["builder_files"])["CADRUMO_UV"]
                if build_toolchain is not None
                else {"path": uv, "sha256": digest(Path(uv))},
            },
        )
    finally:
        if prior_authority is None:
            os.environ.pop(AUTHORITY_ROOT_ENV, None)
        else:
            os.environ[AUTHORITY_ROOT_ENV] = prior_authority
    return identity


def _reusable_wheel_receipt(prior: object, wheels: Path, identity: str) -> dict[str, object] | None:
    if not isinstance(prior, dict):
        return None
    record = cast(dict[str, object], prior)
    artifact = wheels / str(record.get("wheel", ""))
    if (
        record.get("inputs") == identity
        and artifact.is_file()
        and artifact.parent == wheels
        and digest(artifact) == record.get("sha256")
    ):
        return record
    return None


def _build_wheels(
    source: Path,
    python: Path,
    uv: str,
    wheels: Path,
    projects: list[Path],
    receipts: dict[str, object],
    expected_version: str,
    environment: dict[str, str],
    build_toolchain: Mapping[str, object] | None,
    timings: BuildTimings | None,
) -> dict[str, dict[str, object]]:
    current_receipts: dict[str, dict[str, object]] = {}
    for directory in projects:
        name = cast(str, parse_toml((directory / "pyproject.toml").read_text(encoding="utf-8"))["project"]["name"])
        identity = _wheel_identity(directory, source, python, uv, build_toolchain)
        prior = _reusable_wheel_receipt(receipts.get(name, {}), wheels, identity)
        if prior is not None:
            current_receipts[name] = prior
            continue
        with timings.phase(f"wheel-build-{directory.name}") if timings is not None else nullcontext():
            result = run_command(
                [
                    uv,
                    "build",
                    "--wheel",
                    "--no-build-isolation",
                    "--no-sources",
                    "--python",
                    str(python),
                    "--project",
                    str(directory),
                    "--out-dir",
                    str(wheels),
                ],
                cwd=REPO_ROOT,
                environment=environment,
            )
            if result.returncode:
                raise RuntimeError(result.stderr)
        matches = [wheel for wheel in wheels.glob("*.whl") if read_wheel_metadata(wheel)["Name"] == name]
        matches = [wheel for wheel in matches if read_wheel_metadata(wheel)["Version"] == expected_version]
        if len(matches) != 1:
            raise ValueError(f"Product build must produce exactly one current wheel for {name}")
        artifact = matches[0]
        current_receipts[name] = dict(inputs=identity, wheel=artifact.name, sha256=digest(artifact))
    return current_receipts


def _validate_companion_pins(metadata: list[Message], expected_version: str) -> None:
    root_metadata = next(item for item in metadata if item["Name"] == PRODUCT_IDENTITY.distribution)
    companion_pins = {}
    for value in root_metadata.get_all("Requires-Dist", []):
        requirement = Requirement(value)
        name = canonicalize_name(requirement.name)
        if name in PRODUCT_IDENTITY.companion_distributions:
            if requirement.marker is not None or requirement.url is not None or name in companion_pins:
                raise ValueError(f"Companion requirement is not one unconditional exact pin: {value}")
            companion_pins[name] = str(requirement.specifier)
    if companion_pins != {name: f"=={expected_version}" for name in PRODUCT_IDENTITY.companion_distributions}:
        raise ValueError("Product companion requirements must match the exact cohort version")


def _validate_wheel_cohort(artifacts: list[Path], expected_version: str) -> None:
    metadata = [read_wheel_metadata(wheel) for wheel in artifacts]
    expected = set(PRODUCT_IDENTITY.cohort_distributions)
    if {item["Name"] for item in metadata} != expected or len(artifacts) != len(expected):
        raise ValueError("Incomplete product wheel cohort")
    if {item["Version"] for item in metadata} != {expected_version}:
        raise ValueError("Product cohort versions differ")
    _validate_companion_pins(metadata, expected_version)


def _install_changed_wheels(
    artifacts: list[Path], dependencies: Path, uv: str, python: Path, pin: str, target: str
) -> list[Path]:
    changed_artifacts = [wheel for wheel in artifacts if not installed_wheel_matches(wheel, dependencies)]
    if changed_artifacts:
        result = run_command(
            [
                uv,
                "pip",
                "install",
                "--python",
                str(python),
                "--python-version",
                pin,
                "--python-platform",
                uv_platform(target),
                "--no-deps",
                "--reinstall",
                "--link-mode",
                "copy",
                "--target",
                str(dependencies),
                *map(str, changed_artifacts),
            ],
            cwd=REPO_ROOT,
            environment=uv_environment(target),
        )
        if result.returncode:
            raise RuntimeError(result.stderr)
    return changed_artifacts


def _remove_obsolete_wheels(wheels: Path, current_receipts: dict[str, dict[str, object]]) -> None:
    retained = {cast(str, record["wheel"]) for record in current_receipts.values()}
    for wheel in wheels.glob("*.whl"):
        if wheel.name not in retained:
            wheel.unlink()


def build_product(
    output: Path,
    python: Path,
    dependencies: Path,
    target: str,
    *,
    inputs: Path | None = None,
    build_toolchain: Mapping[str, object] | None = None,
    uv_executable: Path | None = None,
    timings: BuildTimings | None = None,
) -> None:
    """Compose existing snapshot, build hooks and wheel metadata owners."""
    client = build_client_json(REPO_ROOT)
    output = output.absolute()
    output.mkdir(parents=True, exist_ok=True)
    # A virtual environment's interpreter is a link to its base interpreter on POSIX;
    # following the link would leave the environment that provides the build backend.
    python = python.absolute()
    if not python.is_file():
        raise ValueError(f"Product construction requires an existing host interpreter: {python}")
    pin = _require_host_python(python)
    dependencies = dependencies.resolve(strict=True)
    uv = selected_uv(build_toolchain, executable=uv_executable)
    source = output / "source"
    # The binary directory's digest cache answers for every unchanged source file.
    with timings.phase("source-snapshot") if timings is not None else nullcontext(), digest_cache(output.parent):
        capture_product_source_snapshot(REPO_ROOT, source, inputs)
    with timings.phase("published-authority-staging") if timings is not None else nullcontext():
        _stage_product_authority(REPO_ROOT, source)
    embedded_client = source / "src/cadrumo/_data/google/oauth_client.json"
    embedded_client.parent.mkdir(parents=True, exist_ok=True)
    encoded_client = client.get_secret_value().encode()
    if not embedded_client.is_file() or embedded_client.read_bytes() != encoded_client:
        embedded_client.write_bytes(encoded_client)
    environment = dict(os.environ)
    environment[GOOGLE_OAUTH_ENV] = client.get_secret_value()
    environment[AUTHORITY_ROOT_ENV] = str(source / ".authority")
    project = parse_toml((source / "pyproject.toml").read_text(encoding="utf-8"))
    wheels = output / "wheels"
    projects = [source]
    projects.extend(
        source / project["tool"]["uv"]["sources"][name]["path"] for name in PRODUCT_IDENTITY.companion_distributions
    )
    receipts_path = output / "wheel-inputs.json"
    try:
        receipts = json.loads(receipts_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        receipts = {}
    if not isinstance(receipts, dict):
        receipts = {}
    receipts = cast(dict[str, object], receipts)
    current_receipts = _build_wheels(
        source,
        python,
        uv,
        wheels,
        projects,
        receipts,
        project["project"]["version"],
        environment,
        build_toolchain,
        timings,
    )
    _remove_obsolete_wheels(wheels, current_receipts)
    artifacts = sorted(wheels.glob("*.whl"))
    _validate_wheel_cohort(artifacts, project["project"]["version"])
    changed_artifacts = _install_changed_wheels(artifacts, dependencies, uv, python, pin, target)
    receipts_path.write_text(json.dumps(current_receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "product-wheels.json").write_text(
        json.dumps({p.name: digest(p) for p in artifacts}, indent=2),
        encoding="utf-8",
    )
    BuildLog("product").status(
        f"installed {len(changed_artifacts)} changed exact-version product wheels into {display_path(dependencies)}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=require_enrolled_output, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dependencies", type=require_enrolled_output, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--inputs", type=Path, help="CMake-enrolled product source inputs")
    parser.add_argument("--uv", type=Path, help="Explicit uv executable for a standalone invocation")
    parser.add_argument("--build-toolchain", type=Path, help="Explicit admitted builder toolchain JSON")
    args = parser.parse_args()
    configured = None
    if args.build_toolchain is not None:
        configured = json.loads(args.build_toolchain.read_text(encoding="utf-8"))
        if not isinstance(configured, dict):
            parser.error("build toolchain must be a JSON object")
    build_product(
        args.output,
        args.python,
        args.dependencies,
        args.target,
        inputs=args.inputs,
        build_toolchain=cast(Mapping[str, object] | None, configured),
        uv_executable=args.uv,
    )
