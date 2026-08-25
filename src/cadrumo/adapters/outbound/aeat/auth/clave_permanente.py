"""Cl@ve Permanente auth provider for AEAT Sede Electrónica.

Implements the :class:`~application.auth.AuthProvider` protocol for
the DNI/NIE + password Cl@ve Permanente flow against the live portal. Unlike
Cl@ve Móvil, routine Cl@ve Permanente login for AEAT *read paths* is fully
headless-automatable: the operator supplies a DNI/NIE and password, the
provider submits AEAT's auth-method selector page and the Cl@ve IdP login form,
and no phone approval, push notification, or QR scan is required. AEAT's
SMS-OTP elevation only applies to account activation, password recovery, and
"top-level services" (elevated write operations) — none of which this project's
permanently-read-only scope reaches.

The provider returns :class:`~adapters.outbound.aeat.auth.AeatSession` and
:class:`~adapters.outbound.aeat.auth.AeatLoginAssertion` records with Cl@ve
Permanente-specific detail payloads. Fresh logins persist
:class:`~adapters.outbound.aeat.auth.clave_permanente_metadata.ClavePermanenteSessionMetadata`
next to encrypted Playwright storage state; resume and diagnostic probes
rebuild :class:`~adapters.outbound.aeat.auth.ClavePermanenteSessionDetail` from
that metadata without carrying credential material in the session record.

Design summary:

* The provider opens a Playwright context and drives the selector page +
  Cl@ve IdP login form directly; there is no human-in-the-loop wait state to
  poll, so both fresh login and resume can run headlessly.
* The persisted session stores Playwright state and provider metadata
  together in the encrypted session object, under a Cl@ve
  Permanente-namespaced logical storage key that keeps it distinct from
  certificate and Cl@ve Móvil sessions.
* AEAT/Cl@ve IdP form selectors are the least stable part of this surface —
  they track the Cl@ve frontend rather than a published AEAT contract — and
  are declared centrally in
  :class:`~core.external_constants.AeatClavePermanenteSurface` so a frontend
  change is a one-file update.

See Also:
    :class:`~adapters.outbound.aeat.auth.clave_permanente_metadata.ClavePermanenteSessionMetadata`
        Provider-owned encrypted persistence contract.
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteSessionDetail`
        Public session detail projected from persisted metadata.
    :func:`~adapters.outbound.aeat.auth.clave_permanente_support.clave_permanente_login_error`
        Builder for operator-reportable live-flow failures.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast
from urllib.parse import quote, urlsplit

from pydantic import ValidationError

import cadrumo.adapters.outbound.aeat.auth.session_store as session_store

from .....application.auth.protocols import (
    BrowserContextPort,
    BrowserPagePort,
    BrowserSessionFactoryPort,
    BrowserSessionPort,
)
from .....application.auth.session_types import (
    AeatLoginAssertion,
    AeatSession,
    ClavePermanenteLoginAssertionDetail,
    ClavePermanenteSessionDetail,
    is_exact_active_provider_session,
)
from .....core import AuthProviderDescription, AuthProviderKind
from .....core.auth_session_keys import aeat_auth_session_storage_state_path
from .....core.bucket_pointer import require_active_bucket_id
from .....core.config import Settings as _Settings
from .....core.config import unwrap_optional_secret
from .....core.errors import AeatLoginAssertionError
from .....core.logging import get_logger
from .....core.time import now
from .....domain.calculations.registry.aeat_hosts import canonical_remote_hostname
from .._playwright import PlaywrightTimeoutError
from ._clave_provider_common import (
    close_clave_browser_session,
    close_clave_context,
    default_sede_target_url,
    verification_probe_url,
)
from ._session_probe import run_authenticated_landing_probe
from .authenticator import AEAT_SESSION_IDLE_TTL
from .browser_lifecycle import _CloseIntentBarrier
from .clave_movil_support import classify_identity as _classify_identity
from .clave_permanente_metadata import ClavePermanenteSessionMetadata
from .clave_permanente_support import ClavePermanenteFailureMode
from .clave_permanente_support import clave_permanente_configuration_error as _configuration_error
from .clave_permanente_support import clave_permanente_login_error as _login_error
from .errors import AuthConfigurationError, AuthProviderCleanupError

if TYPE_CHECKING:
    from .....core.config import Settings
    from .....core.external_constants import AeatClavePermanenteSurface

log = get_logger(__name__)

_NAVIGATION_TIMEOUT_MS_DEFAULT: Final[int] = int(
    _Settings.model_fields["cadrumo_browser_navigation_timeout_ms"].default,
)
# Environment variable names referenced in operator-facing error messages.
# Named constants so grepping for the env-var name surfaces every usage site.
_CLAVE_PERMANENTE_DNI_NIE_ENV: Final[str] = "CADRUMO_CLAVE_PERMANENTE_DNI_NIE"
_CLAVE_PERMANENTE_PASSWORD_ENV: Final[str] = "CADRUMO_CLAVE_PERMANENTE_PASSWORD"


class ClavePermanenteAuthProvider:
    """Cl@ve Permanente implementation of the :class:`~application.auth.AuthProvider` protocol.

    Constructed by :func:`~adapters.outbound.aeat.auth.select_provider`
    when ``kind == AuthProviderKind.CLAVE_PERMANENTE``. Both fresh login and
    resume run headlessly: the DNI/NIE + password form requires no
    operator-mediated approval step for AEAT read paths.
    """

    kind: AuthProviderKind = AuthProviderKind.CLAVE_PERMANENTE

    def __init__(
        self,
        settings: Settings,
        *,
        browser_session_factory: BrowserSessionFactoryPort | None = None,
        navigation_timeout_ms: int = _NAVIGATION_TIMEOUT_MS_DEFAULT,
    ) -> None:
        """Initialize one provider with its settings and browser boundary."""
        self._settings = settings
        self._browser_session_factory = browser_session_factory
        self._navigation_timeout_ms = navigation_timeout_ms
        self._lifecycle = _CloseIntentBarrier()
        self._browser_session: BrowserSessionPort | None = None
        self._context: BrowserContextPort | None = None
        self._active_session: AeatSession | None = None

    # ── Protocol surface ────────────────────────────────────────────────────

    async def authenticate(self) -> AeatSession:
        """Run the provider-neutral Cl@ve Permanente login flow."""
        return await self.authenticate_for_target(target_url=None)

    async def authenticate_for_target(
        self,
        *,
        target_url: str | None = None,
    ) -> AeatSession:
        """Run the Cl@ve Permanente login flow and return an :class:`~adapters.outbound.aeat.auth.AeatSession`.

        Attempts to resume a cached session first. Falls back to a fresh
        DNI/NIE + password form submission against the Cl@ve IdP. Fresh
        success writes
        :class:`~adapters.outbound.aeat.auth.clave_permanente_metadata.ClavePermanenteSessionMetadata`
        and returns a session whose provider detail is
        :class:`~adapters.outbound.aeat.auth.ClavePermanenteSessionDetail`.
        """
        async with self._lifecycle.work():
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "ClavePermanenteAuthProvider already has an active session; "
                    "call close() before authenticating again",
                )
            if self._context is not None or self._browser_session is not None:
                raise AuthProviderCleanupError(
                    "ClavePermanenteAuthProvider retained browser resources after close",
                    translated_message="errors.auth.auth_auth_provider_cleanup",
                )
            dni_nie = self._require_identity()
            password = self._require_password()
            resume_path = self._storage_state_path()
            if session_store.exists(resume_path):
                try:
                    return await self._resume_locked(
                        resume_path,
                        target_url=target_url,
                    )
                except AeatLoginAssertionError as exc:
                    log.info(
                        "ClavePermanenteAuthProvider: persisted session unusable; falling back to fresh login (%s)",
                        exc,
                    )
                    self._invalidate_persisted(resume_path)

            return await self._fresh_login_locked(
                dni_nie=dni_nie,
                password=password,
                storage_state_path=resume_path,
                target_url=target_url,
            )

    async def verify(self, session: AeatSession) -> AeatLoginAssertion:
        """Run the provider-neutral verification flow for ``session``."""
        return await self.verify_for_target(session, target_url=None)

    async def verify_for_target(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion:
        """Re-probe that ``session``'s cookies still unlock a Sede page.

        Explicit ``target_url`` probes go through AEAT's selector dispatcher.
        When no explicit target is supplied and the session metadata has a
        concrete post-auth landing URL, the probe navigates there directly.

        Returns:
            An :class:`~adapters.outbound.aeat.auth.AeatLoginAssertion`
            describing the probe outcome.
        """
        async with self._lifecycle.work():
            return await self._verify_in_work(session, target_url=target_url)

    async def _verify_in_work(
        self,
        session: AeatSession,
        *,
        target_url: str | None,
    ) -> AeatLoginAssertion:
        """Verify a session while the caller holds the provider work lease."""
        context = self._context
        if context is None:
            raise AeatLoginAssertionError(
                "ClavePermanenteAuthProvider.verify() requires an active browser context; call authenticate() first",
            )
        if not is_exact_active_provider_session(
            session,
            self._active_session,
            provider_kind=AuthProviderKind.CLAVE_PERMANENTE,
            detail_type=ClavePermanenteSessionDetail,
        ):
            raise AeatLoginAssertionError(
                "ClavePermanenteAuthProvider.verify() requires the exact active Cl@ve Permanente session",
            )
        session_landing_url = (
            session.provider_detail.landing_url
            if isinstance(session.provider_detail, ClavePermanenteSessionDetail)
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
        attempted_at = now()
        outcome = await run_authenticated_landing_probe(
            context,
            probe_url=probe_url,
            target_path=target_path,
            navigation_timeout_ms=self._navigation_timeout_ms,
            is_authenticated_landing=self._authenticated_landing_predicate,
            on_landing=None,
            log_label="ClavePermanenteAuthProvider.verify",
        )
        is_valid = outcome.session_cookie_present and bool(session.identity_nif)
        return AeatLoginAssertion(
            target_url=probe_url,
            is_valid=is_valid,
            identity_nif=session.identity_nif,
            status_code=outcome.status_code,
            elapsed_ms=outcome.elapsed_ms,
            attempted_at=attempted_at,
            error_message=outcome.error_message,
            assertion_detail=ClavePermanenteLoginAssertionDetail(
                session_cookie_present=outcome.session_cookie_present,
                landing_url=outcome.landing_url,
            ),
        )

    def _authenticated_landing_predicate(self, landing_url: str, target_path: str) -> bool:
        return self._is_authenticated_aeat_landing(landing_url=landing_url, target_path=target_path)

    def describe(self) -> AuthProviderDescription:
        """Return the provider's :class:`core.AuthProviderDescription`.

        A missing identity or missing password is an undeclared state
        (``info``), a malformed identity is a real configuration fault
        (``warning``), and a fully-configured provider is ``info`` with a
        headless-ready summary — Cl@ve Permanente never requires an
        operator-mediated completion step for read paths.
        """
        dni_nie = unwrap_optional_secret(self._settings.cadrumo_clave_permanente_dni_nie).strip()
        password_configured = self._settings.cadrumo_clave_permanente_password is not None
        if not dni_nie or not password_configured:
            return AuthProviderDescription(
                kind=self.kind,
                label="Cl@ve Permanente",
                configured=False,
                available=False,
                health_severity="info",
                health_summary="No DNI/NIE and password have been configured for Cl@ve Permanente.",
            )
        try:
            _classify_identity(dni_nie)
        except AuthConfigurationError as exc:
            return AuthProviderDescription(
                kind=self.kind,
                label="Cl@ve Permanente",
                configured=True,
                available=False,
                identity_nif=dni_nie.upper(),
                health_severity="warning",
                health_summary=str(exc),
            )
        return AuthProviderDescription(
            kind=self.kind,
            label="Cl@ve Permanente",
            configured=True,
            available=True,
            identity_nif=dni_nie.upper(),
            health_severity="info",
            health_summary="Ready; Cl@ve Permanente login is headless for AEAT read paths.",
        )

    async def close(self) -> None:
        """Tear down any retained :class:`BrowserContextPort` and browser session."""
        async with self._lifecycle.close():
            context_closed = await self._drop_context()
            browser_session_closed = await self._close_browser_session(self._browser_session)
            if browser_session_closed:
                self._browser_session = None
            self._active_session = None
        if not context_closed or not browser_session_closed:
            raise AuthProviderCleanupError(
                "ClavePermanenteAuthProvider retained browser resources after close",
                translated_message="errors.auth.auth_auth_provider_cleanup",
            )

    # ── Identity + target helpers ───────────────────────────────────────────

    def _require_identity(self) -> str:
        raw = unwrap_optional_secret(self._settings.cadrumo_clave_permanente_dni_nie)
        if not raw:
            raise _configuration_error(
                f"{_CLAVE_PERMANENTE_DNI_NIE_ENV} is not set; set it to your DNI or NIE "
                "before running `aeat config auth configure --provider clave_permanente`.",
                failure_mode=ClavePermanenteFailureMode.INVALID_CREDENTIALS,
            )
        _classify_identity(raw)
        return raw.strip().upper()

    def _require_password(self) -> str:
        raw = unwrap_optional_secret(self._settings.cadrumo_clave_permanente_password)
        if not raw:
            raise _configuration_error(
                f"{_CLAVE_PERMANENTE_PASSWORD_ENV} is not set; set it to your Cl@ve "
                "Permanente password before running "
                "`aeat config auth configure --provider clave_permanente`.",
                failure_mode=ClavePermanenteFailureMode.INVALID_CREDENTIALS,
            )
        return raw

    def _default_target_url(self) -> str:
        return default_sede_target_url(self._settings)

    def _selector_url(self, target_path: str) -> str:
        template = self._settings.aeat_clave_permanente_sede_access_url_template
        return template.format(target=quote(target_path, safe=""))

    def _clave_surface(self) -> AeatClavePermanenteSurface:
        return self._settings.external_constants().aeat.clave_permanente

    def _target_path_from_url(self, url: str) -> str:
        parsed = urlsplit(url)
        return parsed.path if not parsed.query else f"{parsed.path}?{parsed.query}"

    def _probe_url_for_verification(
        self,
        *,
        explicit_target_url: str | None,
        resolved_target_url: str | None,
        target_path: str,
    ) -> str:
        return verification_probe_url(
            explicit_target_url=explicit_target_url,
            resolved_target_url=resolved_target_url,
            target_path=target_path,
            selector_url_for=self._selector_url,
        )

    def _is_authenticated_aeat_landing(self, *, landing_url: str, target_path: str) -> bool:
        """Return True for a protected AEAT page reached after Cl@ve dispatch."""
        external = self._settings.external_constants()
        surface = self._clave_surface()
        try:
            parsed = urlsplit(landing_url)
        except ValueError:
            return False
        # The authority is decided by the one canonical helper, never by
        # ``parsed.netloc``: that string still ends in the AEAT suffix when a
        # credential prefix rides in front of it, so
        # ``https://evil@www6.agenciatributaria.gob.es/`` was read as a
        # protected AEAT landing.
        host = canonical_remote_hostname(landing_url)
        if host is None:
            return False
        host_suffix = external.aeat.domains.host_suffix.casefold()
        if host != host_suffix and not host.endswith(f".{host_suffix}"):
            return False
        path = parsed.path.casefold()
        if external.aeat.sede_paths.auth_gate_4033.casefold() in path:
            return False
        if surface.selector_access_path_marker.casefold() in path:
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
        if target_parts[0] in {"wlpl", "sede"}:
            return landing_parts[:2] == target_parts[:2]
        return False

    # ── Lifecycle helpers ───────────────────────────────────────────────────

    async def _resolve_browser_session(self) -> BrowserSessionPort:
        if self._browser_session_factory is None:
            raise AeatLoginAssertionError(
                "ClavePermanenteAuthProvider was constructed without a browser "
                "session factory; pass one via select_provider(..., "
                "browser_session_factory=...).",
            )
        return await self._browser_session_factory(self._settings)

    async def _drop_context(self) -> bool:
        context = self._context
        closed = await self._close_context(context, reason="_drop_context")
        if closed:
            self._context = None
        return closed

    async def _close_context(self, context: BrowserContextPort | None, *, reason: str) -> bool:
        return await close_clave_context(
            context,
            settings=self._settings,
            logger=log,
            owner=f"ClavePermanenteAuthProvider:{reason}",
        )

    async def _close_browser_session(self, session: BrowserSessionPort | None) -> bool:
        return await close_clave_browser_session(
            session,
            settings=self._settings,
            logger=log,
            owner="ClavePermanenteAuthProvider",
        )

    # ── Encrypted session state ────────────────────────────────────────────

    def _storage_state_path(self) -> Path:
        profile = require_active_bucket_id()
        return aeat_auth_session_storage_state_path(profile, "clave-permanente-storage")

    @staticmethod
    def _persist_session(
        storage_state_path: Path,
        *,
        storage_state: Mapping[str, object],
        metadata: ClavePermanenteSessionMetadata,
    ) -> None:
        session_store.save(
            storage_state_path,
            storage_state=storage_state,
            metadata=metadata.model_dump(mode="json"),
        )

    def _load_persisted(self, storage_state_path: Path) -> session_store.PersistedBrowserSession:
        persisted = session_store.load(storage_state_path)
        if persisted is None:
            raise AeatLoginAssertionError(
                "no persisted Cl@ve Permanente session; run `aeat config auth status` first",
            )
        return persisted

    @staticmethod
    def _load_metadata(
        storage_state_path: Path,
        persisted: session_store.PersistedBrowserSession,
    ) -> ClavePermanenteSessionMetadata:
        try:
            return ClavePermanenteSessionMetadata.model_validate_json(json.dumps(persisted.metadata, default=str))
        except (ValueError, ValidationError) as exc:
            raise AeatLoginAssertionError(
                f"Cl@ve Permanente metadata invalid for {storage_state_path}: {exc}",
            ) from exc

    def _invalidate_persisted(self, storage_state_path: Path) -> None:
        session_store.delete(storage_state_path)

    def _fresh_login_session(
        self,
        *,
        dni_nie: str,
        authenticated_at: datetime,
        idle_deadline: datetime,
        storage_state_path: Path,
        landing_url: str | None,
    ) -> AeatSession:
        return AeatSession(
            authenticated_at=authenticated_at,
            idle_deadline=idle_deadline,
            storage_state_path=storage_state_path,
            identity_nif=dni_nie,
            provider_detail=ClavePermanenteSessionDetail(
                dni_nie=dni_nie,
                landing_url=landing_url,
            ),
        )

    # ── Flow ────────────────────────────────────────────────────────────────

    async def _drive_login_form(
        self,
        page: BrowserPagePort,
        *,
        dni_nie: str,
        password: str,
    ) -> None:
        """Fill and submit the Cl@ve IdP DNI/NIE + password form.

        Detects the closed error-marker taxonomy (invalid credentials,
        locked account, expired password, SMS-OTP elevation) against the
        page's rendered text and raises a registered
        :class:`~adapters.outbound.aeat.auth.AuthError` with the matching
        :class:`~adapters.outbound.aeat.auth.ClavePermanenteFailureMode`
        before returning control for the post-auth landing wait.
        """
        surface = self._clave_surface()
        fill = getattr(page, "fill", None)
        click = getattr(page, "click", None)
        content = getattr(page, "content", None)
        if callable(fill):
            # CAST-RATIONALE-CLAVE-PERMANENTE-FILL: runtime callable narrowing
            # proves the optional Playwright page extension before invocation.
            fill_page = cast(Callable[..., Awaitable[object]], fill)
            await fill_page(surface.username_input_selector, dni_nie)
            await fill_page(surface.password_input_selector, password)
        if callable(click):
            # CAST-RATIONALE-CLAVE-PERMANENTE-CLICK: runtime callable narrowing
            # proves the optional Playwright page extension before invocation.
            click_page = cast(Callable[..., Awaitable[object]], click)
            await click_page(surface.submit_button_selector)
        if not callable(content):
            return
        # CAST-RATIONALE-CLAVE-PERMANENTE-CONTENT: runtime callable narrowing
        # proves the optional Playwright page extension before invocation.
        content_page = cast(Callable[[], Awaitable[object]], content)
        content_value = await content_page()
        html = content_value if isinstance(content_value, str) else ""
        normalized = html.casefold()
        if surface.elevation_sms_marker.casefold() in normalized:
            raise _login_error(
                "AEAT requested SMS-OTP elevation, which the read-path Cl@ve "
                "Permanente flow cannot satisfy headlessly.",
                failure_mode=ClavePermanenteFailureMode.ELEVATION_REQUIRED,
            )
        if surface.account_locked_marker.casefold() in normalized:
            raise _login_error(
                "Cl@ve reports the account is locked.",
                failure_mode=ClavePermanenteFailureMode.ACCOUNT_LOCKED,
            )
        if surface.password_expired_marker.casefold() in normalized:
            raise _login_error(
                "Cl@ve reports the password has expired (Cl@ve enforces a maximum password age).",
                failure_mode=ClavePermanenteFailureMode.PASSWORD_EXPIRED,
            )
        if surface.invalid_credentials_marker.casefold() in normalized:
            raise _login_error(
                "Cl@ve rejected the configured DNI/NIE + password combination.",
                failure_mode=ClavePermanenteFailureMode.INVALID_CREDENTIALS,
            )

    async def _wait_for_post_auth_landing(
        self,
        page: BrowserPagePort,
        target_path: str,
        timeout_ms: int,
    ) -> None:
        wait_for_url = getattr(page, "wait_for_url", None)
        if not callable(wait_for_url):
            return
        # CAST-RATIONALE-CLAVE-PERMANENTE-WAIT: runtime callable narrowing
        # proves the optional Playwright page extension before invocation.
        wait_for_page_url = cast(Callable[..., Awaitable[object]], wait_for_url)
        await wait_for_page_url(f"**{target_path}**", timeout=timeout_ms)

    async def _fresh_login_locked(
        self,
        *,
        dni_nie: str,
        password: str,
        storage_state_path: Path,
        target_url: str | None,
    ) -> AeatSession:
        target = target_url or self._default_target_url()
        target_path = self._target_path_from_url(target)
        selector_url = self._selector_url(target_path)

        session_like = await self._resolve_browser_session()
        self._browser_session = session_like
        context, storage_state, landing_url = await self._capture_fresh_login_state(
            session_like,
            dni_nie=dni_nie,
            password=password,
            target_path=target_path,
            selector_url=selector_url,
        )

        authenticated_at = now()
        idle_deadline = authenticated_at + AEAT_SESSION_IDLE_TTL
        await self._persist_fresh_session(
            storage_state_path,
            context=context,
            session_like=session_like,
            storage_state=storage_state,
            dni_nie=dni_nie,
            authenticated_at=authenticated_at,
            idle_deadline=idle_deadline,
            landing_url=landing_url,
        )

        session = self._fresh_login_session(
            dni_nie=dni_nie,
            authenticated_at=authenticated_at,
            idle_deadline=idle_deadline,
            storage_state_path=storage_state_path,
            landing_url=landing_url,
        )
        self._browser_session = session_like
        self._context = context
        self._active_session = session
        log.info("ClavePermanenteAuthProvider: authenticated landing=%s", landing_url)
        return session

    async def _capture_fresh_login_state(
        self,
        session_like: BrowserSessionPort,
        *,
        dni_nie: str,
        password: str,
        target_path: str,
        selector_url: str,
    ) -> tuple[BrowserContextPort, Mapping[str, object], str | None]:
        """Drive the fresh Cl@ve Permanente login page to a captured storage state."""
        context: BrowserContextPort | None = None
        page: BrowserPagePort | None = None
        try:
            context = await session_like.create_context()
            self._context = context
            page = await context.new_page()
            try:
                await page.goto(selector_url, timeout=self._navigation_timeout_ms)
            except (TimeoutError, PlaywrightTimeoutError) as exc:
                raise _login_error(
                    f"Cl@ve Permanente initial navigation did not reach the AEAT selector "
                    f"within {self._navigation_timeout_ms // 1000} seconds.",
                    failure_mode=ClavePermanenteFailureMode.INITIAL_NAVIGATION_TIMEOUT,
                    context={"timeout_ms": self._navigation_timeout_ms, "target_path": target_path},
                ) from exc

            log.info("ClavePermanenteAuthProvider: starting fresh login")
            await self._drive_login_form(page, dni_nie=dni_nie, password=password)

            timeout_ms = int(self._settings.cadrumo_clave_permanente_timeout_ms)
            try:
                await self._wait_for_post_auth_landing(page, target_path, timeout_ms)
            except (TimeoutError, PlaywrightTimeoutError) as exc:
                current_url = getattr(page, "url", "") or ""
                raise _login_error(
                    f"Cl@ve Permanente login did not reach the expected AEAT page after {timeout_ms // 1000} seconds.",
                    failure_mode=ClavePermanenteFailureMode.POST_AUTH_LANDING_TIMEOUT,
                    context={"timeout_ms": timeout_ms, "current_url": current_url, "target_path": target_path},
                ) from exc

            storage_state = await context.storage_state()
            landing_url = getattr(page, "url", None)
            await page.close()
        except Exception:
            context_closed = await self._close_context(context, reason="fresh-login cleanup")
            self._context = None if context_closed else context
            session_closed = await self._close_browser_session(session_like)
            self._browser_session = None if session_closed else session_like
            raise
        return context, storage_state, landing_url

    async def _persist_fresh_session(
        self,
        storage_state_path: Path,
        *,
        context: BrowserContextPort,
        session_like: BrowserSessionPort,
        storage_state: Mapping[str, object],
        dni_nie: str,
        authenticated_at: datetime,
        idle_deadline: datetime,
        landing_url: str | None,
    ) -> None:
        """Persist the captured session, cleaning up owned resources on failure."""
        try:
            metadata = ClavePermanenteSessionMetadata(
                identity_nif=dni_nie,
                authenticated_at=authenticated_at,
                idle_deadline=idle_deadline,
                storage_state_sha256=session_store.storage_state_sha256(storage_state),
                landing_url=landing_url,
            )
            self._persist_session(storage_state_path, storage_state=storage_state, metadata=metadata)
        except Exception:
            try:
                self._invalidate_persisted(storage_state_path)
            except Exception as _cleanup_exc:
                log.debug(
                    "ClavePermanenteAuthProvider: _invalidate_persisted during persist-failure cleanup suppressed: %s",
                    _cleanup_exc,
                    exc_info=True,
                )
            context_closed = await self._close_context(context, reason="persist-failure cleanup")
            self._context = None if context_closed else context
            session_closed = await self._close_browser_session(session_like)
            self._browser_session = None if session_closed else session_like
            raise

    async def _resume_locked(
        self,
        storage_state_path: Path,
        *,
        target_url: str | None,
    ) -> AeatSession:
        persisted = self._load_persisted(storage_state_path)
        metadata = self._load_metadata(storage_state_path, persisted)
        if metadata.idle_deadline <= now():
            raise AeatLoginAssertionError(
                "Cl@ve Permanente session past idle deadline",
            )
        observed_sha256 = persisted.storage_state_sha256
        if observed_sha256 != metadata.storage_state_sha256:
            raise AeatLoginAssertionError(
                "Cl@ve Permanente storage-state hash mismatch",
            )

        session_like = await self._resolve_browser_session()
        self._browser_session = session_like
        context: BrowserContextPort | None = None
        try:
            context = await session_like.create_context(storage_state=persisted.storage_state)
            self._context = context
            session = AeatSession(
                authenticated_at=metadata.authenticated_at,
                idle_deadline=metadata.idle_deadline,
                storage_state_path=storage_state_path,
                identity_nif=metadata.identity_nif,
                provider_detail=ClavePermanenteSessionDetail(
                    dni_nie=metadata.identity_nif,
                    landing_url=metadata.landing_url,
                ),
            )
            self._browser_session = session_like
            self._context = context
            self._active_session = session

            assertion = await self._verify_in_work(session, target_url=target_url)
            if not assertion.is_valid:
                raise AeatLoginAssertionError(
                    "Cl@ve Permanente resume failed live verification: "
                    f"status={assertion.status_code} error={assertion.error_message!r}",
                )
            refreshed = session.model_copy(
                update={
                    "authenticated_at": assertion.attempted_at,
                    "idle_deadline": assertion.attempted_at + AEAT_SESSION_IDLE_TTL,
                },
            )
            self._active_session = refreshed
            refreshed_metadata = metadata.model_copy(
                update={
                    "authenticated_at": refreshed.authenticated_at,
                    "idle_deadline": refreshed.idle_deadline,
                },
            )
            self._persist_session(
                storage_state_path,
                storage_state=persisted.storage_state,
                metadata=refreshed_metadata,
            )
            log.info(
                "ClavePermanenteAuthProvider: resumed landing=%s",
                assertion.assertion_detail.landing_url
                if isinstance(assertion.assertion_detail, ClavePermanenteLoginAssertionDetail)
                else None,
            )
            return refreshed
        except Exception:
            context_closed = await self._close_context(context, reason="resume cleanup")
            self._browser_session = None
            self._context = None if context_closed else context
            self._active_session = None
            if not await self._close_browser_session(session_like):
                self._browser_session = session_like
            raise


__all__ = [
    "ClavePermanenteAuthProvider",
]
