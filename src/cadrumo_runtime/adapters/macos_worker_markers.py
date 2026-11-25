"""Canonical macOS worker ownership markers and scoped stale selection."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .macos_job_print import MAXIMUM_MACOS_PID
from .macos_process import MacosProcessIncarnation

MACOS_WORKER_LABEL_PREFIX = "com.cadrumo.worker."
MACOS_WORKER_LABEL_PATTERN = re.compile(r"com\.cadrumo\.worker\.[0-9a-f]{16}\.[0-9a-f]{32}")
MACOS_SCOPE_KEY_PATTERN = re.compile(r"[0-9a-f]{16}")
MACOS_MARKER_SUFFIX = ".json"
MACOS_MARKER_LIMIT = 4096


@dataclass(frozen=True, slots=True)
class MacosWorkerMarker:
    """Crash-durable ownership record naming one job and its runtime incarnation."""

    label: str
    runtime: MacosProcessIncarnation
    coalition: int | None


def encode_macos_worker_marker(marker: MacosWorkerMarker) -> bytes:
    """Render the one canonical marker encoding.

    Args:
        marker: Ownership record to persist.
    """
    if not MACOS_WORKER_LABEL_PATTERN.fullmatch(marker.label) or (
        marker.coalition is not None and marker.coalition <= 0
    ):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    return json.dumps(
        {
            "coalition": marker.coalition,
            "label": marker.label,
            "runtime_pid": marker.runtime.pid,
            "runtime_unique_id": marker.runtime.unique_id,
            "runtime_version": marker.runtime.version,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _valid_incarnation_numbers(pid: int, version: int, unique_id: int) -> bool:
    return 0 < pid <= MAXIMUM_MACOS_PID and 0 < version <= MAXIMUM_MACOS_PID and unique_id > 0


def _marker_fields_valid(
    label: object, name: str, pid: object, version: object, unique_id: object, coalition: object
) -> bool:
    return (
        isinstance(label, str)
        and name == label + MACOS_MARKER_SUFFIX
        and type(pid) is int
        and type(version) is int
        and type(unique_id) is int
        and (coalition is None or type(coalition) is int)
    )


def decode_macos_worker_marker(payload: bytes, *, name: str) -> MacosWorkerMarker:
    """Accept only a canonical marker whose label matches its file name.

    Args:
        payload: Complete marker file contents.
        name: Marker file name within the private marker directory.
    """
    if len(payload) > MACOS_MARKER_LIMIT:
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    try:
        document: object = json.loads(payload.decode("ascii"))
    except (UnicodeError, ValueError):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE) from None
    if not isinstance(document, dict):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    fields = cast(dict[object, object], document)
    label = fields.get("label")
    pid = fields.get("runtime_pid")
    version = fields.get("runtime_version")
    unique_id = fields.get("runtime_unique_id")
    coalition = fields.get("coalition")
    if not _marker_fields_valid(label, name, pid, version, unique_id, coalition):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    label = cast(str, label)
    pid, version, unique_id = cast(int, pid), cast(int, version), cast(int, unique_id)
    coalition = cast(int | None, coalition)
    if not _valid_incarnation_numbers(pid, version, unique_id):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    marker = MacosWorkerMarker(
        label=label,
        runtime=MacosProcessIncarnation(pid=pid, version=version, unique_id=unique_id),
        coalition=coalition,
    )
    if encode_macos_worker_marker(marker) != payload:
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    return marker


def stale_macos_worker_markers(
    entries: Mapping[str, bytes], *, scope_key: str, live: Callable[[MacosProcessIncarnation], bool]
) -> tuple[MacosWorkerMarker, ...]:
    """Select this storage scope's markers whose runtime incarnation has died.

    Other scopes' entries are never decoded or returned. A corrupt marker of
    this scope refuses rather than being silently skipped.

    Args:
        entries: Marker file names and contents from the private directory.
        scope_key: Storage-scope key whose markers may be reaped.
        live: Whether an exact runtime incarnation is still alive.
    """
    prefix = f"{MACOS_WORKER_LABEL_PREFIX}{scope_key}."
    stale: list[MacosWorkerMarker] = []
    for name in sorted(entries):
        if not name.startswith(prefix) or not name.endswith(MACOS_MARKER_SUFFIX):
            continue
        marker = decode_macos_worker_marker(entries[name], name=name)
        if not live(marker.runtime):
            stale.append(marker)
    return tuple(stale)
