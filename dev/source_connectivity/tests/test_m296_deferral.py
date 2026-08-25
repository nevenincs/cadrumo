from datetime import date

import pytest

from cadrumo.application.modelo import CALCULATION_ROUTE_RESOLVER_OWNERSHIP, CALCULATION_ROUTE_SOURCE_DISPOSITIONS
from cadrumo.application.registry import compose_source_connectivity_coverage
from cadrumo.application.registry.source_connectivity import load_source_connectivity_census
from cadrumo.core import BindingSourceKind
from cadrumo.core.resources import resources

from ..check import SourceConnectivityCheckError, check_census_governance
from ..live_proof import CONNECTED_PROOF_FIXTURES, connected_candidate_ids

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
    assert "rows.withholding296" not in connected_candidate_ids()
    assert all(fixture.candidate_id != "rows.withholding296" for fixture in CONNECTED_PROOF_FIXTURES)
    assert CALCULATION_ROUTE_SOURCE_DISPOSITIONS[BindingSourceKind.WITHHOLDING].value == "enrolled"
    coverage = compose_source_connectivity_coverage(
        authority=resources().modelos.authority, census=load_source_connectivity_census(), as_of=date(2026, 8, 25)
    )
    limb = next(item for item in coverage.limbs if item.modelo == "296")
    assert limb.outcome == "unmeasured"
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
