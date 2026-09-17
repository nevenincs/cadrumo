"""Application-level live AEAT read workflow errors.

Every refusal raised here carries a registered locale key plus machine facts;
no raise site authors an operator-facing sentence, so ``str(exc)`` renders the
key and the prose is resolved once, per locale, at the presentation boundary.

A subset of these refusals is additionally a *safety* disposition: the live
read observed a fact that makes retrying the same call actively unsafe rather
than merely futile -- a captured justificante that does not belong to the
filing it would be stamped onto, a notification document that belongs to a
different certificado, an AEAT observation AEAT no longer reports as active.
Those raise sites attach a :class:`~application.operator_actions.models.PreconditionVerdict`
whose ``no_recovery_outcome`` is :attr:`~core.operator_action_enums.NoRecoveryOutcome.SAFETY`, so the
CLI boundary projects an explicit "there is deliberately no recovery here"
rather than reaching for a retry the operator should not run.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Protocol, runtime_checkable

from ...core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict


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


@runtime_checkable
class LiveIvaAcquisitionFailureProtocol(Protocol):
    """Application-facing live-IVA failure classification exposed by adapters.

    Outbound adapters own their provider-specific exception classes and local
    tax-portal failure taxonomies.  When one of those exceptions crosses into
    live application orchestration, it exposes this one application-owned
    classification rather than asking the application to identify the
    concrete adapter type or enum that produced it.
    """

    @property
    def live_iva_failure_mode(self) -> LiveIvaAcquisitionFailureMode:
        """Return the application-level mode for this adapter failure."""
        ...


def _runtime_object(value: object) -> object:
    """Capture an adapter-provided value before checking its runtime shape."""
    return value


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
            :attr:`~core.operator_action_enums.NoRecoveryOutcome.SAFETY`.

    Returns:
        The :class:`~application.operator_actions.models.PreconditionVerdict` carrying
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


def classify_live_iva_acquisition_failure(exc: BaseException) -> LiveIvaAcquisitionFailureMode:
    """Resolve an application-level mode from an application or adapter failure.

    Outbound adapters translate their concrete failures into
    :class:`LiveIvaAcquisitionFailureProtocol` before they cross this boundary.
    The application therefore never identifies an adapter exception or reads
    an adapter-owned taxonomy here.

    Returns:
        A :class:`LiveIvaAcquisitionFailureMode` member identifying the
        failure category.
    """
    if isinstance(exc, LiveIvaSurfaceTimeoutError):
        return LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED
    if isinstance(exc, LiveIvaAcquisitionFailureProtocol):
        # Adapter implementations cross this boundary at runtime; retain the
        # defensive check even though the protocol advertises the enum type.
        mode = _runtime_object(exc.live_iva_failure_mode)
        return mode if isinstance(mode, LiveIvaAcquisitionFailureMode) else LiveIvaAcquisitionFailureMode.UNKNOWN
    return LiveIvaAcquisitionFailureMode.UNKNOWN


__all__ = [
    "LiveApplicationError",
    "LiveApplicationInputError",
    "LiveIvaAcquisitionFailureMode",
    "LiveIvaAcquisitionFailureProtocol",
    "LiveIvaSurfaceTimeoutError",
    "LiveReadPrecondition",
    "classify_live_iva_acquisition_failure",
    "live_read_no_recovery_verdict",
]
