"""Complete import health evidence payload."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .import_check_models import CheckResult, Finding
from .import_health_models import SIGNAL_SCHEMA_VERSION, CandidateInventory, GraphSummary, RatchetReport
from .import_loadability_projection import loadability_int, loadability_items


def health_payload(
    ratchet: RatchetReport,
    blocking_findings: list[Finding],
    load_failures: int,
    load_root_causes: int,
    operational_reasons: list[str],
    failed_reasons: list[str],
    verdict: str,
    classification: str,
    headline: str,
    advisory_findings: list[Finding],
    candidate: CandidateInventory,
    candidate_path: Path | None,
    component_cpu_seconds: dict[str, float] | None,
    component_durations: dict[str, float],
    checker: CheckResult,
    graph: GraphSummary,
    supplemental_occurrences: dict[str, int],
    source_snapshot_before: str,
    source_snapshot_after: str,
    loadability: dict[str, object],
    load_returncode: int,
    step_budget: dict[str, float] | None,
) -> dict[str, object]:
    """Health payload."""
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
    advisory_by_code, advisory_total = _health_advisories(candidate, advisory_findings)
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
        "component_cpu_seconds": {key: round(value, 3) for key, value in sorted((component_cpu_seconds or {}).items())},
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
            "attempted": loadability_int(loadability, "attempted"),
            "failed": load_failures,
            "failure_sample": loadability_items(loadability, "failures")[:20],
            "loaded": loadability_int(loadability, "loaded"),
            "root_cause_count": load_root_causes,
            "root_cause_sample": loadability_items(loadability, "root_causes")[:20],
            "scope": loadability.get("scope", "unavailable"),
            "status": "unavailable" if load_returncode not in {0, 1} else "failed" if load_failures else "loaded",
            "target_digest": loadability.get("target_digest"),
        },
        "ratchet": ratchet,
        "schema_version": SIGNAL_SCHEMA_VERSION,
        "step_budget": dict(sorted((step_budget or {}).items())),
        "verdict": verdict,
    }
    return payload


def _health_advisories(candidate: CandidateInventory, advisory_findings: list[Finding]) -> tuple[Counter[str], int]:
    """Health advisories."""
    candidate_advisory_by_contract = candidate["summary"]["advisory_by_contract"]
    advisory_by_code = Counter(finding.category for finding in advisory_findings)
    advisory_by_code.update({str(key): int(value) for key, value in candidate_advisory_by_contract.items()})
    advisory_total = len(advisory_findings) + candidate["summary"]["advisory_occurrences"]
    return advisory_by_code, advisory_total
