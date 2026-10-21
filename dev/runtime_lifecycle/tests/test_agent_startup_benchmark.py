"""A startup measurement must establish worker readiness, not merely liveness."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from .. import agent_startup_benchmark
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


def test_interrupted_samples_resume_from_durable_observations_after_private_scratch_is_reclaimed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()
    output = tmp_path / "observations.json"
    arguments = [
        "benchmark",
        "--baseline",
        str(baseline),
        "--candidate",
        str(candidate),
        "--output",
        str(output),
        "--samples",
        "1",
    ]
    calls: list[str] = []
    roots: list[Path] = []

    def measure(package: Path, scratch: Path) -> dict[str, object]:
        calls.append(package.name)
        roots.append(scratch)
        (scratch / "synthetic-profile").write_text("private fixture state", encoding="utf-8")
        if calls == ["baseline", "candidate"]:
            raise RuntimeError("interrupted candidate")
        return {
            "runtime_ready_seconds": 1.0,
            "profile_create_and_login_seconds": 2.0,
            "holder_start_seconds": 3.0,
            "profile_language_first_seconds": 4.0,
            "profile_language_cached_seconds": 5.0,
            "starts": [
                {
                    "store_state_before_start": state,
                    "service_ready_seconds": 6.0,
                    "gateway_ready_seconds": 7.0,
                    "worker_available_seconds": 8.0,
                    "worker_warmed_seconds": 9.0,
                }
                for state in ("absent", "current")
            ],
        }

    monkeypatch.setattr(agent_startup_benchmark, "package_identity", lambda package: package.name)
    monkeypatch.setattr(agent_startup_benchmark, "measure", measure)
    monkeypatch.setattr(sys, "argv", arguments)
    with pytest.raises(RuntimeError, match="interrupted candidate"):
        agent_startup_benchmark.main()

    partial = json.loads(output.read_text(encoding="utf-8"))
    assert [sample["package"] for sample in partial["samples"]] == ["baseline"]
    assert not Path(partial["scratch"]).exists()
    assert all(not root.exists() for root in roots)

    monkeypatch.setattr(sys, "argv", [*arguments, "--resume"])
    agent_startup_benchmark.main()
    completed = json.loads(output.read_text(encoding="utf-8"))
    assert calls == ["baseline", "candidate", "candidate"]
    assert completed["samples"][0] == partial["samples"][0]
    assert [sample["package"] for sample in completed["samples"]] == ["baseline", "candidate"]
    assert completed["medians_seconds"]["candidate"]["current"]["worker_warmed_seconds"] == 9.0
    assert completed["scratch_retained"] is False
    assert not Path(completed["scratch"]).exists()
    assert all(not root.exists() for root in roots)
