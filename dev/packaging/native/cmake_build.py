"""Small build actions called by CMake; CMake owns their graph and output paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from cadrumo.core.storage_environment import prepare_temporary_directory, tool_storage_environment
from dev._paths import REPO_ROOT

from ..authority_staging import selected_published_authority
from ..command_execution import CommandResult, run_command
from ..google_oauth import build_client_json, client_build_identity
from .action_cache import action_lock, completed, current, fingerprint
from .assemble import assemble, image_artifact
from .build_paths import build_paths
from .build_toolchain import builder_inputs, native_toolchain_identity, selected_uv
from .docs_stage import RECONFIGURE
from .layout import load_layout
from .product import build_product
from .provision import provision


def reset(build: Path, relative: str) -> Path:
    """Replace only a named generated subtree inside this CMake binary directory."""
    build = build.resolve(strict=True)
    destination = (build / relative).resolve()
    if build == REPO_ROOT or destination == build or not destination.is_relative_to(build):
        raise ValueError("Refusing a generated-directory operation outside the CMake binary directory")
    if destination.exists():
        shutil.rmtree(destination)
    return destination


def run_configured_command(build: Path, configured: dict[str, object], command: list[str]) -> CommandResult:
    """Invalidate only the isolated native Cargo cache when selected producer bytes change."""
    builder_inputs(configured)
    if Path(command[0]).name.lower() not in {"cargo", "cargo.exe"} or command[1:2] not in (
        ["build"],
        ["test"],
        ["check"],
        ["run"],
        ["clippy"],
        ["rustc"],
    ):
        return run_command(command, cwd=REPO_ROOT)
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
    with action_lock(build, "native-cargo"):
        if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != identity:
            clean = [command[0], "clean", "--target-dir", str(directory)]
            if "--manifest-path" in command:
                clean.extend(["--manifest-path", command[command.index("--manifest-path") + 1]])
            result = run_command(clean, cwd=REPO_ROOT)
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            if result.returncode:
                return result
        result = run_command(command, cwd=REPO_ROOT)
        if result.returncode == 0:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(identity + "\n", encoding="utf-8")
        return result


def main() -> None:
    """Run one CMake action with scoped development-tool storage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("provision", "product", "assemble", "run", "tools"))
    parser.add_argument("--build", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--config", choices=("Debug", "Release"))
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--development", action="store_true")
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
            result = run_configured_command(arguments.build, json.loads(selected.read_text(encoding="utf-8")), command)
        else:
            result = run_command(command, cwd=REPO_ROOT)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    if arguments.build is None:
        parser.error("--build is required")
    build = arguments.build.resolve(strict=True)
    paths = build_paths(build)
    identity_file = paths["generated"] / "identity.json"
    configured = json.loads((paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8"))
    selected_builder_inputs = builder_inputs(configured)
    arguments.target = json.loads(identity_file.read_text(encoding="utf-8"))["target"]
    if arguments.action in {"provision", "product", "tools"}:
        if arguments.inputs is None:
            parser.error("Shared actions require --inputs")
        paths = build_paths(build)
        destination = paths[{"provision": "runtime", "tools": "tools", "product": "product"}[arguments.action]]
        extra = selected_published_authority(REPO_ROOT) if arguments.action == "product" else ()
        with action_lock(build, "shared-inputs"):
            identity = fingerprint(
                arguments.inputs, (*extra, identity_file, Path(sys.executable), *selected_builder_inputs)
            )
            if arguments.action == "product":
                identity = client_build_identity(identity, build_client_json(REPO_ROOT))
            if current(destination, identity):
                print(f"Reusing {arguments.action}: inputs and output inventory unchanged")
                return
            destination = build_action(build, arguments)
            completed(destination, identity)
    else:
        destination = build_action(build, arguments)
        (destination / "ready").write_text("complete\n", encoding="utf-8")


def build_action(build: Path, arguments: argparse.Namespace) -> Path:
    """Execute a generated-output action after its reuse and concurrency checks."""
    paths = build_paths(build)
    runtime = paths["runtime"]
    configured = json.loads((paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8"))
    contract = load_layout(arguments.target)
    sdk = runtime / contract["sdk"]["root"]
    if arguments.action == "tools":
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
        )
    else:
        if arguments.config is None:
            raise ValueError("assemble requires --config")
        if not arguments.without_user_docs and "user_docs_stage" not in paths:
            raise SystemExit(RECONFIGURE)
        destination = reset(build, str((paths["stage"] / arguments.config).relative_to(build)))
        assemble(
            sdk,
            paths["product"] / "dependencies",
            paths["bin"] / arguments.config,
            destination / "app",
            paths["generated"] / "build.json",
            None if arguments.without_user_docs else paths["user_docs_stage"],
            images=dict(image_artifact(item) for item in arguments.image),
            binary_dir=build,
            development=arguments.development,
            target=arguments.target,
            provenance={
                "runtime": json.loads((runtime / "runtime-inputs.json").read_text(encoding="utf-8")),
                "cohort_wheels": json.loads(
                    (paths["product"] / "build/product-wheels.json").read_text(encoding="utf-8")
                ),
                "build_toolchain": json.loads(
                    (paths["generated"] / "build-toolchain.json").read_text(encoding="utf-8")
                ),
            },
        )
    return destination


if __name__ == "__main__":
    main()
