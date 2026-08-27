"""Local session telemetry: payload-free per-call trajectory records.

Every console session leaves a local, per-call
trajectory record so the harness is measurable and a live failure can be
traced and promoted into a golden scenario. The records are deliberately
METADATA-ONLY — tool name, command key, confirmation route, error flag,
duration, and content HASHES of the arguments and result — never the payloads
themselves: a tool result carries the taxpayer's figures, and
`sensitive-financial-data-secure-storage-only` forbids persisting those
anywhere outside encrypted secure storage. A hash lets two records be compared
for identity (the flywheel's dedup needs that) without storing a single
figure; the full payloads exist only inside the eval harness's own in-memory
in-memory trajectory record during a measurement run.

Records append as JSON lines to ``<cadrumo_local_storage_root>/telemetry/
<session_id>.jsonl``, following the same state-root derivation the diagnostic
log uses, so each workspace's telemetry stays isolated.

The directory is bounded, not unbounded: a :class:`SessionTelemetryWriter`
sweeps its directory once at construction (server start) via
:func:`prune_telemetry`, dropping trajectory files past an age or count bound
while ALWAYS preserving the newest N sessions. Retention only ever removes whole
per-session files — it never touches the payload-free posture of the rows that
remain, and telemetry is a rebuildable derived surface, so a pruned file is a
lost measurement sample, never a correctness dependency.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.config import load_settings
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import UTF_8_ENCODING as _UTF_8
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.paths import select_filesystem_retention_survivors

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_SECONDS_PER_DAY = 86_400
_SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")


class ToolCallTelemetryRecord(BaseModel):
    """One payload-free tool-call record in a session's trajectory.

    Attributes:
        session_id: The serving session this call belongs to.
        sequence: Zero-based position of the call within the session.
        tool_name: The MCP tool name the client invoked.
        command_key: The registry command key the tool maps to (empty for
            meta/harness tools).
        route: The confirmation route the call took (a
            ``ConfirmRoute``/``ConfirmDecision`` value string), so override
            and refusal rates are computable from telemetry alone.
        transport: The transport that actually served the call (an
            ``McpTransport`` value string: warm in-process, supervised
            subprocess, or the degraded subprocess fallback); empty for a
            refusal that never dispatched.
        is_error: Whether the call returned an error result.
        duration_ms: Wall-clock round-trip duration.
        executable_sha256: SHA-256 of the attested environment CLI path - the
            executable supplied to the supervised runtime, or the resolved
            sibling CLI of the environment a warm in-process call served from;
            empty when the call never dispatched.
        arguments_sha256: SHA-256 of the canonical arguments JSON.
        result_sha256: SHA-256 of the result text; empty for refused calls
            that never ran.
    """

    model_config = _STRICT_FROZEN

    session_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    tool_name: str = Field(min_length=1)
    command_key: str = ""
    route: str = ""
    transport: str = ""
    is_error: bool = False
    duration_ms: int = Field(ge=0, default=0)
    executable_sha256: str = ""
    arguments_sha256: str = ""
    result_sha256: str = ""


def content_sha256(text: str) -> str:
    """The one-way content reference telemetry stores instead of a payload."""
    return sha256_hex(text.encode(_UTF_8))


def telemetry_dir() -> Path:
    """Return the harness-owned, workspace-scoped telemetry directory."""
    configured = os.environ.get("CADRUMO_MCP_TELEMETRY_DIR")
    if configured:
        return Path(configured)
    return load_settings().cadrumo_local_storage_root / "telemetry"


def _session_telemetry_path(directory: Path, *, session_id: str) -> Path:
    """Return the resolved telemetry path for one safe session identifier."""
    if not isinstance(session_id, str) or _SESSION_ID_PATTERN.fullmatch(session_id) is None:
        raise ValueError("session_id must be a safe telemetry filename identifier")
    root = directory.resolve()
    path = (root / f"{session_id}.jsonl").resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("session_id must resolve within the telemetry directory") from exc
    return path


class TelemetryRetention(BaseModel):
    """The bounds the startup trajectory-file sweep enforces.

    Attributes:
        max_age_days: Sessions whose file is older than this are pruned.
        max_sessions: The maximum number of session files kept; the oldest
            beyond this count are pruned.
        keep_newest: The newest N sessions are ALWAYS retained, whatever their
            age or the count bound — the sweep never removes them.
    """

    model_config = _STRICT_FROZEN

    max_age_days: float = Field(gt=0, default=30.0)
    max_sessions: int = Field(ge=1, default=200)
    keep_newest: int = Field(ge=0, default=20)


def prune_telemetry(
    directory: Path,
    *,
    max_age_days: float,
    max_sessions: int,
    keep_newest: int,
    now: float | None = None,
) -> tuple[Path, ...]:
    """Prune per-session trajectory files by age and count, never the newest N.

    Session files are ranked newest-first by modification time (ties broken by
    filename for determinism). The newest ``keep_newest`` are retained
    unconditionally. Of the remainder, a file is removed when it falls beyond
    the ``max_sessions`` count bound OR is older than ``max_age_days`` — the
    survivor decision delegates to the shared
    :func:`~cadrumo.core.paths.select_filesystem_retention_survivors`
    selector in its ``combine="union"`` mode (age and count evaluated
    independently, not staged, since a rank-3 session within the age window
    must still be prunable for being beyond the count bound), with
    ``protect_newest=keep_newest``.

    Args:
        directory: The telemetry directory to sweep. A missing directory is a
            no-op (returns an empty tuple).
        max_age_days: Age bound in days; files with an older mtime are pruned.
        max_sessions: Count bound; files ranked at or beyond this position
            (newest-first, zero-based) are pruned.
        keep_newest: The number of newest sessions to retain unconditionally.
        now: Reference epoch seconds for the age comparison; defaults to the
            wall clock. Injected by tests for deterministic ages.

    Returns:
        The tuple of file paths removed, in the order they were pruned.
    """
    if not directory.exists():
        return ()
    reference = time.time() if now is None else now
    cutoff = reference - max_age_days * _SECONDS_PER_DAY
    entries = [(path, path.stat().st_mtime) for path in scan_directory(directory, pattern="*.jsonl")]
    # Pre-sort by filename descending: the shared selector's stable,
    # timestamp-only sort then preserves this order for any mtime tie,
    # reproducing the newest-first-by-(mtime, name) tie-break deterministically
    # (common in a fast test that writes a burst of sessions).
    entries.sort(key=lambda item: item[0].name, reverse=True)
    _keep, stale = select_filesystem_retention_survivors(
        entries,
        timestamp=lambda item: item[1],
        cutoff=cutoff,
        max_count=max_sessions,
        combine="union",
        protect_newest=keep_newest,
    )
    removed: list[Path] = []
    for path, _mtime in stale:
        path.unlink()
        removed.append(path)
    return tuple(removed)


class SessionTelemetryWriter:
    """Appends one session's records to its JSONL file, creating lazily.

    The writer is append-only for its own session's rows. At construction
    (server start) it runs a single best-effort :func:`prune_telemetry` sweep
    over its directory so a long-lived installation's telemetry stays bounded;
    the sweep is best-effort because a locked or vanished peer file must never
    abort a new session's telemetry. The read path is :func:`read_session_records`;
    the flywheel and any operator inspection read the files back through it, and
    a rebuildable derived surface must never become a correctness dependency.
    """

    def __init__(
        self,
        *,
        session_id: str,
        directory: Path | None = None,
        retention: TelemetryRetention | None = None,
    ) -> None:
        self._session_id = session_id
        self._directory = (directory if directory is not None else telemetry_dir()).resolve()
        self._path = _session_telemetry_path(self._directory, session_id=session_id)
        self._retention = retention if retention is not None else TelemetryRetention()
        self._sequence = 0
        # Best-effort retention: a locked/racing peer file on a shared host must
        # not stop this session from recording, so a sweep error is suppressed
        # and the next server start retries the prune.
        with contextlib.suppress(OSError):
            prune_telemetry(
                self._directory,
                max_age_days=self._retention.max_age_days,
                max_sessions=self._retention.max_sessions,
                keep_newest=self._retention.keep_newest,
            )

    @property
    def session_id(self) -> str:
        """The session identity every record of this writer carries."""
        return self._session_id

    @property
    def path(self) -> Path:
        """The JSONL file this session appends to."""
        return self._path

    def record(
        self,
        *,
        tool_name: str,
        command_key: str = "",
        route: str = "",
        transport: str = "",
        is_error: bool = False,
        duration_ms: int = 0,
        executable_text: str = "",
        arguments_text: str = "",
        result_text: str = "",
    ) -> ToolCallTelemetryRecord:
        """Append one payload-free record and return it.

        Returns:
            A :class:`ToolCallTelemetryRecord`.
        """
        row = ToolCallTelemetryRecord(
            session_id=self.session_id,
            sequence=self._sequence,
            tool_name=tool_name,
            command_key=command_key,
            route=route,
            transport=transport,
            is_error=is_error,
            duration_ms=duration_ms,
            executable_sha256=content_sha256(executable_text) if executable_text else "",
            arguments_sha256=content_sha256(arguments_text) if arguments_text else "",
            result_sha256=content_sha256(result_text) if result_text else "",
        )
        self._sequence += 1
        # Best-effort write: telemetry is diagnostics, never a dependency of
        # the tool call it observes. A telemetry directory that turned
        # unwritable mid-session must not fail the call; the row is still
        # returned so the caller's in-memory view stays coherent.
        with contextlib.suppress(OSError):
            self._directory.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding=_UTF_8, newline="\n") as sink:
                sink.write(json.dumps(row.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
                sink.write("\n")
        return row


def read_session_records(path: Path) -> tuple[ToolCallTelemetryRecord, ...]:
    """Load one session file back into typed records (a strict roundtrip surface).

    Returns:
        A :class:`ToolCallTelemetryRecord`.
    """
    rows: list[ToolCallTelemetryRecord] = []
    for line in path.read_text(encoding=_UTF_8).splitlines():
        if line.strip():
            rows.append(ToolCallTelemetryRecord.model_validate(json.loads(line)))
    return tuple(rows)


__all__ = [
    "SessionTelemetryWriter",
    "TelemetryRetention",
    "ToolCallTelemetryRecord",
    "content_sha256",
    "prune_telemetry",
    "read_session_records",
    "telemetry_dir",
]
