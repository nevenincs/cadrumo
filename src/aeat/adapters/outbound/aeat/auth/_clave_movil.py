"""Cl@ve Móvil auth provider for AEAT Sede Electrónica.

Implements the :class:`AuthProvider` protocol for the human-in-the-loop
Cl@ve Móvil flow against the live portal. Captures the URL template,
form selectors, and polling endpoints needed to drive the AEAT QR page
to a successful login handshake.

Design summary:

* Cl@ve Móvil is a human-in-the-loop flow. The provider observes only
  AEAT browser state; it cannot know whether the Cl@ve app displayed,
  accepted, rejected, or failed to receive a request unless the
  operator reports that separately.
* The provider opens a headed Playwright window on fresh login so the
  operator can scan the QR visually. Resume-from-storage-state runs
  headlessly because no human interaction is required.
* The persisted session stores Playwright state and provider metadata
  together in the encrypted session object. Kind-namespaced logical
  storage keys keep the Cl@ve and certificate sessions separate.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import re
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import IO, TYPE_CHECKING, Final
from urllib.parse import quote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .....core.classification import SensitivityClass
from .....core.config import Settings as _Settings
from .....core.i18n import tr
from .....core.logging import get_logger
from .....domain.calculations.registry import RemoteOperation, RemoteStateGuardPolicy, assert_remote_operation_allowed
from ....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from .._playwright import PlaywrightError, PlaywrightTimeoutError
from . import _session_store
from ._authenticator import (
    AEAT_SESSION_IDLE_TTL,
    AeatLoginAssertion,
    AeatSession,
    BrowserContextLike,
    BrowserPageLike,
    BrowserSessionFactory,
    BrowserSessionLike,
)
from ._errors import AeatLoginAssertionError, AuthConfigurationError, AuthError
from ._providers import (
    AuthProviderDescription,
    AuthProviderKind,
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
)

if TYPE_CHECKING:
    from playwright.async_api import Dialog

    from .....core.config import Settings


log = get_logger(__name__)

_NAVIGATION_TIMEOUT_MS_DEFAULT: Final[int] = _Settings().aeat_browser_navigation_timeout_ms
_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS: Final[float] = 5.0
_OWN_NAME_REPRESENTATION_ACTION: Final[str] = "representation-gate-own-name-continue"


AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION: Final[int] = 2
"""Distinct from certificate metadata v1 so stale certificate objects are rejected."""

CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE: Final[str] = "aeat.outbound.aeat.auth.clave_movil.diagnostics"
_DIAGNOSTIC_NAMESPACE: Final[str] = CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE


def _auth_browser_action_policy(settings: _Settings) -> RemoteStateGuardPolicy:
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


# NIE: X/Y/Z + 7 digits + letter. DNI: 8 digits + letter.
_DNI_RE: Final[re.Pattern[str]] = re.compile(r"^\d{8}[A-Z]$", re.IGNORECASE)
_NIE_RE: Final[re.Pattern[str]] = re.compile(r"^[XYZ]\d{7}[A-Z]$", re.IGNORECASE)
_HTML_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<[^>]+>")
_VERIFICATION_CODE_TEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"c[oó]digo\s+de\s+verificaci[oó]n\s+(?P<code>[A-Z0-9]{3,8})",
    re.IGNORECASE,
)


class ClaveMovilConfigurationError(AuthConfigurationError):
    """Raised when required Cl@ve Móvil settings are missing or malformed."""


class ClaveMovilApprovalTimeoutError(AuthError):
    """Raised when AEAT browser-side Cl@ve authentication does not complete."""

    def __init__(
        self,
        message: str | None = None,
        *,
        failure_mode: ClaveMovilFailureMode | str | None = None,
        context: dict[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: str | None = None,
    ) -> None:
        """Construct a Cl@ve Móvil authentication failure with stable mode context."""

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
    """Closed Cl@ve Móvil live-auth failure modes."""

    PENDING_PETITION_BLOCKED = "pending_petition_blocked"
    PUSH_WAIT_STATE_NOT_REACHED = "push_wait_state_not_reached"
    AUTH_COMPLETION_TIMEOUT = "auth_completion_timeout"
    APPROVAL_TIMEOUT = "approval_timeout"


class _ClaveMovilSessionMetadata(BaseModel):
    """Encrypted metadata stored with the Cl@ve Móvil storage state.

    Strict mode is ON so malformed metadata (e.g. ``"2"`` where the
    integer ``2`` is expected, or an unknown enum value) fails at
    validation rather than being silently coerced. Datetimes are
    stored as ISO-8601 strings by ``model_dump(mode="json")`` and
    parsed back by Pydantic's built-in datetime validator — the only
    coercion permitted is that round-trip.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: int = Field(default=AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION, ge=2)
    provider_kind: AuthProviderKind = AuthProviderKind.CLAVE_MOVIL
    identity_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_sha256: str = Field(min_length=64, max_length=64)
    used_non_qr_fallback: bool = False
    verification_code: str | None = None
    landing_url: str | None = Field(
        default=None,
        description=(
            "Concrete URL Playwright observed after AEAT dispatched the "
            "successful login. "
            "Used as the probe target by auth-session readiness checks because AEAT's "
            "the Cl@ve selector page is a static dispatch page that always "
            "returns 200 regardless of auth state."
        ),
    )


def _classify_identity(raw: str) -> str:
    """Return ``"DNI"`` or ``"NIE"`` for ``raw``; raise on invalid inputs.

    The error message deliberately does NOT echo the user's raw input —
    DNI/NIE values are PII that would otherwise land in shell history,
    CI logs, and Rich error panels. The length hint is safe to surface
    and is usually enough for the user to spot a typo.
    """
    value = (raw or "").strip().upper()
    if _DNI_RE.match(value):
        return "DNI"
    if _NIE_RE.match(value):
        return "NIE"
    raise ClaveMovilConfigurationError(
        f"The value you entered (length {len(value)}) is not a valid DNI "
        "(8 digits + letter) or NIE (X/Y/Z + 7 digits + letter). "
        "Check the identity on your document and try again."
    )


def _extract_verification_code_from_html(html: str) -> str | None:
    """Return the visible Cl@ve Móvil verification code from rendered HTML."""

    text = _HTML_TAG_RE.sub(" ", html.replace("\xa0", " "))
    normalized = " ".join(text.split())
    match = _VERIFICATION_CODE_TEXT_RE.search(normalized)
    if match is None:
        return None
    return match.group("code").strip().upper() or None


def _url_diagnostic(value: str) -> dict[str, object]:
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


def _diagnostic_fingerprint(value: object) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


def _render_progress_banner(
    *,
    verification_code: str | None,
    timeout_seconds: int,
    used_non_qr_fallback: bool,
    stream: IO[str] = sys.stderr,
) -> None:
    """Print operator instructions while waiting for AEAT browser auth completion."""
    lines = [
        "",
        "─────────────────────────────────────────────────────────────",
        " AEAT Cl@ve Móvil login",
        "─────────────────────────────────────────────────────────────",
    ]
    if used_non_qr_fallback:
        lines.extend(
            (
                " • AEAT is showing the Cl@ve Móvil non-QR confirmation flow.",
                " • Open the Cl@ve app; a push notification may not appear.",
                " • Approve only if the app request matches the AEAT verification code below.",
            )
        )
    else:
        lines.extend(
            (
                " • A browser window just opened showing a QR code.",
                " • Scan the QR with the Cl@ve app if it is available to you.",
                " • This is the QR branch, not the configured non-QR fallback.",
            )
        )
    if verification_code:
        lines.extend(
            (
                "",
                f" AEAT page verification code: {verification_code}",
            )
        )
    lines.extend(
        (
            "",
            f" Waiting up to {timeout_seconds // 60}m {timeout_seconds % 60:02d}s for AEAT to complete auth…",
            "─────────────────────────────────────────────────────────────",
            "",
        )
    )
    for line in lines:
        print(line, file=stream, flush=True)


class ClaveMovilAuthProvider:
    """Cl@ve Móvil implementation of the :class:`AuthProvider` protocol.

    Constructed by :func:`aeat.adapters.outbound.aeat.auth.select_provider` when
    ``kind == AuthProviderKind.CLAVE_MOVIL``. Fresh login can run the
    configured non-QR confirmation flow or the alternate QR flow;
    resume runs headlessly because the stored cookies are sufficient.
    """

    kind: AuthProviderKind = AuthProviderKind.CLAVE_MOVIL

    def __init__(
        self,
        settings: Settings,
        *,
        browser_session_factory: BrowserSessionFactory | None = None,
        navigation_timeout_ms: int = _NAVIGATION_TIMEOUT_MS_DEFAULT,
    ) -> None:
        self._settings = settings
        self._browser_session_factory = browser_session_factory
        self._navigation_timeout_ms = navigation_timeout_ms
        self._lock = asyncio.Lock()
        self._browser_session: BrowserSessionLike | None = None
        self._context: BrowserContextLike | None = None
        self._active_session: AeatSession | None = None

    # ── Protocol surface ────────────────────────────────────────────────────

    async def authenticate(
        self,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> AeatSession:
        """Run the Cl@ve Móvil login flow and return an ``AeatSession``.

        Attempts to resume a cached session first. Falls back to the
        human-in-the-loop QR-scan flow (or the non-QR DNI/NIE +
        contraste fallback, when
        ``AEAT_CLAVE_PREFER_NON_QR=true``).
        """
        async with self._lock:
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "ClaveMovilAuthProvider already has an active session; call close() before authenticating again"
                )
            dni_nie = self._require_identity()
            resume_path = self._storage_state_path()
            if _session_store.exists(resume_path):
                try:
                    return await self._resume_locked(
                        resume_path,
                        browser_session=browser_session,
                        target_url=target_url,
                    )
                except AeatLoginAssertionError as exc:
                    log.info(
                        "ClaveMovilAuthProvider: persisted session unusable; falling back to fresh login (%s)",
                        exc,
                    )
                    self._invalidate_persisted(resume_path)

            return await self._fresh_login_locked(
                dni_nie=dni_nie,
                storage_state_path=resume_path,
                browser_session=browser_session,
                target_url=target_url,
            )

    async def probe_persisted_session(
        self,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> tuple[AeatSession, AeatLoginAssertion]:
        """Probe the encrypted persisted session without side effects.

        Unlike :meth:`authenticate`, this method NEVER falls back to a
        fresh login and NEVER deletes the persisted session —
        even when the probe fails. Callers can
        therefore use it as a pure diagnostic without accidentally
        triggering a fresh operator-mediated Cl@ve request.
        """
        async with self._lock:
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "ClaveMovilAuthProvider already has an active session; call close() first"
                )
            storage_state_path = self._storage_state_path()
            if not _session_store.exists(storage_state_path):
                raise AeatLoginAssertionError("no persisted Cl@ve Móvil session; run `aeat config auth status` first")

            persisted = self._load_persisted(storage_state_path)
            metadata = self._load_metadata(storage_state_path, persisted)
            if metadata.idle_deadline <= datetime.now(UTC):
                raise AeatLoginAssertionError("Cl@ve Móvil session past idle deadline")

            session_like, owns_session = await self._resolve_browser_session(browser_session=browser_session)
            context: BrowserContextLike | None = None
            try:
                context = await session_like.create_context(storage_state=persisted.storage_state)
                session = AeatSession(
                    provider_kind=self.kind,
                    authenticated_at=metadata.authenticated_at,
                    idle_deadline=metadata.idle_deadline,
                    storage_state_path=storage_state_path,
                    identity_nif=metadata.identity_nif,
                    provider_detail=ClaveMovilSessionDetail(
                        dni_nie=metadata.identity_nif,
                        used_non_qr_fallback=metadata.used_non_qr_fallback,
                        verification_code=metadata.verification_code,
                        landing_url=metadata.landing_url,
                    ),
                )
                self._browser_session = session_like
                self._context = context
                self._active_session = session
                # Explicit caller targets need selector dispatch; recorded
                # landing metadata is already carried by the session detail
                # and remains a direct probe.
                assertion = await self.verify(session, target_url=target_url)
                # Refresh idle TTL on successful probe so long-running
                # discovery sessions stay alive without re-auth. AEAT's
                # own 18-minute idle window resets on every authenticated
                # hit to the sede — our persisted deadline should too.
                if assertion.is_valid:
                    refreshed = session.model_copy(
                        update={
                            "authenticated_at": assertion.attempted_at,
                            "idle_deadline": assertion.attempted_at + AEAT_SESSION_IDLE_TTL,
                        }
                    )
                    self._active_session = refreshed
                    refreshed_metadata = metadata.model_copy(
                        update={
                            "authenticated_at": refreshed.authenticated_at,
                            "idle_deadline": refreshed.idle_deadline,
                        }
                    )
                    try:
                        self._persist_session(
                            storage_state_path,
                            storage_state=persisted.storage_state,
                            metadata=refreshed_metadata,
                        )
                    except Exception:
                        log.warning(
                            "ClaveMovilAuthProvider: encrypted session refresh write failed;"
                            " session valid but deadline not persisted",
                            exc_info=True,
                        )
                    return refreshed, assertion
                log.warning(
                    "ClaveMovilAuthProvider: live probe returned invalid assertion status=%s error=%r",
                    assertion.status_code,
                    assertion.error_message,
                )
                return session, assertion
            except Exception:  # cleanup on verify error then re-raise; Playwright+AeatError undocumented
                if context is not None:
                    try:
                        await context.close()
                    except Exception as _exc:
                        log.debug(
                            "ClaveMovilAuthProvider: context.close in verify cleanup suppressed: %s",
                            _exc,
                            exc_info=True,
                        )
                if owns_session:
                    await self._close_browser_session(session_like)
                self._browser_session = None
                self._context = None
                self._active_session = None
                raise

    async def verify(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion:
        """Re-probe that ``session``'s cookies still unlock a Sede page.

        Explicit ``target_url`` probes go through AEAT's selector dispatcher,
        because some Cl@ve-backed apps only establish target-local state when
        dispatched from the selector. When no explicit target is supplied and
        the session metadata has a concrete post-auth landing URL, the probe
        can navigate there directly.
        """
        context = self._context
        if context is None:
            raise AeatLoginAssertionError(
                "ClaveMovilAuthProvider.verify() requires an active browser context; call authenticate() first"
            )
        session_landing_url = (
            session.provider_detail.landing_url
            if isinstance(session.provider_detail, ClaveMovilSessionDetail)
            else None
        )
        resolved_target_url = target_url or session_landing_url
        target_path = (
            self._target_path_from_url(resolved_target_url)
            if resolved_target_url
            else self._settings.aeat_sede_expedientes_path
        )
        probe_url = self._probe_url_for_verification(
            explicit_target_url=target_url,
            resolved_target_url=resolved_target_url,
            target_path=target_path,
        )
        attempted_at = datetime.now(UTC)
        start = time.perf_counter()
        status_code = 0
        landing_url: str | None = None
        session_cookie_present = False
        error_message: str | None = None
        page: BrowserPageLike | None = None
        try:
            page = await context.new_page()
            response = await page.goto(probe_url, timeout=self._navigation_timeout_ms)
            if response is not None:
                status_code = int(response.status)
                landing_url = getattr(page, "url", None)
                if landing_url and self._clave_surface().selector_access_path_marker in landing_url:
                    await self._click_clave_movil_button(page)
                    await self._wait_for_post_auth_landing(page, target_path, self._navigation_timeout_ms)
                    landing_url = getattr(page, "url", None)
                if (
                    200 <= status_code < 400
                    and landing_url
                    and self._is_authenticated_aeat_landing(landing_url=landing_url, target_path=target_path)
                ):
                    session_cookie_present = True
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            log.warning(
                "ClaveMovilAuthProvider.verify: probe navigation failed for %s",
                probe_url,
                exc_info=True,
            )
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception as _exc:
                    log.debug("ClaveMovilAuthProvider.verify: page.close suppressed: %s", _exc, exc_info=True)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        is_valid = session_cookie_present and bool(session.identity_nif)
        return AeatLoginAssertion(
            target_url=probe_url,
            is_valid=is_valid,
            provider_kind=self.kind,
            identity_nif=session.identity_nif,
            status_code=status_code,
            elapsed_ms=elapsed_ms,
            attempted_at=attempted_at,
            error_message=error_message,
            assertion_detail=ClaveMovilLoginAssertionDetail(
                session_cookie_present=session_cookie_present,
                landing_url=landing_url,
            ),
        )

    def describe(self) -> AuthProviderDescription:
        """Return an operator-readable description of the Cl@ve Móvil provider state.

        Severity is set explicitly here so a normal pending state — Cl@ve
        Móvil completion requires an operator-mediated tap on the phone —
        is paired with ``info``, never the loudest ``error`` token
        (round-5 M5). A malformed identity is a real configuration
        fault and surfaces as ``warning``; the no-identity case is an
        undeclared state and surfaces as ``info``.
        """
        dni_nie = (self._settings.aeat_clave_movil_dni_nie or "").strip()
        if not dni_nie:
            return AuthProviderDescription(
                kind=self.kind,
                label="Cl@ve Móvil",
                configured=False,
                available=False,
                health_severity="info",
                health_summary=tr("application.auth.clave_movil.health.identity_unset"),
            )
        try:
            _classify_identity(dni_nie)
        except ClaveMovilConfigurationError as exc:
            return AuthProviderDescription(
                kind=self.kind,
                label="Cl@ve Móvil",
                configured=True,
                available=False,
                identity_nif=dni_nie.upper(),
                health_severity="warning",
                health_summary=str(exc),
            )
        # Cl@ve Móvil requires operator-mediated live auth, so availability
        # means the provider is configured to start that AEAT flow.
        return AuthProviderDescription(
            kind=self.kind,
            label="Cl@ve Móvil",
            configured=True,
            available=True,
            identity_nif=dni_nie.upper(),
            health_severity="info",
            health_summary=tr("application.auth.clave_movil.health.operator_completion_required"),
        )

    async def close(self) -> None:
        """Tear down any retained Playwright context + browser session."""
        async with self._lock:
            await self._drop_context()
            await self._close_browser_session(self._browser_session)
            self._browser_session = None
            self._active_session = None

    # ── Identity + target helpers ───────────────────────────────────────────

    def _require_identity(self) -> str:
        raw = self._settings.aeat_clave_movil_dni_nie
        if not raw:
            raise ClaveMovilConfigurationError(
                "AEAT_CLAVE_MOVIL_DNI_NIE is not set; set it to your DNI or NIE "
                "before running `aeat config auth configure --provider clave_movil`."
            )
        _classify_identity(raw)
        return raw.strip().upper()

    def _default_target_url(self) -> str:
        external = self._settings.external_constants()
        return f"{external.aeat.domains.www6}{external.aeat.sede_paths.expedientes_resumen}"

    def _selector_url(self, target_path: str) -> str:
        template = self._settings.aeat_clave_sede_access_url_template
        return template.format(target=quote(target_path, safe=""))

    def _clave_surface(self):
        return self._settings.external_constants().aeat.clave_movil

    def _probe_url_for_verification(
        self,
        *,
        explicit_target_url: str | None,
        resolved_target_url: str | None,
        target_path: str,
    ) -> str:
        if explicit_target_url:
            return self._selector_url(target_path)
        if resolved_target_url and target_path in resolved_target_url:
            return resolved_target_url
        return resolved_target_url or self._selector_url(target_path)

    def _is_authenticated_aeat_landing(self, *, landing_url: str, target_path: str) -> bool:
        """Return True for a protected AEAT page reached after Cl@ve dispatch."""

        external = self._settings.external_constants()
        surface = external.aeat.clave_movil
        try:
            parsed = urlsplit(landing_url)
        except ValueError:
            return False
        host = parsed.netloc.casefold()
        host_suffix = external.aeat.domains.host_suffix.casefold()
        if host != host_suffix and not host.endswith(f".{host_suffix}"):
            return False
        path = parsed.path.casefold()
        if external.aeat.sede_paths.auth_gate_4033.casefold() in path:
            return False
        clave_path_markers = (
            surface.selector_access_path_marker,
            surface.dialogo_representacion_path_marker,
            surface.obtener_clave_movil_path_marker,
            surface.obtener_clave_movil_qr_path_marker,
            surface.cancelar_clave_movil_path_marker,
        )
        if any(marker.casefold() in path for marker in clave_path_markers):
            return False
        if target_path in landing_url:
            return True
        return self._same_aeat_application_path(landing_path=path, target_path=target_path)

    @staticmethod
    def _same_aeat_application_path(*, landing_path: str, target_path: str) -> bool:
        target_path_only = urlsplit(target_path).path.casefold()
        landing_parts = tuple(part for part in landing_path.split("/") if part)
        target_parts = tuple(part for part in target_path_only.split("/") if part)
        if len(landing_parts) < 2 or len(target_parts) < 2:
            return False
        if target_parts[0] == "wlpl":
            return landing_parts[:2] == target_parts[:2]
        if target_parts[0] == "sede":
            return landing_parts[:2] == target_parts[:2]
        return False

    def _attempt_context(self) -> dict[str, object]:
        identity = (self._settings.aeat_clave_movil_dni_nie or "").strip()
        try:
            identity_kind = _classify_identity(identity)
        except ClaveMovilConfigurationError:
            identity_kind = "invalid_or_missing"
        auth_mode = "non_qr" if self._settings.aeat_clave_prefer_non_qr else "qr"
        auth_route = (
            "clave_movil_non_qr_request"
            if self._settings.aeat_clave_prefer_non_qr
            else "clave_movil_qr_request"
        )
        context: dict[str, object] = {
            "auth_mode": auth_mode,
            "auth_route": auth_route,
            "identity_kind": identity_kind,
            "clave_identity_configured": bool(identity),
            "clave_identity_fingerprint": _diagnostic_fingerprint(identity),
            "dni_fecha_configured": bool((self._settings.aeat_clave_movil_dni_fecha or "").strip()),
            "dni_fecha_fingerprint": _diagnostic_fingerprint(self._settings.aeat_clave_movil_dni_fecha),
            "nie_soporte_configured": bool((self._settings.aeat_clave_movil_nie_soporte or "").strip()),
            "nie_soporte_fingerprint": _diagnostic_fingerprint(self._settings.aeat_clave_movil_nie_soporte),
            "prefer_non_qr": self._settings.aeat_clave_prefer_non_qr,
            "headless": self._settings.aeat_browser_headless,
            "timeout_ms": self._settings.aeat_clave_movil_timeout_ms,
            "certificate_path_configured": self._settings.aeat_certificate_path is not None,
            "certificate_password_configured": self._settings.aeat_certificate_password_secret is not None,
            "certificate_backend": self._settings.aeat_certificate_backend.value,
            "certificate_file_present": bool(
                self._settings.aeat_certificate_path is not None
                and self._settings.aeat_certificate_path.is_file()
            ),
            "certificate_path_fingerprint": _diagnostic_fingerprint(self._settings.aeat_certificate_path),
        }
        context.update(self._active_profile_diagnostic_context(identity))
        return context

    def _active_profile_diagnostic_context(self, provider_identity: str) -> dict[str, object]:
        try:
            from .....adapters.persistence.storage import (
                activate_master_key_provider,
                get_master_key_provider,
                has_active_bucket_session,
            )
            from .....application.user_profile._orchestration import build_lifecycle_service
            from .....application.user_profile._projections import record_to_path_values, record_to_values
            from .....application.workflow._models import resolve_active_bucket_id
            from .....application.workflow._profile_bucket_scan import read_profile_bucket_by_id
            from .....core.config import override_settings
            from .....domain.user_profile import ProfileNotFoundError

            bucket_id = resolve_active_bucket_id()
            pointer = read_profile_bucket_by_id(bucket_id) if bucket_id else None
            context: dict[str, object] = {
                "active_profile_id": bucket_id or "",
                "active_profile_label": pointer.label if pointer is not None else "",
                "active_profile_registered": pointer is not None,
                "profile_record_present": False,
                "profile_tax_id_present": False,
                "profile_tax_id_fingerprint": "",
                "identity_alignment": "profile_tax_id_missing",
            }
            if bucket_id is None:
                context["identity_alignment"] = "no_active_profile"
                return context
            try:
                if has_active_bucket_session():
                    record = build_lifecycle_service(bucket_id=bucket_id).read(bucket_id)
                else:
                    with override_settings(aeat_active_profile=bucket_id):
                        service = build_lifecycle_service(bucket_id=bucket_id)
                        with activate_master_key_provider(
                            get_master_key_provider(),
                            fallback_bucket_id=bucket_id,
                        ):
                            record = service.read(bucket_id)
            except ProfileNotFoundError:
                return context

            path_values = record_to_path_values(record)
            profile_identity = str(path_values.get("identity.tax_id") or "").strip().upper()
            if not profile_identity:
                selector_values = record_to_values(record)
                profile_identity = str(selector_values.get("tax.id") or "").strip().upper()
            context["profile_record_present"] = True
            context["profile_tax_id_present"] = bool(profile_identity)
            context["profile_tax_id_fingerprint"] = _diagnostic_fingerprint(profile_identity)
            if not provider_identity:
                context["identity_alignment"] = "clave_identity_missing"
            elif not profile_identity:
                context["identity_alignment"] = "profile_tax_id_missing"
            elif profile_identity == provider_identity.strip().upper():
                context["identity_alignment"] = "matches"
            else:
                context["identity_alignment"] = "mismatch"
            return context
        except Exception as exc:
            log.debug("ClaveMovilAuthProvider: profile diagnostic context unavailable: %s", exc, exc_info=True)
            return {
                "active_profile_id": "",
                "active_profile_label": "",
                "active_profile_registered": False,
                "profile_record_present": False,
                "profile_tax_id_present": False,
                "profile_tax_id_fingerprint": "",
                "identity_alignment": "profile_context_unavailable",
            }

    # ── Lifecycle helpers ───────────────────────────────────────────────────

    async def _resolve_browser_session(
        self,
        *,
        browser_session: BrowserSessionLike | None,
    ) -> tuple[BrowserSessionLike, bool]:
        if browser_session is not None:
            return browser_session, False
        if self._browser_session_factory is None:
            raise AeatLoginAssertionError(
                "ClaveMovilAuthProvider was constructed without a browser "
                "session factory; pass one via select_provider(..., "
                "browser_session_factory=...) or provide a live "
                "BrowserSessionLike to authenticate()."
            )
        session = await self._browser_session_factory(self._settings)
        return session, True

    async def _drop_context(self) -> None:
        context = self._context
        self._context = None
        if context is None:
            return
        try:
            await context.close()
        except Exception as _exc:
            log.debug("ClaveMovilAuthProvider: context.close in _drop_context suppressed: %s", _exc, exc_info=True)

    @staticmethod
    async def _close_browser_session(session: BrowserSessionLike | None) -> None:
        if session is None:
            return
        close = getattr(session, "close", None)
        if not callable(close):
            return
        try:
            result = close()
            if asyncio.iscoroutine(result):
                await result
        except Exception:  # BrowserSessionLike.close() exception surface is undocumented; teardown must not abort
            log.warning("ClaveMovilAuthProvider: browser session close failed", exc_info=True)

    # ── Encrypted session state ────────────────────────────────────────────

    def _storage_state_path(self) -> Path:
        from .....application.workflow._models import require_active_bucket_id

        token_dir = self._settings.aeat_token_dir
        profile = require_active_bucket_id()
        return token_dir / f"{profile}-clave-movil-storage.json"

    @staticmethod
    def _persist_session(
        storage_state_path: Path,
        *,
        storage_state: Mapping[str, object],
        metadata: _ClaveMovilSessionMetadata,
    ) -> None:
        _session_store.save(
            storage_state_path,
            storage_state=storage_state,
            metadata=metadata.model_dump(mode="json"),
        )

    def _load_persisted(self, storage_state_path: Path) -> _session_store.PersistedBrowserSession:
        persisted = _session_store.load(storage_state_path)
        if persisted is None:
            raise AeatLoginAssertionError("no persisted Cl@ve Móvil session; run `aeat config auth status` first")
        return persisted

    @staticmethod
    def _load_metadata(
        storage_state_path: Path,
        persisted: _session_store.PersistedBrowserSession,
    ) -> _ClaveMovilSessionMetadata:
        try:
            return _ClaveMovilSessionMetadata.model_validate_json(json.dumps(persisted.metadata, default=str))
        except (ValueError, ValidationError) as exc:
            raise AeatLoginAssertionError(f"Cl@ve Móvil metadata invalid for {storage_state_path}: {exc}") from exc

    def _invalidate_persisted(self, storage_state_path: Path) -> None:
        _session_store.delete(storage_state_path)

    # ── Flow ────────────────────────────────────────────────────────────────

    async def _fresh_login_locked(
        self,
        *,
        dni_nie: str,
        storage_state_path: Path,
        browser_session: BrowserSessionLike | None,
        target_url: str | None,
    ) -> AeatSession:
        target = target_url or self._default_target_url()
        target_path = self._target_path_from_url(target)
        selector_url = self._selector_url(target_path)
        attempt_context = self._attempt_context()

        session_like, owns_session = await self._resolve_browser_session(browser_session=browser_session)
        context: BrowserContextLike | None = None
        page: BrowserPageLike | None = None
        try:
            context = await session_like.create_context()
            page = await context.new_page()
            self._attach_dialog_autodismiss(page)
            await page.goto(selector_url, timeout=self._navigation_timeout_ms)

            use_non_qr = self._settings.aeat_clave_prefer_non_qr
            verification_code: str | None = None
            log.info(
                "ClaveMovilAuthProvider: starting fresh login mode=%s route=%s identity_kind=%s "
                "identity_alignment=%s profile_present=%s headless=%s",
                attempt_context["auth_mode"],
                attempt_context["auth_route"],
                attempt_context["identity_kind"],
                attempt_context["identity_alignment"],
                attempt_context["profile_tax_id_present"],
                attempt_context["headless"],
            )

            if use_non_qr:
                await self._drive_non_qr_fallback(page, dni_nie)
            else:
                await self._click_clave_movil_button(page)
                await self._raise_if_pending_request_error(page)
            verification_code = await self._extract_verification_code(page)
            await self._assert_push_wait_state(
                page,
                target_path=target_path,
                verification_code=verification_code,
                used_non_qr_fallback=use_non_qr,
            )

            timeout_ms = int(self._settings.aeat_clave_movil_timeout_ms)
            _render_progress_banner(
                verification_code=verification_code,
                timeout_seconds=timeout_ms // 1000,
                used_non_qr_fallback=use_non_qr,
            )

            try:
                await self._wait_for_post_auth_landing(page, target_path, timeout_ms)
            except (TimeoutError, PlaywrightTimeoutError) as exc:
                diagnostic_id = await self._dump_diagnostic(page, reason="post-auth-landing-timeout")
                await self._cancel_pending_auth_request(page)
                current_url = getattr(page, "url", "") or ""
                raise ClaveMovilApprovalTimeoutError(
                    f"Cl@ve Móvil browser authentication did not complete after {timeout_ms // 1000} seconds. "
                    "The driver observed the AEAT browser page but cannot infer the phone/app state.",
                    failure_mode=ClaveMovilFailureMode.AUTH_COMPLETION_TIMEOUT,
                    context={
                        "timeout_ms": timeout_ms,
                        "current_url": _url_diagnostic(current_url),
                        "target_path": target_path,
                        "diagnostic_id": diagnostic_id,
                        "phone_state": "unknown",
                        "operator_report_required": True,
                        "operator_report_options": (
                            "app_prompted_and_accepted",
                            "app_prompted_not_accepted",
                            "app_did_not_prompt",
                            "operator_did_not_check",
                        ),
                        **attempt_context,
                        "verification_code_present": bool(verification_code),
                    },
                    suggestion=(
                        "`aeat config auth diagnostics report "
                        f"{diagnostic_id} --phone-state app_did_not_prompt` if no Cl@ve app prompt appeared, "
                        "or use app_prompted_and_accepted / app_prompted_not_accepted / operator_did_not_check "
                        "for the observed phone state."
                    ),
                ) from exc

            storage_state = await context.storage_state()
            landing_url = getattr(page, "url", None)
            await page.close()
        except Exception as exc:
            if page is not None and not self._exception_already_has_diagnostic(exc):
                try:
                    await self._dump_diagnostic(page, reason=f"fresh-login-exception:{type(exc).__name__}")
                except Exception as _exc:
                    log.debug("ClaveMovilAuthProvider: diagnostic dump suppressed: %s", _exc, exc_info=True)
            if context is not None:
                try:
                    await context.close()
                except Exception as _exc:
                    log.debug(
                        "ClaveMovilAuthProvider: context.close in fresh-login cleanup suppressed: %s",
                        _exc,
                        exc_info=True,
                    )
            if owns_session:
                await self._close_browser_session(session_like)
            raise

        authenticated_at = datetime.now(UTC)
        idle_deadline = authenticated_at + AEAT_SESSION_IDLE_TTL
        try:
            metadata = _ClaveMovilSessionMetadata(
                identity_nif=dni_nie,
                authenticated_at=authenticated_at,
                idle_deadline=idle_deadline,
                storage_state_sha256=_session_store.storage_state_sha256(storage_state),
                used_non_qr_fallback=self._settings.aeat_clave_prefer_non_qr,
                verification_code=verification_code,
                landing_url=landing_url,
            )
            self._persist_session(
                storage_state_path,
                storage_state=storage_state,
                metadata=metadata,
            )
        except Exception:
            # If the encrypted save fails, remove any partial object so the
            # next authenticate() call sees a clean slate and runs fresh.
            self._invalidate_persisted(storage_state_path)
            raise

        session = AeatSession(
            provider_kind=self.kind,
            authenticated_at=authenticated_at,
            idle_deadline=idle_deadline,
            storage_state_path=storage_state_path,
            identity_nif=dni_nie,
            provider_detail=ClaveMovilSessionDetail(
                dni_nie=dni_nie,
                used_non_qr_fallback=self._settings.aeat_clave_prefer_non_qr,
                verification_code=verification_code,
                landing_url=landing_url,
            ),
        )
        self._browser_session = session_like
        self._context = context
        self._active_session = session
        log.info(
            "ClaveMovilAuthProvider: authenticated non_qr=%s landing=%s",
            self._settings.aeat_clave_prefer_non_qr,
            landing_url,
        )
        return session

    async def _resume_locked(
        self,
        storage_state_path: Path,
        *,
        browser_session: BrowserSessionLike | None,
        target_url: str | None,
    ) -> AeatSession:
        persisted = self._load_persisted(storage_state_path)
        metadata = self._load_metadata(storage_state_path, persisted)
        if metadata.idle_deadline <= datetime.now(UTC):
            raise AeatLoginAssertionError("Cl@ve Móvil session past idle deadline")
        observed_sha256 = persisted.storage_state_sha256
        if observed_sha256 != metadata.storage_state_sha256:
            raise AeatLoginAssertionError("Cl@ve Móvil storage-state hash mismatch")

        session_like, owns_session = await self._resolve_browser_session(browser_session=browser_session)
        context: BrowserContextLike | None = None
        try:
            context = await session_like.create_context(
                storage_state=persisted.storage_state,
            )
            session = AeatSession(
                provider_kind=self.kind,
                authenticated_at=metadata.authenticated_at,
                idle_deadline=metadata.idle_deadline,
                storage_state_path=storage_state_path,
                identity_nif=metadata.identity_nif,
                provider_detail=ClaveMovilSessionDetail(
                    dni_nie=metadata.identity_nif,
                    used_non_qr_fallback=metadata.used_non_qr_fallback,
                    verification_code=metadata.verification_code,
                    landing_url=metadata.landing_url,
                ),
            )
            self._browser_session = session_like
            self._context = context
            self._active_session = session

            assertion = await self.verify(session, target_url=target_url)
            if not assertion.is_valid:
                raise AeatLoginAssertionError(
                    "Cl@ve Móvil resume failed live verification: "
                    f"status={assertion.status_code} error={assertion.error_message!r}"
                )
            refreshed = session.model_copy(
                update={
                    "authenticated_at": assertion.attempted_at,
                    "idle_deadline": assertion.attempted_at + AEAT_SESSION_IDLE_TTL,
                }
            )
            self._active_session = refreshed
            refreshed_metadata = metadata.model_copy(
                update={
                    "authenticated_at": refreshed.authenticated_at,
                    "idle_deadline": refreshed.idle_deadline,
                }
            )
            self._persist_session(
                storage_state_path,
                storage_state=persisted.storage_state,
                metadata=refreshed_metadata,
            )
            log.info(
                "ClaveMovilAuthProvider: resumed landing=%s",
                assertion.assertion_detail.landing_url
                if isinstance(assertion.assertion_detail, ClaveMovilLoginAssertionDetail)
                else None,
            )
            return refreshed
        except Exception:  # cleanup on resume error then re-raise; Playwright+AeatError undocumented
            if context is not None:
                try:
                    await context.close()
                except Exception as _exc:
                    log.debug(
                        "ClaveMovilAuthProvider: context.close in resume cleanup suppressed: %s",
                        _exc,
                        exc_info=True,
                    )
            self._browser_session = None
            self._context = None
            self._active_session = None
            if owns_session:
                await self._close_browser_session(session_like)
            raise

    # ── Page-driving helpers ────────────────────────────────────────────────

    @staticmethod
    def _target_path_from_url(target_url: str) -> str:
        """Return just the path portion of ``target_url`` (the selector ``ref=``)."""
        try:
            parsed = urlsplit(target_url)
        except ValueError:
            return target_url
        if not parsed.scheme or not parsed.netloc:
            return target_url
        tail = parsed.path or "/"
        if parsed.query:
            tail = f"{tail}?{parsed.query}"
        return tail

    async def _click_clave_movil_button(self, page: BrowserPageLike) -> None:
        click = getattr(page, "click", None)
        if click is None:
            raise AeatLoginAssertionError("Playwright page does not expose click(); cannot drive Cl@ve Móvil entry")
        await click(self._clave_surface().authorize_button_selector)

    async def _extract_verification_code(self, page: BrowserPageLike) -> str | None:
        wait_for = getattr(page, "wait_for_selector", None)
        text_content = getattr(page, "text_content", None)
        if wait_for is not None and text_content is not None:
            selector = self._clave_surface().verification_code_selector
            try:
                await wait_for(selector, timeout=int(self._settings.aeat_browser_selector_probe_timeout_ms))
                raw = await text_content(selector)
            except (PlaywrightTimeoutError, PlaywrightError):
                raw = None
            if raw is not None and raw.strip():
                return raw.strip()

        content = getattr(page, "content", None)
        if content is None:
            return None
        try:
            html = await content()
        except PlaywrightError:
            return None
        return _extract_verification_code_from_html(html)

    async def _drive_non_qr_fallback(self, page: BrowserPageLike, dni_nie: str) -> None:
        click = getattr(page, "click", None)
        fill = getattr(page, "fill", None)
        type_text = getattr(page, "type", None)
        wait_for = getattr(page, "wait_for_selector", None)
        if click is None or fill is None or type_text is None or wait_for is None:
            raise AeatLoginAssertionError(
                "Playwright page missing click/fill/type/wait_for_selector; "
                "cannot drive the Cl@ve Móvil non-QR fallback"
            )
        surface = self._clave_surface()
        await click(surface.authorize_button_selector)
        await wait_for(
            surface.non_qr_link_selector,
            timeout=self._navigation_timeout_ms,
        )
        await click(surface.non_qr_link_selector)
        await wait_for(surface.nif_input_selector, timeout=self._navigation_timeout_ms)
        await fill(surface.nif_input_selector, "")
        await type_text(surface.nif_input_selector, dni_nie)
        kind = _classify_identity(dni_nie)
        if kind == "DNI":
            await wait_for(surface.dni_fecha_visible_selector, timeout=self._navigation_timeout_ms)
            fecha = (self._settings.aeat_clave_movil_dni_fecha or "").strip()
            if not fecha:
                raise ClaveMovilConfigurationError(
                    "AEAT_CLAVE_MOVIL_DNI_FECHA is required for the non-QR DNI fallback (format YYYY-MM-DD)."
                )
            await type_text(surface.dni_fecha_input_selector, fecha)
        else:
            await wait_for(surface.nie_soporte_visible_selector, timeout=self._navigation_timeout_ms)
            soporte = (self._settings.aeat_clave_movil_nie_soporte or "").strip()
            if not soporte:
                raise ClaveMovilConfigurationError(
                    "AEAT_CLAVE_MOVIL_NIE_SOPORTE is required for the non-QR NIE fallback."
                )
            await type_text(surface.nie_soporte_input_selector, soporte)
        await wait_for(surface.continue_button_visible_selector, timeout=self._navigation_timeout_ms)
        await click(surface.continue_button_selector)
        await self._raise_if_pending_request_error(page)

    async def _assert_push_wait_state(
        self,
        page: BrowserPageLike,
        *,
        target_path: str,
        verification_code: str | None,
        used_non_qr_fallback: bool,
    ) -> None:
        """Require an AEAT-observed Cl@ve waiting state before waiting further."""

        await self._raise_if_pending_request_error(page)
        current_url = getattr(page, "url", "") or ""
        surface = self._clave_surface()
        if target_path in current_url and surface.selector_access_path_marker not in current_url:
            return
        if verification_code:
            return

        content = getattr(page, "content", None)
        html = ""
        if content is not None:
            try:
                html = await content()
            except PlaywrightError:
                html = ""
        normalized = " ".join(html.replace("\xa0", " ").split()).lower()
        wait_markers = tuple(marker.lower() for marker in surface.wait_text_markers)
        url_markers = (
            surface.obtener_clave_movil_path_marker,
            surface.obtener_clave_movil_qr_path_marker,
        )
        has_wait_marker = any(marker in normalized for marker in wait_markers)
        has_wait_url = any(marker in current_url for marker in url_markers)
        if has_wait_marker or has_wait_url:
            log.info(
                "ClaveMovilAuthProvider: detected Cl@ve wait state url=%s non_qr=%s verification_code_present=%s",
                current_url,
                used_non_qr_fallback,
                bool(verification_code),
            )
            return

        diagnostic_id = await self._dump_diagnostic(page, reason="push-wait-state-not-reached")
        raise ClaveMovilApprovalTimeoutError(
            "AEAT Cl@ve Móvil did not reach a browser-observed confirmation waiting state "
            "after submitting the login form.",
            failure_mode=ClaveMovilFailureMode.PUSH_WAIT_STATE_NOT_REACHED,
            context={
                "reason": "aeat-clave-movil-wait-state-not-reached",
                "current_url": _url_diagnostic(current_url),
                "target_path": target_path,
                "used_non_qr_fallback": used_non_qr_fallback,
                "verification_code_present": bool(verification_code),
                "diagnostic_id": diagnostic_id,
            },
            suggestion=(
                "Inspect the encrypted Cl@ve diagnostic artefact, then retry with QR mode "
                "(AEAT_CLAVE_PREFER_NON_QR=false) if the non-QR form no longer reaches the wait page."
            ),
        )

    async def _raise_if_pending_request_error(self, page: BrowserPageLike) -> None:
        """Detect AEAT's 'petición pendiente' refusal page and fail fast.

        After the configured continue button is clicked, AEAT sometimes returns the
        non-QR landing page in an error state: "No ha sido posible
        generar una nueva petición de autenticación con Cl@ve Móvil.
        Por su seguridad, acceda a la APP Cl@ve … y rechace la petición
        pendiente — o espere a que caduque tras un máximo de 5 minutos."
        This happens when a prior login left an unresolved request
        alive server-side. The polling loop that normally redirects on
        browser-side completion is never rendered, so the authenticator would otherwise
        sit on the page until the outer timeout fires. Fail fast with a
        clear remediation message.
        """
        content = getattr(page, "content", None)
        if content is None:
            return
        try:
            html = await content()
        except PlaywrightError:
            return
        normalized = " ".join(html.replace("\xa0", " ").split()).lower()
        pending_markers = self._clave_surface().pending_petition_text_markers
        if any(marker in normalized for marker in pending_markers):
            diagnostic_id = await self._dump_diagnostic(page, reason="pending-request-refusal")
            raise ClaveMovilApprovalTimeoutError(
                "AEAT refused to issue a new Cl@ve Móvil authentication request: a prior "
                "authentication request is still pending server-side.",
                failure_mode=ClaveMovilFailureMode.PENDING_PETITION_BLOCKED,
                context={
                    "reason": "aeat-refused-new-clave-movil-petition",
                    "url": getattr(page, "url", "") or "",
                    "detected_markers": tuple(marker for marker in pending_markers if marker in normalized),
                    "diagnostic_id": diagnostic_id,
                },
                suggestion=tr("adapters.aeat.clave_movil.suggestions.reject_pending_request"),
                translated_message="adapters.aeat.clave_movil.errors.pending_petition_blocked",
            )

    async def _cancel_pending_auth_request(self, page: BrowserPageLike) -> None:
        """Best-effort cancellation for a Cl@ve request left open by timeout."""

        current_url = getattr(page, "url", "") or ""
        if self._clave_surface().obtener_clave_movil_path_marker not in current_url:
            return
        evaluate = getattr(page, "evaluate", None)
        try:
            if evaluate is not None:
                cancelled = await asyncio.wait_for(
                    evaluate(
                        """
                        () => {
                          const button = document.querySelector("#botonCancelar");
                          if (button && typeof button.click === "function") {
                            button.click();
                            return true;
                          }
                          const clave = window.ObtenerClaveMovil;
                          if (clave && typeof clave.cancelarPeticion === "function") {
                            clave.cancelarPeticion();
                            return true;
                          }
                          return false;
                        }
                        """
                    ),
                    timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                )
                if cancelled and await self._wait_for_cancel_confirmation(page):
                    log.info("ClaveMovilAuthProvider: confirmed cancellation of pending Cl@ve request")
                    return
            click = getattr(page, "click", None)
            if click is not None:
                await asyncio.wait_for(
                    click("#botonCancelar"),
                    timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                )
                if await self._wait_for_cancel_confirmation(page):
                    log.info("ClaveMovilAuthProvider: confirmed cancellation of pending Cl@ve request")
                    return
            log.warning("ClaveMovilAuthProvider: pending Cl@ve cancellation was requested but not confirmed")
        except Exception as exc:  # cancellation is cleanup; preserve the original auth timeout
            log.warning("ClaveMovilAuthProvider: pending Cl@ve cancellation failed: %s", exc)

    async def _wait_for_cancel_confirmation(self, page: BrowserPageLike) -> bool:
        wait_for_response = getattr(page, "wait_for_response", None)
        if wait_for_response is not None:
            surface = self._clave_surface()
            try:
                response = await asyncio.wait_for(
                    wait_for_response(
                        lambda candidate: surface.cancelar_clave_movil_path_marker
                        in str(getattr(candidate, "url", ""))
                        and int(getattr(candidate, "status", 599)) < 400,
                        timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS * 1000,
                    ),
                    timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                )
                return int(getattr(response, "status", 599)) < 400
            except (TimeoutError, PlaywrightTimeoutError, PlaywrightError):
                return False

        wait_for_timeout = getattr(page, "wait_for_timeout", None)
        if wait_for_timeout is not None:
            with contextlib.suppress(TimeoutError, PlaywrightTimeoutError):
                await asyncio.wait_for(
                    wait_for_timeout(1000),
                    timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                )
        else:
            await asyncio.sleep(1)
        return not await self._page_still_shows_pending_request(page)

    async def _page_still_shows_pending_request(self, page: BrowserPageLike) -> bool:
        content = getattr(page, "content", None)
        if content is None:
            return True
        try:
            html = await content()
        except PlaywrightError:
            return True
        normalized = " ".join(html.replace("\xa0", " ").split()).lower()
        pending_markers = self._clave_surface().pending_petition_text_markers
        return any(marker in normalized for marker in pending_markers)

    @staticmethod
    def _attach_dialog_autodismiss(page: BrowserPageLike) -> None:
        """Auto-accept any JS dialog AEAT pops during login.

        Playwright blocks the page until ``dialog`` events are handled;
        AEAT sometimes surfaces cookie / representation-consent modals
        that would otherwise silently stall the authenticator.
        """
        on = getattr(page, "on", None)
        if on is None:
            return

        pending: set[asyncio.Task[object]] = set()

        def _handle(dialog: Dialog) -> None:
            accept = getattr(dialog, "accept", None)
            if accept is None:
                return
            log.debug(
                "ClaveMovilAuthProvider: auto-accepting dialog type=%s message=%r",
                getattr(dialog, "type", "?"),
                getattr(dialog, "message", ""),
            )
            result = accept()
            if asyncio.iscoroutine(result):
                task = asyncio.create_task(result)
                pending.add(task)
                task.add_done_callback(pending.discard)

        on("dialog", _handle)

    async def _dump_diagnostic(self, page: BrowserPageLike, *, reason: str) -> str | None:
        """Capture page URL + HTML + screenshot on login failure for offline triage.

        Stores artefacts as encrypted session-class objects so a human
        can inspect what AEAT served at the moment the authenticator
        gave up without leaving bearer-equivalent page state in
        plaintext files.
        """
        try:
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            url = getattr(page, "url", "") or ""
            payload: dict[str, object] = {
                "diagnostic_id": ts,
                "reason": reason,
                "url": url,
                "captured_at": datetime.now(UTC).isoformat(),
                "auth_attempt": self._attempt_context(),
            }
            content = getattr(page, "content", None)
            if content is not None:
                try:
                    payload["html"] = await asyncio.wait_for(
                        content(),
                        timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                    )
                except (TimeoutError, PlaywrightTimeoutError):
                    payload["html_capture_error"] = "timeout"
            screenshot = getattr(page, "screenshot", None)
            if screenshot is not None:
                try:
                    image = await asyncio.wait_for(
                        screenshot(full_page=True),
                        timeout=_DIAGNOSTIC_CAPTURE_TIMEOUT_SECONDS,
                    )
                    if isinstance(image, (bytes, bytearray)):
                        payload["screenshot_png_base64"] = base64.b64encode(bytes(image)).decode("ascii")
                except (TimeoutError, PlaywrightTimeoutError):
                    payload["screenshot_capture_error"] = "timeout"
            secure_object_repository_for_active_bucket().save(
                namespace=_DIAGNOSTIC_NAMESPACE,
                object_key=ts,
                classification=SensitivityClass.SESSION,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=json.dumps(payload, sort_keys=True, default=str).encode("utf-8"),
            )
            log.warning(
                "ClaveMovilAuthProvider: encrypted diagnostic captured id=%s (url=%s reason=%s)",
                ts,
                url,
                reason,
            )
            return ts
        except Exception:  # diagnostic dump is best-effort; Playwright screenshot/content errors must not raise
            log.warning("ClaveMovilAuthProvider: diagnostic dump failed", exc_info=True)
            return None

    @staticmethod
    def _exception_already_has_diagnostic(exc: Exception) -> bool:
        """Return whether an auth exception already carries a diagnostic id."""

        context = getattr(exc, "context", None)
        if not isinstance(context, dict):
            return False
        return bool(context.get("diagnostic_id"))

    async def _wait_for_post_auth_landing(
        self,
        page: BrowserPageLike,
        target_path: str,
        timeout_ms: int,
    ) -> None:
        """Poll until the browser reaches ``target_path`` or timeout.

        After Cl@ve completion AEAT may interpose the representation
        dispatcher. Only the authenticated user's own-name continuation
        is allowed here; representative/third-party action remains
        fail-closed because it would require represented-taxpayer data.
        """
        deadline = time.perf_counter() + timeout_ms / 1000
        while time.perf_counter() < deadline:
            current = getattr(page, "url", "") or ""
            surface = self._clave_surface()
            await self._raise_if_pending_request_error(page)
            if target_path in current and surface.selector_access_path_marker not in current:
                return
            # Only match the representation dispatcher when it is the URL PATH,
            # not the `ref=` query parameter (which contains it URL-
            # encoded on the push-waiting page).
            try:
                current_path = urlsplit(current).path
            except ValueError:
                current_path = ""
            if (
                surface.dialogo_representacion_path_marker in current_path
                and surface.selector_access_path_marker not in current
            ):
                await self._continue_own_name_representation(page)
            await asyncio.sleep(0.5)
        log.warning(
            "ClaveMovilAuthProvider: post-auth landing timeout target_path=%r timeout_ms=%d",
            target_path,
            timeout_ms,
        )
        raise TimeoutError(f"page did not navigate to {target_path!r} within {timeout_ms}ms")

    async def _continue_own_name_representation(self, page: BrowserPageLike) -> None:
        """Continue only through AEAT's authenticated own-name selector."""

        assert_remote_operation_allowed(
            _auth_browser_action_policy(self._settings),
            RemoteOperation(kind="browser_action", action=_OWN_NAME_REPRESENTATION_ACTION),
        )
        pre303 = self._settings.external_constants().aeat.pre303
        wait_for = getattr(page, "wait_for_selector", None)
        click = getattr(page, "click", None)
        if wait_for is None or click is None:
            raise AeatLoginAssertionError(
                "Playwright page does not expose wait_for_selector()/click(); "
                "cannot drive AEAT own-name representation gate"
            )
        try:
            await wait_for(
                pre303.representation_own_name_label_selector,
                timeout=self._settings.aeat_browser_selector_probe_timeout_ms,
            )
            await self._dismiss_pre303_alert_modal_if_present(page)
            await click(pre303.representation_own_name_label_selector)
            await click(pre303.representation_submit_selector)
        except PlaywrightError as exc:
            raise AeatLoginAssertionError(
                "AEAT representation gate did not expose the own-name continuation expected for the "
                "authenticated profile user.",
                context={
                    "failure_mode": "representation_gate_own_name_unavailable",
                    "landing_url": getattr(page, "url", None),
                    "blocked_operation": "representative_or_unknown_representation_gate",
                },
                suggestion="Do not provide represented-third-party data through this driver.",
            ) from exc

    async def _dismiss_pre303_alert_modal_if_present(self, page: BrowserPageLike) -> None:
        pre303 = self._settings.external_constants().aeat.pre303
        content = getattr(page, "content", None)
        click = getattr(page, "click", None)
        if content is None or click is None:
            return
        html = await content()
        modal_marker = pre303.alert_modal_selector.lstrip("#")
        if pre303.alert_modal_selector not in html and modal_marker not in html:
            return
        continue_selector = (
            f'{pre303.alert_modal_selector} button:has-text("{pre303.alert_continue_button_text}")'
        )
        await click(continue_selector)


__all__ = [
    "ClaveMovilApprovalTimeoutError",
    "ClaveMovilAuthProvider",
    "ClaveMovilConfigurationError",
    "ClaveMovilFailureMode",
]
