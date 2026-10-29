"""Small build actions called by CMake; CMake owns their graph and output paths."""

from __future__ import annotations

import hashlib
import os
import re
from contextlib import nullcontext
from pathlib import Path
from typing import cast

from dev._paths import REPO_ROOT

from ..command_execution import CommandResult, run_command
from .action_cache import action_lock
from .build_log import command_line, display_path
from .build_paths import build_paths
from .build_timing import BuildTimings
from .build_toolchain import builder_inputs, native_toolchain_identity


def _run_plain_command(
    configured: dict[str, object],
    command: list[str],
    timings: BuildTimings | None,
    *,
    environment: dict[str, str] | None = None,
) -> CommandResult:
    with timings.phase("builder-admission") if timings is not None else nullcontext():
        builder_inputs(configured)
    _announce(timings, command)
    with timings.phase("configured-command") if timings is not None else nullcontext():
        result = run_command(command, cwd=REPO_ROOT, environment=environment, inherit_output=True)
        if timings is not None:
            timings.command_completed(result.returncode)
        return result


def _check_cargo_members(build: Path, selected: Path) -> None:
    directory = build.resolve(strict=True)
    for part in selected.relative_to(directory).parts:
        directory /= part
        if directory.is_symlink() or directory.is_junction():
            raise ValueError("Native Cargo target directory contains a linked member")


def _selected_target_directory(native: Path, command: list[str]) -> Path:
    selected = native
    for index, argument in enumerate(command):
        if argument == "--":
            break
        if argument == "--target-dir":
            if index + 1 >= len(command) or command[index + 1] == "--":
                raise ValueError("Native Cargo target override requires a directory")
            selected = Path(command[index + 1])
        elif argument.startswith("--target-dir="):
            selected = Path(argument.partition("=")[2])
    return selected


def _cargo_directory(build: Path, command: list[str]) -> tuple[Path, Path]:
    paths = build_paths(build)
    native = paths["cargo"]
    desktop = paths.get("desktop_cargo")
    if desktop is not None and (desktop.is_relative_to(native) or native.is_relative_to(desktop)):
        raise ValueError("Native Cargo invalidation requires a directory isolated from desktop Cargo outputs")
    exported = Path(os.environ.get("CARGO_TARGET_DIR", ""))
    if not exported.is_absolute() or exported.resolve() != native:
        raise ValueError("Native Cargo command requires its declared absolute target directory")
    # The exported directory is only checked against the build's own; every
    # path written below derives from the build layout.
    selected = _selected_target_directory(native, command)
    if not selected.is_absolute() or not selected.resolve().is_relative_to(native):
        raise ValueError("Native Cargo target override escapes its owning binary directory")
    _check_cargo_members(build, selected)
    return selected.resolve(), paths["generated"]


def _timed_cargo_command(
    command: list[str], environment: dict[str, str], timings: BuildTimings | None, phase: str
) -> CommandResult:
    with timings.phase(phase) if timings is not None else nullcontext():
        result = run_command(command, cwd=REPO_ROOT, environment=environment, inherit_output=True)
        if timings is not None:
            timings.command_completed(result.returncode)
        return result


def _run_locked_cargo(
    build: Path,
    command: list[str],
    directory: Path,
    marker: Path,
    identity: str,
    environment: dict[str, str],
    timings: BuildTimings | None,
) -> CommandResult:
    with action_lock(build, "native-cargo", timings=timings):
        if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != identity:
            clean = [command[0], "clean", "--target-dir", str(directory)]
            cargo_options = command[: command.index("--")] if "--" in command else command
            if "--manifest-path" in cargo_options:
                clean.extend(["--manifest-path", cargo_options[cargo_options.index("--manifest-path") + 1]])
            if timings is not None:
                timings.log.status(
                    "the selected Rust toolchain or SDK changed; "
                    f"cleaning {display_path(directory)} before a full Cargo rebuild"
                )
            _announce(timings, clean)
            result = _timed_cargo_command(clean, environment, timings, "cargo-clean")
            if result.returncode:
                return result
        _announce(timings, command)
        result = _timed_cargo_command(command, environment, timings, "cargo-command")
        if result.returncode == 0:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(identity + "\n", encoding="utf-8")
        return result


def _cargo_quality_command(command: list[str]) -> bool:
    arguments = command[1:]
    if arguments[:3] == ["fmt", "--check", "--manifest-path"] and len(arguments) == 4:
        return True
    return (
        len(arguments) == 12
        and arguments[:3] == ["deny", "--locked", "--manifest-path"]
        and arguments[4:6] == ["check", "--config"]
        and arguments[7:] == ["--hide-inclusion-graph", "advisories", "bans", "licenses", "sources"]
    )


def _validate_cargo_build_command(command: list[str]) -> None:
    """Admit only supported subcommands without Cargo output or configuration overrides."""
    if command[1:2] not in (["build"], ["test"], ["check"], ["run"], ["clippy"], ["rustc"]):
        raise ValueError("Native Cargo does not accept this subcommand or global option")
    cargo_options = command[1 : command.index("--")] if "--" in command else command[1:]
    if any(option == "--config" or option.startswith("--config=") for option in cargo_options):
        raise ValueError("Native Cargo commands do not accept configuration overrides")
    if any(option == "--artifact-dir" or option.startswith("--artifact-dir=") for option in cargo_options):
        raise ValueError("Native Cargo commands do not accept artifact directory overrides")


def _cargo_toolchain_identity(configured: dict[str, object]) -> str:
    """Exclude CMake-only flags from the identity governing Cargo invalidation."""
    cmake_flags = re.compile(r"CMAKE_C_FLAGS(_.+)?|CMAKE_[A-Z]+_LINKER_FLAGS(_.+)?")
    target_configuration = configured.get("target_configuration", {})
    return native_toolchain_identity(
        {
            **configured,
            "target_configuration": {
                name: value
                for name, value in (
                    cast(dict[str, object], target_configuration).items()
                    if isinstance(target_configuration, dict)
                    else ()
                )
                if not cmake_flags.fullmatch(str(name))
            },
        }
    )


def run_configured_command(
    build: Path, configured: dict[str, object], command: list[str], *, timings: BuildTimings | None = None
) -> CommandResult:
    """Invalidate only the isolated native Cargo cache when selected producer bytes change."""
    if Path(command[0]).name.lower() not in {"cargo", "cargo.exe"}:
        return _run_plain_command(configured, command, timings)
    quality = _cargo_quality_command(command)
    if not quality:
        _validate_cargo_build_command(command)
    if quality:
        directory, _ = _cargo_directory(build, command)
        environment = dict(os.environ)
        environment["CARGO_BUILD_TARGET_DIR"] = str(directory)
        environment["CARGO_BUILD_BUILD_DIR"] = str(directory)
        return _run_plain_command(configured, command, timings, environment=environment)
    files = configured.get("builder_files", {})
    if not isinstance(files, dict):
        raise ValueError("Configured builder_files must be a mapping")
    files = cast(dict[str, object], files)
    with timings.phase("builder-admission") if timings is not None else nullcontext():
        builder_inputs(
            {
                "builder_files": {
                    name: record
                    for name, record in files.items()
                    if name != "CADRUMO_UV" and not name.startswith("desktop/")
                },
                "sysroots": configured.get("sysroots", {}),
            }
        )
    directory, generated = _cargo_directory(build, command)
    # CMake's own C compile and link flags reach only the targets CMake compiles; Cargo never
    # reads them, so a change to them must not clean the Cargo directory.
    identity = _cargo_toolchain_identity(configured)
    marker = generated / f"rust-toolchain-{hashlib.sha256(str(directory).encode()).hexdigest()}.txt"
    # Cargo subcommands and their drivers must use the selected toolchain too.
    environment = dict(os.environ)
    environment["CARGO_BUILD_TARGET_DIR"] = str(directory)
    environment["CARGO_BUILD_BUILD_DIR"] = str(directory)
    environment["PATH"] = os.pathsep.join((str(Path(command[0]).parent), environment.get("PATH", "")))
    return _run_locked_cargo(build, command, directory, marker, identity, environment, timings)


def _announce(timings: BuildTimings | None, command: list[str]) -> None:
    """Name the program a step runs at STATUS, and its whole command line at DEBUG."""
    if timings is not None:
        subcommand = next((argument for argument in command[1:] if not argument.startswith("-")), "")
        timings.log.status(f"running {Path(command[0]).stem} {subcommand}".rstrip())
        timings.log.debug(f"command: {command_line(command)}")
