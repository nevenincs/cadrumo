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
    configured: dict[str, object], command: list[str], timings: BuildTimings | None
) -> CommandResult:
    with timings.phase("builder-admission") if timings is not None else nullcontext():
        builder_inputs(configured)
    _announce(timings, command)
    with timings.phase("configured-command") if timings is not None else nullcontext():
        result = run_command(command, cwd=REPO_ROOT, inherit_output=True)
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
        if argument == "--target-dir":
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
            if "--manifest-path" in command:
                clean.extend(["--manifest-path", command[command.index("--manifest-path") + 1]])
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


def _is_cargo_command(command: list[str]) -> bool:
    return Path(command[0]).name.lower() in {"cargo", "cargo.exe"} and command[1:2] in (
        ["build"],
        ["test"],
        ["check"],
        ["run"],
        ["clippy"],
        ["rustc"],
    )


def run_configured_command(
    build: Path, configured: dict[str, object], command: list[str], *, timings: BuildTimings | None = None
) -> CommandResult:
    """Invalidate only the isolated native Cargo cache when selected producer bytes change."""
    if not _is_cargo_command(command):
        return _run_plain_command(configured, command, timings)
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
    cmake_flags = re.compile(r"CMAKE_C_FLAGS(_.+)?|CMAKE_[A-Z]+_LINKER_FLAGS(_.+)?")
    target_configuration = configured.get("target_configuration", {})
    identity = native_toolchain_identity(
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
    marker = generated / f"rust-toolchain-{hashlib.sha256(str(directory).encode()).hexdigest()}.txt"
    # Cargo subcommands and their drivers must use the selected toolchain too.
    environment = dict(os.environ)
    environment["PATH"] = os.pathsep.join((str(Path(command[0]).parent), environment.get("PATH", "")))
    return _run_locked_cargo(build, command, directory, marker, identity, environment, timings)


def _announce(timings: BuildTimings | None, command: list[str]) -> None:
    """Name the program a step runs at STATUS, and its whole command line at DEBUG."""
    if timings is not None:
        subcommand = next((argument for argument in command[1:] if not argument.startswith("-")), "")
        timings.log.status(f"running {Path(command[0]).stem} {subcommand}".rstrip())
        timings.log.debug(f"command: {command_line(command)}")
