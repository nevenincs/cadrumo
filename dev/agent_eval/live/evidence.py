"""Keep scrubbed evidence of a failed run before its root is removed.

A run that ends as a harness error or a product finding leaves a run root that
holds the only record of why: the runtime's log, the host's control files and
the runtime's own standard streams. Those are kept here, scrubbed, and only
after a fail-closed residual scan over everything about to be written. If any
file still carries a secret, nothing is kept and the receipt says so.

Only an allow-list is ever read: the log files under ``storage/logs``, the
named control files and the failed command-line calls the host recorded. The
profile password, keys, credential-store material and the encrypted storage
databases are never read, so they cannot be kept. Any other outcome removes the
run root and keeps nothing.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Final

from .capture import Scrubber
from .isolated_host import HEAD_CHARACTERS, FailedCall, RunDirectory, remove_run_directory
from .package_host import READY_FILE, RUNTIME_STDERR_FILE, RUNTIME_STDOUT_FILE, STOPPED_FILE

KEPT_OUTCOMES: Final = ("harness_error", "product_finding")
LOG_PATTERN: Final = "cadrumo.log*"
CONTROL_FILES: Final = (READY_FILE, STOPPED_FILE, RUNTIME_STDOUT_FILE, RUNTIME_STDERR_FILE)
MAXIMUM_FILE_BYTES: Final = 512 * 1024
"""The tail of a larger file is kept: the end of a log is where the failure is."""


def _tail(path: Path) -> str:
    with path.open("rb") as handle:
        size = handle.seek(0, 2)
        handle.seek(max(0, size - MAXIMUM_FILE_BYTES))
        return handle.read().decode("utf-8", errors="replace")


def _readable(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _candidates(run: RunDirectory) -> dict[str, Path]:
    found: dict[str, Path] = {}
    logs = run.root / "logs"
    if logs.is_dir() and not logs.is_symlink():
        found.update({f"logs-{path.name}": path for path in sorted(logs.glob(LOG_PATTERN)) if _readable(path)})
    found.update({f"control-{name}": run.control / name for name in CONTROL_FILES if _readable(run.control / name)})
    return found


def _failed_call_document(call: FailedCall) -> dict[str, Any]:
    document = asdict(call)
    document["stdout_head"] = call.stdout_head[:HEAD_CHARACTERS]
    document["stderr_head"] = call.stderr_head[:HEAD_CHARACTERS]
    return document


def keep_run_evidence(
    run: RunDirectory, directory: Path, scrubber: Scrubber, failures: Sequence[FailedCall], *, reason: str
) -> dict[str, Any]:
    """Write the run's scrubbed evidence under ``directory`` and describe what happened for the receipt.

    All-or-nothing: a residual secret in any file keeps nothing.
    """
    texts: dict[str, str] = {}
    for name, path in _candidates(run).items():
        try:
            texts[name] = scrubber.scrub(_tail(path))
        except OSError as error:
            texts[name] = f"[unreadable: {type(error).__name__}]"
    calls = [scrubber.scrub_value(_failed_call_document(call)) for call in failures]
    texts["failed-cli-calls.json"] = scrubber.scrub(json.dumps(calls, indent=2, sort_keys=True))
    leaking = sorted(name for name, text in texts.items() if scrubber.residual(text))
    entry: dict[str, Any] = {"reason": reason, "directory": directory.name}
    if leaking:
        return entry | {"kept": False, "withheld": "residual_scan_failed", "refused_files": leaking}
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        (directory / name).write_text(text + "\n", encoding="utf-8")
    return entry | {"kept": True, "files": sorted(texts)}


def settle_run_root(
    run: RunDirectory,
    base: Path,
    *,
    keep_reason: str | None,
    directory: Path,
    scrubber: Scrubber,
    failures: Sequence[FailedCall],
) -> dict[str, Any] | None:
    """Keep evidence when the outcome calls for it, then remove the run root whatever happened."""
    entry: dict[str, Any] | None = None
    try:
        if keep_reason in KEPT_OUTCOMES:
            entry = keep_run_evidence(run, directory, scrubber, failures, reason=str(keep_reason))
    finally:
        remove_run_directory(run, base)
    return entry
