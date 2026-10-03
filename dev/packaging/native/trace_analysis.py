"""Check a scoped Windows kernel-file trace without claiming an OS sandbox."""

from __future__ import annotations

import argparse
import ctypes
import json
import re
import sys
from collections import Counter
from pathlib import Path


def analyze(directory: Path) -> None:
    """Require lossless capture and resolve each mutating file operation."""
    if sys.platform != "win32":
        raise RuntimeError("Windows ETW analysis requires Windows")
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
    names: dict[tuple[int, str], str] = {}
    counts: Counter[int] = Counter()
    mutations = []
    writes: Counter[int] = Counter()
    for line in (directory / "application-events.jsonl").read_text(encoding="utf-8-sig").splitlines():
        event = json.loads(line)
        pid, kind, data = event["pid"], event["id"], event["data"]
        counts[pid] += 1
        key = (pid, data.get("FileObject", ""))
        name = data.get("FileName") or data.get("FilePath")
        if name:
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
    parser.add_argument("directory", type=Path)
    analyze(parser.parse_args().directory)
