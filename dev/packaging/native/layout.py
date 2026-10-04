"""Resolve the canonical package contract and its explicitly implemented platform."""

from __future__ import annotations

import importlib
import json
import platform
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT

# Entrypoint names reach C string literals, CMake target names and Python source.
_ENTRYPOINT_NAME = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*")


def load_layout(name: str | None = None, *, root: Path = REPO_ROOT) -> dict[str, Any]:
    """Combine shared locations with one implemented platform's physical mapping."""
    if name is None:
        machine = platform.machine().lower()
        architecture = {"amd64": "x64", "x86_64": "x64"}.get(machine, machine)
        name = f"{ {'win32': 'windows', 'darwin': 'macos'}.get(sys.platform, sys.platform) }-{architecture}"
    shared = json.loads((root / "native/package-layout.json").read_text(encoding="utf-8"))
    mapping = shared.pop("platforms")
    if name not in mapping:
        raise NotImplementedError(f"Native packaging is not implemented for {name}")
    selected = json.loads((root / "native" / mapping[name]).read_text(encoding="utf-8"))
    for key in ("paths", "files"):
        shared[key].update(selected.pop(key))
    shared.update(selected)
    scripts = parse_toml((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    for entrypoint in shared["entrypoints"]:
        if not _ENTRYPOINT_NAME.fullmatch(entrypoint) or entrypoint not in scripts:
            raise ValueError(f"Native entrypoint is not a declared console script: {entrypoint}")
    return shared


def entrypoint_files(layout: dict[str, Any]) -> dict[str, str]:
    """Map each declared console entrypoint to its package-relative executable in the native directory."""
    native = layout["paths"]["native"]
    return {name: f"{native}/{name}{layout['entrypoint_suffix']}" for name in layout["entrypoints"]}


def backend(contract: dict[str, Any]) -> ModuleType:
    """Select only an enrolled backend from the canonical contract."""
    name = contract["backend"]
    if name != "windows":
        raise ValueError("Native backend has no implemented enrollment")
    return importlib.import_module("dev.packaging.native.platforms.windows")
