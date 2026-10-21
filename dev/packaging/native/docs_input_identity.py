"""Portable documentation identity for the enrolled checkout and selected authority."""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from pathlib import Path


def _canonical_file(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Documentation input must be an absolute canonical path: {path}")
    resolved = path.resolve(strict=True)
    if path != resolved or not resolved.is_file():
        raise ValueError(f"Documentation input aliases another path or is not a file: {path}")
    return resolved


def shared_docs_inputs(inputs: Path, authority: tuple[Path, Path], *, source: Path, build: Path) -> str:
    """Hash relative source names and bytes, plus the two selected authority roles.

    CMake owns enrollment. Only its build-directory inputs are excluded; every
    other enrolled input must belong to this checkout or the selected authority.
    Native action and build-local cache identities keep their own path policy.
    """
    source = source.resolve(strict=True)
    build = build.resolve(strict=True)
    if source.is_relative_to(build):
        raise ValueError("Documentation build directory must not contain its checkout")
    descriptor, database = authority
    selected = tuple(_canonical_file(path) for path in (descriptor, database))
    records: list[tuple[str, str]] = []
    physical: set[tuple[int, int]] = set()

    def enroll(label: str, path: Path) -> None:
        with path.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            inode = (stat.st_dev, stat.st_ino)
            if inode in physical:
                raise ValueError(f"Documentation inputs alias one file: {path}")
            physical.add(inode)
            records.append((label, hashlib.file_digest(stream, "sha256").hexdigest()))

    for role, path in zip(("authority/descriptor", "authority/database"), selected, strict=True):
        enroll(role, path)
    names: set[str] = set()
    for line in inputs.read_text(encoding="utf-8").splitlines():
        path = _canonical_file(Path(line))
        if path.is_relative_to(build):
            continue
        if path in selected:
            continue
        if not path.is_relative_to(source):
            raise ValueError(f"Documentation input is outside the enrolled checkout: {path}")
        relative = path.relative_to(source).as_posix()
        if "\\" in relative or ":" in relative:
            raise ValueError(f"Documentation input has a nonportable name: {relative}")
        collision = unicodedata.normalize("NFC", relative).casefold()
        if collision in names:
            raise ValueError(f"Documentation input names collide: {relative}")
        names.add(collision)
        enroll(f"source/{relative}", path)
    encoded = json.dumps({"schema": 1, "files": sorted(records)}, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
