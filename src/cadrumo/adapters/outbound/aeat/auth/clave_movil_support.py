"""Shared support surface for the :class:`ClaveMovilAuthProvider`.

The helpers here keep the live Cl@ve Movil page driver small: they build the
:class:`RemoteStateGuardPolicy` used for allowed browser actions, classify the
configured DNI/NIE identity, redact diagnostic URL fields, and attach the
closed :class:`ClaveMovilFailureMode` taxonomy to provider errors.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import SecretStr

from .....core import OperatorProgress
from .....core.errors import AuthError, resolve_error_message
from .....core.hashing import sha256_hex
from .....core.identity import IdentityError, validate_spanish_tax_id
from .....core.logging import get_logger
from .....domain.calculations.registry import RemoteStateGuardPolicy
from ....persistence.storage import CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE
from ..operator_progress import emit_operator_progress
from .errors import AuthConfigurationError

if TYPE_CHECKING:
    from .....core.config import Settings

log = get_logger(__name__)

DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS: Final[float] = 5.0
DIAGNOSTIC_NAMESPACE: Final[str] = CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace


def mint_diagnostic_id(captured_at: datetime) -> str:
    """Return a collision-resistant, operator-safe Cl@ve diagnostic identifier."""
    return f"{captured_at:%Y%m%dT%H%M%S}.{captured_at.microsecond:06d}Z-{uuid4().hex}"


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
        # Widen to any subdomain under the AEAT apex so a ``www{n}`` load-balancer
        # dispatch (auth choreography landing on a sibling host beyond the
        # enumerated www6/www12) is tolerated, not refused; the closed
        # action-pattern set stays the sole action gate.
        allowed_host_suffixes=(external.aeat.domains.host_suffix,),
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
        translated_message: str | None = None,
    ) -> None:
        """Initialize the timeout with its safe provider failure context."""
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

    The shape gate selects the kind, then
    :func:`~core.identity.validate_spanish_tax_id` verifies the checksum
    letter. ``raw`` is operator-entered configuration text, so a mistyped
    identifier is refused here rather than surfacing later as an opaque
    rejection from the live AEAT portal.
    """
    value = (raw or "").strip().upper()
    if _DNI_RE.match(value):
        kind = "DNI"
    elif _NIE_RE.match(value):
        kind = "NIE"
    else:
        raise ClaveMovilConfigurationError(
            f"The value you entered (length {len(value)}) is not a valid DNI "
            "(8 digits + letter) or NIE (X/Y/Z + 7 digits + letter). "
            "Check the identity on your document and try again.",
        )
    try:
        validate_spanish_tax_id(value)
    except IdentityError as exc:
        raise ClaveMovilConfigurationError(
            translated_message="errors.auth.clave_movil_identity_checksum",
            context={"detail": resolve_error_message(exc)},
        ) from exc
    return kind


def extract_verification_code_from_html(html: str) -> str | None:
    """Extract the AEAT Cl@ve Movil verification code from rendered HTML."""
    text = _HTML_TAG_RE.sub(" ", html.replace("\xa0", " "))
    normalized = " ".join(text.split())
    match = _VERIFICATION_CODE_TEXT_RE.search(normalized)
    if match is None:
        return None
    code = match.group("code")
    if not isinstance(code, str):
        return None
    return code.strip().upper() or None


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
    digest = sha256_hex(text.encode("utf-8"))[:12]
    return f"sha256:{digest}"


def render_progress_banner(
    *,
    verification_code: str | None,
    timeout_seconds: int,
    used_non_qr_fallback: bool,
) -> None:
    """Log the operator-facing progress banner for a fresh Cl@ve attempt.

    Always records the banner to the runtime log. When an operator progress
    sink is armed for the current context (see
    :func:`~cadrumo.adapters.outbound.aeat.operator_progress.operator_progress_sink`),
    the same banner is additionally handed to that sink so a headless operator
    sees the verification code during the wait rather than having to read the
    log file.
    """
    if used_non_qr_fallback:
        instruction = "Open the Cl@ve app and confirm the pending AEAT request; a push notification may not appear"
    else:
        instruction = "Scan the QR code in the visible browser with the Cl@ve app and confirm the AEAT request"
    if verification_code:
        instruction = f"{instruction}. Verify that code {verification_code} matches in both places"
    progress = OperatorProgress(
        message=f"Cl@ve Movil: {instruction}.",
        timeout_seconds=timeout_seconds,
    )
    log.info("auth.waiting_banner banner=%r", progress.render())
    emit_operator_progress(progress)


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
    "mint_diagnostic_id",
    "render_progress_banner",
    "url_diagnostic",
]
