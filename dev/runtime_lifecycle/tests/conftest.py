"""Explicit binary selection for process lifecycle acceptance."""

import json
import math
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from cadrumo.core.storage_environment import STORAGE_ROOT

from ..harness import LifecycleHarness


def _runtime_faults(path: Path) -> list[dict[str, str | int]]:
    """Retain bounded public fault types and only recognized source coordinates."""
    origins = {
        "cadrumo/adapters/local_runtime/windows_native_io.py": (
            "windows_native_io",
            {"windows_deadline_milliseconds", "finish_windows_io"},
        ),
        "cadrumo/adapters/local_runtime/windows_channel.py": ("windows_channel", {"read_exact", "write_all"}),
        "filelock/_api.py": ("filelock_api", {"acquire"}),
        "cadrumo/application/runtime/deadline_budget.py": ("deadline_budget", {"remaining_budget"}),
    }
    faults: list[dict[str, str | int]] = []
    if not path.is_file():
        return faults
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - 32768))
        tail = stream.read(32768).decode("utf-8", errors="replace")
    for line in tail.splitlines():
        _, separator, payload = line.partition(" | ")
        if not separator:
            continue
        try:
            fields = json.loads(payload)
        except ValueError:
            continue
        if not isinstance(fields, dict):
            continue
        error_type = fields.get("error_type")
        if (
            not isinstance(error_type, str)
            or len(error_type) > 128
            or not error_type.isascii()
            or not error_type.isidentifier()
        ):
            continue
        fact: dict[str, str | int] = {"error_type": error_type}
        origin = fields.get("error_origin")
        if isinstance(origin, str) and len(origin) <= 512:
            parts = origin.rsplit(":", 2)
            if len(parts) == 3:
                source, number, function = parts
                source = source.replace("\\", "/")
                for suffix, (owner, functions) in origins.items():
                    if (
                        (source == suffix or source.endswith("/" + suffix))
                        and function in functions
                        and number.isascii()
                        and number.isdecimal()
                        and 0 < int(number) <= 1_000_000
                    ):
                        fact.update(origin_owner=owner, origin_function=function, origin_line=int(number))
                        break
        faults.append(fact)
    return faults[-12:]


def _manager_evidence(path: Path) -> dict[str, Any]:
    """Preserve bounded public driver facts before private scratch is removed."""
    kinds = {
        "launched",
        "ready",
        "adopted",
        "exited",
        "boot_confirmed",
        "restart_scheduled",
        "hang_detected",
        "launch_failed",
        "supervisor_ended",
        "other",
        "driver_failed",
    }
    statuses = {"stopping", "update_failed", "unavailable", "waiting", "adopted", "running", "starting"}
    error_kinds = {
        "NotFound",
        "PermissionDenied",
        "ConnectionRefused",
        "ConnectionReset",
        "HostUnreachable",
        "NetworkUnreachable",
        "ConnectionAborted",
        "NotConnected",
        "AddrInUse",
        "AddrNotAvailable",
        "NetworkDown",
        "BrokenPipe",
        "AlreadyExists",
        "WouldBlock",
        "NotADirectory",
        "IsADirectory",
        "DirectoryNotEmpty",
        "ReadOnlyFilesystem",
        "FilesystemLoop",
        "StaleNetworkFileHandle",
        "InvalidInput",
        "InvalidData",
        "TimedOut",
        "WriteZero",
        "StorageFull",
        "NotSeekable",
        "QuotaExceeded",
        "FileTooLarge",
        "ResourceBusy",
        "ExecutableFileBusy",
        "Deadlock",
        "CrossesDevices",
        "TooManyLinks",
        "InvalidFilename",
        "ArgumentListTooLong",
        "Interrupted",
        "Unsupported",
        "UnexpectedEof",
        "OutOfMemory",
        "InProgress",
        "Other",
        "Uncategorized",
    }
    try:
        with path.open("rb") as stream:
            size = path.stat().st_size
            offset = max(0, size - 65536)
            stream.seek(offset)
            tail = stream.read(65536)
    except FileNotFoundError:
        return {"events": [], "observation": "absent"}
    except OSError as error:
        return {"events": [], "observation": "read_failed", "error_type": type(error).__name__}
    lines = tail.splitlines(keepends=True)
    if offset:
        lines = lines[1:]
    events: list[dict[str, Any]] = []
    invalid = 0
    for line in lines:
        if not line.endswith(b"\n"):
            continue
        try:
            event = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            invalid += 1
            continue
        if not isinstance(event, dict) or not isinstance(event.get("kind"), str) or event["kind"] not in kinds:
            invalid += 1
            continue
        public: dict[str, Any] = {"kind": event["kind"]}
        sequence = event.get("sequence")
        if type(sequence) is int and 0 < sequence < 2**64:
            public["sequence"] = sequence
        pid = event.get("pid")
        seconds = event.get("seconds")
        if type(pid) is int and 0 < pid <= 0xFFFFFFFF:
            public["pid"] = pid
        if type(seconds) in (int, float) and 0 <= seconds <= 1e12 and math.isfinite(seconds):
            public["seconds"] = seconds
        if isinstance(event.get("manager_status"), str) and event["manager_status"] in statuses:
            public["manager_status"] = event["manager_status"]
        if event["kind"] == "driver_failed":
            for key, accepted in (
                ("error_kind", error_kinds),
                ("reason", {"driver_io_failure", "effects_unsettled"}),
                ("stage", {"package_inspection", "session_context", "supervision"}),
            ):
                if isinstance(event.get(key), str) and event[key] in accepted:
                    public[key] = event[key]
            code = event.get("raw_native_code")
            if type(code) is int and -(2**31) <= code < 2**31:
                public["raw_native_code"] = code
        events.append(public)
    return {"events": events[-64:], "observation": "read", "invalid_lines": invalid, "tail_bounded": bool(offset)}


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("runtime lifecycle")
    group.addoption("--lifecycle-manager", type=Path, help="Debug manager lifecycle driver image")
    group.addoption("--lifecycle-package", type=Path, help="Complete real native package directory")


@pytest.fixture
def lifecycle_binaries(pytestconfig: pytest.Config) -> tuple[Path, Path]:
    manager = pytestconfig.getoption("lifecycle_manager")
    package = pytestconfig.getoption("lifecycle_package")
    if not isinstance(manager, Path) or not isinstance(package, Path):
        pytest.fail("Supply --lifecycle-manager and --lifecycle-package; see dev/runtime_lifecycle/README.md")
    return manager.resolve(strict=True), package.resolve(strict=True)


@pytest.fixture
def harness(
    lifecycle_binaries: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, record_property: Any
) -> Iterator[LifecycleHarness]:
    manager, package = lifecycle_binaries
    root = tmp_path / "storage"
    monkeypatch.setenv(STORAGE_ROOT.variable, str(root))
    monkeypatch.setenv(STORAGE_ROOT.development_variable, str(root))
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(package / "data/authority"))
    instance = LifecycleHarness(manager, package, root)
    try:
        with instance:
            probe = instance.connect(uuid4())
            instance.metrics["startup_seconds"] = time.monotonic() - instance.started
            probe.client.close()
            yield instance
    finally:
        record_property("lifecycle_seconds", json.dumps(instance.metrics, sort_keys=True))
        record_property("manager_events", json.dumps(_manager_evidence(root / "manager-events.jsonl"), sort_keys=True))
        record_property("runtime_faults", json.dumps(_runtime_faults(root / "logs/cadrumo.log")))
        if not instance.events():
            raise RuntimeError("Native lifecycle driver did not retain any public supervision evidence")
