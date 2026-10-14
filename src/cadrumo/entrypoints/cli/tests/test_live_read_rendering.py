"""Live read rendering preserves distinct outcomes and redacts profile identity."""

from __future__ import annotations

import pytest

from cadrumo.application.auth.operator_results import LiveAuthPreflightReport
from cadrumo.application.live.errors import LiveIvaAcquisitionFailureMode
from cadrumo.application.live.remote_state_models import (
    IvaRemoteStateAcquisitionReport,
    LiveIvaAuthOutcome,
    LiveIvaReadOutcome,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)
from cadrumo.core.period import Period

from .._app_live import _iva_remote_state_capture_lines, _live_iva_outcome_label
from .._app_live_auth_preflight import _live_auth_preflight_lines

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_live_auth_preflight_lines_redact_active_profile_identifier() -> None:
    report = LiveAuthPreflightReport(
        provider="clave_movil",
        configured=True,
        available=True,
        active_profile="operator-private-profile-id",
        active_profile_status="ready",
        persisted_session_present=True,
        persisted_session_expired=False,
        persisted_session_state="live",
    )

    lines = _live_auth_preflight_lines(report)

    assert "auth_active_profile=<profile-id>" in lines
    assert "auth_persisted_session_state=live" in lines
    assert all(not line.startswith("auth_certificate_backend=") for line in lines)
    assert all("operator-private-profile-id" not in line for line in lines)


def test_every_live_iva_outcome_has_operator_label() -> None:
    for mode in LiveIvaAcquisitionFailureMode:
        label = _live_iva_outcome_label(mode)

        assert label
        assert "cli.app.live.iva_wallet.acquisition.outcome" not in label
        if mode is not LiveIvaAcquisitionFailureMode.UNKNOWN:
            assert label != _live_iva_outcome_label(LiveIvaAcquisitionFailureMode.UNKNOWN)


def test_remote_state_lines_render_auth_and_surface_outcomes_with_labels() -> None:
    report = IvaRemoteStateAcquisitionReport(
        output_root="live/iva-read-evidence",
        year_from=2022,
        year_to=2024,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        auth=LiveIvaAuthOutcome(
            status=LiveIvaReadStatus.FAILED,
            outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
            failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
            failure_type="ClaveMovilApprovalTimeoutError",
        ),
        filed_history=None,
        wallet=None,
        outcomes=(
            LiveIvaReadOutcome(
                surface=LiveIvaReadSurface.FILED_HISTORY,
                status=LiveIvaReadStatus.FAILED,
                outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                failure_type="ClaveMovilApprovalTimeoutError",
                failure_context={
                    "progress": {
                        "stage": "walk_declarations_register",
                        "modelo": "303",
                        "ejercicio": 2026,
                    },
                },
            ),
            LiveIvaReadOutcome(
                surface=LiveIvaReadSurface.WALLET_CARTERA,
                status=LiveIvaReadStatus.FAILED,
                outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                failure_type="ClaveMovilApprovalTimeoutError",
            ),
        ),
    )

    lines = _iva_remote_state_capture_lines(report)

    assert "auth_status=failed" in lines
    assert "auth_outcome=no_clave_prompt" in lines
    no_prompt_label = _live_iva_outcome_label(LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT)
    assert f"auth_outcome_label={no_prompt_label}" in lines
    assert "filed_history_succeeded=False" in lines
    assert "wallet_succeeded=False" in lines
    assert any(
        line.startswith("surface_outcome=filed_history\tstatus=failed\toutcome=no_clave_prompt") for line in lines
    )
    assert any(
        "failure_context=progress={ejercicio:2026,modelo:303,stage:walk_declarations_register}" in line
        for line in lines
    )
    assert any(
        line.startswith("surface_outcome=wallet_cartera\tstatus=failed\toutcome=no_clave_prompt") for line in lines
    )
