"""Small build actions called by CMake; CMake owns their graph and output paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path

from cadrumo.core.storage_environment import prepare_temporary_directory, tool_storage_environment
from dev._paths import REPO_ROOT

from ..authority_staging import selected_published_authority
from ..command_execution import CommandResult, run_command
from ..google_oauth import build_client_json, client_build_identity
from ..runtime_wheel_selection import plan_target_wheels
from .action_cache import action_lock, completed, current, fingerprint
from .assemble import assemble, image_artifact
from .build_paths import build_paths
from .build_timing import BuildTimings, measure_build
from .build_toolchain import builder_inputs, native_toolchain_identity, selected_uv
from .docs_stage import RECONFIGURE
from .layout import backend, load_layout
from .product import build_product
from .provision import provision, provisioning_tools
from .target import toolchain_for_target


def action_toolchain(configured: Mapping[str, object], action: str, target: str) -> dict[str, object]:
    """Select only producers and pins consumed by this action, not desktop inputs."""
    files = configured.get("builder_files", {})
    if not isinstance(files, dict):
        raise ValueError("Configured builder_files must be a mapping")
    selected: dict[str, object] = {
        "builder_files": {name: record for name, record in files.items() if name == "CADRUMO_UV" and action != "sdk"}
    }
    pins = toolchain_for_target(target)
    if action in {"sdk", "provision"}:
        selected["pins"] = {name: value for name, value in pins.items() if name.startswith("cpython_")}
        if action == "provision":
            python = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
            selected["wheels"] = [asdict(wheel) for wheel in plan_target_wheels(REPO_ROOT, target, python)]
        if action == "sdk" and "cpython_archive_decoder" in configured:
            selected["cpython_archive_decoder"] = configured["cpython_archive_decoder"]
    elif action == "tools":
        selected["pins"] = {"resvg_py": pins["resvg_py"]}
    elif action != "product":
        raise ValueError(f"No shared producer selection for {action}")
    # Product wheels use Hatchling's Python/data hooks; native compilers and SDKs
    # never produce their contents. CMake enrolls their declared sources/backend,
    # and the action caller hashes the admitted Python executable.
    return selected


def reset(build: Path, relative: str) -> Path:
    """Replace only a named generated subtree inside this CMake binary directory."""
    build = build.resolve(strict=True)
    destination = (build / relative).resolve()
    if build == REPO_ROOT or destination == build or not destination.is_relative_to(build):
        raise ValueError("Refusing a generated-directory operation outside the CMake binary directory")
    if destination.exists():
        shutil.rmtree(destination)
    return destination


def run_configured_command(
    build: Path, configured: dict[str, object], command: list[str], *, timings: BuildTimings | None = None
) -> CommandResult:
    """Invalidate only the isolated native Cargo cache when selected producer bytes change."""
    if Path(command[0]).name.lower() not in {"cargo", "cargo.exe"} or command[1:2] not in (
        ["build"],
        ["test"],
        ["check"],
        ["run"],
        ["clippy"],
        ["rustc"],
    ):
        with timings.phase("builder-admission") if timings is not None else nullcontext():
            builder_inputs(configured)
        with timings.phase("configured-command") if timings is not None else nullcontext():
            result = run_command(command, cwd=REPO_ROOT)
            if timings is not None:
                timings.command_completed(result.returncode)
            return result
    files = configured.get("builder_files", {})
    if not isinstance(files, dict):
        raise ValueError("Configured builder_files must be a mapping")
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
    paths = build_paths(build)
    native = paths["cargo"]
    desktop = paths.get("desktop_cargo")
    if desktop is not None and (desktop.is_relative_to(native) or native.is_relative_to(desktop)):
        raise ValueError("Native Cargo invalidation requires a directory isolated from desktop Cargo outputs")
    selected = Path(os.environ.get("CARGO_TARGET_DIR", ""))
    if not selected.is_absolute() or selected.resolve() != native:
        raise ValueError("Native Cargo command requires its declared absolute target directory")
    for index, argument in enumerate(command):
        if argument == "--target-dir":
            selected = Path(command[index + 1])
        elif argument.startswith("--target-dir="):
            selected = Path(argument.partition("=")[2])
    if not selected.is_absolute() or not selected.resolve().is_relative_to(native):
        raise ValueError("Native Cargo target override escapes its owning binary directory")
    directory = build.resolve(strict=True)
    for part in selected.relative_to(directory).parts:
        directory /= part
        if directory.is_symlink() or directory.is_junction():
            raise ValueError("Native Cargo target directory contains a linked member")
    directory = selected.resolve()
    identity = native_toolchain_identity(configured)
    marker = paths["generated"] / f"rust-toolchain-{hashlib.sha256(str(directory).encode()).hexdigest()}.txt"
    with action_lock(build, "native-cargo", timings=timings):
        if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != identity:
            clean = [command[0], "clean", "--target-dir", str(directory)]
            if "--manifest-path" in command:
                clean.extend(["--manifest-path", command[command.index("--manifest-path") + 1]])
            with timings.phase("cargo-clean") if timings is not None else nullcontext():
                result = run_command(clean, cwd=REPO_ROOT)
                if timings is not None:
                    timings.command_completed(result.returncode)
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            if result.returncode:
                return result
        with timings.phase("cargo-command") if timings is not None else nullcontext():
            result = run_command(command, cwd=REPO_ROOT)
            if timings is not None:
                timings.command_completed(result.returncode)
        if result.returncode == 0:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(identity + "\n", encoding="utf-8")
        return result


def main() -> None:
    """Run one CMake action with scoped development-tool storage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("sdk", "provision", "product", "assemble", "run", "tools"))
    parser.add_argument("--build", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--config", choices=("Debug", "Release"))
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--interpreter", action="store_true")
    parser.add_argument("--without-user-docs", action="store_true")
    # One FILE=ARTIFACT pair per staged application image, resolved by CMake for the selected configuration.
    parser.add_argument("--image", action="append", default=[])
    argv = sys.argv[1:]
    boundary = argv.index("--") if "--" in argv else len(argv)
    arguments = parser.parse_args(argv[:boundary])
    command = argv[boundary + 1 :]
    environment = tool_storage_environment()
    environment.update(dict.fromkeys(("TEMP", "TMP", "TMPDIR"), str(prepare_temporary_directory())))
    for path in environment.values():
        Path(path).mkdir(parents=True, exist_ok=True)
    environment.update(item.split("=", 1) for item in arguments.env)
    os.environ.update(environment)
    if arguments.action == "run":
        if not command:
            parser.error("run requires -- followed by an executable and arguments")
        if arguments.build is not None:
            selected = build_paths(arguments.build)["generated"] / "build-toolchain.json"
            with measure_build(arguments.build, "native-command") as timings:
                result = run_configured_command(
                    arguments.build, json.loads(selected.read_text(encoding="utf-8")), command, timings=timings
                )
        else:
            result = run_command(command, cwd=REPO_ROOT)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    if arguments.build is None:
        parser.error("--build is required")
    if arguments.action in {"sdk", "provision", "product", "tools"} and arguments.inputs is None:
        parser.error("Shared actions require --inputs")
    build = arguments.build.resolve(strict=True)
    with measure_build(build, arguments.action) as timings:
        execute_action(build, arguments, timings)


def execute_action(build: Path, arguments: argparse.Namespace, timings: BuildTimings) -> None:
    """Admit one stable producer generation and retain its phase durations."""
    paths = build_paths(build)
    identity_file = paths["generated"] / "identity.json"
    configured = json.loads((paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8"))
    arguments.target = json.loads(identity_file.read_text(encoding="utf-8"))["target"]
    if arguments.action in {"sdk", "provision", "product", "tools"}:
        if arguments.inputs is None:
            raise ValueError("Shared actions require --inputs")
        paths = build_paths(build)
        destination = paths[
            {"sdk": "python_sdk", "provision": "runtime", "tools": "tools", "product": "product"}[arguments.action]
        ]
        extra = selected_published_authority(REPO_ROOT) if arguments.action == "product" else ()
        selected = action_toolchain(configured, arguments.action, arguments.target)
        with timings.phase("builder-admission"):
            selected_builder_inputs = builder_inputs(selected)
        with action_lock(build, "shared-inputs", timings=timings):

            def admitted_identity() -> str:
                identity = fingerprint(arguments.inputs, (*extra, Path(sys.executable), *selected_builder_inputs))
                # Hash only this producer's selections, not independent desktop/native inputs.
                identity = hashlib.sha256(
                    json.dumps([identity, arguments.target, selected], sort_keys=True).encode("utf-8")
                ).hexdigest()
                if arguments.action == "product":
                    identity = client_build_identity(identity, build_client_json(REPO_ROOT))
                return identity

            with timings.phase("input-fingerprint"):
                identity = admitted_identity()
            with timings.phase("existing-output-inventory"):
                reusable = current(destination, identity)
            if reusable:
                print(f"Reusing {arguments.action}: inputs and output inventory unchanged")
                return
            (destination / "ready").unlink(missing_ok=True)
            with timings.phase("producer"):
                destination = build_action(build, arguments, timings=timings)
            with timings.phase("input-stability"):
                latest_target = json.loads(identity_file.read_text(encoding="utf-8"))["target"]
                latest_configured = json.loads(
                    (paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8")
                )
                latest_selected = action_toolchain(latest_configured, arguments.action, latest_target)
                if latest_target != arguments.target or latest_selected != selected or admitted_identity() != identity:
                    raise RuntimeError(f"Inputs changed during {arguments.action}; completion receipt refused")
            with timings.phase("output-inventory"):
                completed(destination, identity)
    else:
        destination = build_action(build, arguments, timings=timings)
        (destination / "ready").write_text("complete\n", encoding="utf-8")


def build_action(build: Path, arguments: argparse.Namespace, *, timings: BuildTimings | None = None) -> Path:
    """Execute a generated-output action after its reuse and concurrency checks."""
    paths = build_paths(build)
    runtime = paths["runtime"]
    configured = json.loads((paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8"))
    contract = load_layout(arguments.target)
    sdk_root = paths.get("python_sdk", runtime)
    sdk = sdk_root / contract["sdk"]["root"]
    if arguments.action == "sdk":
        destination = reset(build, str(sdk_root.relative_to(build)))
        pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
        produced = backend(contract).provision_sdk(
            destination, pin, provisioning_tools(arguments.target, configured), contract
        )
        if produced.resolve() != sdk.resolve():
            raise ValueError("SDK backend output differs from the declared SDK root")
    elif arguments.action == "tools":
        destination = reset(build, str(paths["tools"].relative_to(build)))
        uv = selected_uv(configured)
        pins = json.loads((REPO_ROOT / "native/toolchain.json").read_text(encoding="utf-8"))
        result = run_command(
            [
                uv,
                "pip",
                "install",
                "--python",
                sys.executable,
                "--target",
                str(destination),
                "--only-binary",
                ":all:",
                "--no-deps",
                "--link-mode",
                "copy",
                f"resvg-py=={pins['resvg_py']}",
            ],
            cwd=REPO_ROOT,
        )
        if result.returncode:
            raise RuntimeError(result.stderr)
    elif arguments.action == "provision":
        destination = reset(build, str(runtime.relative_to(build)))
        provision(
            destination,
            arguments.target,
            build_toolchain=configured,
            sdk=sdk if "python_sdk" in paths else None,
        )
    elif arguments.action == "product":
        destination = reset(build, str(paths["product"].relative_to(build)))
        destination.mkdir(parents=True)
        shutil.copytree(runtime / "dependencies", destination / "dependencies")
        build_product(
            destination / "build",
            Path(sys.executable),
            destination / "dependencies",
            arguments.target,
            build_toolchain=configured,
            timings=timings,
        )
    else:
        if arguments.config is None:
            raise ValueError("assemble requires --config")
        if not arguments.without_user_docs and "user_docs_stage" not in paths:
            raise SystemExit(RECONFIGURE)
        destination = reset(build, str((paths["stage"] / arguments.config).relative_to(build)))
        assemble(
            sdk,
            None if arguments.interpreter else paths["product"] / "dependencies",
            paths["bin"] / arguments.config,
            destination / "app",
            paths["generated"] / "build.json",
            None if arguments.without_user_docs else paths["user_docs_stage"],
            images=dict(image_artifact(item) for item in arguments.image),
            binary_dir=build,
            development=arguments.development,
            interpreter=arguments.interpreter,
            target=arguments.target,
            provenance={
                "runtime": {}
                if arguments.interpreter
                else json.loads((runtime / "runtime-inputs.json").read_text(encoding="utf-8")),
                "cohort_wheels": {}
                if arguments.interpreter
                else json.loads((paths["product"] / "build/product-wheels.json").read_text(encoding="utf-8")),
                "build_toolchain": json.loads(
                    (paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8")
                ),
            },
            timings=timings,
        )
    return destination


if __name__ == "__main__":
    main()
