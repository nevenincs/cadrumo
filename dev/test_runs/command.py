"""Run a development command with a live, command-identified transcript."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8

from .paths import allocate_run_directory

_UTF_8: Final[str] = UTF_8
_IMPORT_BOUNDARIES_SIGNAL: Final[str] = "import-boundaries"
_REGISTRY_HEALTH_SIGNAL: Final[str] = "registry-health"
_BINDING_SIGNAL: Final[str] = "binding-signal"
_PYTEST_SUMMARY_SIGNAL: Final[str] = "pytest-summary"
_AUDIT_DEAD_WEIGHT_SIGNAL: Final[str] = "audit-dead-weight"
_LOCALES_STATUS_SIGNAL: Final[str] = "locales-status"
_INTERRUPTED_EXIT_STATUS: Final[int] = 130
_CHILD_STOP_TIMEOUT_SECONDS: Final[float] = 5.0
_DIAGNOSTIC_RE: Final[re.Pattern[str]] = re.compile(r"^\[([A-Z][A-Z0-9_]*)\]")
_DIAGNOSTIC_DETAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\[(?P<code>[A-Z][A-Z0-9_]*)\] (?P<path>.+):(?P<line>\d+): (?P<message>.*)$"
)
_ANALYZED_RE: Final[re.Pattern[str]] = re.compile(r"^Analyzed (\d+) files, (\d+) dependencies\.$")
_CONTRACT_RE: Final[re.Pattern[str]] = re.compile(r"^(.+?) (KEPT|BROKEN)$")
_FORBIDDEN_EDGE_RE: Final[re.Pattern[str]] = re.compile(r"^(.+?) is not allowed to import ([^:]+):$")
_DEPENDENCY_EDGE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<source>[A-Za-z_][A-Za-z0-9_.]*)->(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\(l\.[^)]+\)"
)
_QUOTED_TARGET_RE: Final[re.Pattern[str]] = re.compile(r"'([^']+)'")
_HOTSPOT_LIMIT: Final[int] = 10
_PYTEST_SUMMARY_RE: Final[re.Pattern[str]] = re.compile(
    r"^=+\s*(?P<summary>.+?)\s+in\s+(?P<duration>\d+(?:\.\d+)?)s"
    r"(?:\s+\(\d+:\d{2}:\d{2}\))?\s*=+$"
)
_PYTEST_COUNT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<count>\d+)\s+(?:tests?\s+)?(?P<outcome>collected|passed|failed|errors?|skipped|deselected|"
    r"xfailed|xpassed|warnings?)\b"
)
_TEST_IDENTITY_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:FAILED|ERROR) (?P<node>(?P<file>[^\s:]+\.py)(?:::[^\s]+)?)"
)
_ROOT_CAUSE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:E\s+)?(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):\s*(?P<message>.+)$"
)
_REGISTRY_LOAD_FAILURE_RE: Final[re.Pattern[str]] = re.compile(
    r"^registry-runtime-load\s+status=failed\s+loadable=false\s+detail="
    r"(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):\s*(?P<message>.+)$"
)
_PYTEST_OUTCOME_KEYS: Final[dict[str, str]] = {
    "collected": "collected",
    "passed": "passed",
    "failed": "failed",
    "error": "error",
    "errors": "error",
    "skipped": "skipped",
    "deselected": "deselected",
    "xfailed": "xfailed",
    "xpassed": "xpassed",
    "warning": "warning",
    "warnings": "warning",
}
_OPERATIONAL_CODES: Final[frozenset[str]] = frozenset(
    {"AUTHORITY_PREFLIGHT", "INTERNAL_CHECKER", "TOOL_BROKEN", "TOOL_MISSING"}
)
_REMEDIATION_CODE_FAMILIES: Final[dict[str, frozenset[str]]] = {
    "canonical_import_surface": frozenset(
        {"CANONICAL_TARGET_MISSING", "FORWARDING_MODULE", "PACKAGE_FACADE", "REEXPORT_OR_ALIAS"}
    ),
    "dynamic_or_raw_target": frozenset(
        {
            "DYNAMIC_TARGET_UNRESOLVED",
            "RAW_FIRST_PARTY_IMPORT",
            "STATIC_TARGET_UNRESOLVED",
            "UNRESOLVED_DYNAMIC_TARGET",
        }
    ),
    "initializer_hygiene": frozenset({"ACTIVE_INITIALIZER"}),
    "intra_package_spelling": frozenset({"ABSOLUTE_INTRA_CADRUMO"}),
    "private_encapsulation": frozenset({"PRIVATE_CROSS_PACKAGE"}),
}


@dataclass(frozen=True)
class _ContractPath:
    """One normalized dependency path reported under one forbidden edge."""

    forbidden_from: str
    forbidden_to: str
    normalized: str
    edges: tuple[tuple[str, str], ...]


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
        payload: dict[str, object] | None = None
        for line in reversed(self.lines):
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                payload = candidate
                break
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
        marker: dict[str, object] | None = None
        if text.startswith("{"):
            try:
                candidate = json.loads(text)
            except json.JSONDecodeError:
                candidate = None
            if isinstance(candidate, dict) and candidate.get("event") in {
                "lane_started",
                "lane_finished",
                "lane_skipped",
            }:
                marker = candidate
        if marker is not None and marker["event"] == "lane_started":
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
        if marker is not None and marker["event"] == "lane_finished":
            self.current_lane = str(marker["lane"])
            lane = self._lane()
            status = int(marker["exit_status"])
            lane["kind"] = str(marker.get("kind", lane["kind"]))
            lane["role"] = str(marker.get("role", lane["role"]))
            lane["status"] = status
            lane["seconds"] = int(marker["seconds"])
            return {
                "event": "lane_finished",
                "kind": lane["kind"],
                "lane": self.current_lane,
                "role": lane["role"],
                "seconds": lane["seconds"],
                "status": "passed" if status == 0 else "failed",
                "exit_status": status,
            }
        if marker is not None and marker["event"] == "lane_skipped":
            self.current_lane = str(marker["lane"])
            lane = self._lane()
            blocked_by = tuple(str(item) for item in marker.get("blocked_by", ()))
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
            data = self.lane_data.get(name)
            if data is None:
                lanes.append({"name": name, "result": "not_run"})
                continue
            if data["skipped"]:
                blocked_by = data["blocked_by"]
                assert isinstance(blocked_by, tuple)
                lanes.append(
                    {
                        "blocked_by": list(blocked_by),
                        "classification": "blocked_by_preflight",
                        "kind": data["kind"],
                        "name": name,
                        "reason": data["skip_reason"],
                        "result": "blocked",
                    }
                )
                continue
            counts = data["counts"]
            failed_nodes = data["failed_nodes"]
            root_causes = data["root_causes"]
            assert isinstance(counts, Counter)
            assert isinstance(failed_nodes, set)
            assert isinstance(root_causes, Counter)
            files = Counter(file for _, file in failed_nodes)
            internal_error = bool(data["internal_error"])
            kind = str(data["kind"])
            summaryless_failure = data["status"] not in (None, 0) and not counts
            collection_failure = not internal_error and (
                (summaryless_failure and kind == "collection")
                or (counts["error"] and not (counts["passed"] or counts["failed"]))
            )
            load_failure = not internal_error and summaryless_failure and kind == "load" and bool(root_causes)
            phase = (
                "tool"
                if internal_error or (summaryless_failure and kind not in {"collection", "load"})
                else "collection"
                if collection_failure
                else "load"
                if load_failure
                else "execution"
            )
            classification = (
                "tool_failure"
                if internal_error or (summaryless_failure and kind != "collection" and not load_failure)
                else "collection_failure"
                if collection_failure
                else "load_failure"
                if load_failure
                else "clean"
                if data["status"] == 0
                else "blocking_findings"
            )
            lanes.append(
                {
                    "name": name,
                    "result": "passed" if data["status"] == 0 else "failed",
                    "classification": classification,
                    "exit_status": data["status"],
                    "duration_seconds": data["seconds"],
                    "kind": kind,
                    "role": data["role"],
                    "summary": dict(sorted(counts.items())),
                    "failed_test_identities": len(failed_nodes),
                    "top_affected_files": _top(files),
                    "root_causes": [
                        {"count": count, "exception": cause[0], "message": cause[1], "phase": phase}
                        for cause, count in sorted(root_causes.items(), key=lambda item: (-item[1], item[0]))[
                            :_HOTSPOT_LIMIT
                        ]
                    ],
                }
            )
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
        summaryless_collection_failed = sum(
            data["status"] not in (None, 0) and not data["counts"] and data["kind"] == "collection"
            for data in self.lane_data.values()
        )
        summaryless_tool_failed = sum(
            data["status"] not in (None, 0)
            and not data["counts"]
            and data["kind"] != "collection"
            and not (data["kind"] == "load" and bool(data["root_causes"]))
            for data in self.lane_data.values()
        )
        summaryless_load_failed = sum(
            data["status"] not in (None, 0)
            and not data["counts"]
            and data["kind"] == "load"
            and bool(data["root_causes"])
            for data in self.lane_data.values()
        )
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
        elif errors and not (self.counts["passed"] or failures):
            classification = "collection_failure"
            headline = f"{label} could not collect tests: {errors} collection errors across {self.lanes} lanes."
        else:
            classification = "blocking_findings"
            headline = f"{label} failed: {failures} tests failed and {errors} errors across {self.lanes} lanes."
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
                "lanes_tool_failed": sum(
                    bool(data["internal_error"])
                    or (
                        data["status"] not in (None, 0)
                        and not data["counts"]
                        and data["kind"] != "collection"
                        and not (data["kind"] == "load" and bool(data["root_causes"]))
                    )
                    for data in self.lane_data.values()
                ),
                "lanes_load_failed": summaryless_load_failed,
                "lanes_blocked": blocked,
                "lanes_not_run": expected - completed - blocked,
                "pytest_invocations": self.lanes,
                **outcomes,
            },
            "lanes": self._lane_envelopes(),
        }


def _normalize_root_cause(message: str) -> str:
    """Remove checkout and run-specific identity from a root-cause signature."""
    normalized = message.replace(str(REPO_ROOT), "<repo>").replace(REPO_ROOT.as_posix(), "<repo>")
    normalized = re.sub(r"[\\/]\.logs[\\/]test-runs[\\/][^\\/\s]+[\\/][^\\/\s]+", "/.logs/test-runs/<run>", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _top(
    counter: Counter[str],
    *,
    limit: int = _HOTSPOT_LIMIT,
    minimum_count: int = 1,
) -> list[dict[str, object]]:
    """Return a deterministic bounded frequency table."""
    return [
        {"count": count, "value": value}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        if count >= minimum_count
    ][:limit]


def _module_is_test_scoped(module: str) -> bool:
    """Classify module names using explicit test-path naming conventions only."""
    parts = module.split(".")
    leaf = parts[-1]
    return (
        "tests" in parts
        or parts[0] == "test_support"
        or leaf == "conftest"
        or leaf.startswith("test_")
        or leaf.endswith("_test_support")
        or leaf.endswith("_fixture")
    )


def _path_is_test_scoped(path: str) -> bool:
    """Classify checker paths using explicit test-path naming conventions only."""
    parts = path.replace("\\", "/").split("/")
    leaf = parts[-1]
    return (
        "tests" in parts
        or parts[0] == "test_support"
        or leaf == "conftest.py"
        or leaf.startswith("test_")
        or leaf.endswith("_test_support.py")
        or leaf.endswith("_fixture.py")
    )


def _diagnostic_target(code: str, message: str, path: str) -> str | None:
    """Extract the module or symbol surface that makes a diagnostic repeat."""
    quoted = _QUOTED_TARGET_RE.findall(message)
    if code == "CANONICAL_TARGET_MISSING" and quoted:
        return quoted[0]
    if code == "PACKAGE_FACADE" and quoted:
        return quoted[-1]
    if code in {"REEXPORT_OR_ALIAS", "FORWARDING_MODULE"}:
        qualified = message.partition(" is not a canonical defining-module symbol")[0]
        module, separator, _ = qualified.rpartition(".")
        return module if separator else qualified
    if code == "PRIVATE_CROSS_PACKAGE" and quoted:
        return quoted[-1]
    if code == "ACTIVE_INITIALIZER":
        return path
    if quoted:
        return quoted[-1]
    return None


class _ImportBoundariesProcessor:
    """Reduce the import gate transcript to stable counters."""

    def __init__(self) -> None:
        self.files = 0
        self.dependencies = 0
        self.contracts: Counter[str] = Counter()
        self.broken_contracts: list[str] = []
        self.diagnostics: Counter[str] = Counter()
        self.operational_failure = False
        self._current_forbidden_edge: tuple[str, str] | None = None
        self._current_contract_path: list[str] | None = None
        self._contract_paths: list[_ContractPath] = []
        self._diagnostic_files: set[str] = set()
        self._diagnostic_locations: Counter[str] = Counter()
        self._diagnostic_location_codes: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self._diagnostic_files_by_code: defaultdict[str, set[str]] = defaultdict(set)
        self._diagnostic_locations_by_code: defaultdict[str, set[str]] = defaultdict(set)
        self._diagnostic_test_scoped: Counter[str] = Counter()
        self._diagnostic_targets: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self._health_payload: dict[str, object] | None = None

    def consume(self, line: str) -> None:
        text = line.rstrip("\r\n")
        try:
            structured = json.loads(text)
        except json.JSONDecodeError:
            structured = None
        if isinstance(structured, dict) and structured.get("event") == "import_health":
            self._health_payload = structured
            return
        forbidden_edge = _FORBIDDEN_EDGE_RE.fullmatch(text)
        if forbidden_edge:
            self._finish_contract_path()
            self._current_forbidden_edge = (forbidden_edge.group(1), forbidden_edge.group(2))
            return
        if text.startswith("[SUBORDINATE_CHECKER]"):
            self._finish_contract_path()
            self._current_forbidden_edge = None
        elif self._current_forbidden_edge is not None and text.startswith("-   "):
            self._finish_contract_path()
            self._current_contract_path = [text[4:]]
            return
        elif self._current_contract_path is not None:
            if not text.strip():
                self._finish_contract_path()
            else:
                self._current_contract_path.append(text.strip())
            return
        analyzed = _ANALYZED_RE.fullmatch(text)
        if analyzed:
            self.files = int(analyzed.group(1))
            self.dependencies = int(analyzed.group(2))
            return
        contract = _CONTRACT_RE.fullmatch(text)
        if contract:
            status = contract.group(2).lower()
            self.contracts[status] += 1
            if status == "broken":
                self.broken_contracts.append(contract.group(1))
            return
        diagnostic = _DIAGNOSTIC_RE.match(text)
        if diagnostic and diagnostic.group(1) in _OPERATIONAL_CODES:
            self.operational_failure = True
            return
        if diagnostic and diagnostic.group(1) not in {
            "AUTHORITY_PREFLIGHT",
            "GRAPH_AUTHORITY",
            "SUBORDINATE_CHECKER",
        }:
            code = diagnostic.group(1)
            self.diagnostics[code] += 1
            detail = _DIAGNOSTIC_DETAIL_RE.fullmatch(text)
            if detail:
                path = detail.group("path")
                location = f"{path}:{detail.group('line')}"
                self._diagnostic_files.add(path)
                self._diagnostic_locations[location] += 1
                self._diagnostic_location_codes[location][code] += 1
                self._diagnostic_files_by_code[code].add(path)
                self._diagnostic_locations_by_code[code].add(location)
                if _path_is_test_scoped(path):
                    self._diagnostic_test_scoped[code] += 1
                target = _diagnostic_target(code, detail.group("message"), path)
                if target is not None:
                    self._diagnostic_targets[code][target] += 1

    def effective_exit_status(self, child_exit_status: int) -> int:
        """Fail operationally when the child omits or contradicts its health payload."""
        if self._health_payload is None or self._health_payload.get("schema_version") != 2:
            return 7
        verdict = self._health_payload.get("verdict")
        if verdict not in {"clean", "passing_with_debt", "failed"}:
            return 7
        if verdict in {"clean", "passing_with_debt"} and child_exit_status != 0:
            return 7
        if verdict == "failed" and child_exit_status == 0:
            return 7
        return child_exit_status

    def _finish_contract_path(self) -> None:
        """Commit one wrapped Import Linter path to its normalized form."""
        if self._current_contract_path is None or self._current_forbidden_edge is None:
            self._current_contract_path = None
            return
        normalized = re.sub(r"\s+", "", "".join(self._current_contract_path))
        edges = tuple(
            (match.group("source"), match.group("target")) for match in _DEPENDENCY_EDGE_RE.finditer(normalized)
        )
        if edges:
            self._contract_paths.append(
                _ContractPath(
                    forbidden_from=self._current_forbidden_edge[0],
                    forbidden_to=self._current_forbidden_edge[1],
                    normalized=normalized,
                    edges=edges,
                )
            )
        self._current_contract_path = None

    def _contract_path_deductions(self) -> dict[str, object]:
        """Reduce broken-contract paths without treating overlapping contracts as new imports."""
        self._finish_contract_path()
        path_multiplicity = Counter(path.normalized for path in self._contract_paths)
        lanes: defaultdict[tuple[str, str], list[_ContractPath]] = defaultdict(list)
        for path in self._contract_paths:
            lanes[(path.forbidden_from, path.forbidden_to)].append(path)
        by_forbidden_edge: dict[str, object] = {}
        for (forbidden_from, forbidden_to), paths in sorted(lanes.items()):
            sources = Counter(path.edges[0][0] for path in paths)
            terminals = Counter(path.edges[-1][1] for path in paths)
            bridges: Counter[str] = Counter()
            for path in paths:
                bridges.update(target for _, target in path.edges[:-1])
            test_scoped = sum(_module_is_test_scoped(path.edges[0][0]) for path in paths)
            by_forbidden_edge[f"{forbidden_from} -> {forbidden_to}"] = {
                "direct_paths": sum(len(path.edges) == 1 for path in paths),
                "non_test_scoped_paths": len(paths) - test_scoped,
                "reported_paths": len(paths),
                "test_scoped_paths": test_scoped,
                "top_bridge_modules": _top(bridges, minimum_count=2),
                "top_source_modules": _top(sources, minimum_count=2),
                "top_terminal_modules": _top(terminals, minimum_count=2),
                "transitive_paths": sum(len(path.edges) > 1 for path in paths),
                "unique_source_modules": len({path.edges[0][0] for path in paths}),
                "unique_terminal_modules": len(terminals),
            }
        repeated = [count for count in path_multiplicity.values() if count > 1]
        return {
            "by_forbidden_edge": by_forbidden_edge,
            "classification": "test_scoped uses module naming conventions; non_test_scoped is its complement",
            "maximum_contract_multiplicity": max(path_multiplicity.values(), default=0),
            "overlapping_unique_paths": len(repeated),
            "reported_paths": len(self._contract_paths),
            "reports_for_overlapping_paths": sum(repeated),
            "unique_dependency_paths": len(path_multiplicity),
        }

    def _diagnostic_deductions(self) -> dict[str, object]:
        """Expose finding amplification and recurring diagnostic surfaces."""
        by_code: dict[str, object] = {}
        for code, findings in sorted(self.diagnostics.items()):
            test_scoped = self._diagnostic_test_scoped[code]
            by_code[code] = {
                "files": len(self._diagnostic_files_by_code[code]),
                "findings": findings,
                "locations": len(self._diagnostic_locations_by_code[code]),
                "non_test_scoped_findings": findings - test_scoped,
                "test_scoped_findings": test_scoped,
                "top_targets": _top(self._diagnostic_targets[code]),
            }
        multi_locations = Counter(
            {location: count for location, count in self._diagnostic_locations.items() if count > 1}
        )
        top_locations = []
        for item in _top(self._diagnostic_locations):
            location = str(item["value"])
            top_locations.append(
                {
                    **item,
                    "by_code": dict(sorted(self._diagnostic_location_codes[location].items())),
                }
            )
        return {
            "amplification": {
                "files": len(self._diagnostic_files),
                "findings": sum(self.diagnostics.values()),
                "findings_at_multi_finding_locations": sum(multi_locations.values()),
                "locations": len(self._diagnostic_locations),
                "locations_with_multiple_findings": len(multi_locations),
                "maximum_findings_at_one_location": max(self._diagnostic_locations.values(), default=0),
            },
            "by_code": by_code,
            "classification": "test_scoped uses path naming conventions; non_test_scoped is its complement",
            "top_locations": top_locations,
        }

    def _remediation_lanes(self) -> dict[str, object]:
        """Group diagnostic codes by the import defect they describe."""
        lanes: dict[str, object] = {}
        for lane, codes in sorted(_REMEDIATION_CODE_FAMILIES.items()):
            active_codes = sorted(code for code in codes if self.diagnostics[code])
            findings = sum(self.diagnostics[code] for code in active_codes)
            locations = set().union(*(self._diagnostic_locations_by_code[code] for code in active_codes))
            test_scoped = sum(self._diagnostic_test_scoped[code] for code in active_codes)
            lanes[lane] = {
                "codes": active_codes,
                "findings": findings,
                "locations": len(locations),
                "non_test_scoped_findings": findings - test_scoped,
                "test_scoped_findings": test_scoped,
            }
        return lanes

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
        broken = self.contracts["broken"]
        diagnostic_total = sum(self.diagnostics.values())
        contract_deductions = self._contract_path_deductions()
        diagnostic_deductions = self._diagnostic_deductions()
        if self._health_payload is not None:
            payload = dict(self._health_payload)
            payload.pop("event", None)
            payload.update(
                {
                    "command": label,
                    "duration_seconds": round((finished - started).total_seconds(), 3),
                    "event": "run_finished",
                    "exit_status": exit_status,
                    "finished_at": finished.isoformat(),
                    "run_id": run_dir.name,
                    "run_outputs": {
                        "artifacts": str(run_dir / "artifacts"),
                        "candidate_inventory": str(run_dir / "artifacts" / "import-boundary-candidate.json"),
                        "log": str(log_path),
                        "metadata": str(run_dir / "run.json"),
                    },
                    "started_at": started.isoformat(),
                }
            )
            payload["impact"] = {
                "contract_paths": contract_deductions,
                "diagnostic_signal": diagnostic_deductions,
            }
            (run_dir / "artifacts" / "import-health.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding=_UTF_8,
                newline="\n",
            )
            payload["run_outputs"]["report"] = str(run_dir / "artifacts" / "import-health.json")
            return payload
        if self._health_payload is None:
            classification = "tool_failure"
            headline = "Import boundaries did not produce a schema-v2 health payload; inspect the run log."
        elif exit_status == 0:
            classification = "clean"
            headline = "Import boundaries passed with no blocking findings."
        elif self.operational_failure:
            classification = "tool_failure"
            headline = "Import boundaries could not produce a complete verdict; inspect the run log."
        elif broken or diagnostic_total:
            classification = "blocking_findings"
            headline = (
                f"Import boundaries failed: {broken} architectural contracts broken "
                f"and {diagnostic_total} import-form diagnostics found."
            )
        else:
            classification = "failed_without_findings"
            headline = "Import boundaries failed without normalized findings; inspect the run log."
        return {
            "broken_contracts": self.broken_contracts,
            "classification": classification,
            "command": label,
            "deductions": {
                "contract_paths": contract_deductions,
                "diagnostic_signal": diagnostic_deductions,
                "hotspot_limit": _HOTSPOT_LIMIT,
                "remediation_lanes": self._remediation_lanes(),
                "schema_version": 1,
            },
            "diagnostics": {
                "by_code": dict(sorted(self.diagnostics.items())),
                "total": diagnostic_total,
            },
            "duration_seconds": round((finished - started).total_seconds(), 3),
            "exit_status": exit_status,
            "finished_at": finished.isoformat(),
            "graph": {"dependencies": self.dependencies, "files": self.files},
            "headline": headline,
            "result": "passed" if exit_status == 0 else "failed",
            "run_id": run_dir.name,
            "run_outputs": {
                "log": str(log_path),
                "metadata": str(run_dir / "run.json"),
            },
            "started_at": started.isoformat(),
            "summary": {
                "contracts_broken": broken,
                "contracts_kept": self.contracts["kept"],
                "contracts_total": sum(self.contracts.values()),
                "diagnostics_total": diagnostic_total,
            },
        }


class _DeadWeightSignalProcessor:
    """Reduce the combined dead-weight payload to a stable run envelope."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def consume(self, line: str) -> None:
        self.lines.append(line)

    @staticmethod
    def _previous_summary(run_dir: Path) -> tuple[str | None, dict[str, object] | None]:
        family_root = run_dir.parents[1]
        candidates = sorted(
            family_root.glob("*/*-audit-dead-weight-*/artifacts/dead-weight-signal.json"),
            key=lambda path: path.parents[1].name,
            reverse=True,
        )
        for candidate in candidates:
            if candidate.parents[1] == run_dir:
                continue
            try:
                payload = json.loads(candidate.read_text(encoding=_UTF_8))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict) or not isinstance(payload.get("summary"), dict):
                continue
            return str(payload.get("run_id", candidate.parents[1].name)), payload["summary"]
        return None, None

    @staticmethod
    def _comparison(
        summary: dict[str, object],
        baseline_run_id: str | None,
        baseline: dict[str, object] | None,
    ) -> dict[str, object]:
        comparison: dict[str, object] = {"baseline_run_id": baseline_run_id}
        for dimension in ("duplication", "dead_code"):
            current_values = summary.get(dimension, {})
            baseline_values = baseline.get(dimension, {}) if baseline is not None else {}
            if not isinstance(current_values, dict) or not isinstance(baseline_values, dict):
                comparison[dimension] = {
                    "findings_total_delta": None,
                    "rate_delta": None,
                }
                continue
            current_findings = current_values.get("findings_total")
            previous_findings = baseline_values.get("findings_total")
            current_rate = current_values.get("rate")
            previous_rate = baseline_values.get("rate")
            comparison[dimension] = {
                "findings_total_delta": (
                    int(current_findings) - int(previous_findings)
                    if current_findings is not None and previous_findings is not None
                    else None
                ),
                "rate_delta": (
                    round(float(current_rate) - float(previous_rate), 8)
                    if current_rate is not None and previous_rate is not None
                    else None
                ),
            }
        return comparison

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
        try:
            decoded = json.loads("".join(self.lines))
            if not isinstance(decoded, dict):
                raise ValueError("audit payload is not a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            outcome = "unavailable"
            headline = f"{label} signal could not be normalized: {exc}"
            summary: dict[str, object] = {
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
            summary = decoded.get("summary", {})
            if not isinstance(summary, dict):
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
        baseline_run_id, baseline = self._previous_summary(run_dir)
        comparison = self._comparison(summary, baseline_run_id, baseline)
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
            "comparison": comparison,
        }


class _LocalesStatusSignalProcessor:
    """Reduce the complete locale audit payload to a stable advisory envelope."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self._decoded: dict[str, object] | None = None
        self._decode_error: str | None = None

    def consume(self, line: str) -> None:
        self.lines.append(line)

    def _payload(self) -> dict[str, object] | None:
        if self._decoded is not None or self._decode_error is not None:
            return self._decoded
        try:
            decoded = json.loads("".join(self.lines))
            if not isinstance(decoded, dict):
                raise ValueError("locale status payload is not a JSON object")
            if decoded.get("outcome") not in {"backlog", "complete"}:
                raise ValueError("locale status payload has an unknown outcome")
            if not isinstance(decoded.get("summary"), dict):
                raise ValueError("locale status payload has no summary object")
            if not isinstance(decoded.get("details"), dict):
                raise ValueError("locale status payload has no details object")
        except (json.JSONDecodeError, ValueError) as exc:
            self._decode_error = str(exc)
            return None
        self._decoded = decoded
        return decoded

    def effective_exit_status(self, child_exit_status: int) -> int:
        """Normalize every unusable locale report to the operational-failure code."""
        if child_exit_status != 127 and self._payload() is None:
            return 7
        return child_exit_status

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
        decoded = self._payload()
        if decoded is None:
            summary = {
                "inventory": {"closed": False, "processor_failures": 1},
                "translation_backlog": {
                    "exact": False,
                    "unique_keys_to_translate": None,
                    "cells_to_translate": None,
                },
            }
            details = {"processor_error": self._decode_error or "unknown processor failure"}
            outcome = "unavailable"
            headline = "Locale status could not produce a complete verdict; inspect the run log."
        else:
            summary = decoded["summary"]
            details = decoded["details"]
            assert isinstance(summary, dict)
            assert isinstance(details, dict)
            outcome = str(decoded["outcome"])
            headline = str(decoded.get("headline", "Locale status produced no headline."))
        report_path = run_dir / "artifacts" / "locale-status.json"
        backlog_path = run_dir / "artifacts" / "locale-backlog.jsonl"
        findings_path = run_dir / "artifacts" / "locale-findings.jsonl"
        report_path.write_text(
            json.dumps(
                {
                    "details": details,
                    "run_id": run_dir.name,
                    "schema_version": 1,
                    "summary": summary,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding=_UTF_8,
            newline="\n",
        )
        _write_json_lines(backlog_path, details.get("backlog", []))
        _write_json_lines(findings_path, details.get("findings", []))
        blocking = label == "check-locales"
        if exit_status in {7, 127} or outcome == "unavailable":
            classification = "tool_failure"
            result = "unavailable"
        elif outcome == "backlog":
            classification = "blocking_findings" if blocking else "advisory_findings"
            result = "failed" if blocking else "backlog"
        else:
            classification = "clean"
            result = "passed" if blocking else "complete"
        return {
            "classification": classification,
            "command": label,
            "duration_seconds": round((finished - started).total_seconds(), 3),
            "event": "run_finished",
            "exit_status": exit_status,
            "finished_at": finished.isoformat(),
            "headline": headline,
            "posture": "blocking" if blocking else "advisory",
            "result": result,
            "run_id": run_dir.name,
            "run_outputs": {
                "artifacts": str(run_dir / "artifacts"),
                "backlog": str(backlog_path),
                "findings": str(findings_path),
                "log": str(log_path),
                "metadata": str(run_dir / "run.json"),
                "report": str(report_path),
            },
            "schema_version": 1,
            "started_at": started.isoformat(),
            **_compact_locale_summary(summary),
        }


def _write_json_lines(path: Path, rows: object) -> None:
    """Persist a stable JSON-lines collection, refusing non-list payloads."""
    if not isinstance(rows, list):
        rows = []
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding=_UTF_8,
        newline="\n",
    )


def _compact_locale_summary(summary: dict[str, object]) -> dict[str, object]:
    """Keep every locale domain visible without repeating non-actionable zeros."""
    projected = dict(summary)
    raw_domains = summary.get("domains")
    if not isinstance(raw_domains, list):
        return projected
    complete: list[str] = []
    work: list[dict[str, object]] = []
    always = {"domain", "state", "required_keys", "keys_to_translate", "to_translate"}
    for raw_row in raw_domains:
        if not isinstance(raw_row, dict):
            continue
        if raw_row.get("state") == "complete":
            complete.append(str(raw_row.get("domain", "unassigned")))
            continue
        row = {str(key): value for key, value in raw_row.items() if key in always or (value is not None and value != 0)}
        by_locale = row.get("to_translate_by_locale")
        if isinstance(by_locale, dict) and not any(int(value) for value in by_locale.values()):
            row.pop("to_translate_by_locale")
        work.append(row)
    projected["domains"] = {"work": work, "complete": sorted(complete)}
    return projected


def _stop_interrupted_process(process: subprocess.Popen[str]) -> None:
    """Bound cleanup of a child when the command wrapper receives Ctrl+C."""
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=_CHILD_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=_CHILD_STOP_TIMEOUT_SECONDS)
    except OSError:
        # The child can exit between poll() and terminate() after receiving the
        # same console interrupt as this wrapper.
        pass


def _write_run_metadata(
    *,
    run_dir: Path,
    artifacts: Path,
    cache: Path,
    command: tuple[str, ...],
    exit_status: int,
    finished: datetime,
    log_path: Path,
    scratch: Path,
    started: datetime,
) -> None:
    """Atomically persist the canonical run contract."""
    payload = {
        "artifacts": str(artifacts),
        "cache": str(cache),
        "command": list(command),
        "exit_status": exit_status,
        "finished_at": finished.isoformat(),
        "log": str(log_path),
        "run_id": run_dir.name,
        "scratch": str(scratch),
        "started_at": started.isoformat(),
    }
    temporary = scratch / "run.json.tmp"
    temporary.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    os.replace(temporary, run_dir / "run.json")


def run(
    command: tuple[str, ...],
    *,
    repository: Path,
    family: str,
    label: str,
    signal: str | None = None,
    expected_lanes: tuple[str, ...] = (),
) -> int:
    """Stream ``command`` while retaining its full transcript and metadata."""
    if not command:
        raise ValueError("a command is required")
    started = datetime.now(tz=UTC)
    run_dir = allocate_run_directory(repository, family=family, label=label, now=started)
    artifacts = run_dir / "artifacts"
    cache = run_dir / "cache"
    scratch = run_dir / "scratch"
    artifacts.mkdir(parents=True)
    cache.mkdir()
    scratch.mkdir()
    log_path = run_dir / "run.log"
    # PowerShell can terminate every native process in a Ctrl+C pipeline before
    # Python receives a catchable KeyboardInterrupt. Seed a fail-closed record
    # before entering that process tree; normal and catchable-interrupt exits
    # atomically replace it with their actual completion timestamp and status.
    _write_run_metadata(
        run_dir=run_dir,
        artifacts=artifacts,
        cache=cache,
        command=command,
        exit_status=_INTERRUPTED_EXIT_STATUS,
        finished=started,
        log_path=log_path,
        scratch=scratch,
        started=started,
    )
    if signal == _IMPORT_BOUNDARIES_SIGNAL:
        processor = _ImportBoundariesProcessor()
    elif signal in {_BINDING_SIGNAL, _REGISTRY_HEALTH_SIGNAL}:
        processor = _RegistryHealthProcessor()
    elif signal == _PYTEST_SUMMARY_SIGNAL:
        processor = _PytestSummaryProcessor(expected_lanes)
    elif signal == _AUDIT_DEAD_WEIGHT_SIGNAL:
        processor = _DeadWeightSignalProcessor()
    elif signal == _LOCALES_STATUS_SIGNAL:
        processor = _LocalesStatusSignalProcessor()
    else:
        processor = None
    start_envelope_text: str | None = None
    if processor is None:
        print(f"{label} run log: {log_path}", flush=True)
    else:
        start_envelope_text = json.dumps(
            {
                "command": label,
                "event": "run_started",
                "run_id": run_dir.name,
                "run_outputs": {
                    "log": str(log_path),
                    "metadata": str(run_dir / "run.json"),
                },
                "schema_version": 1,
                "status": "running",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        print(start_envelope_text, flush=True)

    environment = os.environ.copy()
    environment["CADRUMO_DEV_RUN_ROOT"] = str(run_dir)
    environment["CADRUMO_DEV_ARTIFACTS_DIR"] = str(artifacts)
    environment["CADRUMO_DEV_CACHE_DIR"] = str(cache)
    environment["CADRUMO_DEV_SCRATCH_DIR"] = str(scratch)
    environment["XDG_CACHE_HOME"] = str(cache)
    environment["TEMP"] = str(scratch)
    environment["TMP"] = str(scratch)
    environment["TMPDIR"] = str(scratch)
    with log_path.open("x", encoding=_UTF_8, newline="\n") as transcript:
        transcript.write(f"START {started.isoformat()} pid={os.getpid()}\n")
        transcript.write(f"COMMAND {' '.join(command)}\n")
        if start_envelope_text is not None:
            transcript.write(start_envelope_text + "\n")
        transcript.flush()
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(  # noqa: S603 - argv is the explicit operator command; shell=False.
                command,
                cwd=repository,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding=_UTF_8,
                errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                if processor is None:
                    print(line, end="", flush=True)
                else:
                    progress = processor.consume(line)
                    if isinstance(progress, dict):
                        progress_text = json.dumps(
                            {
                                "command": label,
                                **progress,
                                "run_id": run_dir.name,
                                "schema_version": 1,
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        print(progress_text, flush=True)
                        transcript.write(progress_text + "\n")
                transcript.write(line)
                transcript.flush()
            exit_status = process.wait()
            normalized_processors = (
                _ImportBoundariesProcessor,
                _LocalesStatusSignalProcessor,
                _PytestSummaryProcessor,
            )
            if isinstance(processor, normalized_processors):
                exit_status = processor.effective_exit_status(exit_status)
        except KeyboardInterrupt:
            exit_status = _INTERRUPTED_EXIT_STATUS
            if process is not None:
                _stop_interrupted_process(process)
            transcript.write(f"INTERRUPTED exit={exit_status}\n")
        finished = datetime.now(tz=UTC)
        transcript.write(f"FINISH {finished.isoformat()} exit={exit_status}\n")

    _write_run_metadata(
        run_dir=run_dir,
        artifacts=artifacts,
        cache=cache,
        command=command,
        exit_status=exit_status,
        finished=finished,
        log_path=log_path,
        scratch=scratch,
        started=started,
    )
    if processor is None:
        print(f"{label} run log: {log_path} (exit={exit_status}, metadata={run_dir / 'run.json'})", flush=True)
    else:
        envelope_text = json.dumps(
            processor.envelope(
                label=label,
                run_dir=run_dir,
                log_path=log_path,
                exit_status=exit_status,
                started=started,
                finished=finished,
            ),
            sort_keys=True,
            separators=(",", ":"),
        )
        with log_path.open("a", encoding=_UTF_8, newline="\n") as transcript:
            transcript.write(envelope_text + "\n")
        print(envelope_text, flush=True)
    return exit_status


def main() -> int:
    """Parse the evidence family/label and execute the remaining argv."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--signal",
        choices=(
            _AUDIT_DEAD_WEIGHT_SIGNAL,
            _BINDING_SIGNAL,
            _IMPORT_BOUNDARIES_SIGNAL,
            _LOCALES_STATUS_SIGNAL,
            _PYTEST_SUMMARY_SIGNAL,
            _REGISTRY_HEALTH_SIGNAL,
        ),
    )
    parser.add_argument("--expected-lane", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = tuple(args.command)
    if command[:1] == ("--",):
        command = command[1:]
    return run(
        command,
        repository=REPO_ROOT,
        family=args.family,
        label=args.label,
        signal=args.signal,
        expected_lanes=tuple(args.expected_lane),
    )


if __name__ == "__main__":
    sys.exit(main())
