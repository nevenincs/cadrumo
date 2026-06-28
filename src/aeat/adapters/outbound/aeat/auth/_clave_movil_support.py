"""Shared support surface for the :class:`ClaveMovilAuthProvider`.

The helpers here keep the live Cl@ve Movil page driver small: they build the
:class:`RemoteStateGuardPolicy` used for allowed browser actions, classify the
configured DNI/NIE identity, redact diagnostic URL fields, and attach the
closed :class:`ClaveMovilFailureMode` taxonomy to provider errors.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from pydantic import SecretStr

from .....core.external_constants import CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE
from .....core.logging import get_logger
from .....domain.calculations.registry import RemoteStateGuardPolicy
from ._errors import AuthConfigurationError, AuthError

if TYPE_CHECKING:
    from .....core.config import Settings

log = get_logger(__name__)

DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS: Final[float] = 5.0
DIAGNOSTIC_NAMESPACE: Final[str] = CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE


def auth_browser_action_policy(settings: Settings) -> RemoteStateGuardPolicy:
    """Build the remote-state guard policy for Cl@ve Movil browser actions.

    The page-flow mixin uses the returned :class:`RemoteStateGuardPolicy`
    before continuing through AEAT's own-name representation gate.
    """
    external = settings.external_constants()
    return RemoteStateGuardPolicy(
        id="aeat-clave-movil-auth-browser-actions",
        evidence_tier="official_source_guidance",
        classification="authenticated_read_surface",
        allowed_hosts=(
            urlsplit(external.aeat.domains.sede).netloc,
            urlsplit(external.aeat.domains.www6).netloc,
            urlsplit(external.aeat.domains.www12).netloc,
        ),
        allowed_browser_action_patterns=external.aeat.live_safety.auth_browser_action_patterns,
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=True,
    )


class ClaveMovilConfigurationError(AuthConfigurationError):
    """Configuration fault for the :class:`ClaveMovilAuthProvider`.

    Raised before or during form driving when required local Cl@ve Movil
    settings, such as DNI/NIE identity or non-QR contrast fields, are missing
    or malformed. It subclasses :class:`AuthConfigurationError` so callers can
    treat it as a local configuration error rather than a live AEAT timeout.
    """


class ClaveMovilApprovalTimeoutError(AuthError):
    """Live Cl@ve Movil timeout carrying provider failure diagnostics.

    :class:`ClaveMovilAuthProvider` and its page-flow mixin raise this
    :class:`AuthError` when AEAT browser state never reaches the expected
    selector, wait state, or post-auth landing page. ``failure_mode`` is stored
    both on the exception and in ``context`` as a :class:`ClaveMovilFailureMode`
    value; timeout contexts may also include a diagnostic id and operator phone
    state reporting options.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        failure_mode: ClaveMovilFailureMode | str | None = None,
        context: dict[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: str | None = None,
    ) -> None:
        enriched_context = dict(context) if context is not None else {}
        if failure_mode is not None:
            failure_mode_value = (
                failure_mode.value if isinstance(failure_mode, ClaveMovilFailureMode) else str(failure_mode)
            )
            enriched_context["failure_mode"] = failure_mode_value
            self.failure_mode: str | None = failure_mode_value
        else:
            self.failure_mode = None
        super().__init__(
            message,
            context=enriched_context or None,
            suggestion=suggestion,
            translated_message=translated_message,
        )


class ClaveMovilFailureMode(StrEnum):
    """Closed failure taxonomy for :class:`ClaveMovilApprovalTimeoutError`."""

    INITIAL_NAVIGATION_TIMEOUT = "initial_navigation_timeout"
    PENDING_PETITION_BLOCKED = "pending_petition_blocked"
    PUSH_WAIT_STATE_NOT_REACHED = "push_wait_state_not_reached"
    AUTH_COMPLETION_TIMEOUT = "auth_completion_timeout"
    APPROVAL_TIMEOUT = "approval_timeout"


_DNI_RE: Final[re.Pattern[str]] = re.compile(r"^\d{8}[A-Z]$", re.IGNORECASE)
_NIE_RE: Final[re.Pattern[str]] = re.compile(r"^[XYZ]\d{7}[A-Z]$", re.IGNORECASE)
_HTML_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<[^>]+>")
_VERIFICATION_CODE_TEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"c[oó]digo\s+de\s+verificaci[oó]n\s+(?P<code>[A-Z0-9]{3,8})",
    re.IGNORECASE,
)


def classify_identity(raw: str) -> str:
    """Return the configured Cl@ve identity kind as ``DNI`` or ``NIE``.

    Values outside the provider-supported DNI/NIE formats raise
    :class:`ClaveMovilConfigurationError`; CIF-style organization identifiers
    are intentionally rejected by the Cl@ve Movil flow.
    """
    value = (raw or "").strip().upper()
    if _DNI_RE.match(value):
        return "DNI"
    if _NIE_RE.match(value):
        return "NIE"
    raise ClaveMovilConfigurationError(
        f"The value you entered (length {len(value)}) is not a valid DNI "
        "(8 digits + letter) or NIE (X/Y/Z + 7 digits + letter). "
        "Check the identity on your document and try again.",
    )


def extract_verification_code_from_html(html: str) -> str | None:
    """Extract the AEAT Cl@ve Movil verification code from rendered HTML."""
    text = _HTML_TAG_RE.sub(" ", html.replace("\xa0", " "))
    normalized = " ".join(text.split())
    match = _VERIFICATION_CODE_TEXT_RE.search(normalized)
    if match is None:
        return None
    return match.group("code").strip().upper() or None


def url_diagnostic(value: str) -> dict[str, object]:
    """Return redacted URL components for auth diagnostic contexts.

    The returned mapping keeps host, path, and query-key names only, so
    :class:`ClaveMovilApprovalTimeoutError` contexts can explain where the
    browser was without persisting query values.
    """
    try:
        parsed = urlsplit(value)
    except ValueError:
        return {"parse": "invalid"}
    query_keys = tuple(part.split("=", 1)[0] for part in parsed.query.split("&") if part)
    return {
        "host": parsed.netloc,
        "path": parsed.path,
        "query_keys": query_keys,
    }


def diagnostic_fingerprint(value: object) -> str:
    """Return a short stable fingerprint for values stored in diagnostics."""
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    text = str(value or "").strip().upper()
    if not text:
        return ""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


def render_progress_banner(
    *,
    verification_code: str | None,
    timeout_seconds: int,
    used_non_qr_fallback: bool,
) -> None:
    """Log the operator-facing progress banner for a fresh Cl@ve attempt."""
    lines = [
        "",
        "-------------------------------------------------------------",
        " AEAT Cl@ve Movil login",
        "-------------------------------------------------------------",
    ]
    if used_non_qr_fallback:
        lines.extend(
            (
                " - AEAT is showing the Cl@ve Movil non-QR confirmation flow.",
                " - Open the Cl@ve app; a push notification may not appear.",
                " - Approve only if the app request matches the AEAT verification code below.",
            ),
        )
    else:
        lines.extend(
            (
                " - A browser window just opened showing a QR code.",
                " - Scan the QR with the Cl@ve app if it is available to you.",
                " - This is the QR branch, not the configured non-QR fallback.",
            ),
        )
    if verification_code:
        lines.extend(("", f" AEAT page verification code: {verification_code}"))
    lines.extend(
        (
            "",
            f" Waiting up to {timeout_seconds // 60}m {timeout_seconds % 60:02d}s for AEAT to complete auth...",
            "-------------------------------------------------------------",
            "",
        ),
    )
    banner = "\n".join(lines)
    log.info("auth.waiting_banner banner=%r", banner)


__all__ = [
    "DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS",
    "DIAGNOSTIC_NAMESPACE",
    "ClaveMovilApprovalTimeoutError",
    "ClaveMovilConfigurationError",
    "ClaveMovilFailureMode",
    "auth_browser_action_policy",
    "classify_identity",
    "diagnostic_fingerprint",
    "extract_verification_code_from_html",
    "render_progress_banner",
    "url_diagnostic",
]
