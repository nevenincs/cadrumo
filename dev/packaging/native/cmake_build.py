"""Small build actions called by CMake; CMake owns their graph and output paths."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from cadrumo.core.storage_environment import prepare_temporary_directory, tool_storage_environment
from dev._paths import REPO_ROOT

from ..authority_staging import selected_published_authority
from ..command_execution import run_command
from .action_cache import action_lock, completed, current, fingerprint
from .assemble import assemble
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


def main() -> None:
    """Run one CMake action with scoped development-tool storage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("provision", "product", "assemble", "run", "tools"))
    parser.add_argument("--build", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--config", choices=("Debug", "Release"))
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--development", action="store_true")
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
        result = run_command(command, cwd=REPO_ROOT)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    if arguments.build is None:
        parser.error("--build is required")
    build = arguments.build.resolve(strict=True)
    if arguments.action in {"provision", "product", "tools"}:
        if arguments.inputs is None:
            parser.error("Shared actions require --inputs")
        relative = {"provision": "_deps/runtime", "tools": "_deps/build-tools", "product": "product"}[arguments.action]
        extra = selected_published_authority(REPO_ROOT) if arguments.action == "product" else ()
        with action_lock(build, "shared-inputs"):
            identity = fingerprint(arguments.inputs, extra)
            if current(build / relative, identity):
                print(f"Reusing {arguments.action}: inputs and output inventory unchanged")
                return
            destination = build_action(build, arguments)
            completed(destination, identity)
    else:
        destination = build_action(build, arguments)
        (destination / "ready").write_text("complete\n", encoding="utf-8")


def build_action(build: Path, arguments: argparse.Namespace) -> Path:
    """Execute a generated-output action after its reuse and concurrency checks."""
    runtime = build / "_deps/runtime"
    contract = load_layout()
    sdk = runtime / contract["sdk"]["root"]
    if arguments.action == "tools":
        destination = reset(build, "_deps/build-tools")
        uv = shutil.which("uv")
        if uv is None:
            raise FileNotFoundError("uv is required")
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
        destination = reset(build, "_deps/runtime")
        provision(destination)
    elif arguments.action == "product":
        destination = reset(build, "product")
        destination.mkdir(parents=True)
        shutil.copytree(runtime / "dependencies", destination / "dependencies")
        build_product(destination / "build", sdk / contract["sdk"]["executable"], destination / "dependencies")
    else:
        if arguments.config is None:
            raise ValueError("assemble requires --config")
        destination = reset(build, f"stage/{arguments.config}")
        assemble(
            sdk,
            build / "product/dependencies",
            build / "bin" / arguments.config,
            destination / "app",
            build / "generated/build.json",
            development=arguments.development,
        )
    return destination


if __name__ == "__main__":
    main()
