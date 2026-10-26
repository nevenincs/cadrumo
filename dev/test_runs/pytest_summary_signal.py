"""Accumulate pytest and lane transcript state and project the completed command-run envelope."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Final

from .pytest_lane_projection import (
    _lane_envelope,
    _lane_tool_failed,
    _only_collection_errors,
    _summaryless_collection_failure,
    _summaryless_load_failure,
    _summaryless_tool_failure,
)
from .pytest_transcript_syntax import (
    _PYTEST_COUNT_RE,
    _PYTEST_OUTCOME_KEYS,
    _PYTEST_SUMMARY_RE,
    _REGISTRY_LOAD_FAILURE_RE,
    _ROOT_CAUSE_RE,
    _TEST_IDENTITY_RE,
    _lane_marker,
    _normalize_root_cause,
)
from .signal_values import _json_int, _json_string_list

_PYTEST_SUMMARY_SIGNAL: Final[str] = "pytest-summary"


class _PytestSummaryProcessor:
    """Reduce one or more pytest transcripts to stable aggregate counters."""

    def __init__(self, expected_lanes: tuple[str, ...] = ()) -> None:
        self.counts: Counter[str] = Counter()
        self.lanes = 0
        self.pytest_duration_seconds = 0.0
        self.current_lane: str | None = None
        self.lane_data: dict[str, dict[str, object]] = {}
        self.expected_lanes = expected_lanes

    def _lane(self) -> dict[str, object]:
        name = self.current_lane or "unlabelled"
        return self.lane_data.setdefault(
            name,
            {
                "counts": Counter(),
                "failed_nodes": set(),
                "root_causes": Counter(),
                "internal_error": False,
                "kind": "command",
                "role": "execution",
                "skipped": False,
                "blocked_by": (),
                "skip_reason": None,
                "status": None,
                "seconds": None,
            },
        )

    def consume(self, line: str) -> dict[str, object] | None:
        text = line.strip()
        marker = _lane_marker(text)
        if marker is not None:
            return _consume_lane_event(self, marker)
        _record_pytest_diagnostics(self, text)
        match = _PYTEST_SUMMARY_RE.fullmatch(text)
        if match is None:
            return None
        lane_counts = Counter(
            {
                _PYTEST_OUTCOME_KEYS[count.group("outcome")]: int(count.group("count"))
                for count in _PYTEST_COUNT_RE.finditer(match.group("summary"))
            }
        )
        if not lane_counts:
            return
        self.counts.update(lane_counts)
        lane_counts_store = self._lane()["counts"]
        assert isinstance(lane_counts_store, Counter)
        lane_counts_store.update(lane_counts)
        self.lanes += 1
        self.pytest_duration_seconds += float(match.group("duration"))
        return None

    def _lane_envelopes(self) -> list[dict[str, object]]:
        lanes: list[dict[str, object]] = []
        names = self.expected_lanes or tuple(self.lane_data)
        for name in names:
            lanes.append(_lane_envelope(name, self.lane_data.get(name)))
        return lanes

    def _completion(self) -> tuple[int, int, int, bool]:
        """Return completed, blocked, expected, and complete lane counts."""
        names = self.expected_lanes or tuple(self.lane_data)
        completed = sum(self.lane_data.get(name, {}).get("status") is not None for name in names)
        blocked = sum(bool(self.lane_data.get(name, {}).get("skipped")) for name in names)
        expected = len(names)
        return completed, blocked, expected, completed + blocked == expected

    def effective_exit_status(self, child_exit_status: int) -> int:
        """Fail closed when an expected lane never reaches a terminal event."""
        if child_exit_status != 0 or not self.expected_lanes:
            return child_exit_status
        _, blocked, _, complete = self._completion()
        lane_failed = any(data["status"] not in (None, 0) for data in self.lane_data.values())
        return child_exit_status if complete and not blocked and not lane_failed else 7

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
        failures = self.counts["failed"]
        errors = self.counts["error"]
        completed, blocked, expected, complete = self._completion()
        summaryless_collection_failed = sum(_summaryless_collection_failure(data) for data in self.lane_data.values())
        summaryless_tool_failed = sum(_summaryless_tool_failure(data) for data in self.lane_data.values())
        summaryless_load_failed = sum(_summaryless_load_failure(data) for data in self.lane_data.values())
        classification, headline = _pytest_headline(
            self,
            label,
            exit_status,
            completed,
            blocked,
            expected,
            complete,
            failures,
            errors,
            summaryless_collection_failed,
            summaryless_tool_failed,
            summaryless_load_failed,
        )
        outcomes = {
            outcome: self.counts[outcome]
            for outcome in (
                "collected",
                "passed",
                "failed",
                "error",
                "skipped",
                "deselected",
                "xfailed",
                "xpassed",
                "warning",
            )
        }
        outcomes["total_selected"] = sum(
            self.counts[outcome] for outcome in ("passed", "failed", "error", "skipped", "xfailed", "xpassed")
        )
        return {
            "classification": classification,
            "command": label,
            "duration_seconds": round((finished - started).total_seconds(), 3),
            "event": "run_finished",
            "exit_status": exit_status,
            "headline": headline,
            "pytest_duration_seconds": round(self.pytest_duration_seconds, 3),
            "result": "passed" if exit_status == 0 else "failed",
            "run_id": run_dir.name,
            "run_outputs": {"log": str(log_path), "metadata": str(run_dir / "run.json")},
            "schema_version": 1,
            "summary": {
                "complete": complete,
                "lanes_completed": completed,
                "lanes_expected": expected,
                "lanes_failed": sum(data["status"] not in (None, 0) for data in self.lane_data.values()),
                "lanes_tool_failed": sum(_lane_tool_failed(data) for data in self.lane_data.values()),
                "lanes_load_failed": summaryless_load_failed,
                "lanes_blocked": blocked,
                "lanes_not_run": expected - completed - blocked,
                "pytest_invocations": self.lanes,
                **outcomes,
            },
            "lanes": self._lane_envelopes(),
        }


def _lane_started(self: _PytestSummaryProcessor, marker: dict[str, object]) -> dict[str, object]:
    """Apply the lane started event and emit its transcript projection."""
    self.current_lane = str(marker["lane"])
    lane = self._lane()
    lane["kind"] = str(marker.get("kind", "command"))
    lane["role"] = str(marker.get("role", "execution"))
    return {
        "event": "lane_started",
        "kind": lane["kind"],
        "lane": self.current_lane,
        "role": lane["role"],
        "status": "running",
    }


def _lane_finished(self: _PytestSummaryProcessor, marker: dict[str, object]) -> dict[str, object]:
    """Apply the lane finished event and emit its transcript projection."""
    self.current_lane = str(marker["lane"])
    lane = self._lane()
    status = _json_int(marker["exit_status"], field="exit_status")
    lane["kind"] = str(marker.get("kind", lane["kind"]))
    lane["role"] = str(marker.get("role", lane["role"]))
    lane["status"] = status
    lane["seconds"] = _json_int(marker["seconds"], field="seconds")
    return {
        "event": "lane_finished",
        "kind": lane["kind"],
        "lane": self.current_lane,
        "role": lane["role"],
        "seconds": lane["seconds"],
        "status": "passed" if status == 0 else "failed",
        "exit_status": status,
    }


def _lane_skipped(self: _PytestSummaryProcessor, marker: dict[str, object]) -> dict[str, object]:
    """Apply the lane skipped event and emit its transcript projection."""
    self.current_lane = str(marker["lane"])
    lane = self._lane()
    blocked_by = () if "blocked_by" not in marker else _json_string_list(marker["blocked_by"], field="blocked_by")
    lane["kind"] = str(marker.get("kind", "command"))
    lane["role"] = str(marker.get("role", "execution"))
    lane["skipped"] = True
    lane["blocked_by"] = blocked_by
    lane["skip_reason"] = str(marker.get("reason", "preflight_failed"))
    return {
        "blocked_by": list(blocked_by),
        "event": "lane_skipped",
        "kind": lane["kind"],
        "lane": self.current_lane,
        "reason": lane["skip_reason"],
        "role": lane["role"],
        "status": "blocked",
    }


def _record_pytest_diagnostics(self: _PytestSummaryProcessor, text: str) -> None:
    """Collect failed test identities and typed root causes before reading terminal counts."""
    identity = _TEST_IDENTITY_RE.fullmatch(text)
    if identity is not None:
        failed_nodes = self._lane()["failed_nodes"]
        assert isinstance(failed_nodes, set)
        failed_nodes.add((identity.group("node"), identity.group("file")))
    diagnostic_text = text
    if diagnostic_text.startswith("INTERNALERROR>"):
        self._lane()["internal_error"] = True
        diagnostic_text = diagnostic_text.removeprefix("INTERNALERROR>").strip()
    root_cause = _ROOT_CAUSE_RE.fullmatch(diagnostic_text)
    if root_cause is None and str(self._lane()["kind"]) == "load":
        root_cause = _REGISTRY_LOAD_FAILURE_RE.fullmatch(diagnostic_text)
    if root_cause is not None:
        causes = self._lane()["root_causes"]
        assert isinstance(causes, Counter)
        signature = _normalize_root_cause(root_cause.group("message"))
        causes[(root_cause.group("type"), signature)] += 1


def _consume_lane_event(self: _PytestSummaryProcessor, marker: dict[str, object]) -> dict[str, object]:
    """Dispatch the closed lane-event vocabulary after parsing the complete marker."""
    if marker["event"] == "lane_started":
        return _lane_started(self, marker)
    if marker["event"] == "lane_finished":
        return _lane_finished(self, marker)
    return _lane_skipped(self, marker)


def _pytest_headline(
    self: _PytestSummaryProcessor,
    label: str,
    exit_status: int,
    completed: int,
    blocked: int,
    expected: int,
    complete: bool,
    failures: int,
    errors: int,
    summaryless_collection_failed: int,
    summaryless_tool_failed: int,
    summaryless_load_failed: int,
) -> tuple[str, str]:
    """Render the original result precedence from incomplete through execution failures."""
    if not complete:
        classification = "incomplete"
        headline = f"{label} was incomplete: {completed} of {expected} lanes completed; inspect the run log."
    elif blocked:
        classification = "preflight_failure"
        headline = (
            f"{label} stopped after a failed preflight: {blocked} granular lanes were blocked; "
            "inspect the preflight lane evidence."
        )
    elif exit_status == 0:
        classification = "clean"
        headline = (
            f"{label} passed: {self.counts['passed']} tests passed across "
            f"{self.lanes} pytest invocations and {completed} lanes."
        )
    elif summaryless_tool_failed:
        classification = "tool_failure"
        headline = (
            f"{label} had {summaryless_tool_failed} lane(s) fail before producing a terminal summary; "
            "inspect the run log."
        )
    elif summaryless_collection_failed:
        classification = "collection_failure"
        headline = (
            f"{label} had {summaryless_collection_failed} collection lane(s) fail before a terminal summary; "
            "inspect the collection evidence."
        )
    elif summaryless_load_failed:
        classification = "load_failure"
        headline = f"{label} had {summaryless_load_failed} registry load lane(s) fail;"
        headline += " inspect the typed load evidence."
    elif self.lanes == 0:
        classification = "tool_failure"
        headline = f"{label} failed before any pytest invocation produced a terminal summary; inspect the run log."
    elif _only_collection_errors(errors, self.counts["passed"], failures):
        classification = "collection_failure"
        headline = f"{label} could not collect tests: {errors} collection errors across {self.lanes} lanes."
    else:
        classification = "blocking_findings"
        headline = f"{label} failed: {failures} tests failed and {errors} errors across {self.lanes} lanes."
    return classification, headline
