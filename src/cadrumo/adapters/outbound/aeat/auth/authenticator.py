"""Certificate-backed live-AEAT authenticator.

This module implements the certificate concrete for the application
:class:`application.auth.AuthProvider` contract. It composes
:class:`CertificateBundle` loading, a
:class:`CertificateContextProvisioner`-backed browser context, and the
canonical protected-resource probe into a narrow async provider surface.

The provider returns the imported :class:`AeatSession` and
:class:`AeatLoginAssertion` records owned by
:mod:`adapters.outbound.aeat.auth.authenticator_types`. Captured
Playwright storage state is written through the encrypted session store
with :class:`PersistedSessionMetadata`, then resumed only after hash,
idle-deadline, certificate thumbprint, certificate subject, and live
probe checks pass.

Design notes:

* The module holds an 18-minute session idle TTL as a code-level
  constant. The value is deliberately **not** an env var — the
  operator surface is kept narrow, and AEAT's observed idle window
  is ~20 minutes (the extra 2 minutes is safety margin).
* ``authenticate()`` uses the configured browser-session factory. The
  authenticator owns and deterministically closes every session it creates.
* ``reauthenticate()`` is single-shot. Callers cap retries at ONE
  per downstream call-site; a second consecutive failure raises
  :class:`AeatSessionExpiredError` upwards rather than loop.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final, NoReturn
from urllib.parse import SplitResult, urlsplit

from pydantic import ValidationError

import cadrumo.adapters.outbound.aeat.auth.session_store as session_store

from .....application.auth_credentials import ActiveCertificateCredentials
from .....core import AuthProviderDescription, AuthProviderKind
from .....core.async_cleanup import close_async_resources
from .....core.config import AEAT_CERTIFICATE_PROTECTED_URL
from .....core.config import Settings as _Settings
from .....core.logging import get_logger
from .....core.time import now
from .authenticator_persistence import (
    AEAT_STORAGE_STATE_SCHEMA_VERSION,
    PersistedSessionMetadata,
    persisted_session_reason_code,
    persisted_session_reason_from_error,
)
from .authenticator_types import (
    AeatLoginAssertion,
    AeatSession,
    BrowserContextLike,
    BrowserPageLike,
    BrowserSessionFactory,
    BrowserSessionLike,
    CertificateHealthCheck,
    PersistedSessionInvalidError,
    _is_exact_active_provider_session,
)
from .browser_lifecycle import _CloseIntentBarrier, close_owned_browser_context, close_owned_browser_session
from .certificate import (
    CertificateBundle,
    CertificateError,
    CertificateHealth,
    CertificateLoadError,
    CertificateNifParseError,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
    load_certificate,
)
from .certificate import (
    health as certificate_health,
)
from .errors import (
    AeatLoginAssertionError,
    AeatSessionExpiredError,
    AuthConfigurationError,
    AuthProviderCleanupError,
    AuthValidationError,
)
from .providers import (
    CertificateContextProvisioner,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
)

if TYPE_CHECKING:
    from .....core.config import Settings

log = get_logger(__name__)

# Environment variable name referenced in operator-facing error messages.
# Named constant so grepping for the env-var name surfaces every usage site.
_CERT_PASSWORD_SECRET_ENV: Final[str] = "CADRUMO_CERTIFICATE_PASSWORD_SECRET"
_PERSISTED_SESSION_LABEL: Final[str] = "<persisted-aeat-session>"


AEAT_SESSION_IDLE_TTL: Final[timedelta] = timedelta(minutes=18)
"""Maximum idle lifetime for an authenticated AEAT Playwright session.

AEAT's observed server-side idle window is ~20 minutes; 18 minutes
leaves a 2-minute safety margin before the next downstream call
would see a 401/403. Tuning this value is a code change, not an
env-var change — the operator surface stays narrow.
"""


AEAT_LOGIN_NAVIGATION_TIMEOUT_MS: Final[int] = int(
    _Settings.model_fields["cadrumo_browser_navigation_timeout_ms"].default,
)
"""Playwright navigation timeout for post-auth verification probes."""


def _require_exact_active_certificate_session(
    session: AeatSession,
    active_session: AeatSession | None,
) -> None:
    if (
        not _is_exact_active_provider_session(
            session,
            active_session,
            provider_kind=AuthProviderKind.CERTIFICATE,
            detail_type=CertificateSessionDetail,
        )
        or active_session is None
        or active_session.certificate_thumbprint is None
        or active_session.certificate_subject is None
    ):
        raise AeatLoginAssertionError(
            "verify() requires the exact active certificate-bound session",
            translated_message="adapters.auth.authenticator.errors.capture_requires_active_session",
        )


def _final_resource_matches(final: SplitResult | None) -> bool:
    """Return ``True`` when the probe's final URL is pinned to the canonical resource."""
    if final is None:
        return False
    canonical = urlsplit(AEAT_CERTIFICATE_PROTECTED_URL)
    return final.scheme == canonical.scheme and final.netloc == canonical.netloc and final.path == canonical.path


def _build_certificate_login_assertion(
    session: AeatSession,
    *,
    status_code: int,
    response_successful: bool,
    final_url: str | None,
    error_message: str | None,
    elapsed_ms: int,
    attempted_at: datetime,
) -> AeatLoginAssertion:
    """Build the login assertion from a completed protected-resource probe.

    The assertion is valid only when the probe succeeded, the final scheme,
    host, and path remain pinned to the canonical certificate resource, and the
    session carries an identity NIF. A successful response that drifted off the
    canonical resource is stamped ``protected_resource_mismatch``.
    """
    final = urlsplit(final_url) if final_url is not None else None
    final_resource_matches = _final_resource_matches(final)
    is_valid = response_successful and final_resource_matches and bool(session.identity_nif)
    if response_successful and not final_resource_matches and error_message is None:
        error_message = "protected_resource_mismatch"
    serialized_final_url = final._replace(query="", fragment="").geturl() if final is not None else None
    return AeatLoginAssertion(
        target_url=AEAT_CERTIFICATE_PROTECTED_URL,
        is_valid=is_valid,
        identity_nif=session.identity_nif,
        status_code=status_code,
        elapsed_ms=elapsed_ms,
        attempted_at=attempted_at,
        error_message=error_message,
        assertion_detail=CertificateLoginAssertionDetail(
            final_url=serialized_final_url,
            response_successful=response_successful,
            parsed_subject=session.certificate_subject,
        ),
    )


# ── Authenticator ───────────────────────────────────────────────────────────


class AeatAuthenticator:
    """Certificate implementation of the application :class:`AuthProvider`.

    The authenticator owns:

    * Certificate loading and health evaluation (via the existing
      module-level ``load_certificate`` / ``health`` surface).
    * Playwright browser-context construction with the cert wired
      through (via an injectable browser session factory).
    * Login-assertion verification.
    * Session lifecycle: ``authenticate``, ``reauthenticate``,
      ``close``.

    Use as an async context manager::

        async with AeatAuthenticator(settings, credentials=credentials) as auth:
            session = await auth.authenticate()
            assertion = await auth.verify(session)

    Returned sessions use :class:`CertificateSessionDetail`, login probes use
    :class:`CertificateLoginAssertionDetail`, and persisted resume state is
    validated against :class:`PersistedSessionMetadata`. Callers that only
    need synchronous health or NIF extraction can instantiate
    without entering the async context.
    """

    kind: AuthProviderKind = AuthProviderKind.CERTIFICATE

    def __init__(
        self,
        settings: Settings,
        *,
        credentials: ActiveCertificateCredentials,
        browser_session_factory: BrowserSessionFactory | None = None,
        navigation_timeout_ms: int = AEAT_LOGIN_NAVIGATION_TIMEOUT_MS,
        certificate_health_check: CertificateHealthCheck | None = None,
    ) -> None:
        """Construct an authenticator bound to ``settings``.

        Args:
            settings: The :class:`core.config.Settings` instance the
                authenticator reads non-credential policy from.
            credentials: The exact typed certificate path, passphrase, and
                friendly name selected by application orchestration.
            browser_session_factory: Optional async callable returning a
                :class:`BrowserSessionLike`. Application orchestration supplies
                the production Playwright factory. Direct async authentication
                requires this dependency; omitting it supports only the
                synchronous certificate-loading and health surface.
            navigation_timeout_ms: Playwright navigation timeout in
                milliseconds applied to every page load during the
                login flow. Defaults to
                ``AEAT_LOGIN_NAVIGATION_TIMEOUT_MS``.
            certificate_health_check: Optional
                :class:`CertificateHealthCheck` callable threaded
                into :meth:`describe`. Defaults to the module-level
                ``certificate_health`` import; tests inject a
                real wrapping callable rather than monkeypatching the
                module attribute.
        """
        self._settings = settings
        self._credentials = credentials
        self._browser_session_factory = browser_session_factory
        self._navigation_timeout_ms = navigation_timeout_ms
        self._certificate_health_check: CertificateHealthCheck = certificate_health_check or certificate_health
        # All asyncio primitives below are bound to the first event
        # loop that awaits the authenticator. The class assumes a
        # single-loop lifetime — constructing an instance in one loop
        # (e.g. a pytest-asyncio fixture) and reusing it in another
        # will trip "attached to a different loop" errors. Callers
        # that need cross-loop reuse must construct a fresh instance.
        self._lifecycle = _CloseIntentBarrier()
        self._lock = asyncio.Lock()
        self._browser_session: BrowserSessionLike | None = None
        self._context: BrowserContextLike | None = None
        self._active_session: AeatSession | None = None
        self._inflight_pages = 0
        self._inflight_drained: asyncio.Event = asyncio.Event()
        self._inflight_drained.set()

    async def __aenter__(self) -> AeatAuthenticator:
        """Return this authenticator as its asynchronous context value."""
        return self

    async def __aexit__(self, exc_type: object, *_exc_info: object) -> None:
        """Close through the single owner-retaining asynchronous cleanup authority."""
        del exc_type, _exc_info
        await close_async_resources(
            self,
            task_name="cadrumo-aeat-authenticator-close",
        )

    # ── Synchronous helpers ─────────────────────────────────────────────────

    def load_certificate(self) -> LoadedCertificate:
        """Load the configured PKCS#12 bundle and return a :class:`LoadedCertificate`."""
        bundle = self._require_bundle()
        return load_certificate(bundle)

    def health(self, *, now: datetime | None = None) -> CertificateHealth:
        """Return a :class:`CertificateHealth` for the configured bundle."""
        cert = self.load_certificate()
        return evaluate_loaded_certificate_health(
            cert,
            warn_days=self._settings.cadrumo_cert_warn_days,
            critical_days=self._settings.cadrumo_cert_critical_days,
            now=now,
        )

    # ── Async lifecycle ─────────────────────────────────────────────────────

    async def authenticate(self) -> AeatSession:
        """Produce an authenticated :class:`AeatSession`.

        The method first attempts to resume a previously captured
        Playwright ``storage_state`` backed by
        :class:`PersistedSessionMetadata`. If that persisted state is
        missing, malformed, stale, certificate-mismatched, or fails a live
        verification probe, it is deleted and the method falls back to a
        fresh certificate-backed browser login flow. Fresh contexts
        are created through :class:`CertificateContextProvisioner` so the
        AEAT origin receives the configured client certificate.

        Returns:
            An authenticated :class:`AeatSession` ready for downstream use.

        Raises:
            AeatLoginAssertionError: When the canonical protected-resource
                assertion does not prove a successful, exact final resource.
            AuthConfigurationError: When async authentication has no browser
                session factory or certificate credentials are incomplete.
            BrowserError: When browser launch or context construction fails.
            Exception: Re-raised when storage-state capture fails after a successful
                context creation.
        """
        async with self._lifecycle.work(), self._lock:
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "AeatAuthenticator already has an active session; "
                    "call close() or reauthenticate() before "
                    "authenticating again",
                    translated_message="adapters.auth.authenticator.errors.already_active",
                )
            if self._browser_session is not None or self._context is not None:
                raise AuthProviderCleanupError(
                    "AeatAuthenticator still owns browser resources whose close did not complete; "
                    "call close() again before authenticating",
                    translated_message="errors.auth.auth_auth_provider_cleanup",
                )
            resume_path = self._resolve_storage_state_path()
            if session_store.exists(resume_path):
                try:
                    return await self._resume_from_storage_state_locked(resume_path)
                except PersistedSessionInvalidError as exc:
                    reason = persisted_session_reason_from_error(exc)
                    log.info(
                        "AeatAuthenticator: persisted session invalid session=%s reason=%s; falling back to fresh auth",
                        _PERSISTED_SESSION_LABEL,
                        reason,
                    )
                    if self._browser_session is not None or self._context is not None:
                        raise

            return await self._fresh_login_locked()

    async def _fresh_login_locked(self) -> AeatSession:
        """Run the fresh certificate-backed browser login under the held lock.

        Called from :meth:`authenticate` after a persisted-session resume has
        been skipped or invalidated; the caller already holds the lifecycle
        work barrier and the instance lock, and has cleared the active-session
        and owned-resource guards.
        """
        cert = self.load_certificate()
        nif = extract_nif_from_subject(cert)

        session_like = await self._resolve_browser_session()
        self._browser_session = session_like
        try:
            context = await session_like.create_context(
                provisioner=CertificateContextProvisioner(cert),
            )
            self._context = context
        except Exception:
            if await self._close_browser_session(session_like):
                self._browser_session = None
            raise

        storage_state_path = self._resolve_storage_state_path()
        provisional_at = now()
        provisional_session = AeatSession(
            authenticated_at=provisional_at,
            idle_deadline=provisional_at + AEAT_SESSION_IDLE_TTL,
            storage_state_path=storage_state_path,
            identity_nif=nif,
            provider_detail=CertificateSessionDetail(
                certificate_thumbprint=cert.sha256_thumbprint,
                certificate_subject=cert.subject,
            ),
        )
        assertion = await self._run_login_probe(context, provisional_session)
        if not assertion.is_valid:
            await self._teardown_failed_attempt(context, session_like)
            raise AeatLoginAssertionError(
                "fresh AEAT authentication did not produce a valid login assertion; "
                f"status={assertion.status_code} error={assertion.error_message!r}",
                translated_message="adapters.auth.authenticator.errors.assertion_failed",
            )

        authenticated_at = assertion.attempted_at
        session = provisional_session.model_copy(
            update={
                "authenticated_at": authenticated_at,
                "idle_deadline": authenticated_at + AEAT_SESSION_IDLE_TTL,
            },
        )
        self._browser_session = session_like
        self._context = context
        self._active_session = session
        try:
            await self._capture_storage_state_locked(session)
        except Exception:  # AeatLoginAssertionError/OSError/PlaywrightError; cleanup + re-raise
            await self._drop_context()
            if await self._close_browser_session(session_like):
                self._browser_session = None
            self._active_session = None
            raise
        log.info(
            "AeatAuthenticator: authenticated thumbprint=%s",
            session.certificate_thumbprint,
        )
        return session

    async def reauthenticate(self, session: AeatSession) -> AeatSession:
        """Drop the current context and re-run :meth:`authenticate`.

        **Single-shot.** The method itself does not retry; callers
        cap retries at one per downstream call-site. A second
        consecutive failure — whether the cert load fails, the
        protected-resource probe fails — MUST raise
        :class:`AeatSessionExpiredError` upwards rather than loop.

        **Not atomic across the teardown + authenticate boundary.**
        If another task calls :meth:`authenticate` between this
        method's ``close()`` completing and its ``authenticate()``
        starting, the second call wins the "already has active
        session" guard check and this call raises
        :class:`AeatLoginAssertionError`. External serialisation is
        required if concurrent ``reauthenticate`` / ``authenticate``
        is a real scenario for the caller.

        Args:
            session: The session to replace. Passed for traceability
                (logging, audit) and to document that the caller
                acknowledges it is discarded.

        Returns:
            A fresh :class:`AeatSession` with a new
            ``authenticated_at`` + ``idle_deadline``.
        """
        log.info(
            "AeatAuthenticator: reauthenticate old_authenticated_at=%s",
            session.authenticated_at.isoformat(),
        )
        # Delegate teardown to close() (itself lock-protected and
        # idempotent) so there is no risk of holding the lock across
        # the authenticate() call. close() also nulls _browser_session
        # and drains in-flight pages, so the subsequent authenticate()
        # starts from a fully clean slate.
        await self.close()
        return await self.authenticate()

    async def verify(self, session: AeatSession) -> AeatLoginAssertion:
        """Navigate the authenticated context to the canonical protected resource.

        The assertion is valid only when Playwright reports a successful
        response and the final scheme, host, and path remain pinned to the
        accepted certificate resource.

        Args:
            session: The :class:`AeatSession` returned from
                :meth:`authenticate`.

        Returns:
            A frozen :class:`AeatLoginAssertion`. Negative results
            (``is_valid=False``) are returned as records, not raised
            — callers may invoke :meth:`reauthenticate` once and
            re-verify.

        Raises:
            AeatSessionExpiredError: When the session's idle
                deadline has elapsed.
            AeatLoginAssertionError: When no browser context is
                available (authenticator was never authenticated,
                or ``close()`` was called).
        """
        if session.is_stale():
            from .....core.redaction import redact_for_log

            raise AeatSessionExpiredError(
                redact_for_log(
                    f"session for nif={session.identity_nif} is stale "
                    f"(idle_deadline={session.idle_deadline.isoformat()})",
                ),
                translated_message="adapters.auth.authenticator.errors.session_stale",
            )

        # Snapshot-and-register the context under the lock so that
        # close() / reauthenticate() cannot null it out mid-navigation.
        # The lifecycle barrier prevents registration while any close caller
        # is queued or tearing down owned browser resources.
        async with self._lifecycle.work(), self._lock:
            context = self._context
            if context is None:
                raise AeatLoginAssertionError(
                    "no active browser context; call authenticate() first",
                    translated_message="adapters.auth.authenticator.errors.no_active_context",
                )
            _require_exact_active_certificate_session(session, self._active_session)
            self._inflight_pages += 1
            self._inflight_drained.clear()

        try:
            return await self._run_login_probe(context, session)
        finally:
            async with self._lock:
                self._inflight_pages -= 1
                if self._inflight_pages <= 0:
                    self._inflight_pages = 0
                    self._inflight_drained.set()

    async def capture_storage_state(self, session: AeatSession) -> Path:
        """Persist the active Playwright state and :class:`PersistedSessionMetadata`."""
        async with self._lifecycle.work(), self._lock:
            if self._active_session != session:
                raise AeatLoginAssertionError(
                    "capture_storage_state() requires the currently active authenticated session",
                    translated_message="adapters.auth.authenticator.errors.capture_requires_active_session",
                )
            return await self._capture_storage_state_locked(session)

    async def resume_from_storage_state(
        self,
        path: Path,
    ) -> AeatSession:
        """Resume a certificate :class:`AeatSession` from encrypted storage.

        The persisted browser state and :class:`PersistedSessionMetadata` are
        validated before a :class:`CertificateContextProvisioner` opens a
        context with the restored storage state. A successful live probe
        refreshes ``authenticated_at`` and ``idle_deadline`` before the
        session is returned.
        """
        async with self._lifecycle.work(), self._lock:
            if self._context is not None or self._browser_session is not None:
                raise AuthValidationError(
                    "AeatAuthenticator already has an active session; call close() before resuming another one",
                    translated_message="adapters.auth.authenticator.errors.already_active_before_resume",
                )
            return await self._resume_from_storage_state_locked(path)

    def describe(self) -> AuthProviderDescription:
        """Return an :class:`AuthProviderDescription` with a safe summary of the configured provider.

        Three distinct certificate states surface here, each with its
        own ``health_summary`` and ``health_severity`` so a downstream
        consumer can render them differently and so the loudest
        severity is reserved for genuine faults (round-5 B1 + minor):

        - **no path set** — ``configured=False``, severity ``info``,
          summary ``application.auth.certificate.health.path_unset``.
          An undeclared state, not a fault.
        - **path set, file missing** — ``configured=False``, severity
          ``warning``, summary
          ``application.auth.certificate.health.file_missing``. The
          operator persisted a path that no longer resolves; the slot
          is operationally unusable until the file returns or a new
          path is supplied.
        - **path set, file present** — proceeds into the password +
          load + health-check chain below; ``configured`` becomes
          ``True`` and severity reflects the certificate's expiry
          health.
        """
        from .....core.i18n import tr

        if self._credentials.certificate_path is None:
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=False,
                available=False,
                health_severity="info",
                health_summary=tr("application.auth.certificate.health.path_unset"),
            )
        if not self._credentials.certificate_path.is_file():
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=False,
                available=False,
                health_severity="warning",
                health_summary=tr(
                    "application.auth.certificate.health.file_missing",
                    path=str(self._credentials.certificate_path),
                ),
            )
        if self._credentials.password is None:
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=True,
                available=False,
                health_summary=f"{_CERT_PASSWORD_SECRET_ENV} not set",
            )
        # Consume the single resolved typed credential bundle. The
        # certificate path and passphrase are the settings-resolved
        # credential (a per-source secure-storage secret is threaded in by
        # the application login/status/test path via the settings scope);
        # `describe` reads them through the same `CertificateBundle`
        # `load_certificate` does rather than re-reading individual
        # settings fields, so the load and health paths cannot diverge. The
        # OpenSSL-binding env channel is gone, so the secret never enters
        # os.environ.
        _deferred_error: AuthValidationError | None = None
        try:
            bundle = self._require_bundle()
            health = self._certificate_health_check(
                bundle.path,
                password=bundle.password,
                warn_days=self._settings.cadrumo_cert_warn_days,
                critical_days=self._settings.cadrumo_cert_critical_days,
                friendly_name=bundle.friendly_name,
            )
            identity_nif: str | None = None
            try:
                identity_nif = extract_nif_from_subject(
                    LoadedCertificate(
                        subject=health.subject,
                        issuer=health.issuer,
                        not_before=health.not_before,
                        not_after=health.not_after,
                        serial_number=health.serial_number,
                        sha256_thumbprint="",
                        source_path=bundle.path,
                        friendly_name=bundle.friendly_name,
                    ),
                )
            except CertificateNifParseError:
                identity_nif = None
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=True,
                available=True,
                identity_nif=identity_nif,
                subject=health.subject,
                expires_on=health.not_after.date(),
                health_severity=health.severity.value,
                days_until_expiry=health.days_until_expiry,
                health_summary=f"{health.severity.value}:{health.days_until_expiry}",
            )
        except (CertificateError, OSError) as exc:
            log.debug(
                "AeatAuthenticator.describe: surfacing unavailable status failure=%s",
                type(exc).__name__,
            )
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=True,
                available=False,
                health_summary=tr("application.auth.certificate.health.unavailable"),
            )
        except Exception as exc:
            log.debug(
                "AeatAuthenticator.describe: unexpected error surfacing unavailable status failure=%s",
                type(exc).__name__,
            )
            _deferred_error = AuthValidationError(
                "certificate health is unavailable",
                translated_message="application.auth.certificate.health.unavailable",
            )
        # Raise outside the except block so __context__ stays None —
        # the sensitive original exception must not leak through the chain.
        if _deferred_error is not None:
            raise _deferred_error

    async def close(self) -> None:
        """Release the browser context + session. Idempotent.

        Waits for any in-flight :meth:`verify` call to finish
        its navigation before tearing down the browser context, so a
        page cannot be closed out from under a running probe. The
        lifecycle barrier serializes the complete close sequence. Each
        caller registers a counted close intent before waiting for that
        gate, so new work remains barred until every registered closer
        has finished.

        After every registered close caller returns, the authenticator is
        re-usable (the browser session and context are nulled).
        ``reauthenticate()`` depends on this re-use path.
        """
        context_closed = False
        browser_session_closed = False
        async with self._lifecycle.close():
            await self._inflight_drained.wait()
            async with self._lock:
                context_closed = await self._drop_context()
                browser_session_closed = await self._close_browser_session(self._browser_session)
                if browser_session_closed:
                    self._browser_session = None
                self._active_session = None
        if not context_closed or not browser_session_closed:
            raise AuthProviderCleanupError(
                "AeatAuthenticator retained browser resources after close",
                translated_message="errors.auth.auth_auth_provider_cleanup",
            )

    # ── Internals ───────────────────────────────────────────────────────────

    async def _run_login_probe(
        self,
        context: BrowserContextLike,
        session: AeatSession,
    ) -> AeatLoginAssertion:
        """Probe the one canonical protected resource and build an assertion."""
        attempted_at = now()
        start = time.perf_counter()

        status_code = 0
        response_successful = False
        final_url: str | None = None
        error_message: str | None = None
        page: BrowserPageLike | None = None
        try:
            page = await context.new_page()
            response = await page.goto(
                AEAT_CERTIFICATE_PROTECTED_URL,
                timeout=self._navigation_timeout_ms,
            )
            if response is not None:
                status_code = int(response.status)
                response_successful = bool(response.ok)
            final_url = page.url
        except Exception as exc:
            error_message = type(exc).__name__
            log.debug(
                "AeatAuthenticator: login probe navigation failed target=<aeat-login-probe> failure=%s",
                type(exc).__name__,
            )
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception as _exc:
                    log.debug("AeatAuthenticator: probe page.close suppressed: %s", _exc, exc_info=True)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return _build_certificate_login_assertion(
            session,
            status_code=status_code,
            response_successful=response_successful,
            final_url=final_url,
            error_message=error_message,
            elapsed_ms=elapsed_ms,
            attempted_at=attempted_at,
        )

    async def _capture_storage_state_locked(self, session: AeatSession) -> Path:
        """Write encrypted storage state with :class:`PersistedSessionMetadata`."""
        context = self._context
        if context is None:
            raise AeatLoginAssertionError(
                "no active browser context; cannot capture storage_state",
                translated_message="adapters.auth.authenticator.errors.no_context_capture_storage",
            )

        storage_state_path = session.storage_state_path or self._resolve_storage_state_path()
        storage_state: Mapping[str, object] = await context.storage_state()
        storage_state_sha256 = session_store.storage_state_sha256(storage_state)
        certificate_thumbprint = session.certificate_thumbprint
        certificate_subject = session.certificate_subject
        if certificate_thumbprint is None or certificate_subject is None:
            raise AeatLoginAssertionError(
                "capture_storage_state() requires a certificate-backed session",
                translated_message="adapters.auth.authenticator.errors.capture_requires_certificate",
            )
        metadata = PersistedSessionMetadata(
            certificate_thumbprint=certificate_thumbprint,
            certificate_subject=certificate_subject,
            certificate_nif=session.identity_nif,
            authenticated_at=session.authenticated_at,
            idle_deadline=session.idle_deadline,
            storage_state_sha256=storage_state_sha256,
        )
        session_store.save(
            storage_state_path,
            storage_state=storage_state,
            metadata=metadata.model_dump(mode="json"),
        )
        return storage_state_path

    async def _resume_from_storage_state_locked(
        self,
        path: Path,
    ) -> AeatSession:
        """Resume encrypted Playwright state under ``self._lock``.

        Rebuilds a certificate-backed :class:`AeatSession` from
        :class:`PersistedSessionMetadata`, verifies it with a live
        :class:`AeatLoginAssertion`, and re-captures storage state after the
        successful probe so the persisted envelope stays current.
        """
        storage_state_path = path
        cert = self.load_certificate()
        persisted = self._load_persisted_browser_session(storage_state_path)
        metadata = self._read_persisted_metadata(storage_state_path)

        self._validate_persisted_session_metadata(
            metadata,
            cert=cert,
            storage_state_sha256=self._validate_storage_state_file(storage_state_path),
            storage_state_path=storage_state_path,
        )

        session_like = await self._resolve_browser_session()
        self._browser_session = session_like
        context: BrowserContextLike | None = None
        session: AeatSession | None = None
        resume_failed = False
        try:
            context = await session_like.create_context(
                provisioner=CertificateContextProvisioner(cert),
                storage_state=persisted.storage_state,
            )
            self._context = context
            session = AeatSession(
                authenticated_at=metadata.authenticated_at,
                idle_deadline=metadata.idle_deadline,
                storage_state_path=storage_state_path,
                identity_nif=metadata.certificate_nif,
                provider_detail=CertificateSessionDetail(
                    certificate_thumbprint=metadata.certificate_thumbprint,
                    certificate_subject=metadata.certificate_subject,
                ),
            )
            assertion = await self._run_login_probe(context, session)
            if not assertion.is_valid:
                raise PersistedSessionInvalidError(
                    "persisted AEAT browser session failed live verification",
                    translated_message="adapters.auth.authenticator.errors.persisted_session_verification_failed",
                )
            session = session.model_copy(
                update={
                    "authenticated_at": assertion.attempted_at,
                    "idle_deadline": assertion.attempted_at + AEAT_SESSION_IDLE_TTL,
                },
            )
        except PersistedSessionInvalidError:
            await self._teardown_resume_attempt(
                context,
                session_like,
            )
            self._invalidate_persisted_state(
                storage_state_path,
                "persisted AEAT browser session failed live verification",
            )
            raise
        except Exception as exc:
            resume_failed = True
            log.debug(
                "AeatAuthenticator: persisted session resume failed session=%s failure=%s",
                _PERSISTED_SESSION_LABEL,
                type(exc).__name__,
            )
            await self._teardown_resume_attempt(
                context,
                session_like,
            )
        if resume_failed:
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted AEAT browser session could not be resumed",
            )

        if context is None or session is None:
            raise AeatLoginAssertionError(
                "persisted AEAT session resume did not produce a usable context",
                translated_message="adapters.auth.authenticator.errors.resume_failed",
            )
        self._browser_session = session_like
        self._context = context
        self._active_session = session
        try:
            await self._capture_storage_state_locked(session)
        except Exception:  # AeatLoginAssertionError/OSError/PlaywrightError; cleanup + re-raise
            await self._drop_context()
            if await self._close_browser_session(session_like):
                self._browser_session = None
            self._active_session = None
            raise
        log.info(
            "AeatAuthenticator: resumed persisted session thumbprint=%s",
            session.certificate_thumbprint,
        )
        return session

    def _validate_persisted_session_metadata(
        self,
        metadata: PersistedSessionMetadata,
        *,
        cert: LoadedCertificate,
        storage_state_sha256: str,
        storage_state_path: Path,
    ) -> None:
        """Run the four ordered persisted-session validation gates.

        The checks fire in a fixed order — storage_state hash, idle
        deadline, certificate thumbprint, certificate subject, NIF/NIE — and each
        delegates to :meth:`_raise_invalid_persisted_state` (``NoReturn``)
        with its specific reason so the redacted reason code is preserved.
        Returns ``None`` only when every gate passes.
        """
        if metadata.storage_state_sha256 != storage_state_sha256:
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted storage_state hash does not match metadata",
            )
        if metadata.idle_deadline <= now():
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted AEAT session is past its idle deadline",
            )
        if metadata.certificate_thumbprint != cert.sha256_thumbprint:
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted AEAT session was captured with a different certificate thumbprint",
            )
        if metadata.certificate_subject != cert.subject:
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted AEAT session was captured with a different certificate subject",
            )
        current_nif = extract_nif_from_subject(cert)
        if metadata.certificate_nif != current_nif:
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted AEAT session was captured with a different certificate nif",
            )

    async def _teardown_resume_attempt(
        self,
        context: BrowserContextLike | None,
        session_like: BrowserSessionLike,
    ) -> None:
        """Bound and retain resources from a failed persisted-session resume."""
        await self._teardown_failed_attempt(context, session_like)

    async def _teardown_failed_attempt(
        self,
        context: BrowserContextLike | None,
        session_like: BrowserSessionLike,
    ) -> None:
        """Bound teardown without masking the authentication failure."""
        context_closed = await close_owned_browser_context(
            context,
            timeout_ms=self._settings.cadrumo_browser_close_timeout_ms,
            logger=log,
            owner="AeatAuthenticator",
        )
        if not context_closed:
            self._context = context
        elif self._context is context:
            self._context = None
        browser_session_closed = await self._close_browser_session(session_like)
        if not browser_session_closed:
            self._browser_session = session_like
        elif self._browser_session is session_like:
            self._browser_session = None
        self._active_session = None

    def _resolve_storage_state_path(
        self,
    ) -> Path:
        """Return the canonical encrypted certificate-session object key."""
        from .....core.auth_session_keys import aeat_auth_session_storage_state_path
        from .....core.bucket_pointer import require_active_bucket_id

        return aeat_auth_session_storage_state_path(require_active_bucket_id(), "storage")

    def _load_persisted_browser_session(self, storage_state_path: Path) -> session_store.PersistedBrowserSession:
        """Load encrypted browser session state or invalidate the logical path."""
        persisted: session_store.PersistedBrowserSession | None = None
        load_failed = False
        try:
            persisted = session_store.load(storage_state_path)
        except (AuthValidationError, ValidationError) as exc:
            load_failed = True
            log.debug(
                "AeatAuthenticator: persisted session load failed session=%s failure=%s",
                _PERSISTED_SESSION_LABEL,
                type(exc).__name__,
            )
        if load_failed:
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted storage_state is malformed",
            )
        if persisted is None:
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted storage_state missing",
            )
        return persisted

    def _read_persisted_metadata(self, storage_state_path: Path) -> PersistedSessionMetadata:
        """Load and validate :class:`PersistedSessionMetadata` from storage."""
        persisted = self._load_persisted_browser_session(storage_state_path)
        metadata: PersistedSessionMetadata | None = None
        metadata_failed = False
        try:
            metadata = PersistedSessionMetadata.model_validate_json(json.dumps(persisted.metadata, default=str))
        except (AuthValidationError, ValidationError) as exc:
            metadata_failed = True
            log.debug(
                "AeatAuthenticator: persisted session metadata parse failed session=%s failure=%s",
                _PERSISTED_SESSION_LABEL,
                type(exc).__name__,
            )
        if metadata_failed:
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted metadata is malformed",
            )
        if metadata is None:
            raise AeatLoginAssertionError(
                "persisted metadata did not produce a parsed model",
                translated_message="adapters.auth.authenticator.errors.metadata_parse_failed",
            )
        if metadata.schema_version != AEAT_STORAGE_STATE_SCHEMA_VERSION:
            self._raise_invalid_persisted_state(
                storage_state_path,
                f"unsupported persisted session schema version: {metadata.schema_version}",
            )
        return metadata

    def _validate_storage_state_file(self, storage_state_path: Path) -> str:
        """Validate the encrypted Playwright storage-state and return its SHA-256."""
        payload = self._load_persisted_browser_session(storage_state_path).storage_state
        if not isinstance(payload, dict):
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted storage_state root must be a JSON object",
            )
        payload_dict = payload
        if not isinstance(payload_dict.get("cookies"), list):
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted storage_state is missing the cookies array",
            )
        if not isinstance(payload_dict.get("origins"), list):
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted storage_state is missing the origins array",
            )
        return session_store.storage_state_sha256(payload_dict)

    def _raise_invalid_persisted_state(self, storage_state_path: Path, reason: str) -> NoReturn:
        """Delete persisted state and raise :class:`PersistedSessionInvalidError`."""
        reason_code = persisted_session_reason_code(reason)
        self._invalidate_persisted_state(storage_state_path, reason_code)
        raise PersistedSessionInvalidError(
            "persisted AEAT browser session is invalid",
            context={"session": _PERSISTED_SESSION_LABEL, "reason": reason_code},
            translated_message="errors.auth.auth_auth_authenticator_persisted_session_invalid",
        ) from None

    def _invalidate_persisted_state(self, storage_state_path: Path, reason_code: str) -> None:
        """Best-effort delete of the persisted state pair."""
        session_store.delete(storage_state_path)
        log.info(
            "AeatAuthenticator: invalidated persisted session session=%s reason=%s",
            _PERSISTED_SESSION_LABEL,
            reason_code,
        )

    def _require_bundle(self) -> CertificateBundle:
        """Assemble a :class:`CertificateBundle` from ``settings``.

        Raises :class:`CertificateLoadError` if the mandatory cert fields
        are not configured. Callers should already have applied the
        relevant operational auth/profile/read-only gates before calling
        the authenticator.
        """
        path = self._credentials.certificate_path
        if path is None:
            raise CertificateLoadError(
                translated_message="application.auth.certificate.load.path_unset",
            )
        password = self._credentials.password
        if password is None:
            raise CertificateLoadError(
                translated_message="application.auth.certificate.load.password_unset",
            )
        return CertificateBundle(
            path=path,
            password=password,
            friendly_name=self._credentials.friendly_name,
        )

    async def _resolve_browser_session(self) -> BrowserSessionLike:
        """Return the browser session supplied by the configured factory.

        Application orchestration owns production factory wiring. Omitting the
        factory is supported only for synchronous certificate helpers and is an
        error for direct async authentication.
        """
        if self._browser_session_factory is not None:
            return await self._browser_session_factory(self._settings)
        raise AuthConfigurationError(
            "AeatAuthenticator was constructed without a browser "
            "session factory; the default Playwright factory is not "
            "yet wired. Pass a factory explicitly or use only the "
            "synchronous health helpers.",
        )

    async def _drop_context(self) -> bool:
        """Close any held browser context and retain failures for retry."""
        context = self._context
        closed = await close_owned_browser_context(
            context,
            timeout_ms=self._settings.cadrumo_browser_close_timeout_ms,
            logger=log,
            owner="AeatAuthenticator",
        )
        if closed:
            self._context = None
        return closed

    async def _close_browser_session(self, session: BrowserSessionLike | None) -> bool:
        """Close an owned browser session, retaining failed cleanup for retry."""
        return await close_owned_browser_session(
            session,
            timeout_ms=self._settings.cadrumo_browser_close_timeout_ms,
            logger=log,
            owner="AeatAuthenticator",
        )


__all__ = [
    "AEAT_SESSION_IDLE_TTL",
    "AeatAuthenticator",
]

