from datetime import date
from pathlib import Path

import pytest

from cadrumo.application.modelo._calculation_route import (
    CALCULATION_ROUTE_RESOLVER_OWNERSHIP,
    CALCULATION_ROUTE_SOURCE_DISPOSITIONS,
)
from cadrumo.application.registry import compose_source_connectivity_coverage
from cadrumo.application.registry.source_connectivity import load_source_connectivity_census
from cadrumo.core import BindingSourceKind
from cadrumo.core.resources import resources

from ..check import SourceConnectivityCheckError, check_census_governance
from ..live_proof import CONNECTED_PROOF_FIXTURES, canonical_live_connected_proof_authority, connected_candidate_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_m296_registry_blocked_refusal_is_bounded_and_unconnected() -> None:
    entry = next(
        item for item in load_source_connectivity_census().entries if item.candidate_id == "rows.withholding296"
    )
    assert entry.disposition.value == "registry_blocked"
    assert entry.owner == "source-connectivity-campaign"
    assert entry.review_condition is not None and len(entry.review_condition) <= 500
    assert "withholding296 resolver" in entry.review_condition
    assert entry.bounded_follow_up is not None
    assert entry.bounded_follow_up.owner == "source-connectivity-campaign"
    source = BindingSourceKind.WITHHOLDING296
    assert CALCULATION_ROUTE_SOURCE_DISPOSITIONS[source].value == "deferred"
    assert all(source not in owner.owned_sources for owner in CALCULATION_ROUTE_RESOLVER_OWNERSHIP)
    modelo_296 = next(modelo for modelo in resources().modelos.all() if str(modelo.id) == "296")
    assert all(
        all(binding.source is not source for binding in revision.bindings) for revision in modelo_296.revisions.values()
    )
    assert "rows.withholding296" not in connected_candidate_ids()
    assert all(fixture.candidate_id != "rows.withholding296" for fixture in CONNECTED_PROOF_FIXTURES)
    # Connected fixtures are the sole lifecycle authority for encrypted persistence,
    # provenance, replay, review, and source-owned repeated-row export.
    with canonical_live_connected_proof_authority(Path.cwd()) as proof_authority:
        assert proof_authority is None
    retenciones = BindingSourceKind.RETENCIONES_AGGREGATION
    assert CALCULATION_ROUTE_SOURCE_DISPOSITIONS[retenciones].value == "enrolled"
    assert any(retenciones in owner.owned_sources for owner in CALCULATION_ROUTE_RESOLVER_OWNERSHIP)
    for modelo_id in ("180", "193"):
        revision = resources().modelos.authority.snapshot(modelo_id, filing_year=2025, period="0A").revision
        assert any(binding.source is retenciones for binding in revision.bindings)
    coverage = compose_source_connectivity_coverage(
        authority=resources().modelos.authority, census=load_source_connectivity_census(), as_of=date(2026, 8, 25)
    )
    limb = next(item for item in coverage.limbs if item.modelo == "296")
    assert limb.outcome == "unmeasured"
    assert limb.refusal is not None and limb.refusal.reason == "unmeasured"
    assert entry.disposition.value == "registry_blocked"
    assert entry.bounded_follow_up.action_id == "source-casilla.rows-withholding296-registry"


def test_m296_refusal_expires() -> None:
    census = load_source_connectivity_census()
    entry = next(item for item in census.entries if item.candidate_id == "rows.withholding296")
    expired = entry.model_copy(update={"expires_on": date(2027, 1, 1)})
    mutated = census.model_copy(
        update={"entries": tuple(expired if item is entry else item for item in census.entries)}
    )
    with pytest.raises(SourceConnectivityCheckError, match="expired without adjudication"):
        check_census_governance(mutated, as_of=date(2027, 1, 1))
