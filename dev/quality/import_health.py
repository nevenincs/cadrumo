"""Truthful occurrence-level health accounting for the import boundary gate."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final, TypedDict

from dev._paths import UTF_8

from .import_checker import Authority, CheckResult, ImportOccurrence

_RATCHET_SCHEMA_VERSION: Final[int] = 1
_SIGNAL_SCHEMA_VERSION: Final[int] = 2
_RATCHET_RELATIVE_PATH: Final[Path] = Path("dev/quality/metadata/import_boundary_ratchet.json")
_ANALYZED_RE: Final[re.Pattern[str]] = re.compile(r"^Analyzed (\d+) files, (\d+) dependencies\.$")
_CONTRACT_RE: Final[re.Pattern[str]] = re.compile(r"^(.+?) (KEPT|BROKEN)$")


class _GraphSummary(TypedDict):
    """Parsed Import Linter graph facts used by the health verdict."""

    contracts_broken: int
    contracts_kept: int
    contracts_total: int
    broken_contract_names: list[str]
    contract_status: dict[str, str]
    dependencies: int
    files: int


class _EvidenceRow(TypedDict):
    line: int
    path: str


class _OccurrenceRow(TypedDict):
    contract: str
    evidence: list[_EvidenceRow]
    fingerprint: str
    import_form: str
    imported_symbols: list[str]
    lexical_scope: str
    multiplicity: int
    source_module: str
    target_module: str
    test_scoped: bool


class _OccurrenceSummary(TypedDict):
    contract_occurrences: int
    by_contract: dict[str, int]
    by_import_form: dict[str, int]
    non_test_scoped_occurrences: int
    test_scoped_occurrences: int
    inventory_digest: str
    unique_contract_occurrences: int
    unique_import_occurrences: int


class _CandidateSummary(_OccurrenceSummary):
    advisory_by_contract: dict[str, int]
    advisory_by_lane_pair: dict[str, int]
    advisory_non_test_scoped_occurrences: int
    advisory_occurrences: int
    advisory_test_scoped_occurrences: int
    advisory_unique_occurrences: int


class _CandidateInventory(TypedDict):
    advisory_occurrences: list[_OccurrenceRow]
    generated_at: str
    occurrences: list[_OccurrenceRow]
    schema_version: int
    summary: _CandidateSummary


class _RatchetCounts(TypedDict):
    approved_active: int
    root_boundary: int
    new_unapproved: int
    expanded_existing: int
    expired: int
    malformed: int
    regressed_retired: int
    retirement_candidates: int
    retirement_ready: int
    retired_verified: int
    retired_source_removed: int


class _RatchetEntry(TypedDict):
    fingerprint: str
    source_module: str
    target_module: str
    import_form: str
    imported_symbols: list[str]
    lexical_scope: str
    contract: str
    owner: str
    reason: str
    capability: str
    multiplicity: int
    created_on: str
    expires_on: str
    status: str


class _RatchetReport(TypedDict):
    baseline_status: str
    counts: _RatchetCounts
    detail_counts: dict[str, int]
    details: dict[str, list[str]]
    path: str
    schema_version: int


def build_import_health(
    *,
    authority: Authority,
    authority_findings: tuple[str, ...],
    linter_returncode: int,
    linter_output: str,
    checker: CheckResult,
    loadability: dict[str, object],
    load_returncode: int,
    source_snapshot_before: str,
    source_snapshot_after: str,
    component_durations: dict[str, float],
) -> tuple[dict[str, object], int]:
    """Build the three-state verdict and return its process exit status."""
    graph = _graph_summary(linter_output)
    candidate = _candidate_inventory(authority, checker.occurrences)
    candidate_path = _write_candidate_artifact(authority.repository, candidate)
    ratchet = _reconcile_ratchet(authority, candidate, _root_boundary_pairs(authority))

    blocking_findings = [finding for finding in checker.findings if not finding.advisory and not finding.fatal]
    advisory_findings = [finding for finding in checker.findings if finding.advisory]
    fatal_findings = [finding for finding in checker.findings if finding.fatal]
    operational_reasons = list(authority_findings)
    if linter_returncode not in {0, 1}:
        operational_reasons.append(f"import-linter exited with operational status {linter_returncode}")
    if load_returncode not in {0, 1} or loadability.get("operational_error"):
        operational_reasons.append(
            str(loadability.get("operational_error") or f"loadability probe exited with status {load_returncode}")
        )
    if checker.files_scanned <= 0:
        operational_reasons.append("subordinate checker produced no governed-file census")
    if graph["files"] and checker.files_scanned and graph["files"] != checker.files_scanned:
        operational_reasons.append(
            "graph census mismatch: "
            f"Import Linter saw {graph['files']} file(s), subordinate saw {checker.files_scanned}"
        )
    if source_snapshot_before != source_snapshot_after:
        operational_reasons.append("governed source tree changed while the gate was running")
    candidate_by_contract = candidate["summary"]["by_contract"]
    contract_status = graph["contract_status"]
    supplemental_occurrences = {
        contract.key: int(candidate_by_contract.get(contract.key, 0))
        for contract in authority.forbidden_contracts
        if int(candidate_by_contract.get(contract.key, 0)) and contract_status.get(contract.name) == "kept"
    }
    operational_reasons.extend(finding.message for finding in fatal_findings)

    failed_reasons: list[str] = []
    if blocking_findings:
        failed_reasons.append(f"{len(blocking_findings)} hard import-authority finding(s)")
    load_failures = _loadability_int(loadability, "failed")
    load_root_causes = _loadability_int(loadability, "root_cause_count", load_failures)
    if load_failures:
        failed_reasons.append(
            f"{load_failures} governed module load failure(s) across {load_root_causes} root-cause group(s)"
        )
    for key, label in (
        ("root_boundary", "shipped-root occurrence(s) reaching a repository-only root, which no ratchet can approve"),
        ("new_unapproved", "new unapproved occurrence(s)"),
        ("expanded_existing", "expanded occurrence(s)"),
        ("expired", "expired debt occurrence(s)"),
        ("malformed", "malformed ratchet entry or occurrence(s)"),
        ("regressed_retired", "retired occurrence regression(s)"),
        ("retirement_candidates", "disappeared occurrence(s) without verified composition evidence"),
    ):
        count = ratchet["counts"][key]
        if count:
            failed_reasons.append(f"{count} {label}")
    if graph["contracts_broken"] and not candidate["summary"]["contract_occurrences"]:
        failed_reasons.append("broken graph contracts have no attributable direct occurrence")

    debt_total = ratchet["counts"]["approved_active"] + ratchet["counts"]["retirement_ready"]
    if operational_reasons:
        verdict = "failed"
        classification = "tool_failure"
        exit_status = 7
    elif failed_reasons:
        verdict = "failed"
        classification = "blocking_findings"
        exit_status = 1
    elif debt_total:
        verdict = "passing_with_debt"
        classification = "passing_with_debt"
        exit_status = 0
    else:
        verdict = "clean"
        classification = "clean"
        exit_status = 0

    headline = _headline(verdict, graph, checker, ratchet, operational_reasons, failed_reasons)
    convergence = {
        "active_debt_occurrences": ratchet["counts"]["approved_active"],
        "blocking_findings": len(blocking_findings),
        "load_failures": load_failures,
        "load_root_causes": load_root_causes,
        "expanded_occurrences": ratchet["counts"]["expanded_existing"],
        "expired_occurrences": ratchet["counts"]["expired"],
        "new_unapproved_occurrences": ratchet["counts"]["new_unapproved"],
        "operational_failures": len(operational_reasons),
        "pending_retirement_occurrences": ratchet["counts"]["retirement_candidates"]
        + ratchet["counts"]["retirement_ready"],
        "regressed_retired_occurrences": ratchet["counts"]["regressed_retired"],
        "zero": verdict == "clean",
        "zero_definition": (
            "authoritative stable graph, every governed non-test module loads, zero hard findings, "
            "zero current or approved architectural debt, and zero pending retirement"
        ),
    }
    candidate_advisory_by_contract = candidate["summary"]["advisory_by_contract"]
    advisory_by_code = Counter(finding.category for finding in advisory_findings)
    advisory_by_code.update({str(key): int(value) for key, value in candidate_advisory_by_contract.items()})
    advisory_total = len(advisory_findings) + candidate["summary"]["advisory_occurrences"]
    payload: dict[str, object] = {
        "advisories": {
            "by_code": dict(sorted(advisory_by_code.items())),
            "total": advisory_total,
        },
        "candidate_inventory": {
            "artifact": str(candidate_path) if candidate_path is not None else None,
            **candidate["summary"],
        },
        "classification": classification,
        "component_durations_seconds": {key: round(value, 3) for key, value in sorted(component_durations.items())},
        "composition_evidence": {
            "missing": ratchet["counts"]["retirement_candidates"],
            "ready_for_ratchet_retirement": ratchet["counts"]["retirement_ready"],
            "retired_verified": ratchet["counts"]["retired_verified"],
        },
        "convergence": convergence,
        "failed_reasons": failed_reasons,
        "graph_authority": {
            **graph,
            "files_scanned_by_subordinate": checker.files_scanned,
            "operational_reasons": operational_reasons,
            "supplemental_direct_occurrences_for_kept_contracts": supplemental_occurrences,
            "source_snapshot_after": source_snapshot_after,
            "source_snapshot_before": source_snapshot_before,
            "status": "authoritative" if not operational_reasons else "unavailable",
        },
        "hard_findings": {
            "by_code": dict(sorted(Counter(finding.category for finding in blocking_findings).items())),
            "total": len(blocking_findings),
        },
        "headline": headline,
        "loadability": {
            "artifact": loadability.get("artifact"),
            "attempted": _loadability_int(loadability, "attempted"),
            "failed": load_failures,
            "failure_sample": _loadability_items(loadability, "failures")[:20],
            "loaded": _loadability_int(loadability, "loaded"),
            "root_cause_count": load_root_causes,
            "root_cause_sample": _loadability_items(loadability, "root_causes")[:20],
            "scope": loadability.get("scope", "unavailable"),
            "status": "unavailable" if load_returncode not in {0, 1} else "failed" if load_failures else "loaded",
            "target_digest": loadability.get("target_digest"),
        },
        "ratchet": ratchet,
        "schema_version": _SIGNAL_SCHEMA_VERSION,
        "verdict": verdict,
    }
    return payload, exit_status


def render_import_health(payload: dict[str, object]) -> str:
    """Render the compact human contract before the machine payload."""
    graph = payload["graph_authority"]
    ratchet = payload["ratchet"]
    hard = payload["hard_findings"]
    advisory = payload["advisories"]
    loadability = payload["loadability"]
    if not isinstance(graph, dict) or not isinstance(ratchet, dict):
        raise TypeError("graph_authority and ratchet payloads must be mappings")
    if not isinstance(hard, dict) or not isinstance(advisory, dict):
        raise TypeError("hard_findings and advisories payloads must be mappings")
    if not isinstance(loadability, dict):
        raise TypeError("loadability payload must be a mapping")
    counts = ratchet["counts"]
    if not isinstance(counts, dict):
        raise TypeError("ratchet counts payload must be a mapping")
    return "\n".join(
        (
            f"VERDICT: {payload['verdict']}",
            f"Graph authority: {graph['status']} ({graph['files']} files, {graph['dependencies']} dependencies)",
            f"Hard findings: {hard['total']}",
            f"Module loadability: {loadability['status']} "
            f"({loadability['loaded']}/{loadability['attempted']} loaded; "
            f"{loadability['root_cause_count']} root-cause group(s))",
            f"Approved debt: {counts['approved_active']} occurrence(s)",
            f"Repository-only reach (not ratchetable): {counts['root_boundary']} occurrence(s)",
            "New / expanded / expired: "
            f"{counts['new_unapproved']} / {counts['expanded_existing']} / {counts['expired']}",
            "Retirement missing evidence / ready / verified: "
            f"{counts['retirement_candidates']} / {counts['retirement_ready']} / {counts['retired_verified']}",
            f"Retired with removed source module: {counts['retired_source_removed']} occurrence(s)",
            f"Advisories: {advisory['total']}",
            f"Baseline status: {ratchet['baseline_status']}",
        )
    )


def unavailable_import_health(reason: str) -> dict[str, object]:
    """Return the same schema when authority cannot be initialized."""
    empty_counts = {
        "approved_active": 0,
        "root_boundary": 0,
        "expanded_existing": 0,
        "expired": 0,
        "malformed": 0,
        "new_unapproved": 0,
        "regressed_retired": 0,
        "retired_source_removed": 0,
        "retired_verified": 0,
        "retirement_candidates": 0,
        "retirement_ready": 0,
    }
    return {
        "advisories": {"by_code": {}, "total": 0},
        "candidate_inventory": {
            "advisory_by_contract": {},
            "advisory_by_lane_pair": {},
            "advisory_non_test_scoped_occurrences": 0,
            "advisory_occurrences": 0,
            "advisory_test_scoped_occurrences": 0,
            "advisory_unique_occurrences": 0,
            "artifact": None,
            "by_contract": {},
            "by_import_form": {},
            "contract_occurrences": 0,
            "inventory_digest": None,
            "non_test_scoped_occurrences": 0,
            "test_scoped_occurrences": 0,
            "unique_contract_occurrences": 0,
            "unique_import_occurrences": 0,
        },
        "classification": "tool_failure",
        "component_durations_seconds": {},
        "composition_evidence": {"missing": 0, "ready_for_ratchet_retirement": 0, "retired_verified": 0},
        "convergence": {
            "active_debt_occurrences": 0,
            "blocking_findings": 0,
            "load_failures": 0,
            "load_root_causes": 0,
            "expanded_occurrences": 0,
            "expired_occurrences": 0,
            "new_unapproved_occurrences": 0,
            "operational_failures": 1,
            "pending_retirement_occurrences": 0,
            "regressed_retired_occurrences": 0,
            "zero": False,
            "zero_definition": (
                "authoritative stable graph, every governed non-test module loads, zero hard findings, "
                "zero current or approved architectural debt, and zero pending retirement"
            ),
        },
        "failed_reasons": [],
        "graph_authority": {
            "broken_contract_names": [],
            "contract_status": {},
            "contracts_broken": 0,
            "contracts_kept": 0,
            "contracts_total": 0,
            "dependencies": 0,
            "files": 0,
            "files_scanned_by_subordinate": 0,
            "supplemental_direct_occurrences_for_kept_contracts": {},
            "operational_reasons": [reason],
            "source_snapshot_after": None,
            "source_snapshot_before": None,
            "status": "unavailable",
        },
        "hard_findings": {"by_code": {}, "total": 0},
        "headline": "Import health is unavailable because authority initialization failed.",
        "loadability": {
            "artifact": None,
            "attempted": 0,
            "failed": 0,
            "failure_sample": [],
            "loaded": 0,
            "root_cause_count": 0,
            "root_cause_sample": [],
            "scope": "unavailable",
            "status": "unavailable",
            "target_digest": None,
        },
        "ratchet": {
            "baseline_status": "unavailable",
            "counts": empty_counts,
            "detail_counts": {},
            "details": {},
            "path": None,
            "schema_version": _RATCHET_SCHEMA_VERSION,
        },
        "schema_version": _SIGNAL_SCHEMA_VERSION,
        "verdict": "failed",
    }


def _loadability_int(loadability: dict[str, object], key: str, default: int = 0) -> int:
    """Read an integer field from the subprocess JSON contract."""
    value = loadability.get(key, default)
    if isinstance(value, int):
        return value
    if isinstance(value, (str, bytes, bytearray, float)):
        return int(value)
    raise TypeError(f"loadability field {key!r} is not integer-compatible")


def _loadability_items(loadability: dict[str, object], key: str) -> list[object]:
    """Read an iterable sample from the subprocess JSON contract."""
    value = loadability.get(key, ())
    if isinstance(value, Iterable):
        return list(value)
    raise TypeError(f"loadability field {key!r} is not iterable")


def _graph_summary(output: str) -> _GraphSummary:
    files = 0
    dependencies = 0
    contracts: Counter[str] = Counter()
    broken: list[str] = []
    contract_status: dict[str, str] = {}
    for line in output.splitlines():
        analyzed = _ANALYZED_RE.fullmatch(line.strip())
        if analyzed:
            files = int(analyzed.group(1))
            dependencies = int(analyzed.group(2))
            continue
        contract = _CONTRACT_RE.fullmatch(line.strip())
        if contract:
            status = contract.group(2).lower()
            contracts[status] += 1
            contract_status[contract.group(1)] = status
            if status == "broken":
                broken.append(contract.group(1))
    return {
        "contracts_broken": contracts["broken"],
        "contracts_kept": contracts["kept"],
        "contracts_total": sum(contracts.values()),
        "broken_contract_names": broken,
        "contract_status": dict(sorted(contract_status.items())),
        "dependencies": dependencies,
        "files": files,
    }


def _candidate_inventory(authority: Authority, occurrences: tuple[ImportOccurrence, ...]) -> _CandidateInventory:
    hard = tuple(occurrence for occurrence in occurrences if not occurrence.contract.startswith("advisory:"))
    advisory = tuple(occurrence for occurrence in occurrences if occurrence.contract.startswith("advisory:"))
    rows, summary = _occurrence_inventory(authority, hard)
    advisory_rows, advisory_summary = _occurrence_inventory(authority, advisory)
    advisory_lane_pairs: Counter[str] = Counter()
    for row in advisory_rows:
        source_lane = _adapter_top_level(str(row["source_module"]))
        target_lane = _adapter_top_level(str(row["target_module"]))
        if source_lane is not None and target_lane is not None:
            advisory_lane_pairs[f"{source_lane} -> {target_lane}"] += int(row["multiplicity"])
    candidate_summary: _CandidateSummary = {
        "contract_occurrences": summary["contract_occurrences"],
        "by_contract": summary["by_contract"],
        "by_import_form": summary["by_import_form"],
        "non_test_scoped_occurrences": summary["non_test_scoped_occurrences"],
        "test_scoped_occurrences": summary["test_scoped_occurrences"],
        "inventory_digest": summary["inventory_digest"],
        "unique_contract_occurrences": summary["unique_contract_occurrences"],
        "unique_import_occurrences": summary["unique_import_occurrences"],
        "advisory_by_contract": advisory_summary["by_contract"],
        "advisory_by_lane_pair": dict(sorted(advisory_lane_pairs.items())),
        "advisory_non_test_scoped_occurrences": advisory_summary["non_test_scoped_occurrences"],
        "advisory_occurrences": advisory_summary["contract_occurrences"],
        "advisory_test_scoped_occurrences": advisory_summary["test_scoped_occurrences"],
        "advisory_unique_occurrences": advisory_summary["unique_contract_occurrences"],
    }
    return {
        "advisory_occurrences": advisory_rows,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "occurrences": rows,
        "schema_version": _RATCHET_SCHEMA_VERSION,
        "summary": candidate_summary,
    }


def _occurrence_inventory(
    authority: Authority, occurrences: tuple[ImportOccurrence, ...]
) -> tuple[list[_OccurrenceRow], _OccurrenceSummary]:
    """Normalize one hard or advisory occurrence class without conflating them."""
    grouped: defaultdict[str, list[ImportOccurrence]] = defaultdict(list)
    for occurrence in occurrences:
        grouped[occurrence.fingerprint].append(occurrence)
    rows: list[_OccurrenceRow] = []
    unique_import_identities: set[tuple[str, str, tuple[str, ...], str, str]] = set()
    production = 0
    test = 0
    by_contract: Counter[str] = Counter()
    by_import_form: Counter[str] = Counter()
    for fingerprint, group in sorted(grouped.items()):
        first = group[0]
        evidence = sorted(
            {
                (
                    occurrence.path.relative_to(authority.repository).as_posix(),
                    occurrence.lineno,
                )
                for occurrence in group
            }
        )
        test_scoped = module_is_test_scoped(first.source_module)
        if test_scoped:
            test += len(group)
        else:
            production += len(group)
        by_contract[first.contract] += len(group)
        by_import_form[first.import_form] += len(group)
        identity = (
            first.source_module,
            first.target_module,
            first.imported_symbols,
            first.import_form,
            first.lexical_scope,
        )
        unique_import_identities.add(identity)
        rows.append(
            {
                "contract": first.contract,
                "evidence": [{"line": line, "path": path} for path, line in evidence],
                "fingerprint": fingerprint,
                "import_form": first.import_form,
                "imported_symbols": list(first.imported_symbols),
                "lexical_scope": first.lexical_scope,
                "multiplicity": len(group),
                "source_module": first.source_module,
                "target_module": first.target_module,
                "test_scoped": test_scoped,
            }
        )
    inventory_digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode(UTF_8)).hexdigest()
    return rows, {
        "contract_occurrences": sum(len(group) for group in grouped.values()),
        "by_contract": dict(sorted(by_contract.items())),
        "by_import_form": dict(sorted(by_import_form.items())),
        "non_test_scoped_occurrences": production,
        "test_scoped_occurrences": test,
        "inventory_digest": inventory_digest,
        "unique_contract_occurrences": len(rows),
        "unique_import_occurrences": len(unique_import_identities),
    }


def _write_candidate_artifact(repository: Path, candidate: _CandidateInventory) -> Path | None:
    raw_artifacts = os.environ.get("CADRUMO_DEV_ARTIFACTS_DIR")
    if not raw_artifacts:
        return None
    artifacts = Path(raw_artifacts).resolve()
    path = artifacts / "import-boundary-candidate.json"
    path.write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n",
        encoding=UTF_8,
        newline="\n",
    )
    return path


def _root_boundary_pairs(authority: Authority) -> frozenset[tuple[str, str]]:
    """Return the root-to-root separations declared by forbidden contracts.

    A contract whose source and forbidden members are both whole first-party
    roots separates independently shipped trees.  That separation holds for
    every module in the source root, test modules included, so it is never
    ratchetable debt.
    """
    roots = authority.root_names
    return frozenset(
        (source, forbidden)
        for contract in authority.forbidden_contracts
        for source in contract.source_modules
        if source in roots
        for forbidden in contract.forbidden_modules
        if forbidden in roots
    )


def _crosses_root_boundary(source_module: str, target_module: str, pairs: frozenset[tuple[str, str]]) -> bool:
    return (source_module.partition(".")[0], target_module.partition(".")[0]) in pairs


def _reconcile_ratchet(
    authority: Authority,
    candidate: _CandidateInventory,
    root_boundaries: frozenset[tuple[str, str]],
) -> _RatchetReport:
    repository = authority.repository
    path = repository / _RATCHET_RELATIVE_PATH
    rows = candidate["occurrences"]
    current = {
        row["fingerprint"]: row
        for row in rows
        if not _crosses_root_boundary(row["source_module"], row["target_module"], root_boundaries)
    }
    boundary_rows = [row for row in rows if row["fingerprint"] not in current]
    details: defaultdict[str, list[str]] = defaultdict(list)
    for row in boundary_rows:
        evidence = row["evidence"][0] if row["evidence"] else None
        location = f"{evidence['path']}:{evidence['line']}" if evidence is not None else row["source_module"]
        details["root_boundary"].append(f"{location} imports {row['target_module']}")
    counts: Counter[str] = Counter(
        {
            "approved_active": 0,
            "root_boundary": sum(int(row["multiplicity"]) for row in boundary_rows),
            "new_unapproved": 0,
            "expanded_existing": 0,
            "expired": 0,
            "malformed": 0,
            "regressed_retired": 0,
            "retirement_candidates": 0,
            "retirement_ready": 0,
            "retired_verified": 0,
            "retired_source_removed": 0,
        }
    )
    if not path.is_file():
        counts["new_unapproved"] = sum(int(row["multiplicity"]) for row in current.values())
        baseline_status = "not_required" if not current else "unestablished"
        details["new_unapproved"].extend(current)
        return {
            "baseline_status": baseline_status,
            "counts": _ratchet_counts(counts),
            "detail_counts": {key: len(values) for key, values in sorted(details.items())},
            "details": {key: sorted(values)[:20] for key, values in sorted(details.items())},
            "path": str(path),
            "schema_version": _RATCHET_SCHEMA_VERSION,
        }

    try:
        payload = json.loads(path.read_text(encoding=UTF_8))
        if payload.get("schema_version") != _RATCHET_SCHEMA_VERSION:
            raise ValueError("unsupported ratchet schema")
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise ValueError("ratchet entries must be a list")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        counts["malformed"] += 1
        return {
            "baseline_status": "malformed",
            "counts": _ratchet_counts(counts),
            "detail_counts": {"malformed": 1},
            "details": {"malformed": [str(exc)]},
            "path": str(path),
            "schema_version": _RATCHET_SCHEMA_VERSION,
        }

    approved: dict[str, _RatchetEntry] = {}
    today = date.today()
    for index, raw in enumerate(entries):
        if not isinstance(raw, dict):
            counts["malformed"] += 1
            details["malformed"].append(f"entry {index} is not an object")
            continue
        fingerprint = str(raw.get("fingerprint", ""))
        if not fingerprint or fingerprint in approved:
            counts["malformed"] += 1
            details["malformed"].append(f"entry {index} has missing or duplicate fingerprint")
            continue
        validated = _validate_ratchet_entry(raw)
        if isinstance(validated, str):
            counts["malformed"] += 1
            details["malformed"].append(f"{fingerprint}: {validated}")
            continue
        if _crosses_root_boundary(validated["source_module"], validated["target_module"], root_boundaries):
            counts["malformed"] += 1
            details["malformed"].append(f"{fingerprint}: a shipped root reaching a repository-only root is not debt")
            continue
        approved[fingerprint] = validated
        allowed = validated["multiplicity"]
        observed = current.get(fingerprint, {}).get("multiplicity", 0)
        status = validated["status"]
        expires = date.fromisoformat(validated["expires_on"])
        if status == "retired":
            if observed:
                counts["regressed_retired"] += observed
                details["regressed_retired"].append(fingerprint)
            elif _is_source_module_removal(raw.get("retirement")):
                source_module = validated["source_module"]
                if _source_module_exists(authority, source_module):
                    counts["malformed"] += allowed
                    details["malformed"].append(
                        f"{fingerprint}: retirement claims {source_module} was removed, but it still exists"
                    )
                else:
                    counts["retired_source_removed"] += allowed
                    details["retired_source_removed"].append(fingerprint)
            elif _valid_retirement(raw.get("retirement"), repository, validated["capability"]):
                counts["retired_verified"] += allowed
            else:
                counts["malformed"] += allowed
                details["malformed"].append(f"{fingerprint}: retired entry lacks valid composition evidence")
            continue
        if expires < today:
            counts["expired"] += max(allowed, observed)
            details["expired"].append(fingerprint)
        counts["approved_active"] += min(allowed, observed)
        if observed > allowed:
            counts["expanded_existing"] += observed - allowed
            details["expanded_existing"].append(fingerprint)
        elif observed < allowed:
            missing = allowed - observed
            if _valid_retirement(raw.get("retirement"), repository, validated["capability"]):
                counts["retirement_ready"] += missing
                details["retirement_ready"].append(fingerprint)
            else:
                counts["retirement_candidates"] += missing
                details["retirement_candidates"].append(fingerprint)
                if not observed and not _source_module_exists(authority, validated["source_module"]):
                    details["source_module_removed"].append(fingerprint)

    for fingerprint, row in current.items():
        if fingerprint not in approved:
            counts["new_unapproved"] += row["multiplicity"]
            details["new_unapproved"].append(fingerprint)
    return {
        "baseline_status": "approved" if not counts["malformed"] else "malformed",
        "counts": _ratchet_counts(counts),
        "detail_counts": {key: len(values) for key, values in sorted(details.items())},
        "details": {key: sorted(values)[:20] for key, values in sorted(details.items())},
        "path": str(path),
        "schema_version": _RATCHET_SCHEMA_VERSION,
    }


def _ratchet_counts(counts: Counter[str]) -> _RatchetCounts:
    """Materialize the closed ratchet-count schema from its mutable counter."""
    return {
        "approved_active": counts["approved_active"],
        "root_boundary": counts["root_boundary"],
        "new_unapproved": counts["new_unapproved"],
        "expanded_existing": counts["expanded_existing"],
        "expired": counts["expired"],
        "malformed": counts["malformed"],
        "regressed_retired": counts["regressed_retired"],
        "retirement_candidates": counts["retirement_candidates"],
        "retirement_ready": counts["retirement_ready"],
        "retired_verified": counts["retired_verified"],
        "retired_source_removed": counts["retired_source_removed"],
    }


def _is_source_module_removal(raw: object) -> bool:
    """Recognise the retirement record that claims the entry's source module was deleted.

    The claim is only a shape here; the reconciler proves it against the live
    authority tree on every run, so a returning module invalidates it.
    """
    if not isinstance(raw, dict) or set(raw) != {"kind", "verified_at"} or raw["kind"] != "source_module_removed":
        return False
    verified_at = raw["verified_at"]
    if not isinstance(verified_at, str):
        return False
    try:
        datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _source_module_exists(authority: Authority, module: str) -> bool:
    """Return whether ``module`` is a module or package file below its declared root."""
    for root in sorted(authority.roots, key=lambda item: len(item.name), reverse=True):
        if module != root.name and not module.startswith(f"{root.name}."):
            continue
        relative = module.split(".")[len(root.name.split(".")) :]
        base = root.path.joinpath(*relative)
        if (base / "__init__.py").is_file():
            return True
        return bool(relative) and base.with_name(f"{relative[-1]}.py").is_file()
    return False


def _validate_ratchet_entry(entry: dict[str, object]) -> str | _RatchetEntry:
    required_text = (
        "fingerprint",
        "source_module",
        "target_module",
        "import_form",
        "lexical_scope",
        "contract",
        "owner",
        "reason",
        "capability",
        "created_on",
        "expires_on",
        "status",
    )
    text_fields: dict[str, str] = {}
    for key in required_text:
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            return "required text field is missing"
        text_fields[key] = value

    imported_symbols_raw = entry.get("imported_symbols")
    if not isinstance(imported_symbols_raw, list):
        return "imported_symbols must be a string list"
    imported_symbols: list[str] = []
    for symbol in imported_symbols_raw:
        if not isinstance(symbol, str):
            return "imported_symbols must be a string list"
        imported_symbols.append(symbol)

    multiplicity = entry.get("multiplicity")
    if not isinstance(multiplicity, int) or multiplicity <= 0:
        return "multiplicity must be a positive integer"
    import_form = text_fields["import_form"]
    if import_form not in {"static", "local", "type_checking", "dynamic"}:
        return "unknown import_form"
    status = text_fields["status"]
    if status not in {"active", "retired"}:
        return "status must be active or retired"
    try:
        created = date.fromisoformat(text_fields["created_on"])
        expires = date.fromisoformat(text_fields["expires_on"])
    except ValueError:
        return "created_on and expires_on must be ISO dates"
    if expires < created:
        return "expires_on precedes created_on"
    from .import_checker import import_occurrence_fingerprint

    expected = import_occurrence_fingerprint(
        source_module=text_fields["source_module"],
        target_module=text_fields["target_module"],
        imported_symbols=tuple(imported_symbols),
        import_form=import_form,
        lexical_scope=text_fields["lexical_scope"],
        contract=text_fields["contract"],
    )
    if text_fields["fingerprint"] != expected:
        return "fingerprint does not match normalized occurrence identity"
    return {
        "fingerprint": text_fields["fingerprint"],
        "source_module": text_fields["source_module"],
        "target_module": text_fields["target_module"],
        "import_form": import_form,
        "imported_symbols": imported_symbols,
        "lexical_scope": text_fields["lexical_scope"],
        "contract": text_fields["contract"],
        "owner": text_fields["owner"],
        "reason": text_fields["reason"],
        "capability": text_fields["capability"],
        "multiplicity": multiplicity,
        "created_on": text_fields["created_on"],
        "expires_on": text_fields["expires_on"],
        "status": status,
    }


def _valid_retirement(raw: object, repository: Path, capability: str) -> bool:
    """Verify a digest-bound clean report from the separate composition signal."""
    if not isinstance(raw, dict):
        return False
    required = ("composition_proof", "evidence_digest", "verified_at")
    if any(not isinstance(raw.get(key), str) or not str(raw[key]).strip() for key in required):
        return False
    matrix = raw.get("capability_matrix")
    if not isinstance(matrix, dict) or not matrix:
        return False
    if not all(value in {"required", "optional", "unsupported"} for value in matrix.values()):
        return False
    try:
        datetime.fromisoformat(str(raw["verified_at"]).replace("Z", "+00:00"))
        proof = (repository / str(raw["composition_proof"])).resolve()
        proof.relative_to(repository.resolve())
        content = proof.read_bytes()
        if hashlib.sha256(content).hexdigest() != raw["evidence_digest"]:
            return False
        report = json.loads(content)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
    if not isinstance(report, dict):
        return False
    if (
        report.get("schema_version") != 1
        or report.get("event") != "composition_integrity"
        or report.get("verdict") != "clean"
        or report.get("capability") != capability
        or report.get("capability_matrix") != matrix
    ):
        return False
    entrypoints = report.get("entrypoints")
    if not isinstance(entrypoints, dict) or set(entrypoints) != set(matrix):
        return False
    for entrypoint, applicability in matrix.items():
        expected = "unsupported" if applicability == "unsupported" else "verified"
        if entrypoints.get(entrypoint) != expected:
            return False
    checks = report.get("vertical_slice_checks")
    required_checks = {
        "application_has_no_concrete_adapter_import",
        "capability_port_owned_inward",
        "port_is_capability_level",
        "dependency_required_at_use_case_boundary",
        "dependency_propagates_internally",
        "no_concrete_infrastructure_default",
        "no_global_service_locator",
        "applicable_entrypoints_bind_implementation",
        "unsupported_entrypoints_declared",
        "adapter_dtos_and_errors_stay_outward",
        "integration_tests_live_at_outer_seam",
        "real_binding_composition_proof",
    }
    return isinstance(checks, dict) and set(checks) == required_checks and all(checks.values())


def module_is_test_scoped(module: str) -> bool:
    parts = module.split(".")
    return (
        "tests" in parts
        or "conftest" in parts
        or any(part.startswith("test_") or part.endswith("_test") for part in parts)
    )


def _adapter_top_level(module: str) -> str | None:
    prefix = "cadrumo.adapters."
    if not module.startswith(prefix):
        return None
    return module.removeprefix(prefix).partition(".")[0] or None


def _headline(
    verdict: str,
    graph: _GraphSummary,
    checker: CheckResult,
    ratchet: _RatchetReport,
    operational: list[str],
    failed: list[str],
) -> str:
    if operational:
        return "Import health is unavailable because an authority component failed."
    if verdict == "failed":
        return "Import health failed: " + "; ".join(failed)
    counts = ratchet["counts"]
    if not isinstance(counts, dict):
        raise TypeError("ratchet counts payload must be a mapping")
    if verdict == "passing_with_debt":
        return (
            "Import health is passing with explicit debt: "
            f"{counts['approved_active']} active occurrence(s), "
            f"{counts['retirement_candidates']} pending verified retirement."
        )
    return (
        "Import health is clean: authoritative graph, all governed non-test modules load, zero hard findings, "
        "zero architectural occurrences, and zero pending retirements."
    )


__all__ = ["build_import_health", "render_import_health", "unavailable_import_health"]
