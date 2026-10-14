"""Serve an explicitly configured storage root for the process that launched this runtime.

The installed manager supervises only the canonical default root. A caller that
selects another root with ``CADRUMO_LOCAL_STORAGE_ROOT`` owns that root's
runtime itself: it starts the process, reads one readiness line from standard
output, and ends the runtime by closing standard input. A caller that exits
closes that pipe too, so a runtime never outlives the owner of its root.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from threading import Event, Thread
from typing import Protocol

from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.paths import effective_storage_root
from cadrumo.core.storage_environment import (
    configured_root_value,
    ensure_storage_root,
    host_installed_default_root,
    normalize_storage_path,
    storage_mode,
)
from cadrumo_client.contracts.contracts import ExitReason, RefusalCode, RefusalError

from .shutdown import RuntimeStop

_READ_CHUNK_BYTES = 4096


class CallerServing(Protocol):
    """The transport fact the readiness line waits for."""

    @property
    def ready(self) -> Event:
        """Return the event set once the listener owns the endpoint."""
        ...


def configured_storage_root() -> Path:
    """Return the explicitly configured root that clients of this environment resolve.

    The root comes from the same settings resolution every CLI, TUI and external client
    client uses to derive its endpoint. Without an explicit override, or when the
    override names the installed default root, the runtime refuses: that root
    belongs to the installed manager.
    """
    try:
        if configured_root_value(os.environ, storage_mode().mode) is None:
            raise RefusalError(RefusalCode.ROOT_MISMATCH)
        root = normalize_storage_path(effective_storage_root())
        # Refuse before creating anything, so a refused root is left untouched.
        if _overlaps_installed_default(root):
            raise RefusalError(RefusalCode.ROOT_MISMATCH)
        return ensure_storage_root(root)
    except CoreValidationError:
        raise RefusalError(RefusalCode.ROOT_MISMATCH) from None


def _overlaps_installed_default(root: Path) -> bool:
    """Report whether ``root`` is, contains or lies inside the installed default root."""
    try:
        default = normalize_storage_path(host_installed_default_root(os.environ))
    except CoreValidationError:
        # A host with no per-user data directory has no installed default to collide with.
        return False
    root_text, default_text = os.path.normcase(str(root)), os.path.normcase(str(default))
    if root_text == default_text or Path(root_text).is_relative_to(default_text):
        return True
    if Path(default_text).is_relative_to(root_text):
        return True
    try:
        return default.exists() and root.samefile(default)
    except OSError:
        return False


class CallerOwnedRuntime:
    """Tie this runtime's lifetime to the launching caller's standard streams."""

    def __init__(self, stop: RuntimeStop) -> None:
        """Bind the runtime's stop latch."""
        self._stop = stop

    def start(self) -> None:
        """Request a stop when the caller closes standard input or the pipe breaks."""
        Thread(target=self._watch_input, name="runtime-caller-input", daemon=True).start()

    def attach(self, serving: CallerServing, *, pid: int, version: str, storage_identity: str) -> None:
        """Print the readiness line once ``serving`` owns the endpoint."""
        line = json.dumps(
            {
                "kind": "runtime_ready",
                "pid": pid,
                "product_version": version,
                "storage_identity": storage_identity,
            },
            separators=(",", ":"),
        )
        Thread(target=self._announce_ready, args=(serving, line), name="runtime-caller-ready", daemon=True).start()

    def _watch_input(self) -> None:
        try:
            while os.read(0, _READ_CHUNK_BYTES):
                pass
        except OSError:
            pass
        self._stop.request(ExitReason.SUPERVISOR_STOP)

    def _announce_ready(self, serving: CallerServing, line: str) -> None:
        while not self._stop.is_set():
            if serving.ready.wait(0.05):
                try:
                    sys.stdout.write(line + "\n")
                    sys.stdout.flush()
                except (OSError, ValueError):
                    # Nobody reads the readiness line; the caller has gone.
                    self._stop.request(ExitReason.SUPERVISOR_STOP)
                return
