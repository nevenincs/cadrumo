"""Read the one core-metadata document a wheel carries."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import os
import zipfile
from configparser import ConfigParser
from email.message import Message
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import override

from dev._paths import UTF_8

_METADATA_SUFFIX = ".dist-info/METADATA"


class _WheelEntryPoints(ConfigParser):
    """Keep the executable names' case when reading entry point declarations."""

    @override
    def optionxform(self, optionstr: str) -> str:
        """Return the declared executable name without normalization."""
        return optionstr


def read_wheel_metadata(wheel: Path) -> Message:
    """Return ``wheel``'s core metadata, refusing a wheel without exactly one document.

    Picking the first of several would let a wheel that smuggles a second
    ``METADATA`` member answer for itself with whichever the archive lists
    first, so anything other than one member is a refusal.
    """
    with zipfile.ZipFile(wheel) as archive:
        members = [name for name in archive.namelist() if name.endswith(_METADATA_SUFFIX)]
        if len(members) != 1:
            raise SystemExit(f"expected one wheel METADATA member in {wheel}; got {members!r}")
        return Parser().parsestr(archive.read(members[0]).decode(UTF_8))


def installed_wheel_matches(wheel: Path, dependencies: Path) -> bool:
    """Require matching wheel bytes and ownership, including removed wheel members."""
    with zipfile.ZipFile(wheel) as archive:
        records = [name for name in archive.namelist() if name.endswith(".dist-info/RECORD")]
        if len(records) != 1:
            raise ValueError("Wheel must contain one RECORD")
        record_member = PurePosixPath(records[0])
        if len(record_member.parts) != 2 or record_member.is_absolute() or "\\" in records[0] or ":" in records[0]:
            return False
        rows = list(csv.reader(io.StringIO(archive.read(records[0]).decode(UTF_8))))
        if any(len(row) != 3 for row in rows):
            return False
        wheel_members = {name for name, _checksum, _size in rows}
        if len(wheel_members) != len(rows):
            return False
        record = dependencies / records[0]
        if not record.is_file() or any(path.is_symlink() or path.is_junction() for path in (record, *record.parents)):
            return False
        installed_rows = list(csv.reader(io.StringIO(record.read_text(encoding=UTF_8))))
        if any(len(row) != 3 for row in installed_rows):
            return False
        installed_members = {name for name, _checksum, _size in installed_rows}
        if len(installed_members) != len(installed_rows):
            return False
        # uv adds these exact installation records. Other extra members still
        # belong to the previous wheel and must force its uninstall/reinstall.
        metadata = PurePosixPath(records[0]).parent
        generated = {str(metadata / name) for name in ("INSTALLER", "REQUESTED", "direct_url.json", "uv_cache.json")}
        entry_points = str(metadata / "entry_points.txt")
        if entry_points in archive.namelist():
            configuration = _WheelEntryPoints(interpolation=None)
            configuration.read_string(archive.read(entry_points).decode(UTF_8))
            for group in ("console_scripts", "gui_scripts"):
                if configuration.has_section(group):
                    for name in configuration[group]:
                        if PurePosixPath(name).name != name or name in {".", ".."} or "\\" in name or ":" in name:
                            return False
                        generated.add(f"bin/{name}{'.exe' if os.name == 'nt' else ''}")
        if not wheel_members <= installed_members or installed_members - wheel_members - generated:
            return False
        for name, checksum, _size in rows:
            if not checksum:
                continue
            relative = PurePosixPath(name)
            if (
                not relative.parts
                or relative.is_absolute()
                or ".." in relative.parts
                or relative.parts[0].endswith(".data")
                or "\\" in name
                or ":" in name
            ):
                return False
            installed = dependencies.joinpath(*relative.parts)
            algorithm, _, encoded = checksum.partition("=")
            if (
                algorithm != "sha256"
                or not installed.is_file()
                or any(path.is_symlink() or path.is_junction() for path in (installed, *installed.parents))
            ):
                return False
            with installed.open("rb") as stream:
                checksum_bytes = hashlib.file_digest(stream, "sha256").digest()
            observed = base64.urlsafe_b64encode(checksum_bytes).rstrip(b"=").decode()
            if observed != encoded:
                return False
    return True
