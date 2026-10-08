"""Reduce registry health collector output to its truthful command-run envelope."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Final

from .signal_values import _is_json_object

_REGISTRY_HEALTH_SIGNAL: Final[str] = "registry-health"


_BINDING_SIGNAL: Final[str] = "binding-signal"


class _RegistryHealthProcessor:
    """Reduce the registry collector's strict JSON to one persisted run envelope."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def consume(self, line: str) -> None:
        self.lines.append(line)

    def envelope(
        self,
        *,
        label: str,
        run_dir: Path,
        log_path: Path,
        exit_status: int,
        started: datetime,
        finished: datetime,
    ) -> dict[str, object]:
        payload = _registry_health_payload(self.lines)
        if payload is None:
            diagnostic = next(
                (
                    line.strip()
                    for line in reversed(self.lines)
                    if line.strip() and not line.lstrip().startswith(("File ", "Traceback (", "^"))
                ),
                "child command produced no diagnostic output",
            )
            error_type, separator, error_message = diagnostic.partition(":")
            payload = {
                "schema_version": 1,
                "command": label,
                "posture": "blocking" if label == "check-registry" else "advisory",
                "result": "failed",
                "classification": "tool_failure",
                "headline": f"Registry health could not start: {diagnostic}",
                "summary": {
                    "lanes_total": 0,
                    "lanes_passed": 0,
                    "lanes_failed": 0,
                    "lanes_partial": 0,
                    "details_total": 1,
                },
                "lanes": {},
                "failed_lanes": [],
                "partial_lanes": [],
                "targets": {},
                "authority": {},
                "details": [diagnostic],
                "actions": [],
                "error": {
                    "type": error_type if separator else "ChildProcessError",
                    "message": error_message.strip() if separator else diagnostic,
                },
            }
        payload["exit_status"] = exit_status
        payload["event"] = "run_finished"
        payload["duration_seconds"] = round((finished - started).total_seconds(), 3)
        payload["run_id"] = run_dir.name
        payload["run_outputs"] = {
            "log": str(log_path),
            "metadata": str(run_dir / "run.json"),
        }
        return payload


def _registry_health_payload(lines: list[str]) -> dict[str, object] | None:
    """Select the last complete JSON object before falling back to diagnostic evidence."""
    payload: dict[str, object] | None = None
    for line in reversed(lines):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if _is_json_object(candidate):
            payload = candidate
            break
    return payload
