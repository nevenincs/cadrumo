"""Small build actions called by CMake; CMake owns their graph and output paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path

from dev._paths import REPO_ROOT

from ..authority_staging import selected_published_authority
from ..command_execution import CommandResult, run_command
from ..google_oauth import build_client_json, client_build_identity
from ..runtime_wheel_selection import plan_target_wheels
from ..wheel_metadata import installed_wheel_matches
from .action_cache import action_lock, completed, fingerprint, modified_inputs, staleness
from .agent import agent_wheel, build_agent, validate_wheel_dependencies
from .agent_runtime import build_agent_runtime
from .assemble import assemble, image_artifact
from .build_directory import require_enrolled_build
from .build_log import BuildLog, command_line, display_path
from .build_paths import build_paths
from .build_timing import BuildTimings, measure_build
from .build_toolchain import builder_inputs, native_toolchain_identity, selected_uv
from .docs_stage import RECONFIGURE
from .layout import backend, load_layout
from .process_quiescence import quiesce
from .product import BUNDLED_EXTRAS, build_product
from .provision import provision, provisioning_tools
from .stable_output import write_text
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
            wheels = plan_target_wheels(REPO_ROOT, target, python, extras=BUNDLED_EXTRAS)
            selected["wheels"] = [asdict(wheel) for wheel in wheels]
        if action == "sdk" and "cpython_archive_decoder" in configured:
            selected["cpython_archive_decoder"] = configured["cpython_archive_decoder"]
    elif action == "tools":
        selected["pins"] = {"resvg_py": pins["resvg_py"]}
    elif action == "agent":
        tools = configured.get("desktop_tools")
        if not isinstance(tools, dict) or not all(isinstance(tools.get(name), str) for name in ("node", "npm_cli")):
            raise ValueError("Agent runtime construction requires configured Node/npm builders; reconfigure CMake")
        selected["node"] = tools["node"]
        selected["npm_cli"] = tools["npm_cli"]
        selected["builder_files"] = {
            name: record
            for name, record in files.items()
            if name in {"CADRUMO_UV", "desktop/node", "desktop/npm-cli", "desktop/npm-package"}
        }
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
        _announce(timings, command)
        with timings.phase("configured-command") if timings is not None else nullcontext():
            result = run_command(command, cwd=REPO_ROOT, inherit_output=True)
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
    exported = Path(os.environ.get("CARGO_TARGET_DIR", ""))
    if not exported.is_absolute() or exported.resolve() != native:
        raise ValueError("Native Cargo command requires its declared absolute target directory")
    # The exported directory is only checked against the build's own; every
    # path written below derives from the build layout.
    selected = native
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
    # Cargo subcommands and their drivers must use the selected toolchain too.
    environment = dict(os.environ)
    environment["PATH"] = os.pathsep.join((str(Path(command[0]).parent), environment.get("PATH", "")))
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
            with timings.phase("cargo-clean") if timings is not None else nullcontext():
                result = run_command(clean, cwd=REPO_ROOT, environment=environment, inherit_output=True)
                if timings is not None:
                    timings.command_completed(result.returncode)
            if result.returncode:
                return result
        _announce(timings, command)
        with timings.phase("cargo-command") if timings is not None else nullcontext():
            result = run_command(command, cwd=REPO_ROOT, environment=environment, inherit_output=True)
            if timings is not None:
                timings.command_completed(result.returncode)
        if result.returncode == 0:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(identity + "\n", encoding="utf-8")
        return result


def _announce(timings: BuildTimings | None, command: list[str]) -> None:
    """Name the program a step runs at STATUS, and its whole command line at DEBUG."""
    if timings is not None:
        subcommand = next((argument for argument in command[1:] if not argument.startswith("-")), "")
        timings.log.status(f"running {Path(command[0]).stem} {subcommand}".rstrip())
        timings.log.debug(f"command: {command_line(command)}")


def main() -> None:
    """Run one CMake action without changing machine-managed tool caches."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("sdk", "provision", "product", "assemble", "run", "tools", "agent"))
    parser.add_argument("--agent-source", type=Path)
    parser.add_argument("--build", type=require_enrolled_build)
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
    environment = dict(item.split("=", 1) for item in arguments.env)
    if arguments.build is not None:
        temporary = build_paths(arguments.build)["temporary"]
        temporary.mkdir(exist_ok=True)
        environment.update(dict.fromkeys(("TEMP", "TMP", "TMPDIR"), str(temporary)))
        tempfile.tempdir = str(temporary)
    os.environ.update(environment)
    if arguments.action == "run":
        if not command:
            parser.error("run requires -- followed by an executable and arguments")
        if arguments.build is not None:
            selected = build_paths(arguments.build)["generated"] / "build-toolchain.json"
            with measure_build(arguments.build, _command_step(command)) as timings:
                result = run_configured_command(
                    arguments.build, json.loads(selected.read_text(encoding="utf-8")), command, timings=timings
                )
        else:
            log = BuildLog(_command_step(command))
            log.debug(f"command: {command_line(command)}")
            result = run_command(command, cwd=REPO_ROOT, inherit_output=True)
            if result.returncode:
                log.error(f"exited with status {result.returncode} after {result.duration_seconds:.1f} s")
            else:
                log.verbose(f"finished in {result.duration_seconds:.1f} s")
        raise SystemExit(result.returncode)
    if arguments.build is None:
        parser.error("--build is required")
    if arguments.action in {"sdk", "provision", "product", "tools", "agent"} and arguments.inputs is None:
        parser.error("Shared actions require --inputs")
    build = arguments.build.resolve(strict=True)
    with measure_build(build, arguments.action) as timings:
        execute_action(build, arguments, timings)


def _command_step(command: list[str]) -> str:
    """Attribute a wrapped command to the module or program it runs."""
    if "-m" in command[:-1]:
        return command[command.index("-m") + 1].rsplit(".", 1)[-1]
    return Path(command[0]).stem.lower()


def execute_action(build: Path, arguments: argparse.Namespace, timings: BuildTimings) -> None:
    """Admit one stable producer generation and retain its phase durations."""
    paths = build_paths(build)
    identity_file = paths["generated"] / "identity.json"
    configured = json.loads((paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8"))
    arguments.target = json.loads(identity_file.read_text(encoding="utf-8"))["target"]
    if arguments.action in {"sdk", "provision", "product", "tools", "agent"}:
        if arguments.inputs is None:
            raise ValueError("Shared actions require --inputs")
        paths = build_paths(build)
        destination = paths[
            {"sdk": "python_sdk", "provision": "runtime", "tools": "tools", "product": "product", "agent": "agent"}[
                arguments.action
            ]
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
            timings.log.debug(f"input identity {identity}")
            with timings.phase("existing-output-inventory"):
                reason = staleness(destination, identity)
            if reason is None:
                timings.log.status(
                    f"up to date, reusing {display_path(destination)}: inputs and output inventory unchanged"
                )
                return
            timings.log.status(f"building ({reason}) -> {display_path(destination)}")
            (destination / "ready").unlink(missing_ok=True)
            started_ns = time.time_ns()
            with timings.phase("producer"):
                destination = build_action(build, arguments, timings=timings)
            with timings.phase("input-stability"):
                latest_target = json.loads(identity_file.read_text(encoding="utf-8"))["target"]
                latest_configured = json.loads(
                    (paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8")
                )
                latest_selected = action_toolchain(latest_configured, arguments.action, latest_target)
                if latest_target != arguments.target or latest_selected != selected:
                    raise RuntimeError(
                        f"The configured target or toolchain changed during {arguments.action}; "
                        "completion receipt refused"
                    )
                if admitted_identity() != identity:
                    changed = modified_inputs(
                        arguments.inputs, (*extra, Path(sys.executable), *selected_builder_inputs), started_ns
                    )
                    detail = (
                        f"{len(changed)} modified while it ran, first {display_path(changed[0])}"
                        if changed
                        else "no enrolled file was modified while it ran; the client build identity changed"
                    )
                    if arguments.action == "product":
                        # The wheels were built from the producer's isolated
                        # snapshot. Later checkout edits invalidate reuse, not
                        # those completed outputs. Give this receipt an identity
                        # that no checkout fingerprint can claim on a later run.
                        identity = hashlib.sha256(f"snapshot:{identity}:{time.time_ns()}".encode()).hexdigest()
                        timings.log.status(
                            f"Checkout changed during the product snapshot build ({detail}); "
                            "keeping the completed output without reusable checkout identity"
                        )
                    else:
                        raise RuntimeError(
                            f"Inputs changed during {arguments.action} ({detail}); completion receipt refused. "
                            "Build again once nothing edits the checkout."
                        )
            with timings.phase("output-inventory"):
                completed(destination, identity)
            timings.log.status(f"built {display_path(destination)}")
    else:
        timings.log.status(f"assembling the {arguments.config} payload")
        destination = build_action(build, arguments, timings=timings)
        (destination / "ready").write_text("complete\n", encoding="utf-8")


def _sync_base_dependencies(source: Path, product: Path) -> None:
    """Refresh only changed base wheels, retaining the separately owned product build."""
    from .hashing import digest

    destination = product / "dependencies"
    receipt = product / "base-dependencies.json"
    previous = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
    members: dict[str, str] = {}
    for member in sorted(source.rglob("*")):
        if member.is_symlink() or member.is_junction():
            raise ValueError("Base dependency closure contains a linked member")
        if not member.is_file():
            continue
        relative = member.relative_to(source).as_posix()
        identity = digest(member)
        members[relative] = identity
        target = destination / relative
        for ancestor in (target, *target.parents):
            if ancestor == product:
                break
            if ancestor.is_symlink() or ancestor.is_junction():
                raise ValueError("Base dependency destination contains a linked member")
        if not target.is_file() or digest(target) != identity:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(member, target)
    for relative, identity in previous.items():
        target = destination / relative
        if not target.resolve().is_relative_to(destination.resolve()):
            raise ValueError("Base dependency receipt escapes its owning directory")
        if relative not in members and target.is_file():
            if digest(target) != identity:
                raise ValueError(f"Obsolete base dependency changed outside its producer: {relative}")
            target.unlink()
    write_text(receipt, json.dumps(members, sort_keys=True) + "\n")


def build_action(build: Path, arguments: argparse.Namespace, *, timings: BuildTimings | None = None) -> Path:
    """Execute a generated-output action after its reuse and concurrency checks."""
    paths = build_paths(build)
    runtime = paths["runtime"]
    configured = json.loads((paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8"))
    contract = load_layout(arguments.target)
    sdk_root = paths.get("python_sdk", runtime)
    sdk = sdk_root / contract["sdk"]["root"]
    if arguments.action == "agent":
        if arguments.agent_source is None:
            raise ValueError("Agent construction requires the configured source folder")
        destination = paths["agent"]
        destination.mkdir(parents=True, exist_ok=True)
        build_agent(destination, arguments.agent_source, selected_uv(configured))
        tools = configured["desktop_tools"]
        build_agent_runtime(
            destination / "runtime",
            arguments.agent_source,
            arguments.target,
            node=Path(tools["node"]),
            npm_cli=Path(tools["npm_cli"]),
        )
    elif arguments.action == "sdk":
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
            inherit_output=True,
        )
        if result.returncode:
            raise RuntimeError(f"Installing the pinned build tools failed with exit status {result.returncode}")
    elif arguments.action == "provision":
        destination = reset(build, str(runtime.relative_to(build)))
        provision(
            destination,
            arguments.target,
            build_toolchain=configured,
            sdk=sdk if "python_sdk" in paths else None,
        )
    elif arguments.action == "product":
        destination = paths["product"]
        destination.mkdir(parents=True, exist_ok=True)
        _sync_base_dependencies(runtime / "dependencies", destination)
        build_product(
            destination / "build",
            Path(sys.executable),
            destination / "dependencies",
            arguments.target,
            inputs=arguments.inputs,
            build_toolchain=configured,
            timings=timings,
        )
        pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
        wheel = agent_wheel(paths["agent"])
        validate_wheel_dependencies(wheel, arguments.target, pin)
        if not installed_wheel_matches(wheel, destination / "dependencies"):
            result = run_command(
                [
                    selected_uv(configured),
                    "pip",
                    "install",
                    "--python",
                    sys.executable,
                    "--no-deps",
                    "--reinstall",
                    "--link-mode",
                    "copy",
                    "--target",
                    str(destination / "dependencies"),
                    str(wheel),
                ],
                cwd=REPO_ROOT,
            )
            if result.returncode:
                raise RuntimeError(result.stderr)
        write_text(destination / "agent-wheel.json", (paths["agent"] / "agent-wheel.json").read_text(encoding="utf-8"))
    else:
        if arguments.config is None:
            raise ValueError("assemble requires --config")
        if not arguments.without_user_docs and "user_docs_stage" not in paths:
            raise SystemExit(RECONFIGURE)
        quiesce(build, arguments.target)
        destination = paths["stage"] / arguments.config
        destination.mkdir(parents=True, exist_ok=True)
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
            agent_runtime=None if arguments.interpreter else paths["agent"] / "runtime",
            provenance={
                "runtime": {}
                if arguments.interpreter
                else json.loads((runtime / "runtime-inputs.json").read_text(encoding="utf-8")),
                "cohort_wheels": {}
                if arguments.interpreter
                else json.loads((paths["product"] / "build/product-wheels.json").read_text(encoding="utf-8")),
                "agent": {}
                if arguments.interpreter
                else json.loads((paths["product"] / "agent-wheel.json").read_text(encoding="utf-8")),
                "build_toolchain": json.loads(
                    (paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8")
                ),
            },
            timings=timings,
        )
    return destination


if __name__ == "__main__":
    main()
