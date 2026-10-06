"""Acquire the platform runtime and install the locked production dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from ..runtime_wheel_selection import plan_target_wheels
from .build_toolchain import selected_uv
from .hashing import digest
from .layout import backend, load_layout
from .target import toolchain_for_target, uv_environment, uv_platform


def provisioning_tools(target: str, build_toolchain: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project an admitted builder decoder without changing the reviewed target pins."""
    tools = toolchain_for_target(target)
    if tools.get("cpython_archive_format") != "tar.zst":
        return tools
    if build_toolchain is None or build_toolchain.get("CADRUMO_TARGET") != target:
        raise ValueError("SDK archive provisioning requires the selected target's explicit build toolchain")
    decoder = build_toolchain.get("cpython_archive_decoder")
    if not isinstance(decoder, dict):
        raise ValueError("SDK archive provisioning requires an explicit builder decoder")
    if decoder.get("provenance") != tools.get("cpython_archive_decoder_provenance"):
        raise ValueError("SDK archive decoder provenance differs from the reviewed source pin")
    executable = decoder.get("executable")
    if not isinstance(executable, str) or not Path(executable).is_absolute() or not Path(executable).is_file():
        raise ValueError("SDK archive decoder requires an existing absolute builder executable")
    if digest(Path(executable)) != decoder.get("sha256"):
        raise ValueError("SDK archive decoder differs from its configured content identity")
    return dict(tools, cpython_archive_decoder=decoder)


def provision(
    destination: Path,
    target: str,
    *,
    build_toolchain: Mapping[str, Any] | None = None,
    uv_executable: Path | None = None,
) -> None:
    """Download one verified SDK and install the repository's base closure."""
    destination = destination.resolve()
    uv = selected_uv(build_toolchain, executable=uv_executable)
    destination.mkdir(parents=True, exist_ok=True)
    pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    tools = provisioning_tools(target, build_toolchain)
    contract = load_layout(target)
    wheels = plan_target_wheels(REPO_ROOT, target, pin)
    sdk = backend(contract).provision_sdk(destination, pin, tools, contract)
    if sdk.resolve() != (destination / contract["sdk"]["root"]).resolve():
        raise ValueError("SDK backend output differs from the declared SDK root")
    requirements = destination / "requirements.txt"
    requirements.write_text(
        "".join(f"{wheel.distribution} @ {wheel.url} --hash=sha256:{wheel.sha256}\n" for wheel in wheels),
        encoding="utf-8",
    )
    dependencies = destination / "dependencies"
    if dependencies.exists():
        raise FileExistsError("Use a fresh dependency destination")
    result = run_command(
        [
            uv,
            "pip",
            "install",
            "--python",
            sys.executable,
            "--python-version",
            pin,
            "--python-platform",
            uv_platform(target),
            "--require-hashes",
            "--no-config",
            "--target",
            str(dependencies),
            "--only-binary",
            ":all:",
            "--no-deps",
            "--link-mode",
            "copy",
            "-r",
            str(requirements),
        ],
        cwd=REPO_ROOT,
        environment=uv_environment(target),
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    (destination / "runtime-inputs.json").write_text(
        json.dumps(
            {
                "target": target,
                "python": pin,
                "lock_sha256": digest(REPO_ROOT / "uv.lock"),
                "toolchain": tools,
                "wheels": [asdict(wheel) for wheel in wheels],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--uv", type=Path, help="Explicit uv executable for a standalone invocation")
    parser.add_argument(
        "--build-toolchain", type=Path, help="Explicit builder toolchain JSON, required for tar.zst SDKs"
    )
    args = parser.parse_args()
    build_toolchain = None
    if args.build_toolchain is not None:
        build_toolchain = json.loads(args.build_toolchain.read_text(encoding="utf-8"))
        if not isinstance(build_toolchain, dict):
            parser.error("build toolchain must be a JSON object")
    provision(args.destination, args.target, build_toolchain=build_toolchain, uv_executable=args.uv)
