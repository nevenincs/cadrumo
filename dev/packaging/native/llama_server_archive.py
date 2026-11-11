"""Unpack a pinned llama-server archive flat into a scratch directory, refusing any unsafe member."""

from __future__ import annotations

import io
import shutil
import tarfile
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import IO, Final

from .llama_server_errors import ArchiveMismatchError
from .package_inventory import checked_member

_LIBRARY_LINK_DEPTH: Final = 8


def _flat_name(raw: str, base: PurePosixPath) -> str | None:
    """Return the file name of an archive member of the program directory, or ``None`` for the directory itself."""
    name = raw.removeprefix("./").rstrip("/")
    if name in {"", "."}:
        return None
    path = PurePosixPath(name)
    if path.is_absolute() or "\\" in name or "\x00" in name or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveMismatchError(f"the llama-server archive holds an unsafe member name: {raw!r}")
    if path == base:
        return None
    if path.parent != base:
        raise ArchiveMismatchError(f"the llama-server archive holds a member outside its program directory: {raw!r}")
    return checked_member(path.name)


def _write(scratch: Path, name: str, source: IO[bytes], mode: int | None) -> None:
    target = scratch / name
    with target.open("xb") as output:
        shutil.copyfileobj(source, output)
    if mode is not None:
        target.chmod(mode & 0o777 | 0o400)


def unpack_tar(content: bytes, base: PurePosixPath, scratch: Path) -> dict[str, str]:
    """Write the regular members of a gzip tar flat into ``scratch`` and return its symbolic links by name."""
    links: dict[str, str] = {}
    seen: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
        for member in tar:
            name = _flat_name(member.name, base)
            if name is None:
                if not member.isdir():
                    raise ArchiveMismatchError(f"the llama-server archive holds a non-directory root: {member.name!r}")
                continue
            if name.casefold() in seen:
                raise ArchiveMismatchError(f"the llama-server archive repeats the member {name!r}")
            seen.add(name.casefold())
            if member.isfile():
                source = tar.extractfile(member)
                if source is None:
                    raise ArchiveMismatchError(f"the llama-server archive member is unreadable: {name!r}")
                _write(scratch, name, source, member.mode)
            elif member.issym():
                if "/" in member.linkname or member.linkname in {"", ".", ".."}:
                    raise ArchiveMismatchError(f"the llama-server archive links {name!r} beyond its directory")
                links[name] = member.linkname
            else:
                raise ArchiveMismatchError(f"the llama-server archive holds a special member: {name!r}")
    return links


def unpack_zip(content: bytes, base: PurePosixPath, scratch: Path) -> dict[str, str]:
    """Write the members of a zip flat into ``scratch``; a zip holds no links, so none are returned."""
    seen: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in archive.infolist():
            name = _flat_name(info.orig_filename, base)
            if name is None:
                continue
            if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ArchiveMismatchError(f"the llama-server archive holds a directory or link: {name!r}")
            if name.casefold() in seen:
                raise ArchiveMismatchError(f"the llama-server archive repeats the member {name!r}")
            seen.add(name.casefold())
            with archive.open(info) as source:
                _write(scratch, name, source, None)
    return {}


def resolve_link(name: str, links: Mapping[str, str], scratch: Path) -> str:
    """Follow library links to the regular file that holds the bytes."""
    current = name
    for _ in range(_LIBRARY_LINK_DEPTH):
        if current not in links:
            if not (scratch / current).is_file():
                raise ArchiveMismatchError(f"the llama-server archive link {name!r} names no file")
            return current
        current = links[current]
    raise ArchiveMismatchError(f"the llama-server archive link {name!r} does not end in a file")
