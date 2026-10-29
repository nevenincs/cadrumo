"""Small build actions called by CMake; CMake owns their graph and output paths."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import cast

from dev._paths import REPO_ROOT


def _select_python_toolchain(
    selected: dict[str, object], pins: dict[str, object], configured: Mapping[str, object], action: str, target: str
) -> None:
    from ..runtime_wheel_selection import plan_target_wheels
    from .product import BUNDLED_EXTRAS

    selected["pins"] = {name: value for name, value in pins.items() if name.startswith("cpython_")}
    if action == "provision":
        python = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
        wheels = plan_target_wheels(REPO_ROOT, target, python, extras=BUNDLED_EXTRAS)
        selected["wheels"] = [asdict(wheel) for wheel in wheels]
    if action == "sdk" and "cpython_archive_decoder" in configured:
        selected["cpython_archive_decoder"] = configured["cpython_archive_decoder"]


def _select_agent_toolchain(
    selected: dict[str, object], configured: Mapping[str, object], files: dict[str, object]
) -> None:
    tools = configured.get("desktop_tools")
    if not isinstance(tools, dict) or not all(
        isinstance(cast(dict[str, object], tools).get(name), str) for name in ("node", "npm_cli")
    ):
        raise ValueError("Agent runtime construction requires configured Node/npm builders; reconfigure CMake")
    tools = cast(dict[str, object], tools)
    selected["node"] = tools["node"]
    selected["npm_cli"] = tools["npm_cli"]
    selected["builder_files"] = {
        name: record
        for name, record in files.items()
        if name in {"CADRUMO_UV", "desktop/node", "desktop/npm-cli", "desktop/npm-package"}
    }


def action_toolchain(configured: Mapping[str, object], action: str, target: str) -> dict[str, object]:
    """Select only producers and pins consumed by this action, not desktop inputs."""
    from .target import toolchain_for_target

    files = configured.get("builder_files", {})
    if not isinstance(files, dict):
        raise ValueError("Configured builder_files must be a mapping")
    files = cast(dict[str, object], files)
    selected: dict[str, object] = {
        "builder_files": {name: record for name, record in files.items() if name == "CADRUMO_UV" and action != "sdk"}
    }
    pins = toolchain_for_target(target)
    if action in {"sdk", "provision"}:
        _select_python_toolchain(selected, pins, configured, action, target)
    elif action == "tools":
        selected["pins"] = {"resvg_py": pins["resvg_py"]}
    elif action == "agent":
        _select_agent_toolchain(selected, configured, files)
    elif action != "product":
        raise ValueError(f"No shared producer selection for {action}")
    # Product wheels use Hatchling's Python/data hooks; native compilers and SDKs
    # never produce their contents. CMake enrolls their declared sources/backend,
    # and the action caller hashes the admitted Python executable.
    return selected
