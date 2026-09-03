from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.application.registry.source_connectivity import (
    RegistryDestinationCandidate,
    load_source_connectivity_census,
    validate_census_destination_candidates,
)
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.source_connectivity import SourceConnectivityGroundingLocatorKind
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.censo_modelos import CensoModeloEventKind
from cadrumo.domain.calculations.registry.loader import load_modelo_directory
from cadrumo.domain.calculations.registry.temporal import select_revision

from ..check import SourceConnectivityCheckError, check_capability_locators
from ..discovery import (
    assign_capabilities_to_census,
    discover_source_ownership,
    discovered_source_capability_evidence,
    discovered_source_capability_ids,
    validate_census_completeness,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_every_live_capability_has_exactly_one_frozen_census_assignment() -> None:
    discovered = discovered_source_capability_ids(REPO_ROOT)

    assignments = validate_census_completeness(REPO_ROOT)

    assigned = tuple(capability_id for row in assignments.values() for capability_id in row)
    assignment_counts = Counter(assigned)
    assert discovered
    assert set(assignment_counts) == set(discovered)
    assert all(count == 1 for count in assignment_counts.values())


@pytest.mark.parametrize(
    "new_capability",
    (
        "calculation_helper:src/cadrumo/domain/probe.py:calculate_probe",
        "ingress:src/cadrumo/entrypoints/cli/_unclassified_source_probe.py:record_source_probe",
    ),
)
def test_new_capability_refuses_selector_digest_drift(new_capability: str) -> None:
    manifest = load_source_connectivity_census()
    discovered = discovered_source_capability_ids(REPO_ROOT)

    with pytest.raises(ValueError, match="capability coverage drift"):
        assign_capabilities_to_census((*discovered, new_capability), manifest)


def test_registry_destination_candidates_have_one_census_owner() -> None:
    manifest = load_source_connectivity_census()
    destination_ids = tuple(
        destination.identity for entry in manifest.entries for destination in entry.registry_destination_candidates
    )

    assert destination_ids
    assert len(destination_ids) == len(set(destination_ids))


def test_inventory_census_tracks_only_the_live_connection_gap() -> None:
    manifest = load_source_connectivity_census()
    inventory = next(entry for entry in manifest.entries if entry.candidate_id == "inventory.stock-valuation")

    assert inventory.disposition.value == "connect_candidate"
    assert inventory.expires_on == date(2026, 12, 31)
    assert "canonical InventorySourceResolver enrollment" in inventory.review_condition
    assert "supported inventory ingress" in inventory.review_condition
    assert "Registry bindings" in inventory.review_condition
    assert "connection candidate" in inventory.review_condition
    assert "grounded repeated activity-row values" in inventory.review_condition
    assert "rendered through the supported official filing structure" in inventory.review_condition
    assert "verified end to end" in inventory.review_condition
    assert "fabricated activity-envelope facts" in inventory.review_condition
    assert "registry-blocked" not in inventory.review_condition
    assert "complete acquisition cost" not in inventory.review_condition
    assert "explicit-closing authority remain blocking" not in inventory.review_condition
    summaries = " ".join(item.summary for item in inventory.grounding)
    assert "schema-v3" in summaries
    assert "0181" in summaries
    assert "resolve_inventory_authoritative_closing" in summaries
    assert "compute_inventory_anexo_d_projection" in summaries
    assert inventory.review_condition.endswith(
        "Promote this connection candidate only after grounded repeated activity-row values are rendered through the "
        "supported official filing structure and the resulting filing is verified end to end without fabricated "
        "activity-envelope facts."
    )


def test_asset_amortization_census_retains_the_unimplemented_ingress_boundary() -> None:
    manifest = load_source_connectivity_census()
    amortization = next(entry for entry in manifest.entries if entry.candidate_id == "assets.amortization-ledger")

    assert amortization.disposition.value == "ingress_blocked"
    assert amortization.expires_on == date(2026, 12, 31)
    assert amortization.bounded_follow_up is not None
    assert amortization.bounded_follow_up.action_id == "source-casilla.assets-amortization-ingress"
    assert "exclusive future source" in amortization.review_condition
    assert "casillas 0208 and 0227" in amortization.review_condition
    assert "finca casilla 0131 separate" in amortization.review_condition
    assert "current encrypted scalar ledger remains ingress-blocked" in amortization.review_condition


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


def test_modelo_036_profile_ownership_uses_the_canonical_route_locator() -> None:
    """The human-filed M036 row may name the profile resolver but owns it through the route."""
    manifest = load_source_connectivity_census()
    entry = next(item for item in manifest.entries if item.candidate_id == "censo.modelo-036-profile-status")
    focused_manifest = manifest.model_copy(update={"entries": (entry,)})
    evidence = discovered_source_capability_evidence(REPO_ROOT)
    canonical_route = "src/cadrumo/application/modelo/calculation_route.py"

    assert canonical_route in entry.capability_locators
    check_capability_locators(REPO_ROOT, focused_manifest, capability_evidence=evidence)

    stale = entry.model_copy(
        update={"capability_locators": tuple(item for item in entry.capability_locators if item != canonical_route)}
    )
    with pytest.raises(SourceConnectivityCheckError, match="census capability locator drift"):
        check_capability_locators(
            REPO_ROOT,
            focused_manifest.model_copy(update={"entries": (stale,)}),
            capability_evidence=evidence,
        )


def test_inventory_repository_ownership_uses_its_live_discovery_locator() -> None:
    """Inventory's source candidate must retain the canonical encrypted-repository pointer."""
    manifest = load_source_connectivity_census()
    entry = next(item for item in manifest.entries if item.candidate_id == "inventory.stock-valuation")
    focused_manifest = manifest.model_copy(update={"entries": (entry,)})
    evidence = discovered_source_capability_evidence(REPO_ROOT)
    repository_locator = "src/cadrumo/adapters/persistence/profile/inventory.py:119"
    closing_locator = "src/cadrumo/domain/contribuyente/inventory/records.py:1150"
    projection_locator = "src/cadrumo/domain/contribuyente/inventory/valuation.py:192"
    create_locator = "src/cadrumo/entrypoints/cli/_app_ledger_inventory_command_specs.py:28"
    movement_locator = "src/cadrumo/entrypoints/cli/_app_ledger_inventory_analysis_command_specs.py:26"

    assert repository_locator in entry.capability_locators
    assert closing_locator in entry.capability_locators
    assert projection_locator in entry.capability_locators
    assert create_locator in entry.capability_locators
    assert movement_locator in entry.capability_locators
    check_capability_locators(REPO_ROOT, focused_manifest, capability_evidence=evidence)

    stale_locators = {
        repository_locator,
        closing_locator,
        projection_locator,
        create_locator,
        movement_locator,
    }
    stale = entry.model_copy(
        update={"capability_locators": tuple(item for item in entry.capability_locators if item not in stale_locators)}
    )
    with pytest.raises(SourceConnectivityCheckError, match="census capability locator drift"):
        check_capability_locators(
            REPO_ROOT,
            focused_manifest.model_copy(update={"entries": (stale,)}),
            capability_evidence=evidence,
        )


def test_new_calculation_helpers_preserve_their_reviewed_inventory_or_non_source_ownership() -> None:
    """Keep new helper discovery from silently changing source-census ownership."""
    manifest = load_source_connectivity_census()
    discovered = discovered_source_capability_ids(REPO_ROOT)
    assignments = assign_capabilities_to_census(discovered, manifest)
    inventory = next(item for item in manifest.entries if item.candidate_id == "inventory.stock-valuation")
    inventory_closing = (
        "calculation_helper:src/cadrumo/domain/contribuyente/inventory/records.py:"
        "resolve_inventory_authoritative_closing"
    )
    inventory_projection = (
        "calculation_helper:src/cadrumo/domain/contribuyente/inventory/valuation.py:"
        "compute_inventory_anexo_d_projection"
    )
    registry_helpers = {
        "calculation_helper:src/cadrumo/domain/calculations/registry/deadline_coordinate.py:"
        "deadline_semantic_coordinate",
        "calculation_helper:src/cadrumo/domain/calculations/registry/deadline_coordinate.py:"
        "deadline_window_semantic_coordinates",
        "calculation_helper:src/cadrumo/domain/calculations/registry/relations.py:source_presence_gaps",
    }

    assert inventory_closing in inventory.capability_ids
    assert inventory_closing not in assignments["coverage.remaining-calculation-helpers"]
    assert inventory_projection in inventory.capability_ids
    assert inventory_projection not in assignments["coverage.remaining-calculation-helpers"]
    assert registry_helpers <= set(assignments["coverage.remaining-calculation-helpers"])

    manual_m036_ingress = {
        "ingress:src/cadrumo/entrypoints/cli/_modelo_m036_cli.py:m036_alta",
        "ingress:src/cadrumo/entrypoints/cli/_modelo_m036_cli.py:m036_modificacion",
        "ingress:src/cadrumo/entrypoints/cli/_modelo_m036_cli.py:m036_baja",
    }
    assert manual_m036_ingress <= set(assignments["coverage.remaining-ingress-surfaces"])

    unowned_inventory = inventory.model_copy(
        update={"capability_ids": tuple(item for item in inventory.capability_ids if item != inventory_closing)}
    )
    mutated = manifest.model_copy(
        update={"entries": tuple(unowned_inventory if item is inventory else item for item in manifest.entries)}
    )

    with pytest.raises(ValueError, match="capability coverage drift"):
        assign_capabilities_to_census(discovered, mutated)


def test_reviewed_helpers_have_no_new_connectivity_candidate_or_connected_outcome() -> None:
    """The reviewed helper handoff closes without manufacturing a source claim."""
    manifest = load_source_connectivity_census()
    assignments = assign_capabilities_to_census(discovered_source_capability_ids(REPO_ROOT), manifest)
    helper_ids = {
        "calculation_helper:src/cadrumo/domain/calculations/registry/temporal.py:revision_selection_coordinates",
        "calculation_helper:src/cadrumo/domain/portals/errors.py:portal_integrity_error",
    }
    census_claims = {
        capability_id
        for entry in manifest.entries
        for capability_id in entry.capability_ids
        if capability_id in helper_ids
    }

    assert helper_ids <= set(assignments["coverage.remaining-calculation-helpers"])
    assert census_claims == set()


def test_profile_repeatable_row_ingress_stays_in_structural_coverage() -> None:
    """A profile write surface is not a new source owner or connection claim."""
    manifest = load_source_connectivity_census()
    assignments = assign_capabilities_to_census(discovered_source_capability_ids(REPO_ROOT), manifest)
    capability_id = "ingress:src/cadrumo/entrypoints/cli/config/_profile_repeatable_row.py:profile_add_row"

    assert capability_id in assignments["coverage.remaining-ingress-surfaces"]
    assert all(capability_id not in entry.capability_ids for entry in manifest.entries)


def test_s115_freezes_reviewed_s112_helper_set_by_secondary_count() -> None:
    """Count is a secondary selector guard; the digest remains its canonical identity proof."""
    manifest = load_source_connectivity_census()
    entry = next(item for item in manifest.entries if item.candidate_id == "coverage.remaining-calculation-helpers")
    discovered = discovered_source_capability_ids(REPO_ROOT)

    assignments = assign_capabilities_to_census(discovered, manifest)

    assert entry.expected_capability_count == 267
    assert len(assignments[entry.candidate_id]) == entry.expected_capability_count

    stale_count = entry.model_copy(update={"expected_capability_count": 266})
    stale_manifest = manifest.model_copy(
        update={"entries": tuple(stale_count if item is entry else item for item in manifest.entries)}
    )
    with pytest.raises(ValueError, match="capability coverage count drift"):
        assign_capabilities_to_census(discovered, stale_manifest)


def test_registry_destination_candidates_resolve_against_live_authority() -> None:
    manifest = load_source_connectivity_census()

    validate_census_destination_candidates(manifest, bundled_authority())


def test_manual_source_reference_grounding_must_resolve_from_catalogue_and_selected_revision() -> None:
    """Terminal M036 evidence cannot carry an invented or another revision's source."""
    manifest = load_source_connectivity_census()
    authority = bundled_authority()
    entry = next(item for item in manifest.entries if item.candidate_id == "censo.modelo-036-profile-status")
    grounding = next(
        item for item in entry.grounding if item.locator_kind is SourceConnectivityGroundingLocatorKind.SOURCE_REFERENCE
    )

    invented = grounding.model_copy(update={"reference": "invented-source-reference"})
    invented_entry = entry.model_copy(
        update={"grounding": tuple(invented if item is grounding else item for item in entry.grounding)}
    )
    invented_manifest = manifest.model_copy(
        update={"entries": tuple(invented_entry if item is entry else item for item in manifest.entries)}
    )
    with pytest.raises(ValueError, match="absent from the validated source catalogue"):
        validate_census_destination_candidates(invented_manifest, authority)

    selected_revision = authority.modelo(Modelo.M036).revisions["2025-02-03-y-siguientes"]
    outside_scope_reference = next(
        source_ref for source_ref in authority.catalogues.sources if source_ref not in selected_revision.source_refs
    )
    outside_scope = grounding.model_copy(update={"reference": outside_scope_reference})
    outside_scope_entry = entry.model_copy(
        update={"grounding": tuple(outside_scope if item is grounding else item for item in entry.grounding)}
    )
    outside_scope_manifest = manifest.model_copy(
        update={"entries": tuple(outside_scope_entry if item is entry else item for item in manifest.entries)}
    )
    with pytest.raises(ValueError, match="outside its exact selected revision source scope"):
        validate_census_destination_candidates(outside_scope_manifest, authority)


def test_censo_event_coordinate_refuses_modelo_100_alta() -> None:
    """The existing censo event enum is not a generic registry period vocabulary."""
    with pytest.raises(ValidationError, match="reserved for canonical Modelo 036"):
        RegistryDestinationCandidate(
            kind="binding_source",
            modelo_id=Modelo.M100,
            revision_id="2025",
            filing_year=2025,
            period=CensoModeloEventKind.ALTA,
            source_kind=BindingSourceKind.PROFILE,
        )


def test_absent_registry_destination_candidate_is_rejected() -> None:
    manifest = load_source_connectivity_census()
    first = next(entry for entry in manifest.entries if entry.candidate_id == "inventory.stock-valuation")
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
    changed = manifest.model_copy(
        update={"entries": tuple(mutated if entry is first else entry for entry in manifest.entries)}
    )

    with pytest.raises(ValueError, match="semantic role is absent"):
        validate_census_destination_candidates(changed, bundled_authority())


def test_ambiguous_registry_destination_candidate_is_rejected() -> None:
    manifest = load_source_connectivity_census()
    first = next(entry for entry in manifest.entries if entry.candidate_id == "inventory.stock-valuation")
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
    changed = manifest.model_copy(
        update={"entries": tuple(mutated if entry is first else entry for entry in manifest.entries)}
    )

    with pytest.raises(ValueError, match="semantic role is ambiguous"):
        validate_census_destination_candidates(changed, bundled_authority())


def test_registry_destination_revision_must_match_its_law_selected_coordinate() -> None:
    manifest = load_source_connectivity_census()
    first = manifest.entries[0]
    candidate = first.registry_destination_candidates[0]
    mismatched = candidate.model_copy(update={"revision_id": "2024"})
    changed_entry = first.model_copy(update={"registry_destination_candidates": (mismatched,)})
    changed = manifest.model_copy(update={"entries": (changed_entry, *manifest.entries[1:])})

    with pytest.raises(ValueError, match="revision does not match its law-selected filing coordinate"):
        validate_census_destination_candidates(changed, bundled_authority())


def test_registry_destination_period_must_be_law_selectable() -> None:
    manifest = load_source_connectivity_census()
    first = manifest.entries[0]
    candidate = first.registry_destination_candidates[0]
    mismatched = candidate.model_copy(update={"period": Period.from_year_and_code(2025, "1T")})
    changed_entry = first.model_copy(update={"registry_destination_candidates": (mismatched,)})
    changed = manifest.model_copy(update={"entries": (changed_entry, *manifest.entries[1:])})

    with pytest.raises(ValueError, match="filing coordinate is not law-selectable"):
        validate_census_destination_candidates(changed, bundled_authority())
