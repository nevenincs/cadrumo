"""Check a scoped Windows kernel-file trace without claiming an OS sandbox."""

from __future__ import annotations

import argparse
import ctypes
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import NotRequired, TypedDict, cast

from ..build_directory import require_enrolled_build
from ..build_paths import build_paths


class _EventData(TypedDict):
    FileObject: NotRequired[str]
    FileName: NotRequired[str]
    FilePath: NotRequired[str]
    IOSize: NotRequired[object]


class _Event(TypedDict):
    pid: int
    id: int
    data: _EventData


def _trace_directory(directory: Path, testing_root: Path) -> Path:
    if not directory.is_absolute() or not directory.is_dir():
        raise ValueError("Trace analysis requires an existing absolute trace directory")
    lexical = directory.absolute()
    try:
        relative = lexical.relative_to(testing_root)
    except ValueError as error:
        raise ValueError("Trace analysis output must be beneath the CMake testing output directory") from error
    if not relative.parts:
        raise ValueError("Trace analysis requires a dedicated trace directory")
    member = testing_root
    for part in relative.parts:
        member = member / part
        if member.is_symlink() or member.is_junction():
            raise ValueError("Trace analysis directory must not use linked directories")
    directory = directory.resolve(strict=True)
    if not directory.is_relative_to(testing_root):
        raise ValueError("Trace analysis output must be beneath the CMake testing output directory")
    return directory


def _trace_events(directory: Path, device_root: str) -> tuple[Counter[int], Counter[int], list[dict[str, object]]]:
    names: dict[tuple[int, str], str] = {}
    counts: Counter[int] = Counter()
    mutations: list[dict[str, object]] = []
    writes: Counter[int] = Counter()
    for line in (directory / "application-events.jsonl").read_text(encoding="utf-8-sig").splitlines():
        event = cast(_Event, json.loads(line))
        pid, kind, data = event["pid"], event["id"], event["data"]
        counts[pid] += 1
        key = (pid, data.get("FileObject", ""))
        name = data.get("FileName") or data.get("FilePath")
        if bool(name):
            names[key] = name
        if kind not in {16, 17, 18, 19, 26, 27, 28, 29, 30, 31, 33}:
            continue
        path = name or names.get(key, "")
        entry = {"pid": pid, "event_id": kind, "path": path, "bytes": data.get("IOSize")}
        mutations.append(entry)
        if kind == 16:
            writes[pid] += 1
        if path.lower() != device_root.lower() and not path.lower().startswith(device_root.lower() + "\\"):
            raise ValueError(f"Unresolved or outside-root file mutation: {entry}")
    return counts, writes, mutations


def analyze(directory: Path, build: Path) -> None:
    """Require lossless capture and resolve each mutating file operation."""
    if sys.platform != "win32":
        raise RuntimeError("Windows ETW analysis requires Windows")
    testing_root = build_paths(build)["testing"].resolve(strict=True)
    directory = _trace_directory(directory, testing_root)
    report = (directory / "capture-summary.txt").read_text(errors="replace")
    lost = re.search(r"Total Events\s+Lost\s+(\d+)", report)
    if lost is None or int(lost[1]):
        raise ValueError("Trace has lost events or an unrecognized loss report")
    identity = json.loads((directory / "processes.json").read_text(encoding="utf-8-sig"))
    root = Path(identity["user_root"])
    drive = root.drive
    target = ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.QueryDosDeviceW(drive, target, len(target)):
        raise ctypes.WinError()
    device_root = target.value + str(root)[len(drive) :]
    counts, writes, mutations = _trace_events(directory, device_root)
    if any(not writes[pid] for pid in identity["pids"]):
        raise ValueError("Missing actual write evidence for parent or child")
    summary = {
        "events_lost": 0,
        "pids": identity["pids"],
        "scoped_events": dict(counts),
        "writes": dict(writes),
        "user_root": str(root),
        "mutations": mutations,
        "scope": (
            "Kernel file creation, writes, set-information, deletion, rename/link, security and EA changes; "
            "parent and child probe only"
        ),
    }
    (directory / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Trace passed: {sum(counts.values())} scoped events, {sum(writes.values())} writes, zero events lost")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build", type=require_enrolled_build, required=True, help="The owning CMake binary directory."
    )
    parser.add_argument("directory", type=Path)
    arguments = parser.parse_args()
    analyze(arguments.directory, arguments.build)
