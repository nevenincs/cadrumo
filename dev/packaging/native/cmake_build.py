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
from collections.abc import Callable
from pathlib import Path
from typing import cast

from dev._paths import REPO_ROOT

from ..command_execution import CommandResult, run_command
from .action_cache import action_lock, completed, fingerprint, modified_inputs, receipt_staleness, staleness
from .action_selection import action_toolchain
from .base_dependencies import sync_base_dependencies
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
from .build_toolchain import builder_inputs, selected_uv
from .cargo_command import run_configured_command
from .hashing import digest, digest_cache
from .stable_output import write_text
from .stage_reuse import record_reuse


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


def _run_unenrolled(command: list[str]) -> CommandResult:
    log = BuildLog(_command_step(command))
    log.debug(f"command: {command_line(command)}")
    result = run_command(command, cwd=REPO_ROOT, inherit_output=True)
    if result.returncode:
        log.error(f"exited with status {result.returncode} after {result.duration_seconds:.1f} s")
    else:
        log.verbose(f"finished in {result.duration_seconds:.1f} s")
    return result


def _record_command_result(
    arguments: argparse.Namespace, command: list[str], result: CommandResult, reuse: list[str] | None
) -> None:
    if result.returncode == 0 and arguments.build_identity is not None and command[1:2] in (["build"], ["rustc"]):
        # The component's images are compiled; staging adds what it ships of them.
        component = arguments.build_identity
        settled = native_settled(arguments.build, [component], configuration=arguments.config)[component]
        settle_record(arguments.build, component, settled=settled)
    if result.returncode == 0 and reuse is not None:
        record_built(arguments.build, reuse[0], str(arguments.config), Path(reuse[1]), command)


def _run_command_action(parser: argparse.ArgumentParser, arguments: argparse.Namespace, command: list[str]) -> None:
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
        result = _run_unenrolled(command)
    _record_command_result(arguments, command, result, reuse)
    raise SystemExit(result.returncode)


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
        resolved = resolve(cast(Path, arguments.build), [arguments.build_identity], configuration=arguments.config)
        environment.update(image_environment(resolved[arguments.build_identity]))
    os.environ.update(environment)
    if arguments.action == "run":
        _run_command_action(parser, arguments, command)
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


def _check_input_stability(
    build: Path,
    arguments: argparse.Namespace,
    timings: BuildTimings,
    identity_file: Path,
    paths: dict[str, Path],
    selected: dict[str, object],
    component: str | None,
    admitted_identity: Callable[[], str],
    identity: str,
    extra: tuple[Path, ...],
    selected_builder_inputs: tuple[Path, ...],
    started_ns: int,
) -> tuple[str, bool]:
    with timings.phase("input-stability"):
        latest_target = json.loads(identity_file.read_text(encoding="utf-8"))["target"]
        latest_configured = json.loads((paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8"))
        latest_selected = action_toolchain(latest_configured, arguments.action, latest_target)
        if latest_target != arguments.target or latest_selected != selected:
            if component is not None:
                settle_record(build, component, settled=False)
            raise RuntimeError(
                f"The configured target or toolchain changed during {arguments.action}; completion receipt refused"
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
    return identity, settled


def _record_current_output(
    build: Path,
    arguments: argparse.Namespace,
    component: str | None,
    identity: str,
    enrolled: tuple[Path, ...],
    selection: list[object],
) -> None:
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


def _execute_shared_action(
    build: Path,
    arguments: argparse.Namespace,
    timings: BuildTimings,
    identity_file: Path,
    configured: dict[str, object],
) -> None:
    from ..authority_staging import selected_published_authority
    from ..google_oauth import build_client_json, client_build_identity

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
        selection: list[object] = [arguments.target, selected]
        if reason is None:
            _record_current_output(build, arguments, component, identity, enrolled, selection)
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
        identity, settled = _check_input_stability(
            build,
            arguments,
            timings,
            identity_file,
            paths,
            selected,
            component,
            admitted_identity,
            identity,
            extra,
            selected_builder_inputs,
            started_ns,
        )
        with timings.phase("output-inventory"):
            completed(destination, identity)
        if component is not None and settled:
            settle_record(build, component, settled=True)
        timings.log.status(f"built {display_path(destination)}")


def execute_action(build: Path, arguments: argparse.Namespace, timings: BuildTimings) -> None:
    """Admit one stable producer generation and retain its phase durations."""
    paths = build_paths(build)
    identity_file = paths["generated"] / "identity.json"
    configured = json.loads((paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8"))
    arguments.target = json.loads(identity_file.read_text(encoding="utf-8"))["target"]
    if arguments.action in {"sdk", "provision", "product", "tools", "agent"}:
        _execute_shared_action(build, arguments, timings, identity_file, configured)
    else:
        timings.log.status(f"assembling the {arguments.config} payload")
        destination = build_action(build, arguments, timings=timings)
        (destination / "ready").write_text("complete\n", encoding="utf-8")


def _assembly_provenance(paths: dict[str, Path], runtime: Path, interpreter: bool) -> dict[str, object]:
    return {
        "runtime": {} if interpreter else json.loads((runtime / "runtime-inputs.json").read_text(encoding="utf-8")),
        "cohort_wheels": {}
        if interpreter
        else json.loads((paths["product"] / "build/product-wheels.json").read_text(encoding="utf-8")),
        "agent": {} if interpreter else json.loads((paths["product"] / "agent-wheel.json").read_text(encoding="utf-8")),
        "build_toolchain": json.loads((paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8")),
    }


def _assemble_action(
    build: Path,
    arguments: argparse.Namespace,
    timings: BuildTimings | None,
    paths: dict[str, Path],
    runtime: Path,
    sdk: Path,
) -> Path:
    from .assemble import assemble
    from .assembly_images import image_artifact
    from .docs_stage import RECONFIGURE
    from .process_quiescence import quiesce

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
        provenance=_assembly_provenance(paths, runtime, arguments.interpreter),
        timings=timings,
    )
    return destination


def _build_sdk(
    build: Path,
    arguments: argparse.Namespace,
    configured: dict[str, object],
    contract: dict[str, object],
    sdk_root: Path,
    sdk: Path,
) -> Path:
    from .layout import backend
    from .provision import provisioning_tools

    # The backend reconciles the SDK in place; the archive download is kept.
    destination = owned(build, str(sdk_root.relative_to(build)))
    pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    produced = backend(contract).provision_sdk(
        destination, pin, provisioning_tools(arguments.target, configured), contract
    )
    if produced.resolve() != sdk.resolve():
        raise ValueError("SDK backend output differs from the declared SDK root")
    return destination


def _require_tools_installed(result: CommandResult) -> None:
    if result.returncode:
        raise RuntimeError(f"Installing the pinned build tools failed with exit status {result.returncode}")


def build_action(build: Path, arguments: argparse.Namespace, *, timings: BuildTimings | None = None) -> Path:
    """Execute a generated-output action after its reuse and concurrency checks."""
    from ..wheel_metadata import installed_wheel_matches
    from .agent import agent_wheel, build_agent, gate_agent_dependencies, validate_wheel_dependencies
    from .agent_runtime import build_agent_runtime
    from .layout import load_layout
    from .product import build_product
    from .provision import provision

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
        destination = _build_sdk(build, arguments, configured, contract, sdk_root, sdk)
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
        _require_tools_installed(result)
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
        sync_base_dependencies(runtime / "dependencies", destination)
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
        destination = _assemble_action(build, arguments, timings, paths, runtime, sdk)
    return destination


if __name__ == "__main__":
    main()
