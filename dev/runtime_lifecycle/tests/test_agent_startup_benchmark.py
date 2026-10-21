"""A startup measurement must establish worker readiness, not merely liveness."""

from __future__ import annotations

import pytest

from ..agent_startup_benchmark import _health_facts
from ..caller_owned_root import AcceptanceError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_hosted_health_requires_a_live_probed_worker() -> None:
    assert _health_facts({"service": "gateway", "status": "ok", "ready": True, "worker_status": "up"}) == {
        "gateway_health": "ready",
        "worker_health": "up",
        "run_admission": "not measured",
    }


def test_desktop_health_preserves_blocked_provider_admission() -> None:
    assert _health_facts({"gateway_readiness": "ready", "worker_state": "ready", "run_admission": "blocked"}) == {
        "gateway_health": "ready",
        "worker_health": "ready",
        "run_admission": "blocked",
    }


@pytest.mark.parametrize(
    "health",
    [
        {"liveness": "alive"},
        {"service": "gateway", "status": "ok", "ready": True, "worker_status": "pending"},
        {"service": "gateway", "status": "ok", "ready": False, "worker_status": "up"},
        {"service": "gateway", "status": "degraded", "ready": True, "worker_status": "up"},
        {"gateway_readiness": "ready", "worker_state": "starting"},
    ],
)
def test_liveness_and_incomplete_startup_are_not_success(health: dict[str, object]) -> None:
    with pytest.raises(AcceptanceError):
        _health_facts(health)
