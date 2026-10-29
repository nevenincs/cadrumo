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
        return _matches_record(archive, records[0], dependencies)


def _matches_record(archive: zipfile.ZipFile, record_name: str, dependencies: Path) -> bool:
    record_member = PurePosixPath(record_name)
    if not _valid_record_name(record_name, record_member):
        return False
    rows = list(csv.reader(io.StringIO(archive.read(record_name).decode(UTF_8))))
    wheel_members = _record_members(rows)
    if wheel_members is None:
        return False
    record = dependencies / record_name
    if not record.is_file() or _has_link_ancestor(record):
        return False
    installed_rows = list(csv.reader(io.StringIO(record.read_text(encoding=UTF_8))))
    installed_members = _record_members(installed_rows)
    if installed_members is None:
        return False
    generated = _generated_members(archive, record_member.parent)
    if generated is None or not wheel_members <= installed_members or installed_members - wheel_members - generated:
        return False
    return all(_record_member_matches(name, checksum, dependencies) for name, checksum, _size in rows)


def _valid_record_name(name: str, member: PurePosixPath) -> bool:
    return len(member.parts) == 2 and not member.is_absolute() and "\\" not in name and ":" not in name


def _record_members(rows: list[list[str]]) -> set[str] | None:
    if any(len(row) != 3 for row in rows):
        return None
    members = {name for name, _checksum, _size in rows}
    return members if len(members) == len(rows) else None


def _has_link_ancestor(path: Path) -> bool:
    return any(parent.is_symlink() or parent.is_junction() for parent in (path, *path.parents))


def _generated_members(archive: zipfile.ZipFile, metadata: PurePosixPath) -> set[str] | None:
    generated = {str(metadata / name) for name in ("INSTALLER", "REQUESTED", "direct_url.json", "uv_cache.json")}
    entry_points = str(metadata / "entry_points.txt")
    if entry_points not in archive.namelist():
        return generated
    configuration = _WheelEntryPoints(interpolation=None)
    configuration.read_string(archive.read(entry_points).decode(UTF_8))
    for group in ("console_scripts", "gui_scripts"):
        if configuration.has_section(group):
            for name in configuration[group]:
                if not _valid_entry_point_name(name):
                    return None
                generated.add(f"bin/{name}{'.exe' if os.name == 'nt' else ''}")
    return generated


def _valid_entry_point_name(name: str) -> bool:
    return PurePosixPath(name).name == name and name not in {".", ".."} and "\\" not in name and ":" not in name


def _record_member_matches(name: str, checksum: str, dependencies: Path) -> bool:
    if not checksum:
        return True
    relative = PurePosixPath(name)
    if not _valid_record_member(name, relative):
        return False
    installed = dependencies.joinpath(*relative.parts)
    algorithm, _, encoded = checksum.partition("=")
    if algorithm != "sha256" or not installed.is_file() or _has_link_ancestor(installed):
        return False
    with installed.open("rb") as stream:
        checksum_bytes = hashlib.file_digest(stream, "sha256").digest()
    observed = base64.urlsafe_b64encode(checksum_bytes).rstrip(b"=").decode()
    return observed == encoded


def _valid_record_member(name: str, relative: PurePosixPath) -> bool:
    return bool(relative.parts) and not (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.parts[0].endswith(".data")
        or "\\" in name
        or ":" in name
    )
