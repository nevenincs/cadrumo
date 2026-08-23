"""Operator-readable projections for source-connectivity maintenance."""

from __future__ import annotations

import pytest

from cadrumo.application.registry.source_connectivity import load_source_connectivity_census

from ..check import SourceConnectivityCheckResult
from ..cli import project_census_memberships

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_membership_projection_retains_per_capability_decision_evidence() -> None:
    manifest = load_source_connectivity_census()
    entry = manifest.entries[0]
    capability_id = entry.capability_ids[0]
    result = SourceConnectivityCheckResult(
        capability_count=1,
        census_entry_count=len(manifest.entries),
        assignment_count=1,
        assignments=((entry.candidate_id, (capability_id,)),),
        manifest=manifest,
    )

    assert project_census_memberships(result) == (
        {
            "capability_id": capability_id,
            "candidate_id": entry.candidate_id,
            "disposition": entry.disposition.value,
            "decision_reason": entry.review_condition,
            "grounding_refs": tuple(item.reference for item in entry.grounding),
        },
    )
