from datetime import date

import pytest

from cadrumo.application.aggregation import collect_unhandled_source_diagnostics
from cadrumo.application.modelo import CALCULATION_ROUTE_RESOLVER_OWNERSHIP, CALCULATION_ROUTE_SOURCE_DISPOSITIONS
from cadrumo.application.registry import compose_source_connectivity_coverage
from cadrumo.application.registry.source_connectivity import load_source_connectivity_census
from cadrumo.core import BindingSourceKind, RegistryAuthorityGrade
from cadrumo.core.resources import resources
from cadrumo.domain.calculations.registry import InputKind

from ..check import SourceConnectivityCheckError, check_census_governance
from ..live_proof import CONNECTED_PROOF_FIXTURES, connected_candidate_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_m193_remains_measurably_ingress_blocked_until_its_missing_authority_exists() -> None:
    reopening_predicate = (
        "Manual M193 gasto casillas remain direct entry, not source ownership; withholding storage is separate. Reopen "
        "only when a secure owner retains a non-synthetic contributor/representative carrier with durable "
        "identity/fingerprint and capture provenance, a resolver resolves canonical gasto193_contributor, and "
        "diagnostics, provenance, encrypted persistence/replay, review, and supported repeated-record export are "
        "proven for both revisions."
    )
    entry = next(
        item for item in load_source_connectivity_census().entries if item.candidate_id == "rows.gasto193-contributor"
    )

    assert entry.disposition.value == "ingress_blocked"
    assert entry.owner == "source-connectivity-campaign"
    assert entry.expires_on == date(2026, 12, 31)
    assert entry.review_condition == reopening_predicate
    assert len(entry.review_condition) == len(reopening_predicate) <= 500
    assert entry.bounded_follow_up is not None
    assert entry.bounded_follow_up.action_id == "source-casilla.rows-gasto193-ingress"
    assert entry.bounded_follow_up.owner == "source-connectivity-campaign"
    assert entry.bounded_follow_up.deadline == date(2026, 11, 30)


def test_m193_deferred_source_preserves_manual_gasto_casillas_without_connected_ownership() -> None:
    source_kind = BindingSourceKind.GASTO193_CONTRIBUTOR
    candidate_id = "rows.gasto193-contributor"
    census = load_source_connectivity_census()
    entry = next(item for item in census.entries if item.candidate_id == candidate_id)
    snapshot = resources().modelos.authority.snapshot(
        "193", filing_year=2025, period="0A", grade=RegistryAuthorityGrade.FILING
    )

    assert {str(casilla.id) for casilla in snapshot.revision.casillas if casilla.input_kind is InputKind.MANUAL} >= {
        "gasto.nif",
        "gasto.nombre",
        "gasto.nif-representante",
        "gasto.importe",
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
    assert CALCULATION_ROUTE_SOURCE_DISPOSITIONS[BindingSourceKind.WITHHOLDING].value == "enrolled"
    assert any(BindingSourceKind.WITHHOLDING in owner.owned_sources for owner in CALCULATION_ROUTE_RESOLVER_OWNERSHIP)

    coverage = compose_source_connectivity_coverage(
        authority=resources().modelos.authority, census=census, as_of=date(2026, 8, 25)
    )
    limb = next(item for item in coverage.limbs if item.modelo == "193" and item.revision == "2025-y-siguientes")
    assert limb.outcome == "refused"
    assert limb.refusal is not None
    assert limb.refusal.disposition.work_item == "source-casilla.rows-gasto193-ingress"
    assert limb.refusal.disposition.reconsideration_condition == entry.review_condition


def test_m193_terminal_deferral_is_rejected_after_its_expiry() -> None:
    census = load_source_connectivity_census()
    entry = next(item for item in census.entries if item.candidate_id == "rows.gasto193-contributor")
    expired = entry.model_copy(update={"expires_on": date(2027, 1, 1)})
    expired_census = census.model_copy(
        update={"entries": tuple(expired if item is entry else item for item in census.entries)}
    )

    with pytest.raises(SourceConnectivityCheckError, match="expired without adjudication"):
        check_census_governance(expired_census, as_of=date(2027, 1, 1))
