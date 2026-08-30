from datetime import date
from pathlib import Path

import pytest

from cadrumo.application.aggregation import collect_unhandled_source_diagnostics
from cadrumo.application.modelo.calculation_route import (
    CALCULATION_ROUTE_RESOLVER_OWNERSHIP,
    CALCULATION_ROUTE_SOURCE_DISPOSITIONS,
)
from cadrumo.application.registry.source_connectivity import load_source_connectivity_census
from cadrumo.application.registry.source_connectivity_coverage import compose_source_connectivity_coverage
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..check import SourceConnectivityCheckError, check_capability_locators, check_census_governance
from ..discovery import discovered_source_capability_evidence
from ..live_proof import CONNECTED_PROOF_FIXTURES, connected_candidate_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_m232_remains_measurably_ingress_blocked_until_its_missing_authority_exists() -> None:
    entry = next(
        item
        for item in load_source_connectivity_census().entries
        if item.candidate_id == "rows.related-party-operation"
    )
    assert entry.disposition.value == "ingress_blocked"
    assert entry.bounded_follow_up is not None
    assert entry.bounded_follow_up.action_id == "source-casilla.rows-related-party-owner"
    assert entry.bounded_follow_up.owner == "source-connectivity-campaign"
    assert entry.expires_on is not None
    assert "direction" in entry.review_condition
    assert "relationship type" in entry.review_condition
    assert "secure worksheet/source owner" in entry.review_condition
    assert "S94 proves the real encrypted revision route" in entry.review_condition
    assert "direction, relationship type, stable identity, and secure ingress" in (
        entry.bounded_follow_up.completion_criterion
    )


def test_m232_related_party_dispatch_locator_bites_on_the_pre_dispatch_line() -> None:
    """The census must name the related-party dispatch, not a neighboring branch."""
    entry = next(
        item
        for item in load_source_connectivity_census().entries
        if item.candidate_id == "rows.related-party-operation"
    )
    focused = load_source_connectivity_census().model_copy(update={"entries": (entry,)})
    evidence = discovered_source_capability_evidence(REPO_ROOT)
    canonical = "src/cadrumo/application/calculations/row_set_assembly.py:170"

    assert canonical in entry.capability_locators
    assert any(item.reference == canonical for item in entry.grounding)
    check_capability_locators(REPO_ROOT, focused, capability_evidence=evidence)

    stale = entry.model_copy(
        update={"capability_locators": ("src/cadrumo/application/calculations/row_set_assembly.py:168",)},
    )
    with pytest.raises(SourceConnectivityCheckError, match="census capability locator drift"):
        check_capability_locators(
            REPO_ROOT,
            focused.model_copy(update={"entries": (stale,)}),
            capability_evidence=evidence,
        )


def test_m232_deferred_source_has_no_connected_downstream_lifecycle() -> None:
    """M232 row assembly stays blocked before any persistent source claim can form.

    The positional ``Modelo232VinculadaRow`` form-entry path is intentionally
    outside this test: it is not the unowned ``related_party_operation`` source
    family. This test proves the latter has no calculation resolver, encrypted
    connected-proof fixture, review clearance, or repeated-record projection.
    """
    source_kind = BindingSourceKind.RELATED_PARTY_OPERATION
    candidate_id = "rows.related-party-operation"
    census = load_source_connectivity_census()
    entry = next(item for item in census.entries if item.candidate_id == candidate_id)
    snapshot = bundled_authority().snapshot("232", filing_year=2025, period="0A")

    assert any(binding.source is source_kind for binding in snapshot.revision.bindings)
    assert CALCULATION_ROUTE_SOURCE_DISPOSITIONS[source_kind].value == "deferred"
    assert all(source_kind not in owner.owned_sources for owner in CALCULATION_ROUTE_RESOLVER_OWNERSHIP)

    handled_sources = frozenset(
        kind.value
        for kind, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition.value == "enrolled"
    )
    diagnostics = collect_unhandled_source_diagnostics(snapshot.revision, handled_sources=handled_sources)
    assert any(
        diagnostic.source_kind == source_kind.value and diagnostic.reason == "unhandled_binding_source"
        for diagnostic in diagnostics
    )

    assert candidate_id not in connected_candidate_ids()
    assert all(fixture.candidate_id != candidate_id for fixture in CONNECTED_PROOF_FIXTURES)

    coverage = compose_source_connectivity_coverage(
        authority=bundled_authority(),
        census=census,
        as_of=date(2026, 8, 25),
    )
    limb = next(item for item in coverage.limbs if item.modelo == "232" and item.revision == "2018-y-siguientes")
    assert limb.outcome == "refused"
    assert limb.refusal is not None
    assert limb.refusal.disposition.work_item == "source-casilla.rows-related-party-owner"
    assert limb.refusal.disposition.reconsideration_condition == entry.review_condition

    assert all(
        record.repeat != "projection_rows"
        and all(field.kind is not CasillaFieldKind.PROJECTION for field in record.fields)
        for layout in snapshot.revision.export_layouts
        for record in layout.records
    )


def test_m232_terminal_deferral_is_rejected_after_its_expiry() -> None:
    """The bounded M232 deferral cannot remain current after 2026-12-31."""
    census = load_source_connectivity_census()
    entry = next(item for item in census.entries if item.candidate_id == "rows.related-party-operation")
    expired = entry.model_copy(update={"expires_on": date(2027, 1, 1)})
    expired_census = census.model_copy(
        update={"entries": tuple(expired if item is entry else item for item in census.entries)},
    )

    with pytest.raises(SourceConnectivityCheckError, match="expired without adjudication"):
        check_census_governance(expired_census, as_of=date(2027, 1, 1))
