"""Accumulate import-health diagnostics and enforce truthful command-run completion."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.first_party_source import is_test_source

from .import_signal_projection import (
    _contract_path_deductions,
    _ContractPath,
    _diagnostic_deductions,
    _remediation_lanes,
)
from .signal_values import _HOTSPOT_LIMIT, _is_json_object

_IMPORT_BOUNDARIES_SIGNAL: Final[str] = "import-boundaries"


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


_OPERATIONAL_CODES: Final[frozenset[str]] = frozenset(
    {"AUTHORITY_PREFLIGHT", "INTERNAL_CHECKER", "TOOL_BROKEN", "TOOL_MISSING"}
)


def _path_is_test_scoped(path: str) -> bool:
    """Classify checker paths using explicit test-path naming conventions only."""
    parts = path.replace("\\", "/").split("/")
    return (
        is_test_source(path, root=REPO_ROOT if Path(path).is_absolute() else None)
        or parts[0] == "test_support"
        or parts[-1].endswith(("_test_support.py", "_fixture.py"))
    )


def _diagnostic_target(code: str, message: str, path: str) -> str | None:
    """Extract the module or symbol surface that makes a diagnostic repeat."""
    quoted = _quoted_diagnostic_targets(message)
    if code == "CANONICAL_TARGET_MISSING" and quoted:
        return quoted[0]
    if code == "PACKAGE_FACADE" and quoted:
        return quoted[-1]
    if code in {"REEXPORT_OR_ALIAS", "FORWARDING_MODULE"}:
        return _forwarded_diagnostic_module(message)
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
        if _is_json_object(structured) and structured.get("event") == "import_health":
            self._health_payload = structured
            return
        if _consume_contract_prefix(self, text):
            return
        if _consume_import_census(self, text):
            return
        _consume_import_diagnostic(self, text)

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
        contract_deductions = _contract_path_deductions(self)
        diagnostic_deductions = _diagnostic_deductions(self)
        if self._health_payload is not None:
            payload = dict(self._health_payload)
            payload.pop("event", None)
            run_outputs: dict[str, object] = {
                "artifacts": str(run_dir / "artifacts"),
                "candidate_inventory": str(run_dir / "artifacts" / "import-boundary-candidate.json"),
                "log": str(log_path),
                "metadata": str(run_dir / "run.json"),
            }
            payload.update(
                {
                    "command": label,
                    "duration_seconds": round((finished - started).total_seconds(), 3),
                    "event": "run_finished",
                    "exit_status": exit_status,
                    "finished_at": finished.isoformat(),
                    "run_id": run_dir.name,
                    "run_outputs": run_outputs,
                    "started_at": started.isoformat(),
                }
            )
            payload["impact"] = {
                "contract_paths": contract_deductions,
                "diagnostic_signal": diagnostic_deductions,
            }
            (run_dir / "artifacts" / "import-health.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding=UTF_8,
                newline="\n",
            )
            run_outputs["report"] = str(run_dir / "artifacts" / "import-health.json")
            return payload
        classification = "tool_failure"
        headline = "Import boundaries did not produce a schema-v2 health payload; inspect the run log."
        return {
            "broken_contracts": self.broken_contracts,
            "classification": classification,
            "command": label,
            "deductions": {
                "contract_paths": contract_deductions,
                "diagnostic_signal": diagnostic_deductions,
                "hotspot_limit": _HOTSPOT_LIMIT,
                "remediation_lanes": _remediation_lanes(self),
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


def _consume_contract_prefix(self: _ImportBoundariesProcessor, text: str) -> bool:
    """Consume contract prefix."""
    forbidden_edge = _FORBIDDEN_EDGE_RE.fullmatch(text)
    if forbidden_edge:
        self._finish_contract_path()
        self._current_forbidden_edge = (forbidden_edge.group(1), forbidden_edge.group(2))
        return True
    if text.startswith("[SUBORDINATE_CHECKER]"):
        self._finish_contract_path()
        self._current_forbidden_edge = None
    elif self._current_forbidden_edge is not None and text.startswith("-   "):
        self._finish_contract_path()
        self._current_contract_path = [text[4:]]
        return True
    elif self._current_contract_path is not None:
        if not text.strip():
            self._finish_contract_path()
        else:
            self._current_contract_path.append(text.strip())
        return True
    return False


def _consume_import_census(self: _ImportBoundariesProcessor, text: str) -> bool:
    """Consume import census."""
    analyzed = _ANALYZED_RE.fullmatch(text)
    if analyzed:
        self.files = int(analyzed.group(1))
        self.dependencies = int(analyzed.group(2))
        return True
    contract = _CONTRACT_RE.fullmatch(text)
    if contract:
        status = contract.group(2).lower()
        self.contracts[status] += 1
        if status == "broken":
            self.broken_contracts.append(contract.group(1))
        return True
    return False


def _consume_import_diagnostic(self: _ImportBoundariesProcessor, text: str) -> None:
    """Consume import diagnostic."""
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


def _quoted_diagnostic_targets(message: str) -> list[str]:
    """Read only the existing single-quoted diagnostic target syntax."""
    return [str(match.group(1)) for match in _QUOTED_TARGET_RE.finditer(message)]


def _forwarded_diagnostic_module(message: str) -> str:
    """Keep the exact forwarded symbol module and separator fallback."""
    qualified = message.partition(" is not a canonical defining-module symbol")[0]
    module, separator, _ = qualified.rpartition(".")
    return module if separator else qualified
