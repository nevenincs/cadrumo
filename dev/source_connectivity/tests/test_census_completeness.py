from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.application.registry.source_connectivity import (
    RegistryDestinationCandidate,
    load_source_connectivity_census,
    validate_census_destination_candidates,
)
from cadrumo.core import Period
from cadrumo.core.resources import bundled_path, resources
from cadrumo.domain.calculations.registry import CensoModeloEventKind
from cadrumo.domain.calculations.registry._loader import load_modelo_directory
from cadrumo.domain.calculations.registry._temporal import select_revision

from ..discovery import (
    assign_capabilities_to_census,
    discover_source_ownership,
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


def test_inventory_census_tracks_only_the_live_connection_gap() -> None:
    manifest = load_source_connectivity_census()
    inventory = next(entry for entry in manifest.entries if entry.candidate_id == "inventory.stock-valuation")

    assert inventory.disposition.value == "connect_candidate"
    assert "prerequisites are complete" in inventory.review_condition
    assert "S39" in inventory.review_condition
    assert "complete acquisition cost" not in inventory.review_condition
    assert "explicit-closing authority remain blocking" not in inventory.review_condition
    summaries = " ".join(item.summary for item in inventory.grounding)
    assert "schema-v3" in summaries
    assert "0181" in summaries
    assert "missing resolver" in summaries


def test_modelo_036_manual_profile_evidence_uses_its_exact_event_coordinate() -> None:
    """Keep M036's human-filed censo event out of ordinary filing-period tokens."""
    manifest = load_source_connectivity_census()
    entry = next(item for item in manifest.entries if item.candidate_id == "censo.modelo-036-profile-status")
    destinations = entry.registry_destination_candidates

    assert entry.disposition.value == "manual_by_design"
    assert entry.capability_ids == ("source_ownership:profile",)
    assert "must not submit an M036 artifact" in entry.review_condition
    assert {candidate.kind for candidate in destinations} == {"binding_source", "casilla_semantic_role"}
    assert {candidate.period for candidate in destinations} == {CensoModeloEventKind.ALTA}
    assert {candidate.period_token for candidate in destinations} == {"alta"}

    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "036"))
    revision = select_revision(modelo, filing_year=2025, period=destinations[0].period_token)

    assert revision.id == "2025-02-03-y-siguientes"
    assert any(binding.source.value == "profile" for binding in revision.bindings)
    assert any(casilla.semantic_role == "tipo_evento_censal" for casilla in revision.casillas)


def test_modelo_036_manual_profile_evidence_refuses_ad_hoc_period_substitution() -> None:
    """An M036 event decision cannot be broadened into a generic ad-hoc period."""
    manifest = load_source_connectivity_census()
    entry = next(item for item in manifest.entries if item.candidate_id == "censo.modelo-036-profile-status")
    destination = entry.registry_destination_candidates[0]
    mutated = destination.model_copy(update={"period": Period.from_year_and_code(2025, "AD-HOC")})
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "036"))

    with pytest.raises(ValueError, match="no revision"):
        select_revision(modelo, filing_year=2025, period=mutated.period_token)


def test_modelo_036_profile_ownership_has_one_census_assignment_and_bites_on_remainder_drift() -> None:
    """The manual M036 disposition owns profile without bypassing census completeness."""
    manifest = load_source_connectivity_census()
    entry = next(item for item in manifest.entries if item.candidate_id == "censo.modelo-036-profile-status")
    ownership_entries = tuple(
        item
        for item in manifest.entries
        if item.capability_selector == "remaining_source_ownership"
        or (
            item.capability_ids
            and all(capability_id.startswith("source_ownership:") for capability_id in item.capability_ids)
        )
    )
    ownership_manifest = manifest.model_copy(update={"entries": ownership_entries})
    discovered = tuple(item.capability_id for item in discover_source_ownership())

    assignments = assign_capabilities_to_census(discovered, ownership_manifest)

    assert assignments[entry.candidate_id] == ("source_ownership:profile",)
    assert "source_ownership:profile" not in assignments["coverage.remaining-source-ownership"]

    misplaced = entry.model_copy(update={"capability_ids": ("source_ownership:manual_input",)})
    mutated = ownership_manifest.model_copy(
        update={"entries": tuple(misplaced if item == entry else item for item in ownership_entries)}
    )
    with pytest.raises(ValueError, match="capability coverage drift"):
        assign_capabilities_to_census(discovered, mutated)


def test_registry_destination_candidates_resolve_against_live_authority() -> None:
    manifest = load_source_connectivity_census()

    validate_census_destination_candidates(manifest, resources().modelos.authority)


def test_absent_registry_destination_candidate_is_rejected() -> None:
    manifest = load_source_connectivity_census()
    first = manifest.entries[0]
    phantom = RegistryDestinationCandidate(
        kind="casilla_semantic_role",
        modelo_id="100",
        revision_id="2025",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        semantic_role="phantom_inventory_destination",
    )
    mutated = first.model_copy(
        update={"registry_destination_candidates": (*first.registry_destination_candidates, phantom)}
    )
    changed = manifest.model_copy(update={"entries": (mutated, *manifest.entries[1:])})

    with pytest.raises(ValueError, match="semantic role is absent"):
        validate_census_destination_candidates(changed, resources().modelos.authority)


def test_ambiguous_registry_destination_candidate_is_rejected() -> None:
    manifest = load_source_connectivity_census()
    first = manifest.entries[0]
    ambiguous = RegistryDestinationCandidate(
        kind="casilla_semantic_role",
        modelo_id="100",
        revision_id="2025",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        semantic_role="irpf_inmueble_base_amortizacion",
    )
    mutated = first.model_copy(
        update={"registry_destination_candidates": (*first.registry_destination_candidates, ambiguous)}
    )
    changed = manifest.model_copy(update={"entries": (mutated, *manifest.entries[1:])})

    with pytest.raises(ValueError, match="semantic role is ambiguous"):
        validate_census_destination_candidates(changed, resources().modelos.authority)


def test_registry_destination_revision_must_match_its_law_selected_coordinate() -> None:
    manifest = load_source_connectivity_census()
    first = manifest.entries[0]
    candidate = first.registry_destination_candidates[0]
    mismatched = candidate.model_copy(update={"revision_id": "2024"})
    changed_entry = first.model_copy(update={"registry_destination_candidates": (mismatched,)})
    changed = manifest.model_copy(update={"entries": (changed_entry, *manifest.entries[1:])})

    with pytest.raises(ValueError, match="revision does not match its law-selected filing coordinate"):
        validate_census_destination_candidates(changed, resources().modelos.authority)


def test_registry_destination_period_must_be_law_selectable() -> None:
    manifest = load_source_connectivity_census()
    first = manifest.entries[0]
    candidate = first.registry_destination_candidates[0]
    mismatched = candidate.model_copy(update={"period": Period.from_year_and_code(2025, "1T")})
    changed_entry = first.model_copy(update={"registry_destination_candidates": (mismatched,)})
    changed = manifest.model_copy(update={"entries": (changed_entry, *manifest.entries[1:])})

    with pytest.raises(ValueError, match="filing coordinate is not law-selectable"):
        validate_census_destination_candidates(changed, resources().modelos.authority)
