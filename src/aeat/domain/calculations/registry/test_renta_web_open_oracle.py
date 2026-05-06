"""Contract tests for the Renta WEB Open parity oracle adapter."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._remote_state_guard import (
    RemoteStateGuardPolicy,
    remote_state_policy_from_cross_reference,
)
from ._renta_web_open_oracle import RENTA_WEB_OPEN_LANDING_URL, RentaWebOpenOracle
from ._schema import LiveCrossReferenceDecision

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _open_simulator_policy() -> RemoteStateGuardPolicy:
    decision = LiveCrossReferenceDecision(
        id="modelo-100-renta-web-open",
        evidence_tier="executable_parity_evidence",
        surface="open_simulator",
        guard_policy_id="modelo-100-renta-web-open-read-only",
        allowed_hosts=("sede.agenciatributaria.gob.es", "www2.agenciatributaria.gob.es"),
        allowed_methods=("GET", "POST"),
        forbidden_actions=(
            "authenticated-renta-web",
            "fiscal-data-read",
            "borrador-read",
            "filed-declaration-read",
            "server-side-save",
            "signing",
            "presentation",
            "payment",
            "amendment",
            "cancellation",
            "document-submission",
            "declaration-submission",
        ),
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=("ley-35-2006:art-99",),
        source_refs=("aeat-renta-2025-manual-parte1",),
    )
    return remote_state_policy_from_cross_reference(decision)


def test_oracle_id_is_stable_and_documented() -> None:
    assert RentaWebOpenOracle().oracle_id == "modelo-100-renta-web-open"


def test_oracle_surface_kind_is_open_simulator() -> None:
    assert RentaWebOpenOracle().surface_kind == "open_simulator"


def test_landing_url_targets_aeat_sede_documentation() -> None:
    assert "sede.agenciatributaria.gob.es" in str(RENTA_WEB_OPEN_LANDING_URL)
    assert "renta-web-open" in str(RENTA_WEB_OPEN_LANDING_URL)


def test_planned_operations_lists_get_navigate_fill_scrape_and_discard() -> None:
    oracle = RentaWebOpenOracle()
    expected = {"0180": object(), "0224": object(), "0235": object()}
    plan = oracle.planned_operations(b"", expected=expected)
    actions = tuple(op.action for op in plan if op.action is not None)
    assert actions == ("requires-renta-web-open-driver",)
    http_operations = tuple(op for op in plan if op.kind == "http")
    assert len(http_operations) == 1
    assert http_operations[0].method == "GET"


def test_planned_operations_rejects_empty_expected_mapping() -> None:
    with pytest.raises(Exception, match="at least one expected casilla"):
        RentaWebOpenOracle().planned_operations(b"", expected={})


def test_verify_payload_without_driver_is_unverifiable_not_live_implementation() -> None:
    oracle = RentaWebOpenOracle()
    policy = _open_simulator_policy()
    result = oracle.verify_payload(policy, b"", expected={"0180": Decimal("1200.00")})

    assert result.verdict == "unverifiable"
    assert "browser driver is not configured" in result.narrative
