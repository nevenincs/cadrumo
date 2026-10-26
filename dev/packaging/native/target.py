"""Translate canonical runtime targets to build-tool arguments."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dev._paths import REPO_ROOT

from ..runtime_wheelhouse_contract import target_platform


def toolchain_for_target(name: str, *, root: Path = REPO_ROOT) -> dict[str, Any]:
    """Select target SDK/toolchain pins without inheriting another target's binaries."""
    target_platform(name)
    tools = json.loads((root / "native/toolchain.json").read_text(encoding="utf-8"))
    targets = tools.pop("targets")
    selected = targets[name]
    if not selected.get("cpython_source") or not selected.get("cpython_sha256"):
        raise ValueError(f"CPython SDK source/trust pins are not enrolled for {name}")
    return tools | selected


def uv_platform(name: str) -> str:
    """Derive uv's platform spelling and floor from the runtime declaration."""
    target = target_platform(name)
    if target.sys_platform == "win32":
        return "x86_64-pc-windows-msvc"
    if target.sys_platform == "darwin":
        return "aarch64-apple-darwin"
    version = target.floor.removeprefix("glibc-").replace(".", "_")
    return f"{target.platform_machine}-manylinux_{version}"


def uv_environment(name: str) -> dict[str, str]:
    """Pin uv's macOS floor instead of inheriting its default or a host override."""
    target = target_platform(name)
    environment = dict(os.environ)
    if target.sys_platform == "darwin":
        environment["MACOSX_DEPLOYMENT_TARGET"] = target.floor.removeprefix("macos-")
    return environment
