"""Bind package release claims to separately generated build expectations."""

from __future__ import annotations

from typing import Any


def verify_release(manifest: dict[str, Any], expected: dict[str, Any]) -> None:
    """Refuse target, ABI, interpreter or cohort claims that differ from build inputs."""
    for key in ("target", "python", "version", "channel"):
        if manifest["build"][key] != expected[key]:
            raise ValueError(f"Package release {key} differs from configured build")
    if manifest["python"] != expected["python"]:
        raise ValueError("Package interpreter differs from configured build")
    for key in ("platform", "abi"):
        if manifest["layout"][key] != expected[key]:
            raise ValueError(f"Package layout {key} differs from configured build")
    for name in expected["cohort"]:
        if manifest["distributions"].get(name) != expected["version"]:
            raise ValueError(f"Package cohort differs from configured build: {name}")
