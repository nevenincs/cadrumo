"""Ordered import health refusals and verdict selection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from .import_check_models import CheckResult, Finding
from .import_health_models import CandidateInventory, GraphSummary, RatchetReport
from .import_loadability_projection import loadability_int


def operational_health_reasons(
    authority_findings: tuple[str, ...],
    linter_returncode: int,
    load_returncode: int,
    loadability: dict[str, object],
    checker: CheckResult,
    graph: GraphSummary,
    source_snapshot_before: str,
    source_snapshot_after: str,
) -> list[str]:
    """Operational health reasons."""
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
    return operational_reasons


def failed_health_reasons(
    blocking_findings: list[Finding],
    loadability: dict[str, object],
    ratchet: RatchetReport,
    graph: GraphSummary,
    candidate: CandidateInventory,
) -> tuple[list[str], int, int]:
    """Failed health reasons."""
    failed_reasons: list[str] = []
    if blocking_findings:
        failed_reasons.append(f"{len(blocking_findings)} hard import-authority finding(s)")
    load_failures = loadability_int(loadability, "failed")
    load_root_causes = loadability_int(loadability, "root_cause_count", load_failures)
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
        count = cast("Mapping[str, int]", ratchet["counts"])[key]
        if count:
            failed_reasons.append(f"{count} {label}")
    if graph["contracts_broken"] and not candidate["summary"]["contract_occurrences"]:
        failed_reasons.append("broken graph contracts have no attributable direct occurrence")
    return failed_reasons, load_failures, load_root_causes


def select_health_verdict(
    ratchet: RatchetReport, graph: GraphSummary, operational_reasons: list[str], failed_reasons: list[str]
) -> tuple[str, str, int]:
    """Select health verdict."""
    debt_total = (
        ratchet["counts"]["approved_active"] + ratchet["counts"]["retirement_ready"] + graph["contracts_broken"]
    )
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
    return verdict, classification, exit_status
