"""Import health rendering."""

from __future__ import annotations

from typing import cast

from .import_check_models import CheckResult
from .import_health_models import RATCHET_SCHEMA_VERSION, SIGNAL_SCHEMA_VERSION, GraphSummary, RatchetReport


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
    counts: object = cast("dict[str, object]", ratchet)["counts"]
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
        "component_cpu_seconds": {},
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
            "schema_version": RATCHET_SCHEMA_VERSION,
        },
        "schema_version": SIGNAL_SCHEMA_VERSION,
        "step_budget": {},
        "verdict": "failed",
    }


def health_headline(
    verdict: str,
    graph: GraphSummary,
    checker: CheckResult,
    ratchet: RatchetReport,
    operational: list[str],
    failed: list[str],
) -> str:
    """Describe the verdict using its operational, blocking, and debt evidence."""
    if operational:
        return "Import health is unavailable because an authority component failed."
    if verdict == "failed":
        return "Import health failed: " + "; ".join(failed)
    counts = ratchet["counts"]
    if not isinstance(counts, dict):
        raise TypeError("ratchet counts payload must be a mapping")
    if verdict == "passing_with_debt":
        broken = graph["contracts_broken"]
        contracts = f", {broken} broken contract(s)" if broken else ""
        return (
            "Import health is passing with explicit debt: "
            f"{counts['approved_active']} active occurrence(s)"
            f"{contracts}, "
            f"{counts['retirement_candidates']} pending verified retirement."
        )
    return (
        "Import health is clean: authoritative graph, all governed non-test modules load, zero hard findings, "
        "zero architectural occurrences, and zero pending retirements."
    )
