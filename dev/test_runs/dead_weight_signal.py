"""Carry duplication and dead-code observations into their command-run signal envelope."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Final

from .signal_values import _UTF_8, _is_json_object

_AUDIT_DEAD_WEIGHT_SIGNAL: Final[str] = "audit-dead-weight"


class _DeadWeightSignalProcessor:
    """Reduce the combined dead-weight payload to a stable run envelope."""

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
        summary: dict[str, object]
        try:
            decoded = json.loads("".join(self.lines))
            if not _is_json_object(decoded):
                raise ValueError("audit payload is not a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            outcome = "unavailable"
            headline = f"{label} signal could not be normalized: {exc}"
            summary = {
                "duplication": {
                    "result": "unavailable",
                    "available": False,
                    "scanned_total": 0,
                    "findings_total": 0,
                    "rate": 0.0,
                },
                "dead_code": {
                    "result": "unavailable",
                    "available": False,
                    "scanned_total": 0,
                    "findings_total": 0,
                    "rate": 0.0,
                },
            }
        else:
            outcome = str(decoded.get("outcome", "unavailable"))
            headline = str(decoded.get("headline", f"{label} produced no headline"))
            raw_summary = decoded.get("summary", {})
            if not _is_json_object(raw_summary):
                outcome = "unavailable"
                headline = f"{label} signal contained no structured summary"
                summary = {
                    "duplication": {
                        "result": "unavailable",
                        "available": False,
                        "scanned_total": 0,
                        "findings_total": 0,
                        "rate": 0.0,
                    },
                    "dead_code": {
                        "result": "unavailable",
                        "available": False,
                        "scanned_total": 0,
                        "findings_total": 0,
                        "rate": 0.0,
                    },
                }
            else:
                summary = raw_summary
        signal_artifact = {
            "schema_version": 1,
            "run_id": run_dir.name,
            "summary": summary,
        }
        (run_dir / "artifacts" / "dead-weight-signal.json").write_text(
            json.dumps(signal_artifact, indent=2, sort_keys=True) + "\n",
            encoding=_UTF_8,
            newline="\n",
        )
        result = {
            "findings": "findings",
            "clean": "clean",
        }.get(outcome, "unavailable")
        return {
            "command": label,
            "duration_seconds": round((finished - started).total_seconds(), 3),
            "event": "run_finished",
            "exit_status": exit_status,
            "headline": headline,
            "posture": "advisory",
            "result": result,
            "run_id": run_dir.name,
            "run_outputs": {
                "log": str(log_path),
                "metadata": str(run_dir / "run.json"),
            },
            "schema_version": 1,
            "summary": summary,
        }
