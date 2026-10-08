"""Resolve installed script targets and dispatch their packaged native launchers."""

from __future__ import annotations

import importlib.metadata
import re
import subprocess
from collections.abc import Collection
from pathlib import Path


def declared_entrypoints(
    distribution: importlib.metadata.Distribution, declared: Collection[str]
) -> tuple[importlib.metadata.EntryPoint, ...]:
    """Reject metadata that cannot implement the canonical layout's script names."""
    entries = tuple(entry for entry in distribution.entry_points if entry.group == "console_scripts")
    names = [entry.name for entry in entries]
    if len(names) != len(set(names)):
        raise AssertionError("Installed console script metadata has duplicate names")
    if set(names) != set(declared):
        raise AssertionError(f"Installed console scripts differ from the package layout: {names}")
    for entry in entries:
        try:
            target = entry.load()
        except BaseException as error:
            # A target import must not exit the acceptance process successfully.
            raise AssertionError(f"Installed console script cannot resolve: {entry.name} -> {entry.value}") from error
        if not callable(target):
            raise AssertionError(f"Installed console script target is not callable: {entry.name} -> {entry.value}")
    return entries


def verify_entrypoints(root: Path, names: Collection[str], native: str, suffix: str) -> None:
    """Use shipped metadata and native images, under the packaged interpreter's environment."""
    entries = declared_entrypoints(importlib.metadata.distribution("cadrumo"), names)
    for entry in entries:
        image = root / native / f"{entry.name}{suffix}"
        result = subprocess.run(  # noqa: S603 -- canonical package entrypoint, no shell.
            [str(image), "--help"], cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60, check=False
        )
        if entry.name == "aeat":
            # AEAT renders its own localized root document rather than argparse usage.
            help_dispatched = result.stdout.lstrip().casefold().startswith("cadrumo") and all(
                marker in result.stdout
                for marker in (
                    "aeat config",
                    "aeat app",
                    "--profile-secrets-stdin",
                    "--profile-secrets-fd",
                    "--profile-auth-method",
                    "--profile-credential-ref",
                )
            )
        else:
            help_dispatched = bool(re.search(rf"(?m)^usage:\s+{re.escape(entry.name)}\b", result.stdout))
        if result.returncode != 0 or not help_dispatched:
            raise AssertionError(
                f"Packaged console script did not dispatch help: {image}\n{result.stdout}{result.stderr}"
            )
