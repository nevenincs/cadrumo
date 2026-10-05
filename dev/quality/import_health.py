"""Truthful occurrence-level health coordinator."""

from __future__ import annotations

from .import_candidate_inventory import candidate_inventory, write_candidate_artifact
from .import_check_models import Authority, CheckResult, Finding
from .import_graph_summary import graph_summary
from .import_health_models import CandidateInventory, GraphSummary
from .import_health_payload import health_payload
from .import_health_reasoning import failed_health_reasons, operational_health_reasons, select_health_verdict
from .import_health_rendering import health_headline
from .import_ratchet import reconcile_ratchet
from .import_root_boundaries import root_boundary_pairs


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
    component_cpu_seconds: dict[str, float] | None = None,
    step_budget: dict[str, float] | None = None,
) -> tuple[dict[str, object], int]:
    """Build the three-state verdict and return its process exit status."""
    graph = graph_summary(linter_output)
    candidate = candidate_inventory(authority, checker.occurrences)
    candidate_path = write_candidate_artifact(authority.repository, candidate)
    ratchet = reconcile_ratchet(authority, candidate, root_boundary_pairs(authority))

    blocking_findings, advisory_findings, fatal_findings = _classify_checker_findings(checker)
    operational_reasons = operational_health_reasons(
        authority_findings,
        linter_returncode,
        load_returncode,
        loadability,
        checker,
        graph,
        source_snapshot_before,
        source_snapshot_after,
    )
    supplemental_occurrences = _supplemental_occurrences(authority, candidate, graph)
    operational_reasons.extend(finding.message for finding in fatal_findings)

    failed_reasons, load_failures, load_root_causes = failed_health_reasons(
        blocking_findings, loadability, ratchet, graph, candidate
    )
    # A linter that aborts before evaluating anything exits 1 and prints its
    # reason, which is indistinguishable from a clean run by returncode and
    # by contract counts alike -- both leave `contracts_broken` at 0. Reading
    # that as an authoritative graph is how a missing layer in an exhaustive
    # contract took all fifteen contracts out of the merge gate without
    # changing its verdict.
    #
    # Raised only when nothing else already explains the empty graph. A
    # planted source defect stops the linter building a graph too, and
    # there the subordinate finding IS the verdict: calling that a tool
    # failure would bury a real finding under "unavailable".
    if not graph["contracts_total"] and not blocking_findings and not load_failures:
        operational_reasons.append("import-linter evaluated no contracts; the configured contract set was not applied")

    # A broken contract is debt whether or not the ratchet has an entry for it.
    # Blocking is a separate policy question and the answer is no; reading
    # identically to a clean run is not.
    verdict, classification, exit_status = select_health_verdict(ratchet, graph, operational_reasons, failed_reasons)

    headline = health_headline(verdict, graph, checker, ratchet, operational_reasons, failed_reasons)
    payload = health_payload(
        ratchet,
        blocking_findings,
        load_failures,
        load_root_causes,
        operational_reasons,
        failed_reasons,
        verdict,
        classification,
        headline,
        advisory_findings,
        candidate,
        candidate_path,
        component_cpu_seconds,
        component_durations,
        checker,
        graph,
        supplemental_occurrences,
        source_snapshot_before,
        source_snapshot_after,
        loadability,
        load_returncode,
        step_budget,
    )
    return payload, exit_status


def _classify_checker_findings(checker: CheckResult) -> tuple[list[Finding], list[Finding], list[Finding]]:
    """Classify checker findings."""
    blocking_findings = [finding for finding in checker.findings if not finding.advisory and not finding.fatal]
    advisory_findings = [finding for finding in checker.findings if finding.advisory]
    fatal_findings = [finding for finding in checker.findings if finding.fatal]
    return blocking_findings, advisory_findings, fatal_findings


def _supplemental_occurrences(
    authority: Authority, candidate: CandidateInventory, graph: GraphSummary
) -> dict[str, int]:
    """Supplemental occurrences."""
    candidate_by_contract = candidate["summary"]["by_contract"]
    contract_status = graph["contract_status"]
    supplemental_occurrences = {
        contract.key: int(candidate_by_contract.get(contract.key, 0))
        for contract in authority.forbidden_contracts
        if int(candidate_by_contract.get(contract.key, 0)) and contract_status.get(contract.name) == "kept"
    }
    return supplemental_occurrences
