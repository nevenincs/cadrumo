"""Attribute runtime opens and summarize Process Monitor file API events.

The audit observer records open attempts and code locations, never file contents.
It does not count reads. Process Monitor CSV supplies native ReadFile counts and
reported lengths, including SQLite and the packaged host. These are file API
bytes, which Windows may satisfy from memory; they are not physical disk bytes.
Capture before launching the target, export without filters, and select its PIDs
with ``summarize``. Recorder imports precede the audit scope and output follows it.
"""

from __future__ import annotations

import argparse
import csv
import json
import ntpath
import os
import re
import sys
import threading
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import FrameType

_FILE_OPERATIONS = frozenset(
    {
        "CreateFile",
        "ReadFile",
        "WriteFile",
        "CloseFile",
        "QueryOpen",
        "QueryDirectory",
        "QueryBasicInformationFile",
        "QueryStandardInformationFile",
        "QueryNameInformationFile",
        "QueryInformationVolume",
        "QueryAttributeTagFile",
        "QueryNetworkOpenInformationFile",
        "QuerySecurityFile",
        "CreateFileMapping",
        "Load Image",
        "SetDispositionInformationFile",
        "SetRenameInformationFile",
        "SetEndOfFileInformationFile",
        "FlushBuffersFile",
    }
)
_LENGTH = re.compile(r"(?:^|, )Length: ([\d,.]+)(?:, |$)")


def _file_type(path: str) -> str:
    normalized = path.replace("/", "\\").lower()
    if "\\namedpipe\\" in normalized or normalized.startswith("\\\\.\\pipe\\"):
        return "<pipe>"
    return ntpath.splitext(normalized)[1] or "<no suffix>"


def summarize_file_events(events: Iterable[Mapping[str, str]], *, pids: set[int]) -> dict[str, object]:
    """Account only selected processes, preserving failures and EOF separately."""
    operations: Counter[str] = Counter()
    results: Counter[str] = Counter()
    files: dict[str, Counter[str]] = {}
    for event in events:
        if int(event["PID"]) not in pids or event["Operation"] not in _FILE_OPERATIONS:
            continue
        operation, result = event["Operation"], event["Result"]
        path = ntpath.normcase(event["Path"])
        operations[operation] += 1
        results[f"{operation}: {result}"] += 1
        totals = files.setdefault(path, Counter())
        totals["events"] += 1
        totals[operation] += 1
        if operation == "ReadFile" and result == "SUCCESS":
            length = _LENGTH.search(event["Detail"])
            if length is None:
                raise ValueError("successful ReadFile lacks a reported length")
            totals["successful_reads"] += 1
            totals["reported_read_bytes"] += int(length[1].replace(",", "").replace(".", ""))
        if operation == "CreateFile":
            totals["successful_opens" if result == "SUCCESS" else "unsuccessful_opens"] += 1
    types: dict[str, Counter[str]] = {}
    for path, totals in files.items():
        type_totals = types.setdefault(_file_type(path), Counter())
        type_totals.update(totals)
        type_totals["unique_paths"] += 1
    return {
        "coverage": "Windows file API events; reported ReadFile bytes include cached reads, not physical media I/O",
        "pids": sorted(pids),
        "operations": dict(operations),
        "results": dict(results),
        "file_types": {suffix: dict(totals) for suffix, totals in sorted(types.items())},
        "files": [{"path": path, **dict(totals)} for path, totals in sorted(files.items())],
    }


def _callers(frame: FrameType | None) -> tuple[str, ...]:
    callers = []
    while frame is not None and len(callers) < 32:
        module = frame.f_globals.get("__name__", "<unknown>")
        if module != __name__:
            callers.append(f"{module}:{frame.f_code.co_name}:{frame.f_lineno}")
        frame = frame.f_back
    return tuple(callers)


class FileOpenTrace:
    """Collect open attempts in memory, retaining no arguments beyond file identity."""

    def __init__(self) -> None:
        """Prepare an inactive observer without filesystem activity."""
        self.active = False
        self._registered = False
        self._thread = threading.local()
        self._lock = threading.Lock()
        self._counts: Counter[tuple[str, bool, tuple[str, ...]]] = Counter()

    def _observe(self, event: str, arguments: tuple[object, ...]) -> None:
        if not self.active or event != "open" or getattr(self._thread, "recording", False):
            return
        path, _, flags = arguments
        if not isinstance(path, (str, bytes)) or not isinstance(flags, int):
            return
        self._thread.recording = True
        try:
            reading = flags & (os.O_WRONLY | os.O_RDWR) != os.O_WRONLY
            identity = (os.fsdecode(path), reading, _callers(sys._getframe(1)))
            with self._lock:
                self._counts[identity] += 1
        finally:
            self._thread.recording = False

    def __enter__(self) -> FileOpenTrace:
        """Enable this observer for the bounded diagnostic scope."""
        if self.active:
            raise RuntimeError("file-open trace is already active")
        if not self._registered:
            sys.addaudithook(self._observe)
            self._registered = True
        self.active = True
        return self

    def __exit__(self, *_exception: object) -> None:
        """Deactivate the irreversible audit hook before writing diagnostics."""
        self.active = False

    def report(self) -> dict[str, object]:
        """Return a stable snapshot after observation, excluding report serialization."""
        with self._lock:
            rows = [
                {
                    "path": path,
                    "file_type": _file_type(path),
                    "readable": reading,
                    "callers": callers,
                    "attempts": count,
                }
                for (path, reading, callers), count in self._counts.items()
            ]
        return {
            "pid": os.getpid(),
            "coverage": "Python open attempts with caller stacks; not reads or bytes",
            "opens": sorted(rows, key=lambda row: str(row["path"])),
        }


def _scenario(name: str, arguments: list[str]) -> dict[str, object]:
    if name == "registry":
        from cadrumo.entrypoints.operation_composition import build_production_operation_registry

        registry = build_production_operation_registry()
        return {
            "contract_count": len(registry.public_contract_set.definitions),
            "contract_digest": str(registry.public_contract_set.contract_set_digest),
        }
    elif name == "authority":
        from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
        from cadrumo.domain.calculations.registry.authority_store import SQLiteAuthorityReader

        descriptor_path = bundled_authority_descriptor_path()
        reader = SQLiteAuthorityReader(descriptor_path)
        reader.close()
    elif name == "runtime":
        from cadrumo.entrypoints.runtime.bootstrap import main

        sys.argv = ["cadrumo-runtime", *arguments]
        main()
    else:
        raise ValueError("unknown runtime file access scenario")
    return {}


def main() -> None:
    """Run an unchanged source boundary or summarize a native file-event export."""
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    record = subcommands.add_parser("record")
    record.add_argument("--output", type=Path, required=True)
    record.add_argument("--scenario", choices=("registry", "authority", "runtime"), required=True)
    record.add_argument("arguments", nargs=argparse.REMAINDER)
    summarize = subcommands.add_parser("summarize")
    summarize.add_argument("--csv", type=Path, required=True)
    summarize.add_argument("--pid", type=int, action="append", required=True)
    summarize.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    if options.command == "summarize":
        with options.csv.open(encoding="utf-8-sig", newline="") as source:
            report = summarize_file_events(csv.DictReader(source), pids=set(options.pid))
        options.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return
    trace = FileOpenTrace()
    os.environ["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
    started, cpu = time.perf_counter(), time.process_time()
    outcome = "ok"
    details: dict[str, object] = {}
    try:
        with trace:
            details = _scenario(
                options.scenario, options.arguments[1:] if options.arguments[:1] == ["--"] else options.arguments
            )
    except BaseException as error:
        outcome = type(error).__name__
        if isinstance(error, SystemExit) and isinstance(error.code, int):
            details["exit_code"] = error.code
        raise
    finally:
        report = {
            **trace.report(),
            "scenario": options.scenario,
            "outcome": outcome,
            **details,
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu,
        }
        options.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
