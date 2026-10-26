"""Small build actions called by CMake; CMake owns their graph and output paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path

from dev._paths import REPO_ROOT

from ..command_execution import CommandResult, run_command
from .action_cache import action_lock, completed, fingerprint, modified_inputs, receipt_staleness, staleness
from .build_directory import require_enrolled_build
from .build_log import BuildLog, command_line, display_path
from .build_paths import build_paths
from .build_stamp import (
    ACTION_COMPONENTS,
    SETTLED,
    action_identity,
    begin_record,
    build_type,
    built_current,
    image_environment,
    native_settled,
    read_record,
    record_built,
    resolve,
    settle_record,
)
from .build_timing import BuildTimings, measure_build
from .build_toolchain import builder_inputs, native_toolchain_identity, selected_uv
from .hashing import digest, digest_cache
from .stable_output import write_text
from .stage_reuse import record_reuse


def action_toolchain(configured: Mapping[str, object], action: str, target: str) -> dict[str, object]:
    """Select only producers and pins consumed by this action, not desktop inputs."""
    from ..runtime_wheel_selection import plan_target_wheels
    from .product import BUNDLED_EXTRAS
    from .target import toolchain_for_target

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


def owned(build: Path, relative: str) -> Path:
    """Return a generated directory inside this CMake binary directory, creating it if missing."""
    build = build.resolve(strict=True)
    destination = (build / relative).resolve()
    if build == REPO_ROOT or destination == build or not destination.is_relative_to(build):
        raise ValueError("Refusing a generated-directory operation outside the CMake binary directory")
    destination.mkdir(parents=True, exist_ok=True)
    return destination


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
    # CMake's own C compile and link flags reach only the targets CMake compiles; Cargo never
    # reads them, so a change to them must not clean the Cargo directory.
    cmake_flags = re.compile(r"CMAKE_C_FLAGS(_.+)?|CMAKE_[A-Z]+_LINKER_FLAGS(_.+)?")
    target_configuration = configured.get("target_configuration", {})
    identity = native_toolchain_identity(
        {
            **configured,
            "target_configuration": {
                name: value
                for name, value in (target_configuration.items() if isinstance(target_configuration, dict) else ())
                if not cmake_flags.fullmatch(str(name))
            },
        }
    )
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
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--config", choices=("Debug", "Release"))
    parser.add_argument("--env", action="append", default=[])
    # Names the component image this Cargo command builds and exports that component's identity
    # (CADRUMO_<COMPONENT>_BUILD_*). Crates linked into it as libraries consume none, so an
    # unchanged component, or another component's change, rebuilds nothing.
    parser.add_argument("--build-identity", metavar="COMPONENT")
    # Skips the command when it last built ARTIFACT from COMPONENT's current fingerprint: the
    # fingerprint covers every input of the image, so the driver would only confirm it.
    parser.add_argument("--reuse-built", nargs=2, metavar=("COMPONENT", "ARTIFACT"))
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
    if arguments.build_identity is not None:
        resolved = resolve(arguments.build, [arguments.build_identity], configuration=arguments.config)
        environment.update(image_environment(resolved[arguments.build_identity]))
    os.environ.update(environment)
    if arguments.action == "run":
        if not command:
            parser.error("run requires -- followed by an executable and arguments")
        reuse = arguments.reuse_built
        if reuse is not None:
            if arguments.config is None:
                parser.error("--reuse-built requires --config")
            if built_current(arguments.build, reuse[0], arguments.config, Path(reuse[1]), command):
                BuildLog(_command_step(command)).status(
                    f"up to date, reusing {display_path(Path(reuse[1]))}: built from the current {reuse[0]} fingerprint"
                )
                raise SystemExit(0)
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
        if result.returncode == 0 and arguments.build_identity is not None and command[1:2] in (["build"], ["rustc"]):
            # The component's images are compiled; staging adds what it ships of them.
            component = arguments.build_identity
            settled = native_settled(arguments.build, [component], configuration=arguments.config)[component]
            settle_record(arguments.build, component, settled=settled)
        if result.returncode == 0 and reuse is not None:
            record_built(arguments.build, reuse[0], str(arguments.config), Path(reuse[1]), command)
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


def action_inventory(build: Path, inputs: Path, extra: tuple[Path, ...], selection: object) -> dict[str, str]:
    """Hash each input a payload producer admits, by absolute path, plus its tool selection.

    The keys are the files :func:`.action_cache.fingerprint` reads for the producer's identity,
    so a reader can name exactly which of them changed since the recorded build.
    """
    paths = {*map(Path, inputs.read_text(encoding="utf-8").splitlines()), *extra}
    with digest_cache(build):
        entries = {path.resolve().as_posix(): digest(path) if path.is_file() else "missing" for path in sorted(paths)}
    entries["@selection"] = hashlib.sha256(json.dumps(selection, sort_keys=True).encode("utf-8")).hexdigest()
    return entries


def execute_action(build: Path, arguments: argparse.Namespace, timings: BuildTimings) -> None:
    """Admit one stable producer generation and retain its phase durations."""
    from ..authority_staging import selected_published_authority
    from ..google_oauth import build_client_json, client_build_identity

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
        # One digest cache serves the input fingerprint, the reuse checks and the stability recheck.
        with action_lock(build, "shared-inputs", timings=timings), digest_cache(build):

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
            # The Python payload producers keep build records beside the native components.
            component = ACTION_COMPONENTS.get(arguments.action)
            if component is not None:
                # The receipt was written for exactly these inputs and the settled record of that
                # build still matches every artifact it staged: nothing to rebuild or re-read.
                with timings.phase("record-currency"):
                    unproven = receipt_staleness(destination, identity) or record_reuse(build, component, identity)
                if unproven is None:
                    timings.log.status(
                        f"up to date, reusing {display_path(destination)}: "
                        f"inputs unchanged and the settled {component} record matches its staged artifacts"
                    )
                    return
                timings.log.verbose(f"verifying every output: {unproven}")
            with timings.phase("existing-output-inventory"):
                reason = staleness(destination, identity)
            enrolled = (*extra, Path(sys.executable), *selected_builder_inputs)
            selection = [arguments.target, selected]
            if reason is None:
                if component is not None:
                    record = read_record(build, component)
                    if record is None or record["fingerprint"] != identity or record["state"] != SETTLED:
                        # The receipt proves these outputs were built from exactly these inputs.
                        begin_record(
                            build,
                            action_identity(build, arguments.action, identity),
                            action_inventory(build, arguments.inputs, enrolled, selection),
                        )
                        settle_record(build, component, settled=True)
                timings.log.status(
                    f"up to date, reusing {display_path(destination)}: inputs and output inventory unchanged"
                )
                return
            if component is not None:
                begin_record(
                    build,
                    action_identity(build, arguments.action, identity),
                    action_inventory(build, arguments.inputs, enrolled, selection),
                )
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
                    if component is not None:
                        settle_record(build, component, settled=False)
                    raise RuntimeError(
                        f"The configured target or toolchain changed during {arguments.action}; "
                        "completion receipt refused"
                    )
                settled = admitted_identity() == identity
                if not settled:
                    if component is not None:
                        settle_record(build, component, settled=False)
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
            if component is not None and settled:
                settle_record(build, component, settled=True)
            timings.log.status(f"built {display_path(destination)}")
    else:
        timings.log.status(f"assembling the {arguments.config} payload")
        destination = build_action(build, arguments, timings=timings)
        (destination / "ready").write_text("complete\n", encoding="utf-8")


def _sync_base_dependencies(source: Path, product: Path) -> None:
    """Refresh only changed base wheels, retaining the separately owned product build."""
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
    _remove_empty_directories(destination)
    write_text(receipt, json.dumps(members, sort_keys=True) + "\n")


def _remove_empty_directories(root: Path) -> None:
    """Remove directories a replaced distribution left empty, deepest first.

    An emptied ``*.dist-info`` directory (one that kept only a ``licenses`` folder, or
    nothing) is still discovered as an installed distribution without metadata, so the
    staged closure must not keep it. No installed payload is an empty directory.
    """
    directories = [path for path in root.rglob("*") if path.is_dir()]
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        if directory.is_symlink() or directory.is_junction():
            raise ValueError("Base dependency destination contains a linked member")
        if not any(directory.iterdir()):
            directory.rmdir()


def build_action(build: Path, arguments: argparse.Namespace, *, timings: BuildTimings | None = None) -> Path:
    """Execute a generated-output action after its reuse and concurrency checks."""
    from ..wheel_metadata import installed_wheel_matches
    from .agent import agent_wheel, build_agent, gate_agent_dependencies, validate_wheel_dependencies
    from .agent_runtime import build_agent_runtime
    from .assemble import assemble, image_artifact
    from .docs_stage import RECONFIGURE
    from .layout import backend, load_layout
    from .process_quiescence import quiesce
    from .product import build_product
    from .provision import provision, provisioning_tools

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
        gate_agent_dependencies(destination, arguments.agent_source, arguments.target, selected_uv(configured))
        tools = configured["desktop_tools"]
        build_agent_runtime(
            destination / "runtime",
            arguments.agent_source,
            arguments.target,
            node=Path(tools["node"]),
            npm_cli=Path(tools["npm_cli"]),
        )
    elif arguments.action == "sdk":
        # The backend reconciles the SDK in place; the archive download is kept.
        destination = owned(build, str(sdk_root.relative_to(build)))
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
            agent_dependencies=paths["agent"],
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
        validate_wheel_dependencies(wheel, arguments.target, pin, paths["agent"])
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
            paths["generated"] / arguments.config / "build.json",
            None if arguments.without_user_docs else paths["user_docs_stage"],
            images=dict(image_artifact(item) for item in arguments.image),
            binary_dir=build,
            build_type=build_type(arguments.config),
            development=arguments.development,
            interpreter=arguments.interpreter,
            target=arguments.target,
            agent_runtime=None if arguments.interpreter else paths["agent"] / "runtime",
            agent_dependencies=None if arguments.interpreter else paths["agent"],
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
