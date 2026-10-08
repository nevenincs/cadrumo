"""Coverage and finding accounting checks for registry collapse verification."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from cadrumo.domain.calculations.registry.keyed_families import CANONICAL_FAMILY_SPECS
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
)
from dev.registry.edition_delta_assessment import MigrationAssessment

from .registry_collapse_models import _EXPECTED_ASSESSMENT_FAMILIES, FindingTransition


def finding_identities(assessment: MigrationAssessment) -> frozenset[str]:
    """Identify findings by content, so equal counts cannot hide defect replacement."""
    return frozenset(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for item in (*assessment.unresolved_duplication, *assessment.blocked_work)
    )


def finding_transition(before: MigrationAssessment, after: MigrationAssessment) -> FindingTransition:
    """Report exact finding identities added and removed between assessments."""
    old, new = finding_identities(before), finding_identities(after)
    return {"removed": sorted(old - new), "added": sorted(new - old), "unchanged": len(old & new)}


def assessor_scope_gaps() -> tuple[Mapping[str, object], ...]:
    """Independently reconcile the assessor's family policy with the typed schema."""
    enrolled = {spec.section for spec in CANONICAL_FAMILY_SPECS}
    missing = sorted(_EXPECTED_ASSESSMENT_FAMILIES - enrolled)
    unknown = sorted(enrolled - _EXPECTED_ASSESSMENT_FAMILIES)
    return tuple(
        {"revision": "*", "family": family, "reason": "assessor_family_not_enrolled"} for family in missing
    ) + tuple({"revision": "*", "family": family, "reason": "assessor_family_not_in_schema"} for family in unknown)


def assessment_coverage_gaps(
    assessment: MigrationAssessment,
    modelo: ModeloDefinition,
    *,
    stage: str,
) -> tuple[Mapping[str, object], ...]:
    """Prove every revision has one row for every family and its scalar bucket."""
    expected_families = (*sorted(_EXPECTED_ASSESSMENT_FAMILIES), "$scalars")
    expected = {(str(revision_id), family) for revision_id in modelo.revisions for family in expected_families}
    actual = {(str(row.get("revision")), str(row.get("family"))) for row in assessment.by_revision_family}
    return tuple(
        {
            "stage": stage,
            "revision": revision,
            "family": family,
            "reason": "assessment_row_missing",
        }
        for revision, family in sorted(expected - actual)
    ) + tuple(
        {
            "stage": stage,
            "revision": revision,
            "family": family,
            "reason": "unexpected_assessment_row",
        }
        for revision, family in sorted(actual - expected)
    )


def _assessment_accounting(results: Sequence[Mapping[str, object]], key: str) -> Mapping[str, int]:
    totals = _empty_accounting()
    for result in results:
        assessment = result.get(key)
        if not isinstance(assessment, Mapping):
            continue
        _account_assessment_payload(assessment, totals)
        _account_assessment_findings(assessment, totals)
        _account_assessment_gaps(assessment, totals)
        _account_assessor_gaps(result, totals)
    return totals


def _empty_accounting() -> dict[str, int]:
    return {
        "authored_payload_fields": 0,
        "inherited_payload_fields": 0,
        "genuine_overrides": 0,
        "redundant_overrides": 0,
        "additions": 0,
        "removals": 0,
        "structural_overhead": 0,
        "findings": 0,
        "repeated_values": 0,
        "coverage_gaps": 0,
    }


def _account_assessment_payload(assessment: Mapping[str, object], totals: dict[str, int]) -> None:
    for name in tuple(totals)[:7]:
        value = assessment.get(name)
        if isinstance(value, int):
            totals[name] += value


def _account_assessment_findings(assessment: Mapping[str, object], totals: dict[str, int]) -> None:
    findings = assessment.get("unresolved_duplication")
    if not isinstance(findings, list | tuple):
        return
    totals["findings"] += len(findings)
    totals["repeated_values"] += sum(
        len(fields)
        for item in findings
        if isinstance(item, Mapping) and isinstance((fields := item.get("fields")), list | tuple)
    )


def _account_assessment_gaps(assessment: Mapping[str, object], totals: dict[str, int]) -> None:
    gaps = assessment.get("blocked_work")
    if isinstance(gaps, list | tuple):
        totals["coverage_gaps"] += len(gaps)


def _account_assessor_gaps(result: Mapping[str, object], totals: dict[str, int]) -> None:
    assessor_gaps = result.get("assessor_scope_gaps")
    if isinstance(assessor_gaps, list | tuple):
        totals["coverage_gaps"] += len(assessor_gaps)
