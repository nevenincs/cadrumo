"""Real CLI coverage for ``config check`` hardware and contention rows.

The production provisioning assessor receives injected measurements through its
public arguments. Each projection assertion therefore consumes a genuine typed
outcome and verifies that the CLI layer neither recreates a condition nor
retains a prose compatibility field.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from .....application.provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    assess_model_load_contention,
    probe_hardware_profile,
)
from .....core.config import override_settings
from .....core.hardware import AcceleratorKind, ContentionCause
from .....tests.cli_runner import invoke_cached_cli
from .._check_hardware_rows import CONTENTION_ROW_ID, contention_row
from .._check_payloads import CheckDependencyPayload
from ._isolated_storage_fixture import config_check_backend, config_check_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["config_check_backend", "config_check_isolated_backend"]

_GIB = 1024**3
_HARDWARE_ROW_ID = "local-inference-hardware"


def _config_check_payload() -> dict[str, Any]:
    result = invoke_cached_cli(["--format", "json", "config", "check"])
    assert result.exit_code in (0, 2), result.output
    return json.loads(result.output)["result"]


def _profile(*, kind: AcceleratorKind, free_vram_bytes: int | None = None) -> HardwareProfile:
    """Create a production profile from explicit measured values."""
    devices = (
        ()
        if kind is not AcceleratorKind.NVIDIA_CUDA
        else (
            AcceleratorDevice(
                index=0,
                name="test-accelerator",
                total_vram_bytes=16 * _GIB,
                free_vram_bytes=free_vram_bytes,
            ),
        )
    )
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=32 * _GIB, free_bytes=16 * _GIB),
        accelerator=AcceleratorReading(kind=kind, devices=devices),
    )


def _contention_snapshot(*, kind: AcceleratorKind, free_vram_bytes: int | None, requirement_bytes: int):
    """Assess the exact production contention branch from injected measurements."""
    with override_settings(cadrumo_llm_contention_safety_margin_bytes=0):
        return assess_model_load_contention(
            "test-model:1b",
            requirement_bytes,
            profile=_profile(kind=kind, free_vram_bytes=free_vram_bytes),
            residents=(),
        )


def test_the_doctor_reports_the_hardware_profile_and_contention_rows() -> None:
    """Both rows reach the operator through the existing dependency channel."""
    payload = _config_check_payload()
    by_id = {row["service"]: row for row in payload["dependencies"]}

    assert _HARDWARE_ROW_ID in by_id
    assert CONTENTION_ROW_ID in by_id
    assert by_id[_HARDWARE_ROW_ID]["facts"]


def test_dependency_rows_use_the_typed_outcome_schema() -> None:
    """The doctor has no bespoke hardware block or legacy text fields."""
    payload = _config_check_payload()

    assert set(payload) == {"profile_id", "ok", "capabilities", "dependencies", "preflight", "issues"}
    for row in payload["dependencies"]:
        assert set(row) == {"service", "available", "facts", "precondition_action"}

    with pytest.raises(ValidationError):
        CheckDependencyPayload(service="dependency", available=False, detail="legacy")


def test_neither_row_flips_the_commands_exit_contract() -> None:
    """Capability/dependency pairing owns ``ok``, not diagnostic contention."""
    payload = _config_check_payload()
    by_id = {row["service"]: row for row in payload["dependencies"]}
    contention = by_id[CONTENTION_ROW_ID]

    assert not any(CONTENTION_ROW_ID in issue for issue in payload["issues"])
    if not contention["available"]:
        assert payload["ok"] == (not payload["issues"])


def test_unmeasurable_load_is_reported_open_without_forwarding_a_refusal() -> None:
    """The report preserves facts but does not turn an observation into a rejection."""
    snapshot = _contention_snapshot(
        kind=AcceleratorKind.UNKNOWN,
        free_vram_bytes=None,
        requirement_bytes=4 * _GIB,
    )
    assert snapshot.causes == (ContentionCause.UNREADABLE,)
    assert snapshot.precondition_verdict is not None

    row = contention_row(snapshot)

    assert row.available is True
    assert row.facts == snapshot.facts
    assert row.precondition_verdict is None


def test_measured_shortfall_preserves_the_exact_typed_refusal() -> None:
    """The CLI projection must not recreate an instruction from contention causes."""
    snapshot = _contention_snapshot(
        kind=AcceleratorKind.NVIDIA_CUDA,
        free_vram_bytes=_GIB,
        requirement_bytes=4 * _GIB,
    )
    assert snapshot.causes == (ContentionCause.PEER_PROCESS,)
    assert snapshot.precondition_verdict is not None

    row = contention_row(snapshot)

    assert row.available is False
    assert row.facts == snapshot.facts
    assert row.precondition_verdict == snapshot.precondition_verdict


def test_admitted_load_and_no_selected_model_remain_distinct_factual_states() -> None:
    """Both report available, but their machine facts retain the distinction."""
    admitted = contention_row(
        _contention_snapshot(
            kind=AcceleratorKind.NVIDIA_CUDA,
            free_vram_bytes=12 * _GIB,
            requirement_bytes=4 * _GIB,
        ),
    )
    unselected = contention_row(None)

    assert admitted.available is True
    assert admitted.precondition_verdict is None
    assert admitted.facts["shortfall_bytes"] == 0
    assert unselected.available is True
    assert unselected.precondition_verdict is None
    assert unselected.facts == {"model_selected": False}
