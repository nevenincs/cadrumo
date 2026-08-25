from datetime import date
from pathlib import Path

import pytest

from cadrumo.application.aggregation import collect_unhandled_source_diagnostics
from cadrumo.application.modelo import CALCULATION_ROUTE_RESOLVER_OWNERSHIP, CALCULATION_ROUTE_SOURCE_DISPOSITIONS
from cadrumo.application.registry import compose_source_connectivity_coverage
from cadrumo.application.registry.source_connectivity import load_source_connectivity_census
from cadrumo.core import BindingSourceKind, RegistryAuthorityGrade
from cadrumo.core.resources import resources
from cadrumo.domain.calculations.registry import InputKind

from ..check import (
    SourceConnectivityCheckError,
    check_capability_locators,
    check_census_governance,
)
from ..discovery import discovered_source_capability_evidence
from ..live_proof import CONNECTED_PROOF_FIXTURES, connected_candidate_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_m182_remains_measurably_ingress_blocked_until_its_missing_authority_exists() -> None:
    reopening_predicate = (
        "Donor bindings and worksheet assembler are only a partial type-2 carrier, not distinct non-lossy type-1 "
        "declarant/header and type-2 donor-detail carriers. Reopen only when secure owner(s) retain both at native "
        "grain, with nature-3 administrator/holder identity, durable immutable identity/fingerprint, and lifecycle "
        "proof through diagnostics, provenance, encrypted revision persistence/replay, and review. Export stays "
        "negative until supported; then it needs positive non-lossy repeated-record proof."
    )
    entry = next(
        item for item in load_source_connectivity_census().entries if item.candidate_id == "rows.donativo-donor"
    )

    assert entry.disposition.value == "ingress_blocked"
    assert entry.owner == "source-connectivity-campaign"
    assert entry.review_condition == reopening_predicate
    assert entry.expires_on == date(2026, 12, 31)
    assert entry.bounded_follow_up is not None
    assert entry.bounded_follow_up.action_id == "source-casilla.rows-donativo-ingress"
    assert entry.bounded_follow_up.owner == "source-connectivity-campaign"
    assert entry.follow_up_owner() == "source-connectivity-campaign"
    assert entry.bounded_follow_up.deadline == date(2026, 11, 30)
    assert entry.bounded_follow_up.completion_criterion == (
        "Keep ingress_blocked until the review condition is satisfied: distinct non-lossy declarant/header and "
        "donor-detail carriers, secure owner(s), durable immutable identity/fingerprint, and lifecycle/export proof "
        "must all exist before resolver enrollment or any connected claim."
    )

    repo_root = Path.cwd()
    m182_census = load_source_connectivity_census().model_copy(update={"entries": (entry,)})
    capability_evidence = discovered_source_capability_evidence(repo_root)
    check_capability_locators(repo_root, m182_census, capability_evidence=capability_evidence)

    stale_entry = entry.model_copy(
        update={
            "capability_locators": (
                "src/cadrumo/application/calculations/_row_set_assembly.py:176",
            ),
        },
    )
    stale_census = m182_census.model_copy(update={"entries": (stale_entry,)})
    with pytest.raises(SourceConnectivityCheckError, match="capability locator drift"):
        check_capability_locators(repo_root, stale_census, capability_evidence=capability_evidence)


def test_m182_deferred_source_has_no_connected_downstream_lifecycle() -> None:
    """Refuse the partial donor carrier without suppressing direct manual casillas.

    A connected fixture is the only source-connectivity path that exercises
    encrypted revision persistence, primary provenance, replay, and review.
    The deferred donor family has neither that fixture nor a calculation-route
    owner. Its standing diagnostic and refused closure limb therefore remain
    visible, while the separately declared type-2 manual casillas retain their
    real direct-entry route.
    """
    source_kind = BindingSourceKind.DONATIVO_DONOR
    candidate_id = "rows.donativo-donor"
    census = load_source_connectivity_census()
    entry = next(item for item in census.entries if item.candidate_id == candidate_id)
    snapshot = resources().modelos.authority.snapshot(
        "182",
        filing_year=2025,
        period="0A",
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )

    assert snapshot.revision.authority_grade is RegistryAuthorityGrade.APPLICABILITY
    assert {str(casilla.id) for casilla in snapshot.revision.casillas if casilla.input_kind is InputKind.MANUAL} == {
        "tipo2.donante-nif",
        "tipo2.donante-nombre",
        "tipo2.importe-donado",
        "tipo2.porcentaje-deduccion",
        "tipo2.recurrencia",
    }
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
        authority=resources().modelos.authority,
        census=census,
        as_of=date(2026, 8, 25),
    )
    limb = next(item for item in coverage.limbs if item.modelo == "182" and item.revision == "2025")
    assert limb.outcome == "refused"
    assert limb.refusal is not None
    assert limb.refusal.disposition.work_item == "source-casilla.rows-donativo-ingress"
    assert limb.refusal.disposition.reconsideration_condition == entry.review_condition

    assert not snapshot.revision.export_layouts


def test_m182_terminal_deferral_is_rejected_after_its_expiry() -> None:
    """The bounded M182 deferral cannot remain current after 2026-12-31."""
    census = load_source_connectivity_census()
    entry = next(item for item in census.entries if item.candidate_id == "rows.donativo-donor")
    expired = entry.model_copy(update={"expires_on": date(2027, 1, 1)})
    expired_census = census.model_copy(
        update={"entries": tuple(expired if item is entry else item for item in census.entries)},
    )

    with pytest.raises(SourceConnectivityCheckError, match="expired without adjudication"):
        check_census_governance(expired_census, as_of=date(2027, 1, 1))
