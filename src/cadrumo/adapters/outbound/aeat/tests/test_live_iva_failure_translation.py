"""Outbound-adapter translations into the application live-IVA contract."""

from __future__ import annotations

import pytest

from cadrumo.adapters.outbound.aeat.auth.clave_movil_support import (
    ClaveMovilApprovalTimeoutError,
    ClaveMovilConfigurationError,
)
from cadrumo.adapters.outbound.aeat.sede.errors import (
    SedeFailureMode,
    SedeNavigationError,
    SedeParseError,
)
from cadrumo.application.live.errors import LiveIvaAcquisitionFailureMode

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize(
    ("failure_mode", "context", "expected"),
    (
        (
            "auth_completion_timeout",
            {"phone_state": "app_did_not_prompt", "auth_mode": "non_qr"},
            LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
        ),
        (
            "pending_petition_blocked",
            {"auth_mode": "non_qr"},
            LiveIvaAcquisitionFailureMode.PENDING_CLAVE_REQUEST,
        ),
        (
            "initial_navigation_timeout",
            {"auth_mode": "non_qr"},
            LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED,
        ),
        (
            "auth_completion_timeout",
            {"phone_state": "operator_did_not_check", "auth_mode": "non_qr"},
            LiveIvaAcquisitionFailureMode.OPERATOR_TIMEOUT,
        ),
        (
            "approval_timeout",
            {"auth_mode": "non_qr"},
            LiveIvaAcquisitionFailureMode.OPERATOR_TIMEOUT,
        ),
        (
            "push_wait_state_not_reached",
            {"auth_mode": "qr"},
            LiveIvaAcquisitionFailureMode.QR_REQUIRED,
        ),
        (
            "push_wait_state_not_reached",
            {"auth_mode": "non_qr"},
            LiveIvaAcquisitionFailureMode.DOM_DRIFT,
        ),
        (
            "unrecognised",
            {},
            LiveIvaAcquisitionFailureMode.UNKNOWN,
        ),
    ),
)
def test_clave_movil_failure_exposes_application_mode(
    failure_mode: str,
    context: dict[str, object],
    expected: LiveIvaAcquisitionFailureMode,
) -> None:
    """The Cl@ve adapter translates its local taxonomy before handoff."""
    error = ClaveMovilApprovalTimeoutError(failure_mode=failure_mode, context=context)

    assert error.live_iva_failure_mode is expected


def test_clave_movil_configuration_exposes_wrong_identity() -> None:
    """The provider-specific configuration refusal has an app-level mode."""
    assert ClaveMovilConfigurationError().live_iva_failure_mode is LiveIvaAcquisitionFailureMode.WRONG_IDENTITY


@pytest.mark.parametrize(
    ("failure", "expected"),
    (
        (
            SedeNavigationError(failure_mode=SedeFailureMode.AUTH_GATE_DETECTED),
            LiveIvaAcquisitionFailureMode.AEAT_403,
        ),
        (
            SedeNavigationError(
                failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
                context={"required_auth_provider": "certificado"},
            ),
            LiveIvaAcquisitionFailureMode.CERTIFICATE_REQUIRED,
        ),
        (
            SedeParseError(failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED),
            LiveIvaAcquisitionFailureMode.DOM_DRIFT,
        ),
        (
            SedeNavigationError(failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED),
            LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED,
        ),
        (
            SedeNavigationError(failure_mode=SedeFailureMode.BROWSER_BACKEND_FAILED),
            LiveIvaAcquisitionFailureMode.UNKNOWN,
        ),
    ),
)
def test_sede_failure_exposes_application_mode(
    failure: SedeNavigationError | SedeParseError,
    expected: LiveIvaAcquisitionFailureMode,
) -> None:
    """The Sede adapter translates its local taxonomy before handoff."""
    assert failure.live_iva_failure_mode is expected
