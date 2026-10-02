"""Canonical workstation contention rows and their CLI transport shape."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....application.provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
)
from .....application.provisioning_runtime import assess_model_load_contention
from .....application.workstation_contention import CONTENTION_ROW_ID, contention_row
from .....core.config import override_settings
from .....core.hardware import AcceleratorKind, ContentionCause
from ..check_payloads import CheckDependencyPayload, CheckPreflightPayload, ConfigCheckResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_GIB = 1024**3


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


def test_workstation_cli_result_keeps_the_closed_row_schemas() -> None:
    """The authenticated presenter retains the established JSON result rows."""
    assert set(ConfigCheckResult.model_fields) == {
        "profile_id",
        "ok",
        "capabilities",
        "dependencies",
        "preflight",
        "issues",
    }
    assert set(CheckDependencyPayload.model_fields) == {"service", "available", "facts", "precondition_action"}
    assert set(CheckPreflightPayload.model_fields) == {
        "check",
        "healthy",
        "severity",
        "facts",
        "precondition_action",
    }
    with pytest.raises(ValidationError):
        CheckDependencyPayload(service="dependency", available=False, detail="legacy")


def test_unmeasurable_load_is_reported_open_without_forwarding_a_refusal() -> None:
    """A report distinguishes unreadable measurements from a measured shortfall."""
    snapshot = _contention_snapshot(
        kind=AcceleratorKind.UNKNOWN,
        free_vram_bytes=None,
        requirement_bytes=4 * _GIB,
    )
    assert snapshot.causes == (ContentionCause.UNREADABLE,)
    assert snapshot.precondition_verdict is not None

    row = contention_row(snapshot)

    assert row.service == CONTENTION_ROW_ID
    assert row.available is True
    assert row.facts == snapshot.facts
    assert row.precondition_verdict is None


def test_measured_shortfall_preserves_the_exact_typed_refusal() -> None:
    """The canonical row retains its owning precondition verdict and measurements."""
    snapshot = _contention_snapshot(
        kind=AcceleratorKind.NVIDIA_CUDA,
        free_vram_bytes=_GIB,
        requirement_bytes=4 * _GIB,
    )
    assert snapshot.causes == (ContentionCause.PEER_PROCESS,)
    assert snapshot.precondition_verdict is not None

    row = contention_row(snapshot)

    assert row.service == CONTENTION_ROW_ID
    assert row.available is False
    assert row.facts == snapshot.facts
    assert row.precondition_verdict == snapshot.precondition_verdict


def test_admitted_load_and_no_selected_model_remain_distinct_factual_states() -> None:
    """Both rows are available, while only the selected load has measured figures."""
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
