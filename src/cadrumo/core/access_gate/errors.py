"""Policy errors for the AEAT live-access gate.

All errors inherit from :class:`core.errors.CadrumoError` so callers
have a single root they can catch at integration boundaries.

``LiveSubmitForbiddenError`` lives here (rather than in the
``adapters/outbound/aeat/export`` layer) because:

1. The gate module (``core/access_gate/``) raises it, and
   ``core/`` must remain independent from adapter implementations.
2. The policy "live AEAT submission is permanently forbidden" is
   a foundational invariant, not an adapter implementation detail.

There is no outbound submitter transport anywhere in the tree: no submitter
ABC, no browser-session submitter, no remote filing transport. That absence
is deliberate and is stated here, beside the refusal that enforces it, rather
than in an empty adapter package that shipped and did nothing. File
generation remains a local export concern and writes disk artefacts, never
remote submissions.

See Also:
    :class:`core.access_gate.AeatAccessGate`
        Gate that raises these errors from live-read and live-write checks.
    :class:`LiveSubmitForbiddenError`
        Permanent refusal raised by every attempted live AEAT write.
"""

from __future__ import annotations

from ..errors.hierarchy import CadrumoError


class AccessGateSubmissionError(CadrumoError):
    """Base class for live-write access-gate submission policy failures.

    Attributes:
        translated_message: Optional :class:`core.i18n.Translatable`
            payload carrying a user-facing version of the message.
    """

    def __init__(self, message: str, *, translated_message: str | None = None) -> None:
        """Construct a submission error.

        Args:
            message: English-authoritative error message (logged).
            translated_message: Optional multilingual payload surfaced
                to the CLI and any user-facing consumer.
        """
        super().__init__(message)
        self.translated_message: str | None = translated_message


class AccessGateSubmissionPreflightError(AccessGateSubmissionError):
    """Raised when access-gate preflight rejects a write-shaped operation."""


class LiveSubmitForbiddenError(AccessGateSubmissionPreflightError):
    """Raised when any caller attempts a permanently forbidden live AEAT write."""

    def __init__(
        self,
        message: str = (
            "live AEAT submission is permanently forbidden; use produce -> verify -> "
            "export and upload the file yourself in the AEAT portal"
        ),
        *,
        translated_message: str | None = "errors.locked.locked_access_gate_live_submit_forbidden",
    ) -> None:
        """Construct the permanent live-submit refusal error.

        By default the user-facing text uses the same locale key as the
        central error registry entry bound to this class.
        """
        super().__init__(message, translated_message=translated_message)


class AeatLiveReadNotEnabledError(CadrumoError):
    """Raised when pytest live-read access is required but the test gate is shut.

    Emitted by :meth:`core.access_gate.AeatAccessGate.require_live_read` during pytest
    execution when ``CADRUMO_LIVE_TESTS_ENABLED`` is not set to ``"1"``.
    Operator-facing live reads are controlled by auth/profile/read-only
    guards rather than this test opt-in variable.
    """


class AuthorizationManifestError(CadrumoError):
    """Raised when the multi-year-renta authorization manifest is malformed.

    Emitted by the authorization-manifest loader when an
    ``authorization.d/<modelo>.toml`` fragment cannot be parsed or declares
    an entry that violates the manifest invariants (a single-year enrollment
    claim, a duplicate modelo, an unknown field). An absent fragment directory
    is not an error: default-deny-by-absence yields an empty manifest that
    authorizes zero modelos.
    """


__all__ = [
    "AccessGateSubmissionError",
    "AccessGateSubmissionPreflightError",
    "AeatLiveReadNotEnabledError",
    "AuthorizationManifestError",
    "LiveSubmitForbiddenError",
]
