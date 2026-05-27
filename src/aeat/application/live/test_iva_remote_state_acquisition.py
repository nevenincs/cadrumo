"""Combined IVA remote-state acquisition report tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.outbound.aeat.sede import SedeFailureMode, SedeNavigationError

from . import (
    IvaCompensationHistoryCaptureReport,
    IvaRemoteStateAcquisitionReport,
    LiveIvaAcquisitionFailureMode,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
    build_iva_remote_state_acquisition_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_CAPTURED_AT = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)


def test_combined_acquisition_preserves_filed_history_when_wallet_auth_gate_fails(tmp_path: Path) -> None:
    filed_history = IvaCompensationHistoryCaptureReport(
        output_root=str(tmp_path / "filed-history"),
        year_from=2022,
        year_to=2024,
        captured_count=12,
        observation_paths=("observations/303-2022-1T.json",),
        artefact_refs=("secure-object:artefact",),
        casilla_count=948,
        calculation_observation_count=12,
        calculation_observation_keys=("303:2022:1T",),
        reloaded_history_count=12,
        reloaded_rows=(),
    )
    wallet_error = SedeNavigationError(
        "AEAT wallet auth gate",
        failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
        context={"captured_at": _CAPTURED_AT.isoformat()},
    )

    report = build_iva_remote_state_acquisition_report(
        output_root=tmp_path,
        year_from=2022,
        year_to=2024,
        target_year=2026,
        target_period="2T",
        filed_history=filed_history,
        wallet_error=wallet_error,
    )

    assert isinstance(report, IvaRemoteStateAcquisitionReport)
    assert report.filed_history_succeeded is True
    assert report.wallet_succeeded is False
    assert report.filed_history is filed_history
    assert report.wallet is None
    filed_outcome, wallet_outcome = report.outcomes
    assert filed_outcome.surface is LiveIvaReadSurface.FILED_HISTORY
    assert filed_outcome.status is LiveIvaReadStatus.SUCCEEDED
    assert filed_outcome.captured_count == 12
    assert filed_outcome.calculation_observation_count == 12
    assert wallet_outcome.surface is LiveIvaReadSurface.WALLET_CARTERA
    assert wallet_outcome.status is LiveIvaReadStatus.FAILED
    assert wallet_outcome.failure_mode is LiveIvaAcquisitionFailureMode.AEAT_403
    assert wallet_outcome.failure_type == "SedeNavigationError"
    assert "AEAT wallet auth gate" not in report.model_dump_json()


def test_combined_acquisition_reports_missing_surface_as_typed_failure(tmp_path: Path) -> None:
    report = build_iva_remote_state_acquisition_report(
        output_root=tmp_path,
        year_from=2024,
        year_to=2024,
        target_year=2026,
        target_period="1T",
    )

    assert report.filed_history_succeeded is False
    assert report.wallet_succeeded is False
    assert tuple(outcome.status for outcome in report.outcomes) == (
        LiveIvaReadStatus.FAILED,
        LiveIvaReadStatus.FAILED,
    )
    assert tuple(outcome.failure_type for outcome in report.outcomes) == (
        "MissingSurfaceReport",
        "MissingSurfaceReport",
    )
