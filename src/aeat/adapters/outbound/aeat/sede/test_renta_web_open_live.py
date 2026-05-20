"""Opt-in live calculation check for the Renta WEB Open Sede driver."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....domain.calculations.registry import RentaWebOpenLivePayload, RentaWebOpenOracle
from .....domain.calculations.registry._remote_state_guard import (
    RemoteStateGuardPolicy,
    remote_state_policy_from_cross_reference,
)
from .....domain.calculations.registry._schema import LiveCrossReferenceDecision
from aeat.tests.live_gate import requires_live_enabled
from ._renta_web_open import RentaWebOpenSedeDriver

pytestmark = [pytest.mark.live_read, pytest.mark.domain_outbound]


def test_renta_web_open_sede_driver_verifies_baseline_profile_calculations() -> None:
    requires_live_enabled()
    payload = RentaWebOpenLivePayload(timeout_ms=90_000).model_dump_json().encode("utf-8")
    result = RentaWebOpenOracle(driver=RentaWebOpenSedeDriver()).verify_payload(
        _open_simulator_policy(),
        payload,
        expected={
            "Resultado de la declaración": Decimal("0.00"),
            "Mínimo personal y familiar. Parte estatal": Decimal("5550.00"),
            "Mínimo personal y familiar. Parte autonómica": Decimal("5790.00"),
            "Cuota diferencial": Decimal("0.00"),
        },
    )

    assert result.verdict == "match", result
    assert result.raw_evidence_locator is not None
    assert "www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN" in result.raw_evidence_locator


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
