"""Expand a package manifest's delegated inventories into one checked file inventory."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .hashing import digest

DELEGATED_INVENTORIES = "delegated_inventories"
# The manifest's explicit statement of whether the user documentation tree ships.
USER_DOCS = "user_docs"
_RESERVED_STEM = re.compile(r"(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])")


def checked_member(relative: str) -> str:
    """Return a portable package-relative path, refusing every escape or platform alias."""
    if (
        not relative
        or any(character in relative for character in "\\:")
        or any(ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F for character in relative)
    ):
        raise ValueError(f"Unsafe package-relative path: {relative!r}")
    for part in relative.split("/"):
        if (
            part in {"", ".", ".."}
            or part.endswith((".", " "))
            or _RESERVED_STEM.fullmatch(part.split(".")[0].upper())
            or any(character in part for character in '<>"|?*')
        ):
            raise ValueError(f"Unsafe package-relative path component: {relative!r}")
    return relative


def _inside(root: Path, relative: str) -> Path:
    resolved_root = root.resolve()
    path = (resolved_root / checked_member(relative)).resolve()
    if path == resolved_root or not path.is_relative_to(resolved_root):
        raise ValueError(f"Package path escapes its root: {relative}")
    return path


def _digests(value: object, owner: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{owner} must map package paths to SHA-256 digests")
    digests: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"{owner} must map package paths to SHA-256 digests")
        digests[key] = item
    return digests


def user_docs_bundled(manifest: Mapping[str, Any]) -> bool:
    """Return the manifest's documentation statement after proving its inventory agrees with it."""
    statement = manifest.get(USER_DOCS)
    if not isinstance(statement, dict):
        raise ValueError("The package manifest must state whether the user documentation is bundled")
    directory, bundled = statement.get("directory"), statement.get("bundled")
    if not isinstance(directory, str) or not isinstance(bundled, bool):
        raise ValueError("The package manifest must state whether the user documentation is bundled")
    checked_member(directory)
    delegated = manifest.get(DELEGATED_INVENTORIES, {})
    if bundled and directory not in delegated:
        raise ValueError(f"The package states bundled documentation but delegates no inventory for {directory}")
    if not bundled and (directory in delegated or any(name.startswith(f"{directory}/") for name in manifest["files"])):
        raise ValueError(f"The package states no bundled documentation but inventories {directory}")
    return bundled


def package_inventory(root: Path, manifest: Mapping[str, Any]) -> dict[str, str]:
    """Merge each hash-checked delegated inventory into the manifest's own files, refusing collisions."""
    files = _digests(manifest["files"], "package manifest")
    user_docs_bundled(manifest)
    merged = dict(files)
    for prefix, member in manifest.get(DELEGATED_INVENTORIES, {}).items():
        checked_member(prefix)
        if member not in files or not checked_member(member).startswith(f"{prefix}/"):
            raise ValueError(f"Delegated inventory {member} must be a listed file beneath {prefix}")
        path = _inside(root, member)
        if not path.is_file() or digest(path) != files[member]:
            raise ValueError(f"Delegated inventory manifest is missing or modified: {member}")
        nested = _digests(json.loads(path.read_text(encoding="utf-8"))["files"], member)
        for relative, value in nested.items():
            key = checked_member(f"{prefix}/{checked_member(relative)}")
            if key in merged:
                raise ValueError(f"Delegated inventory entry collides with another package file: {key}")
            merged[key] = value
    return merged
