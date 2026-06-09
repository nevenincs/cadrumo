"""Application-level live AEAT read workflow errors."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.errors import AeatError

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import ClaveMovilApprovalTimeoutError
    from ...adapters.outbound.aeat.sede import SedeError


class LiveIvaAcquisitionFailureMode(StrEnum):
    """Application-level IVA live acquisition failure modes."""

    AUTHENTICATED = "authenticated"
    NO_CLAVE_PROMPT = "no_clave_prompt"
    OPERATOR_TIMEOUT = "operator_timeout"
    QR_REQUIRED = "qr_required"
    CERTIFICATE_REQUIRED = "certificate_required"
    WRONG_IDENTITY = "wrong_identity"
    AEAT_403 = "aeat_403"
    DOM_DRIFT = "dom_drift"
    PENDING_CLAVE_REQUEST = "pending_clave_request"
    LIVE_NAVIGATION_FAILED = "live_navigation_failed"
    UNKNOWN = "unknown"


class LiveApplicationError(AeatError):
    """Raised when live AEAT read orchestration fails."""


class LiveApplicationInputError(LiveApplicationError):
    """Raised when a live AEAT read request is not executable."""


class LiveIvaSurfaceTimeoutError(LiveApplicationError):
    """Raised when one live IVA read surface exceeds its orchestration timeout."""

    def __init__(
        self,
        message: str,
        *,
        surface: str,
        timeout_ms: int,
        progress_context: Mapping[str, object] | None = None,
    ) -> None:
        context: dict[str, object] = {"surface": surface, "timeout_ms": timeout_ms}
        if progress_context:
            context["progress"] = dict(progress_context)
        super().__init__(
            message,
            context=context,
            translated_message="errors.error.error_application_live_iva_surface_timeout",
        )
        self.surface = surface
        self.timeout_ms = timeout_ms


def _classify_clave_movil_timeout(exc: ClaveMovilApprovalTimeoutError) -> LiveIvaAcquisitionFailureMode:
    from ...adapters.outbound.aeat.auth import ClaveMovilFailureMode

    context = exc.context if isinstance(exc.context, dict) else {}
    phone_state = str(context.get("phone_state") or "")
    auth_mode = str(context.get("auth_mode") or "")
    if phone_state == "app_did_not_prompt":
        return LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT
    if exc.failure_mode == ClaveMovilFailureMode.PENDING_PETITION_BLOCKED.value:
        return LiveIvaAcquisitionFailureMode.PENDING_CLAVE_REQUEST
    if exc.failure_mode == ClaveMovilFailureMode.INITIAL_NAVIGATION_TIMEOUT.value:
        return LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED
    if exc.failure_mode in {
        ClaveMovilFailureMode.AUTH_COMPLETION_TIMEOUT.value,
        ClaveMovilFailureMode.APPROVAL_TIMEOUT.value,
    }:
        return LiveIvaAcquisitionFailureMode.OPERATOR_TIMEOUT
    if auth_mode == "qr":
        return LiveIvaAcquisitionFailureMode.QR_REQUIRED
    if exc.failure_mode == ClaveMovilFailureMode.PUSH_WAIT_STATE_NOT_REACHED.value:
        return LiveIvaAcquisitionFailureMode.DOM_DRIFT
    return LiveIvaAcquisitionFailureMode.UNKNOWN


def _classify_sede_error(exc: SedeError) -> LiveIvaAcquisitionFailureMode:
    from ...adapters.outbound.aeat.sede import SedeFailureMode

    if exc.failure_mode == SedeFailureMode.AUTH_GATE_DETECTED.value:
        context = exc.context if isinstance(exc.context, dict) else {}
        required_provider = str(context.get("required_auth_provider") or "").casefold()
        if required_provider in {"certificate", "certificado"}:
            return LiveIvaAcquisitionFailureMode.CERTIFICATE_REQUIRED
        return LiveIvaAcquisitionFailureMode.AEAT_403
    if exc.failure_mode == SedeFailureMode.EXTERNAL_SHAPE_CHANGED.value:
        return LiveIvaAcquisitionFailureMode.DOM_DRIFT
    if exc.failure_mode == SedeFailureMode.LIVE_NAVIGATION_FAILED.value:
        return LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED
    return LiveIvaAcquisitionFailureMode.UNKNOWN


def classify_live_iva_acquisition_failure(exc: BaseException) -> LiveIvaAcquisitionFailureMode:
    """Map adapter exceptions to the live IVA acquisition result vocabulary.

    Returns a :class:`LiveIvaAcquisitionFailureMode` member identifying
    the failure category.
    """
    from ...adapters.outbound.aeat.auth import (
        ClaveMovilApprovalTimeoutError,
        ClaveMovilConfigurationError,
    )
    from ...adapters.outbound.aeat.sede import SedeError

    if isinstance(exc, LiveIvaSurfaceTimeoutError):
        return LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED
    if isinstance(exc, ClaveMovilApprovalTimeoutError):
        return _classify_clave_movil_timeout(exc)
    if isinstance(exc, ClaveMovilConfigurationError):
        return LiveIvaAcquisitionFailureMode.WRONG_IDENTITY
    if isinstance(exc, SedeError):
        return _classify_sede_error(exc)
    return LiveIvaAcquisitionFailureMode.UNKNOWN


__all__ = [
    "LiveApplicationError",
    "LiveApplicationInputError",
    "LiveIvaAcquisitionFailureMode",
    "LiveIvaSurfaceTimeoutError",
    "classify_live_iva_acquisition_failure",
]
