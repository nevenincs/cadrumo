"""Application-level live AEAT read workflow errors.

Every refusal raised here carries a registered locale key plus machine facts;
no raise site authors an operator-facing sentence, so ``str(exc)`` renders the
key and the prose is resolved once, per locale, at the presentation boundary.

A subset of these refusals is additionally a *safety* disposition: the live
read observed a fact that makes retrying the same call actively unsafe rather
than merely futile -- a captured justificante that does not belong to the
filing it would be stamped onto, a notification document that belongs to a
different certificado, an AEAT observation AEAT no longer reports as active.
Those raise sites attach a :class:`~application.operator_actions.PreconditionVerdict`
whose ``no_recovery_outcome`` is :attr:`~core.NoRecoveryOutcome.SAFETY`, so the
CLI boundary projects an explicit "there is deliberately no recovery here"
rather than reaching for a retry the operator should not run.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth.clave_movil_support import ClaveMovilApprovalTimeoutError
    from ...adapters.outbound.aeat.sede.errors import SedeError


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


class LiveReadPrecondition(StrEnum):
    """Closed failed-condition identities for live-read safety dispositions.

    Membership is deliberately narrow. A condition earns a place here only when
    an automatic retry of the same live read would be *unsafe* -- it would
    attach evidence to the wrong filing, take custody of a document under the
    wrong certificado, or persist an observation AEAT no longer stands behind.
    An input refusal an operator fixes by supplying a different argument is not
    a safety disposition and stays a plain typed refusal.
    """

    JUSTIFICANTE_MATCHES_CAPTURE = "live.justificante.matches_capture"
    JUSTIFICANTE_MATCHES_FILING_RECORD = "live.justificante.matches_filing_record"
    JUSTIFICANTE_FILING_EVIDENCE_ABSENT = "live.justificante.filing_evidence_absent"
    JUSTIFICANTE_FILING_IDENTITY_RESOLVED = "live.justificante.filing_identity_resolved"
    NOTIFICATION_DOCUMENT_MATCHES_ROW = "live.notifications.document_matches_row"
    FILED_OBSERVATION_ACTIVE = "live.filed_observations.observation_active"
    SURFACE_COMPLETED = "live.iva.surface.completed"


def live_read_no_recovery_verdict(
    condition: LiveReadPrecondition,
    *,
    facts: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome = NoRecoveryOutcome.SAFETY,
) -> PreconditionVerdict:
    """Return one explicitly non-actionable outcome for a live-read refusal.

    The facts name exactly what the live read observed; the closed outcome is
    what stops a downstream boundary from manufacturing a recovery command out
    of that observation. No action is bound because none of these conditions
    has a safe automatic remedy -- resolving them is an operator judgement made
    against AEAT's own record.

    Args:
        condition: The live-read condition that failed.
        facts: Stable machine facts, never prose, describing the observation.
        outcome: The closed no-recovery reason. Defaults to
            :attr:`~core.NoRecoveryOutcome.SAFETY`.

    Returns:
        The :class:`~application.operator_actions.PreconditionVerdict` carrying
        the failed condition and its explicit no-recovery outcome.
    """
    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=outcome,
    )


class LiveApplicationError(TerminalPreconditionErrorMixin[PreconditionVerdict], CadrumoError):
    """Raised when live AEAT read orchestration fails.

    Accepts an optional ``precondition_verdict`` so a raise site that has
    already decided a failure has no safe recovery can say so in typed form.
    The verdict is surfaced through ``terminal_precondition_verdict``, the
    attribute the shared CLI exception boundary reads.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        precondition_verdict: PreconditionVerdict | None = None,
    ) -> None:
        """Initialize this public contract."""
        super().__init__(
            message,
            context=context,
            translated_message=translated_message,
            precondition_verdict=precondition_verdict,
        )


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
        """Initialize this public contract."""
        context: dict[str, object] = {"surface": surface, "timeout_ms": timeout_ms}
        if progress_context:
            context["progress"] = dict(progress_context)
        super().__init__(
            message,
            context=context,
            translated_message="errors.error.error_application_live_iva_surface_timeout",
            precondition_verdict=live_read_no_recovery_verdict(
                LiveReadPrecondition.SURFACE_COMPLETED,
                facts={
                    "surface": surface,
                    "timeout_ms": timeout_ms,
                    "progress_observed": bool(progress_context),
                },
            ),
        )
        self.surface = surface
        self.timeout_ms = timeout_ms


def _classify_clave_movil_timeout(exc: ClaveMovilApprovalTimeoutError) -> LiveIvaAcquisitionFailureMode:
    from ...adapters.outbound.aeat.auth.clave_movil_support import ClaveMovilFailureMode

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
    from ...adapters.outbound.aeat.sede.errors import SedeFailureMode

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
    from ...adapters.outbound.aeat.auth.clave_movil_support import (
        ClaveMovilApprovalTimeoutError,
        ClaveMovilConfigurationError,
    )
    from ...adapters.outbound.aeat.sede.errors import SedeError

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
    "LiveReadPrecondition",
    "classify_live_iva_acquisition_failure",
    "live_read_no_recovery_verdict",
]
