"""Small build actions called by CMake; CMake owns their graph and output paths."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast

from .hashing import digest
from .stable_output import write_text


def _check_dependency_destination(target: Path, product: Path) -> None:
    for ancestor in (target, *target.parents):
        if ancestor == product:
            break
        if ancestor.is_symlink() or ancestor.is_junction():
            raise ValueError("Base dependency destination contains a linked member")


def _copy_base_dependencies(source: Path, product: Path, destination: Path, members: dict[str, str]) -> None:
    for member in sorted(source.rglob("*")):
        if member.is_symlink() or member.is_junction():
            raise ValueError("Base dependency closure contains a linked member")
        if not member.is_file():
            continue
        relative = member.relative_to(source).as_posix()
        identity = digest(member)
        members[relative] = identity
        target = destination / relative
        _check_dependency_destination(target, product)
        if not target.is_file() or digest(target) != identity:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(member, target)


def _remove_obsolete_dependencies(destination: Path, previous: dict[str, str], members: dict[str, str]) -> None:
    for relative, identity in previous.items():
        target = destination / relative
        if not target.resolve().is_relative_to(destination.resolve()):
            raise ValueError("Base dependency receipt escapes its owning directory")
        if relative not in members and target.is_file():
            if digest(target) != identity:
                raise ValueError(f"Obsolete base dependency changed outside its producer: {relative}")
            target.unlink()


def sync_base_dependencies(source: Path, product: Path) -> None:
    """Refresh only changed base wheels, retaining the separately owned product build."""
    destination = product / "dependencies"
    receipt = product / "base-dependencies.json"
    previous = cast(dict[str, str], json.loads(receipt.read_text(encoding="utf-8"))) if receipt.is_file() else {}
    members: dict[str, str] = {}
    _copy_base_dependencies(source, product, destination, members)
    _remove_obsolete_dependencies(destination, previous, members)
    _remove_empty_directories(destination)
    write_text(receipt, json.dumps(members, sort_keys=True) + "\n")


def _remove_empty_directories(root: Path) -> None:
    """Remove directories a replaced distribution left empty, deepest first.

    An emptied ``*.dist-info`` directory (one that kept only a ``licenses`` folder, or
    nothing) is still discovered as an installed distribution without metadata, so the
    staged closure must not keep it. No installed payload is an empty directory.
    """
    directories = [path for path in root.rglob("*") if path.is_dir()]
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        if directory.is_symlink() or directory.is_junction():
            raise ValueError("Base dependency destination contains a linked member")
        if not any(directory.iterdir()):
            directory.rmdir()
