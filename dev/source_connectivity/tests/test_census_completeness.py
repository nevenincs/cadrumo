from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.application.registry.source_connectivity import load_source_connectivity_census

from ..discovery import (
    assign_capabilities_to_census,
    discovered_source_capability_ids,
    validate_census_completeness,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_every_live_capability_has_exactly_one_frozen_census_assignment() -> None:
    discovered = discovered_source_capability_ids(REPO_ROOT)

    assignments = validate_census_completeness(REPO_ROOT)

    assigned = tuple(capability_id for row in assignments.values() for capability_id in row)
    assert len(discovered) == 428
    assert len(assigned) == len(set(assigned))
    assert set(assigned) == set(discovered)


def test_new_capability_refuses_selector_digest_drift() -> None:
    manifest = load_source_connectivity_census()
    discovered = discovered_source_capability_ids(REPO_ROOT)
    new_capability = "calculation_helper:src/cadrumo/domain/probe.py:calculate_probe"

    with pytest.raises(ValueError, match="capability coverage drift"):
        assign_capabilities_to_census((*discovered, new_capability), manifest)


def test_advisory_destination_candidates_have_one_census_owner() -> None:
    manifest = load_source_connectivity_census()
    destination_refs = tuple(
        destination_ref
        for entry in manifest.entries
        for destination_ref in entry.advisory_destination_refs
    )

    assert destination_refs
    assert len(destination_refs) == len(set(destination_refs))
