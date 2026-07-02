"""Local session telemetry: payload-free per-call trajectory records.

ADR R7's operational half: every console session leaves a local, per-call
trajectory record so the harness is measurable and a live failure can be
traced and promoted into a golden scenario. The records are deliberately
METADATA-ONLY — tool name, command key, confirmation route, error flag,
duration, and content HASHES of the arguments and result — never the payloads
themselves: a tool result carries the taxpayer's figures, and
`sensitive-financial-data-secure-storage-only` forbids persisting those
anywhere outside encrypted secure storage. A hash lets two records be compared
for identity (the flywheel's dedup needs that) without storing a single
figure; the full payloads exist only inside the eval harness's own in-memory
:class:`~agent.eval.LiveTrajectory` during a measurement run.

Records append as JSON lines to ``<aeat_local_storage_root>/telemetry/
<session_id>.jsonl``, following the same state-root derivation the diagnostic
log uses, so each workspace's telemetry stays isolated.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...core.config import load_settings
from ...core.external_constants import UTF_8_ENCODING as _UTF_8

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_TELEMETRY_DIRNAME = "telemetry"


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
        is_error: Whether the call returned an error result.
        duration_ms: Wall-clock round-trip duration.
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
    is_error: bool = False
    duration_ms: int = Field(ge=0, default=0)
    arguments_sha256: str = ""
    result_sha256: str = ""


def content_sha256(text: str) -> str:
    """The one-way content reference telemetry stores instead of a payload."""
    return hashlib.sha256(text.encode(_UTF_8)).hexdigest()


def telemetry_dir() -> Path:
    """The workspace-scoped telemetry directory under the local storage root."""
    return load_settings().aeat_local_storage_root / _TELEMETRY_DIRNAME


class SessionTelemetryWriter:
    """Appends one session's records to its JSONL file, creating lazily.

    The writer is deliberately dumb and append-only: no rotation, no read
    path — the flywheel and any operator inspection read the files directly,
    and a rebuildable derived surface must never become a correctness
    dependency.
    """

    def __init__(self, *, session_id: str, directory: Path | None = None) -> None:
        self._session_id = session_id
        self._directory = directory if directory is not None else telemetry_dir()
        self._sequence = 0

    @property
    def session_id(self) -> str:
        """The session identity every record of this writer carries."""
        return self._session_id

    @property
    def path(self) -> Path:
        """The JSONL file this session appends to."""
        return self._directory / f"{self._session_id}.jsonl"

    def record(
        self,
        *,
        tool_name: str,
        command_key: str = "",
        route: str = "",
        is_error: bool = False,
        duration_ms: int = 0,
        arguments_text: str = "",
        result_text: str = "",
    ) -> ToolCallTelemetryRecord:
        """Append one payload-free record and return it.

        Returns:
            A :class:`ToolCallTelemetryRecord`.
        """
        row = ToolCallTelemetryRecord(
            session_id=self._session_id,
            sequence=self._sequence,
            tool_name=tool_name,
            command_key=command_key,
            route=route,
            is_error=is_error,
            duration_ms=duration_ms,
            arguments_sha256=content_sha256(arguments_text) if arguments_text else "",
            result_sha256=content_sha256(result_text) if result_text else "",
        )
        self._sequence += 1
        self._directory.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding=_UTF_8) as sink:
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
    "ToolCallTelemetryRecord",
    "content_sha256",
    "read_session_records",
    "telemetry_dir",
]
