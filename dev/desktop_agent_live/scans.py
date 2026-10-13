"""The desktop agent lane's two after-run checks: no started process survives, and no provider key leaks.

Processes are read from WMI ``Win32_Process``: identity, parent and creation
time for the survivor check, and the command line for the key scan. A command
line is scanned as soon as it is read and never kept. Process environment
blocks are not read.

The key scan looks for the provider key prefix, in UTF-8 and in UTF-16LE, in
every file below the given directories and inside the ZIP archives among them,
which is how Playwright writes traces. A finding names where the prefix was
found, never what followed it. A file that cannot be read is reported as such,
because an unread file is not a clean one.
"""

from __future__ import annotations

import io
import os
import sys
import zipfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Final

KEY_PREFIX: Final = "sk-ant-"
"""The prefix every Anthropic API key starts with."""

_PATTERNS: Final = ((KEY_PREFIX.encode("ascii"), "utf-8"), (KEY_PREFIX.encode("utf-16-le"), "utf-16-le"))
READ_CHUNK_BYTES: Final = 1 << 20
_OVERLAP: Final = max(len(pattern) for pattern, _encoding in _PATTERNS) - 1
_ZIP_DEPTH: Final = 3


@dataclass(frozen=True, slots=True, order=True)
class ProcessRecord:
    """One process as WMI reports it; the creation time tells a reused PID apart."""

    pid: int
    parent: int
    name: str
    created: str


@dataclass(frozen=True, slots=True)
class KeyFinding:
    """Where the key prefix was found, in which encoding; never the text around it."""

    location: str
    encoding: str


@dataclass(frozen=True, slots=True)
class ScanResult:
    """The findings of one scan, and what it could not read."""

    findings: tuple[KeyFinding, ...]
    unreadable: tuple[str, ...]

    @property
    def clean(self) -> bool:
        """Whether every place was read and none held the prefix."""
        return not self.findings and not self.unreadable


def _wmi_rows(fields: tuple[str, ...], pids: frozenset[int] | None = None) -> list[dict[str, Any]]:
    """Return ``Win32_Process`` instances as plain values, releasing every COM object before returning.

    With ``pids``, only those processes' fields are read.
    """
    if sys.platform != "win32":
        raise RuntimeError("The process checks read WMI, which only Windows has")
    import pythoncom
    import win32com.client

    # The apartment stays initialised for this thread: uninitialising it while
    # a COM reference is still being released crashes the interpreter.
    pythoncom.CoInitialize()
    service = win32com.client.GetObject("winmgmts:")
    rows = [
        {field: getattr(instance, field) for field in fields}
        for instance in service.InstancesOf("Win32_Process")
        if pids is None or int(instance.ProcessId) in pids
    ]
    del service
    return rows


def process_table() -> dict[int, ProcessRecord]:
    """Every running process, by PID, without command lines."""
    table: dict[int, ProcessRecord] = {}
    for row in _wmi_rows(("ProcessId", "ParentProcessId", "Name", "CreationDate")):
        pid = int(row["ProcessId"])
        table[pid] = ProcessRecord(
            pid=pid,
            parent=int(row["ParentProcessId"] or 0),
            name=str(row["Name"] or ""),
            created=str(row["CreationDate"] or ""),
        )
    return table


def descendants(table: Mapping[int, ProcessRecord], roots: Iterable[int]) -> set[ProcessRecord]:
    """The processes below ``roots``, following parents that were created before their children.

    A parent PID can name a later, unrelated process once the real parent has
    exited, so a child is followed only from a parent no younger than itself.
    """
    found: set[ProcessRecord] = set()
    frontier = [table[pid] for pid in roots if pid in table]
    while frontier:
        parent = frontier.pop()
        for child in table.values():
            follows = child.parent == parent.pid and child.pid != parent.pid and child.created >= parent.created
            if follows and child not in found:
                found.add(child)
                frontier.append(child)
    return found


def survivors(started: Iterable[ProcessRecord], table: Mapping[int, ProcessRecord]) -> list[ProcessRecord]:
    """The started processes still running: the same PID with the same creation time."""
    return sorted(process for process in started if table.get(process.pid) == process)


def scan_command_lines(processes: Iterable[ProcessRecord]) -> ScanResult:
    """Scan the command lines of ``processes`` that still run, keeping no command line."""
    wanted = {process.pid: process for process in processes}
    findings: list[KeyFinding] = []
    if not wanted:
        return ScanResult((), ())
    for row in _wmi_rows(("ProcessId", "CreationDate", "CommandLine"), frozenset(wanted)):
        process = wanted.get(int(row["ProcessId"]))
        if process is None or str(row["CreationDate"] or "") != process.created:
            continue
        # WMI decodes the command line, so it is searched as text, once.
        if KEY_PREFIX in str(row.pop("CommandLine") or ""):
            findings.append(KeyFinding(f"command line of process {process.pid} ({process.name})", "text"))
    return ScanResult(tuple(findings), ())


def _scan_stream(stream: IO[bytes], location: str) -> list[KeyFinding]:
    """Scan one byte stream in bounded chunks, with an overlap so no match is split."""
    findings: list[KeyFinding] = []
    offset = 0
    tail = b""
    while chunk := stream.read(READ_CHUNK_BYTES):
        # The carried tail is shorter than a pattern, so a match found here
        # was not wholly inside the previous window.
        window = tail + chunk
        start = offset - len(tail)
        for pattern, encoding in _PATTERNS:
            index = window.find(pattern)
            while index != -1:
                findings.append(KeyFinding(f"{location} at byte {start + index}", encoding))
                index = window.find(pattern, index + 1)
        offset += len(chunk)
        tail = window[-_OVERLAP:]
    return findings


def _scan_archive(source: IO[bytes], location: str, depth: int) -> tuple[list[KeyFinding], list[str]]:
    """Scan every member of a ZIP archive, and archives inside it to a bounded depth."""
    findings: list[KeyFinding] = []
    unreadable: list[str] = []
    try:
        archive = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError):
        return findings, [f"{location}: not a readable archive"]
    with archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            where = f"{location} member {member.filename}"
            try:
                with archive.open(member) as stream:
                    findings.extend(_scan_stream(stream, where))
                if depth > 1:
                    with archive.open(member) as stream:
                        if stream.read(4) == b"PK\x03\x04":
                            inner = io.BytesIO(archive.read(member))
                            more, missed = _scan_archive(inner, where, depth - 1)
                            findings.extend(more)
                            unreadable.extend(missed)
            except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError):
                unreadable.append(where)
    return findings, unreadable


def scan_file(path: Path) -> ScanResult:
    """Scan one file's bytes, and its members when it is a ZIP archive."""
    try:
        with path.open("rb") as stream:
            findings = _scan_stream(stream, f"file {path}")
            stream.seek(0)
            if stream.read(4) != b"PK\x03\x04":
                return ScanResult(tuple(findings), ())
            stream.seek(0)
            more, unreadable = _scan_archive(stream, f"file {path}", _ZIP_DEPTH)
    except OSError:
        return ScanResult((), (f"file {path}",))
    return ScanResult((*findings, *more), tuple(unreadable))


def scan_tree(roots: Iterable[Path], *, on_file: Callable[[Path], None] | None = None) -> ScanResult:
    """Scan every regular file below ``roots``, following no link out of them."""
    findings: list[KeyFinding] = []
    unreadable: list[str] = []

    def unlisted(error: OSError) -> None:
        unreadable.append(f"directory {error.filename}")

    for root in roots:
        if not root.exists():
            continue
        for directory, _subdirectories, files in os.walk(root, followlinks=False, onerror=unlisted):
            for name in files:
                path = Path(directory, name)
                if path.is_symlink() or not path.is_file():
                    continue
                if on_file is not None:
                    on_file(path)
                result = scan_file(path)
                findings.extend(result.findings)
                unreadable.extend(result.unreadable)
    return ScanResult(tuple(findings), tuple(unreadable))


def merge(*results: ScanResult) -> ScanResult:
    """One result holding every finding and unread place of ``results``."""
    return ScanResult(
        tuple(finding for result in results for finding in result.findings),
        tuple(place for result in results for place in result.unreadable),
    )
