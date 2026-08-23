from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.application.registry.source_connectivity import (
    RegistryDestinationCandidate,
    load_source_connectivity_census,
    validate_census_destination_candidates,
)
from cadrumo.core.resources import resources

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
    assert len(discovered) == 448
    assert len(assigned) == len(set(assigned))
    assert set(assigned) == set(discovered)


def test_new_capability_refuses_selector_digest_drift() -> None:
    manifest = load_source_connectivity_census()
    discovered = discovered_source_capability_ids(REPO_ROOT)
    new_capability = "calculation_helper:src/cadrumo/domain/probe.py:calculate_probe"

    with pytest.raises(ValueError, match="capability coverage drift"):
        assign_capabilities_to_census((*discovered, new_capability), manifest)


def test_registry_destination_candidates_have_one_census_owner() -> None:
    manifest = load_source_connectivity_census()
    destination_ids = tuple(
        destination.identity
        for entry in manifest.entries
        for destination in entry.registry_destination_candidates
    )

    assert destination_ids
    assert len(destination_ids) == len(set(destination_ids))


def test_registry_destination_candidates_resolve_against_live_authority() -> None:
    manifest = load_source_connectivity_census()

    validate_census_destination_candidates(manifest, resources().modelos.authority.modelos)


def test_absent_registry_destination_candidate_is_rejected() -> None:
    manifest = load_source_connectivity_census()
    first = manifest.entries[0]
    phantom = RegistryDestinationCandidate(
        kind="casilla_semantic_role",
        modelo_id="100",
        semantic_role="phantom_inventory_destination",
    )
    mutated = first.model_copy(
        update={"registry_destination_candidates": (*first.registry_destination_candidates, phantom)}
    )
    changed = manifest.model_copy(update={"entries": (mutated, *manifest.entries[1:])})

    with pytest.raises(ValueError, match="semantic role is absent"):
        validate_census_destination_candidates(changed, resources().modelos.authority.modelos)


def test_ambiguous_registry_destination_candidate_is_rejected() -> None:
    manifest = load_source_connectivity_census()
    first = manifest.entries[0]
    ambiguous = RegistryDestinationCandidate(
        kind="casilla_semantic_role",
        modelo_id="100",
        semantic_role="irpf_inmueble_base_amortizacion",
    )
    mutated = first.model_copy(
        update={"registry_destination_candidates": (*first.registry_destination_candidates, ambiguous)}
    )
    changed = manifest.model_copy(update={"entries": (mutated, *manifest.entries[1:])})

    with pytest.raises(ValueError, match="semantic role is ambiguous"):
        validate_census_destination_candidates(changed, resources().modelos.authority.modelos)
