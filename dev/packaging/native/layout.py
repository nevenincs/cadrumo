"""Resolve the canonical package contract and its explicitly implemented platform."""

from __future__ import annotations

import importlib
import json
import platform
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from dev._paths import REPO_ROOT


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
    return shared


def backend(contract: dict[str, Any]) -> ModuleType:
    """Select only an enrolled backend from the canonical contract."""
    name = contract["backend"]
    if not name.isidentifier():
        raise ValueError("Invalid native backend name")
    return importlib.import_module(f"{__package__}.platforms.{name}")
