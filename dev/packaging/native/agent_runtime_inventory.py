"""Inventory runtime files and reject unsafe filesystem entries."""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath

from .hashing import digest

RECEIPT_NAME = "runtime-receipt.json"
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def inventory_runtime(root: Path) -> tuple[list[str], dict[str, str]]:
    """Inventory the runtime tree without following links."""
    directories: list[str] = []
    files: dict[str, str] = {}
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda item: item.name)
        except OSError as exc:
            raise ValueError("Agent runtime tree cannot be enumerated") from exc
        child_directories: list[Path] = []
        for entry in entries:
            path = Path(entry.path)
            if is_link_or_reparse(path):
                raise ValueError("Agent runtime tree cannot contain links or junctions")
            relative = path.relative_to(root).as_posix()
            validate_relative_name(relative)
            if entry.is_dir(follow_symlinks=False):
                directories.append(relative)
                child_directories.append(path)
            elif entry.is_file(follow_symlinks=False):
                if relative != RECEIPT_NAME:
                    files[relative] = digest(path)
            else:
                raise ValueError("Agent runtime tree cannot contain special files")
        stack.extend(reversed(child_directories))
    return sorted(directories), dict(sorted(files.items()))


def validate_relative_name(name: str) -> None:
    """Reject names that escape or misrepresent the runtime root."""
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or any(part in {"", ".", ".."} for part in name.split("/"))
        or path.as_posix() != name
    ):
        raise ValueError("Agent runtime receipt contains an invalid relative path")


def lstat(path: Path) -> os.stat_result | None:
    """Return filesystem metadata without following links, if present."""
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def is_link_or_reparse(path: Path) -> bool:
    """Detect symbolic links and platform reparse points."""
    info = lstat(path)
    return info is not None and (
        stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)
    )
