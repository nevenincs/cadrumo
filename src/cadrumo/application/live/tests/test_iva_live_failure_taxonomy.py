"""Application taxonomy for live IVA acquisition failures."""

from __future__ import annotations

import pytest

from ....adapters.outbound.aeat.auth.clave_movil_support import (
    ClaveMovilApprovalTimeoutError,
    ClaveMovilConfigurationError,
)
from ....adapters.outbound.aeat.sede.errors import SedeFailureMode, SedeNavigationError, SedeParseError
from ..errors import (
    LiveIvaAcquisitionFailureMode,
    classify_live_iva_acquisition_failure,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_clave_no_prompt_timeout_is_not_collapsed_to_generic_unavailable() -> None:
    exc = ClaveMovilApprovalTimeoutError(
        "operator reported no Cl@ve prompt",
        failure_mode="auth_completion_timeout",
        context={"phone_state": "app_did_not_prompt", "auth_mode": "non_qr"},
    )

    assert classify_live_iva_acquisition_failure(exc) is LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT


def test_clave_operator_timeout_keeps_its_own_outcome() -> None:
    exc = ClaveMovilApprovalTimeoutError(
        "operator did not complete approval in time",
        failure_mode="auth_completion_timeout",
        context={"phone_state": "operator_did_not_check", "auth_mode": "non_qr"},
    )

    assert classify_live_iva_acquisition_failure(exc) is LiveIvaAcquisitionFailureMode.OPERATOR_TIMEOUT


def test_clave_initial_navigation_timeout_maps_to_live_navigation_failure() -> None:
    exc = ClaveMovilApprovalTimeoutError(
        "initial selector navigation timed out",
        failure_mode="initial_navigation_timeout",
        context={"auth_mode": "non_qr"},
    )

    assert classify_live_iva_acquisition_failure(exc) is LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED


def test_qr_wait_state_failure_is_reported_as_qr_required() -> None:
    exc = ClaveMovilApprovalTimeoutError(
        "QR flow did not reach the expected wait state",
        failure_mode="push_wait_state_not_reached",
        context={"auth_mode": "qr"},
    )

    assert classify_live_iva_acquisition_failure(exc) is LiveIvaAcquisitionFailureMode.QR_REQUIRED


def test_identity_configuration_failure_maps_to_wrong_identity() -> None:
    exc = ClaveMovilConfigurationError("configured identity is not a supported DNI/NIE")

    assert classify_live_iva_acquisition_failure(exc) is LiveIvaAcquisitionFailureMode.WRONG_IDENTITY


def test_sede_403_auth_gate_is_distinct_from_dom_drift() -> None:
    auth_gate = SedeNavigationError("AEAT returned 4033", failure_mode=SedeFailureMode.AUTH_GATE_DETECTED)
    dom_drift = SedeParseError("wallet table missing", failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED)

    assert classify_live_iva_acquisition_failure(auth_gate) is LiveIvaAcquisitionFailureMode.AEAT_403
    assert classify_live_iva_acquisition_failure(dom_drift) is LiveIvaAcquisitionFailureMode.DOM_DRIFT


def test_certificate_required_auth_gate_is_not_collapsed_to_generic_403() -> None:
    exc = SedeNavigationError(
        "AEAT requires certificate",
        failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
        context={"required_auth_provider": "certificate"},
    )

    assert classify_live_iva_acquisition_failure(exc) is LiveIvaAcquisitionFailureMode.CERTIFICATE_REQUIRED
