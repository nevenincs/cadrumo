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
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.toml import parse_toml
from dev._paths import AUTHORITY_ROOT_ENV, REPO_ROOT
from dev.first_party_source import PYTEST_CONFTEST
from dev.source_tree import content_digest, member_content_digest, normalised_content, repository_files, snapshot

from ..authority_staging import selected_published_authority
from ..command_execution import run_command
from ..google_oauth import GOOGLE_OAUTH_ENV, build_client_json
from ..wheel_metadata import installed_wheel_matches, read_wheel_metadata
from .build_directory import require_enrolled_output
from .build_log import BuildLog, display_path
from .build_timing import BuildTimings
from .build_toolchain import selected_uv
from .hashing import digest
from .target import uv_environment, uv_platform

BUNDLED_EXTRAS: tuple[str, ...] = ("llm",)
"""Optional extras the native application ships with its core closure.

The application serves the local model's review operations, which refuse
without ``llm``; the wheel's core install stays without it.
"""

_PRODUCT_INPUT_EXCLUSIONS = frozenset({"__pycache__", ".git", "tests"})


def _product_source_roots(root: Path) -> tuple[str, ...]:
    """Read the package roots from the same declarations used by CMake."""
    project = parse_toml((root / "pyproject.toml").read_text(encoding="utf-8"))
    paths = [project["tool"]["uv"]["sources"][name]["path"] for name in PRODUCT_IDENTITY.companion_distributions]
    hook = Path(project["tool"]["hatch"]["build"]["targets"]["wheel"]["hooks"]["custom"]["path"])
    paths.append(hook.parent.as_posix())

    root = root.resolve()
    resolved: list[str] = ["src"]
    for value in paths:
        candidate = (root / value).resolve(strict=False)
        try:
            relative = candidate.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("Product wheel source roots must stay inside the repository") from exc
        resolved.append("" if relative == "." else relative)
    return tuple(dict.fromkeys(resolved))


def _excluded_product_input(relative: str) -> bool:
    """Mirror cadrumo_product_inputs' exclusions for the snapshot source census."""
    path = PurePosixPath(relative)
    parts = path.parts
    return (
        relative == "src/cadrumo/_data/google/oauth_client.json"
        or any(part in _PRODUCT_INPUT_EXCLUSIONS for part in parts)
        or path.suffix in {".pyc", ".lock"}
        or path.name == PYTEST_CONFTEST
        or any(
            part.startswith(
                (".aeat-generated-export-transaction-", ".generated-export-backup-", ".generated-export-stage-")
            )
            for part in parts
        )
    )


def _input_manifest_members(root: Path, inputs: Path | None) -> frozenset[str] | None:
    """Return manifest paths that belong to the source snapshot."""
    if inputs is None:
        return None
    repository = root.resolve()
    members: set[str] = set()
    for line in inputs.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        candidate = Path(line)
        if not candidate.is_absolute():
            candidate = repository / candidate
        try:
            relative = candidate.resolve(strict=False).relative_to(repository).as_posix()
        except ValueError:
            # Runtime receipts and generated authority are admitted by CMake but
            # live outside the source snapshot and are checked by its input hash.
            continue
        # CMake has already filtered recursive inputs. Keep explicit owners such
        # as the root uv.lock even when their suffix matches that filter.
        members.add(relative)
    return frozenset(members)


def _membership_changed(detail: str) -> RuntimeError:
    return RuntimeError(
        "Product source membership changed while capturing the wheel inputs "
        f"({detail}). Re-run the CMake build so CONFIGURE_DEPENDS refreshes inputs-product.txt, then retry."
    )


def _capture_product_source_snapshot(root: Path, destination: Path, inputs: Path | None) -> None:
    """Capture and verify one coherent, enrolled source set before building any wheel."""
    root = root.resolve()
    source_roots = _product_source_roots(root)
    metadata = ("pyproject.toml", "uv.lock", "README.md", "LICENSE", "NOTICE", ".gitignore", ".gitattributes")
    files = tuple(
        sorted(
            {
                *(name for name in repository_files(root, under=source_roots) if not _excluded_product_input(name)),
                *(name for name in metadata if (root / name).is_file()),
            }
        )
    )
    file_members = frozenset(files)
    package_members = frozenset(
        name for name in repository_files(root, under=source_roots) if not _excluded_product_input(name)
    )
    if not package_members <= file_members:
        raise _membership_changed("the package source census changed before snapshotting")

    manifest_members = _input_manifest_members(root, inputs)
    if manifest_members is None:
        # Standalone callers still receive a bounded content-stability check.
        enrolled = set(package_members)
        if "pyproject.toml" in file_members:
            enrolled.add("pyproject.toml")
    else:
        missing = sorted(package_members - manifest_members)
        if missing:
            raise _membership_changed(f"{missing[0]} is absent from inputs-product.txt")
        enrolled = set(file_members & manifest_members)
    enrolled_members = tuple(sorted(enrolled))
    before = content_digest(root, enrolled_members)

    _sync_source_snapshot(root, files, destination)
    captured = member_content_digest(enrolled_members, lambda name: (destination / name).read_bytes())
    captured_package_members = frozenset(
        name for name in repository_files(destination, under=source_roots) if not _excluded_product_input(name)
    )
    if captured_package_members != package_members:
        raise _membership_changed("the captured wheel source membership differs from its initial census")

    current_roots = _product_source_roots(root)
    current_package_members = frozenset(
        name for name in repository_files(root, under=current_roots) if not _excluded_product_input(name)
    )
    if current_roots != source_roots or current_package_members != package_members:
        raise _membership_changed("wheel package roots or source files changed during snapshotting")
    if manifest_members is not None:
        missing = sorted(current_package_members - manifest_members)
        if missing:
            raise _membership_changed(f"{missing[0]} is absent from inputs-product.txt")

    after = content_digest(root, enrolled_members)
    if before != captured or captured != after:
        raise RuntimeError(
            "Enrolled product source content changed while capturing the wheel inputs; "
            "retry after the enrolled source files are stable."
        )


def _sync_source_snapshot(root: Path, files: tuple[str, ...], destination: Path) -> None:
    """Preserve unchanged normalized source files and remove obsolete snapshot members."""
    for ancestor in (destination, *destination.parents):
        if ancestor.is_symlink() or ancestor.is_junction():
            raise ValueError("Product source snapshot contains a linked member")
    pending = [destination] if destination.is_dir() else []
    while pending:
        for member in pending.pop().iterdir():
            if member.is_symlink() or member.is_junction():
                raise ValueError("Product source snapshot contains a linked member")
            if member.is_dir():
                pending.append(member)
    if not destination.exists():
        snapshot(root, files, destination)
        return
    expected = set(files)
    for path in destination.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(destination).as_posix()
        if relative.startswith(".authority/") or relative == "src/cadrumo/_data/google/oauth_client.json":
            continue
        if relative not in expected:
            path.unlink()
    for relative in files:
        path = destination / relative
        content = normalised_content(root, relative)
        if path.is_file() and path.read_bytes() == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        shutil.copystat(root / relative, path)
    for directory in sorted(destination.rglob("*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


def _wheel_input_digest(directory: Path, *, toolchain: Mapping[str, Any] | None) -> str:
    """Name the actual Hatch selection, including hook-owned payloads and metadata."""
    from hatchling.builders.wheel import WheelBuilder

    builder = WheelBuilder(str(directory))
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
        if builder.metadata.core.readme_path:
            metadata_paths.add(directory / builder.metadata.core.readme_path)
        for pattern in builder.metadata.core.license_files:
            metadata_paths.update(path for path in directory.glob(pattern) if path.is_file())
        metadata = {path.relative_to(directory).as_posix(): digest(path) for path in metadata_paths}
        for hook in hooks:
            hook_path = directory / hook.config.get("path", "hatch_build.py")
            if hook_path.is_file():
                metadata[hook_path.relative_to(directory).as_posix()] = digest(hook_path)
        configuration = dict(members=members, metadata=metadata, backend=version("hatchling"), toolchain=toolchain)
        return hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    finally:
        for hook in hooks:
            hook.finalize("standard", data, "")


def _stage_product_authority(root: Path, source: Path) -> None:
    """Capture the selected pair before publication and retire old snapshot generations."""
    originals = selected_published_authority(root)
    expected = {path.name: digest(path) for path in originals}
    destination = source / ".authority"
    if destination.is_symlink() or destination.is_junction():
        raise ValueError("Product authority snapshot cannot be linked")
    destination.mkdir(parents=True, exist_ok=True)
    for member in destination.iterdir():
        if member.is_symlink() or member.is_junction() or not member.is_file():
            raise ValueError("Product authority snapshot must contain only regular files")
    changed = [
        path
        for path in originals
        if not (destination / path.name).is_file() or digest(destination / path.name) != expected[path.name]
    ]
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
    for member in destination.iterdir():
        if member.name not in expected:
            member.unlink()


def build_product(
    output: Path,
    python: Path,
    dependencies: Path,
    target: str,
    *,
    inputs: Path | None = None,
    build_toolchain: Mapping[str, Any] | None = None,
    uv_executable: Path | None = None,
    timings: BuildTimings | None = None,
) -> None:
    """Compose existing snapshot, build hooks and wheel metadata owners."""
    client = build_client_json(REPO_ROOT)
    output = output.absolute()
    output.mkdir(parents=True, exist_ok=True)
    python = python.resolve(strict=True)
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
    dependencies = dependencies.resolve(strict=True)
    uv = selected_uv(build_toolchain, executable=uv_executable)
    source = output / "source"
    with timings.phase("source-snapshot") if timings is not None else nullcontext():
        _capture_product_source_snapshot(REPO_ROOT, source, inputs)
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
    current_receipts = {}
    for directory in projects:
        name = parse_toml((directory / "pyproject.toml").read_text(encoding="utf-8"))["project"]["name"]
        prior_authority = os.environ.get(AUTHORITY_ROOT_ENV)
        os.environ[AUTHORITY_ROOT_ENV] = str(source / ".authority")
        try:
            identity = _wheel_input_digest(
                directory,
                toolchain={
                    "python": digest(python),
                    "python_version": sys.version,
                    "uv": build_toolchain["builder_files"]["CADRUMO_UV"]
                    if build_toolchain is not None
                    else {"path": uv, "sha256": digest(Path(uv))},
                },
            )
        finally:
            if prior_authority is None:
                os.environ.pop(AUTHORITY_ROOT_ENV, None)
            else:
                os.environ[AUTHORITY_ROOT_ENV] = prior_authority
        prior = receipts.get(name, {})
        artifact = wheels / str(prior.get("wheel", "")) if isinstance(prior, dict) else wheels
        if (
            isinstance(prior, dict)
            and prior.get("inputs") == identity
            and artifact.is_file()
            and artifact.parent == wheels
            and digest(artifact) == prior.get("sha256")
        ):
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
        expected_version = project["project"]["version"]
        matches = [wheel for wheel in matches if read_wheel_metadata(wheel)["Version"] == expected_version]
        if len(matches) != 1:
            raise ValueError(f"Product build must produce exactly one current wheel for {name}")
        artifact = matches[0]
        current_receipts[name] = dict(inputs=identity, wheel=artifact.name, sha256=digest(artifact))
    retained = {record["wheel"] for record in current_receipts.values()}
    for wheel in wheels.glob("*.whl"):
        if wheel.name not in retained:
            wheel.unlink()
    artifacts = sorted(wheels.glob("*.whl"))
    metadata = [read_wheel_metadata(wheel) for wheel in artifacts]
    expected = set(PRODUCT_IDENTITY.cohort_distributions)
    if {item["Name"] for item in metadata} != expected or len(artifacts) != len(expected):
        raise ValueError("Incomplete product wheel cohort")
    if {item["Version"] for item in metadata} != {project["project"]["version"]}:
        raise ValueError("Product cohort versions differ")
    root_metadata = next(item for item in metadata if item["Name"] == PRODUCT_IDENTITY.distribution)
    companion_pins = {}
    for value in root_metadata.get_all("Requires-Dist", []):
        requirement = Requirement(value)
        name = canonicalize_name(requirement.name)
        if name in PRODUCT_IDENTITY.companion_distributions:
            if requirement.marker is not None or requirement.url is not None or name in companion_pins:
                raise ValueError(f"Companion requirement is not one unconditional exact pin: {value}")
            companion_pins[name] = str(requirement.specifier)
    if companion_pins != {
        name: f"=={project['project']['version']}" for name in PRODUCT_IDENTITY.companion_distributions
    }:
        raise ValueError("Product companion requirements must match the exact cohort version")
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
        build_toolchain=configured,
        uv_executable=args.uv,
    )
