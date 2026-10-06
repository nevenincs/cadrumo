"""Extract application ZIPs with portable paths and executable permissions."""

from __future__ import annotations

import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath


def extract_bundle(archive: Path, destination: Path) -> None:
    """Reject links, aliases and special files before writing any archive member."""
    members: list[tuple[zipfile.ZipInfo, Path, int]] = []
    names: set[str] = set()
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            name = entry.orig_filename.rstrip("/")
            path = PurePosixPath(name)
            if (
                not name
                or path.is_absolute()
                or "\\" in name
                or ":" in name
                or "\x00" in name
                or any(part in {"", ".", ".."} for part in name.split("/"))
                or name.casefold() in names
            ):
                raise ValueError(f"Invalid or duplicate bundle member: {entry.filename}")
            names.add(name.casefold())
            mode = entry.external_attr >> 16
            kind = stat.S_IFMT(mode)
            expected = stat.S_IFDIR if entry.is_dir() else stat.S_IFREG
            if kind not in {0, expected}:
                raise ValueError(f"Bundle contains a link or special file: {entry.filename}")
            output = destination.joinpath(*path.parts)
            if not output.resolve().is_relative_to(destination.resolve()):
                raise ValueError(f"Bundle member escapes extraction root: {entry.filename}")
            members.append((entry, output, mode))
        for entry, output, mode in members:
            if entry.is_dir():
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as incoming, output.open("xb") as target:
                shutil.copyfileobj(incoming, target)
            if entry.create_system == 3:
                output.chmod(stat.S_IMODE(mode) & 0o777)
