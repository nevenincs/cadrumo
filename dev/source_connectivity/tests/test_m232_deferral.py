import pytest

from cadrumo.application.registry.source_connectivity import load_source_connectivity_census

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

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
