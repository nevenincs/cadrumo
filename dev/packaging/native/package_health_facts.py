"""Project bounded diagnostic facts from staged package health logs."""

import json
from collections.abc import Set
from pathlib import Path
from typing import Final

from cadrumo.core.type_guards import is_str_keyed_dict

# Wire spellings of `ErrorCode` in native/application/src/error/application.rs; a parity
# gate compares this set with the enum and the frontend's `HostErrorCode`.
NATIVE_ERROR_CODES: Final = frozenset(
    {
        "invalid_arguments",
        "package_unavailable",
        "environment_failed",
        "timed_out",
        "output_limit",
        "spawn_failed",
        "child_failed",
        "read_failed",
        "write_failed",
        "resize_failed",
        "cleanup_failed",
        "session_unavailable",
        "setup_failed",
        "queue_full",
        "cli_busy",
        "cli_wait_timed_out",
        "lock_poisoned",
        "log_unavailable",
        "desktop_unavailable",
        "webview_failed",
        "webview_process_failed",
        "webview_monitor_unavailable",
        "unsupported_platform",
        "instance_lock_foreign",
        "manager_unavailable",
        "manager_dispatch_failed",
        "installation_unavailable",
        "installation_refused",
        "installation_cancelled",
        "installation_failed",
        "installation_unsettled",
        "panic",
    }
)


def health_events(root: Path) -> list[dict[str, object]]:
    """Read bounded native log events from the disposable health root."""
    events: list[dict[str, object]] = []
    for log in root.rglob("cadrumo-native.jsonl"):
        with log.open("rb") as stream:
            stream.seek(max(0, log.stat().st_size - 65536))
            lines = stream.read(65536).splitlines()
        for line in lines:
            try:
                event = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if is_str_keyed_dict(event):
                events.append(event)
    return events


def health_facts(root: Path) -> dict[str, object]:
    """Project bounded native codes and timings; discard messages and coordinates."""
    codes = NATIVE_ERROR_CODES
    stage_names = (
        "admission environment manager window shutdown job_escape instance storage package session supervision "
    )
    stages = set(stage_names.split())
    operation_names = "launch package environment cli terminal logging webview shutdown manager installation "
    operations = set(operation_names.split())
    io_kind_names = (
        "NotFound PermissionDenied ConnectionRefused ConnectionReset HostUnreachable NetworkUnreachable "
        "ConnectionAborted NotConnected AddrInUse AddrNotAvailable NetworkDown BrokenPipe AlreadyExists "
        "WouldBlock NotADirectory IsADirectory DirectoryNotEmpty ReadOnlyFilesystem FilesystemLoop "
        "StaleNetworkFileHandle InvalidInput InvalidData TimedOut WriteZero StorageFull NotSeekable "
        "QuotaExceeded FileTooLarge ResourceBusy ExecutableFileBusy Deadlock CrossesDevices TooManyLinks "
        "InvalidFilename ArgumentListTooLong Interrupted Unsupported UnexpectedEof OutOfMemory InProgress Other "
    )
    io_kinds = set(io_kind_names.split())
    failures: list[dict[str, object]] = []
    helpers: list[dict[str, object]] = []
    for event in health_events(root):
        if is_str_keyed_dict(failure := event.get("failure")):
            fact = _failure_fact(event, failure, stages, codes, operations, io_kinds)
            failures.append(fact)
        if event.get("kind") == "helper_timing" and is_str_keyed_dict(timing := event.get("helperTiming")):
            fact = _helper_timing_fact(timing)
            helpers.append(fact)
    return {"schema": 1, "failures": failures[-8:], "helpers": helpers[-8:]}


def _helper_timing_fact(timing: dict[str, object]) -> dict[str, object]:
    fact: dict[str, object] = {
        key: value
        for key, value in timing.items()
        if key in {"admissionWaitMs", "spawnMs", "executionMs", "cleanupMs", "outputJoinMs", "totalMs"}
        and type(value) is int
        and 0 <= value <= 2**64 - 1
    }
    for key, allowed in (
        ("helperKind", {"read", "mutation"}),
        ("outcome", {"admission_refused", "spawn_failed", "execution_failed", "completed"}),
    ):
        if isinstance(value := timing.get(key), str) and value in allowed:
            fact[key] = value
    return fact


def _failure_fact(
    event: dict[str, object],
    failure: dict[str, object],
    stages: Set[str],
    codes: Set[str],
    operations: Set[str],
    io_kinds: Set[str],
) -> dict[str, object]:
    fact: dict[str, object] = {
        "stage": _allowed_health_value(event.get("stage"), stages),
        "code": _allowed_health_value(failure.get("code"), codes, "unexpected"),
        "operation": _allowed_health_value(failure.get("operation"), operations),
        "ioKind": _allowed_health_value(failure.get("ioKind"), io_kinds),
        "osCode": failure.get("osCode")
        if type(value := failure.get("osCode")) is int and -(2**31) <= value <= 2**31 - 1
        else None,
    }
    return fact


def _allowed_health_value(value: object, allowed: Set[str], default: str | None = None) -> str | None:
    return value if isinstance(value, str) and value in allowed else default
