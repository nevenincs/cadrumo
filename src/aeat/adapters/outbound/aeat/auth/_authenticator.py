"""Certificate-backed live-AEAT authenticator.

This module implements the certificate concrete for the application
:class:`aeat.application.auth.AuthProvider` contract. It composes
:class:`CertificateBundle` loading, mTLS handshake checks, a
:class:`CertificateContextProvisioner`-backed browser context, and a
post-auth login probe into a narrow async provider surface.

The provider returns the imported :class:`AeatSession` and
:class:`AeatLoginAssertion` records owned by
:mod:`aeat.adapters.outbound.aeat.auth._authenticator_types`. Captured
Playwright storage state is written through the encrypted session store
with :class:`PersistedSessionMetadata`, then resumed only after hash,
idle-deadline, certificate thumbprint, certificate subject, and live
probe checks pass.

Design notes:

* The module holds an 18-minute session idle TTL as a code-level
  constant. The value is deliberately **not** an env var — the
  operator surface is kept narrow, and AEAT's observed idle window
  is ~20 minutes (the extra 2 minutes is safety margin).
* ``authenticate()`` accepts an optional injectable browser session
  factory. Unit tests pass an in-process factory that produces a stand-in
  context honouring the ``_aeat_certificate_thumbprint`` marker
  contract. This lets the whole authenticator exercise run under
  ``@pytest.mark.unit`` without importing Playwright.
* ``reauthenticate()`` is single-shot. Callers cap retries at ONE
  per downstream call-site; a second consecutive failure raises
  :class:`AeatSessionExpiredError` upwards rather than loop.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final, NoReturn

from pydantic import ValidationError

from .....core.config import Settings as _Settings
from .....core.logging import get_logger
from .....core.time import now
from .._playwright import PlaywrightError
from . import _session_store
from ._authenticator_persistence import (
    AEAT_STORAGE_STATE_SCHEMA_VERSION,
    PersistedSessionMetadata,
    persisted_session_reason_code,
    persisted_session_reason_from_error,
)
from ._authenticator_types import (
    AeatLoginAssertion,
    AeatSession,
    BrowserContextLike,
    BrowserPageLike,
    BrowserResponseLike,
    BrowserSessionFactory,
    BrowserSessionLike,
    CertificateHealthCheck,
    _PersistedSessionInvalidError,
)
from ._errors import AeatLoginAssertionError, AeatSessionExpiredError, AuthValidationError
from ._providers import (
    CERTIFICATE_CONTEXT_MARKER,
    AuthProviderDescription,
    AuthProviderKind,
    CertificateContextProvisioner,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
)
from .certificate import (
    CertificateBundle,
    CertificateError,
    CertificateHealth,
    CertificateLoadError,
    CertificateNifParseError,
    HandshakeResult,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
    load_certificate,
    verify_handshake,
)
from .certificate import (
    health as certificate_health,
)

if TYPE_CHECKING:
    from .....core.config import Settings

log = get_logger(__name__)

# Environment variable name referenced in operator-facing error messages.
# Named constant so grepping for the env-var name surfaces every usage site.
_CERT_PASSWORD_SECRET_ENV: Final[str] = "AEAT_CERTIFICATE_PASSWORD_SECRET"
_PERSISTED_SESSION_LABEL: Final[str] = "<persisted-aeat-session>"


AEAT_SESSION_IDLE_TTL: Final[timedelta] = timedelta(minutes=18)
"""Maximum idle lifetime for an authenticated AEAT Playwright session.

AEAT's observed server-side idle window is ~20 minutes; 18 minutes
leaves a 2-minute safety margin before the next downstream call
would see a 401/403. Tuning this value is a code change, not an
env-var change — the operator surface stays narrow.
"""


AEAT_LOGIN_NAVIGATION_TIMEOUT_MS: Final[int] = _Settings().aeat_browser_navigation_timeout_ms
"""Playwright navigation timeout for post-auth verification probes."""


# ── Authenticator ───────────────────────────────────────────────────────────


class AeatAuthenticator:
    """Certificate implementation of the application :class:`AuthProvider`.

    The authenticator owns:

    * Certificate loading and health evaluation (via the existing
      module-level ``load_certificate`` / ``health`` surface).
    * TLS handshake verification (via the existing
      ``verify_handshake``).
    * Playwright browser-context construction with the cert wired
      through (via an injectable browser session factory).
    * Login-assertion verification.
    * Session lifecycle: ``authenticate``, ``reauthenticate``,
      ``close``.

    Use as an async context manager::

        async with AeatAuthenticator(settings) as auth:
            session = await auth.authenticate()
            assertion = await auth.verify_login(session)

    Returned sessions use :class:`CertificateSessionDetail`, login probes use
    :class:`CertificateLoginAssertionDetail`, and persisted resume state is
    validated against :class:`PersistedSessionMetadata`. Callers that only
    need synchronous health, handshake, or NIF extraction can instantiate
    without entering the async context.
    """

    kind: AuthProviderKind = AuthProviderKind.CERTIFICATE

    def __init__(
        self,
        settings: Settings,
        *,
        browser_session_factory: BrowserSessionFactory | None = None,
        handshake_verifier: Callable[[LoadedCertificate, str], HandshakeResult] | None = None,
        navigation_timeout_ms: int = AEAT_LOGIN_NAVIGATION_TIMEOUT_MS,
        certificate_health_check: CertificateHealthCheck | None = None,
    ) -> None:
        """Construct an authenticator bound to ``settings``.

        Args:
            settings: The :class:`aeat.core.config.Settings` instance the
                authenticator reads its certificate path,
                passphrase env var, backend, and verify URL from.
            browser_session_factory: Optional async callable
                returning a :class:`BrowserSessionLike`. When
                omitted, the authenticator constructs a real
                :class:`aeat.adapters.outbound.aeat.browser.BrowserSession` lazily at
                :meth:`authenticate` time. Tests pass an in-process implementation here
                to avoid the Playwright import path.
            handshake_verifier: Optional callable used to confirm the
                certificate handshake during login. Defaults to the
                module-level :func:`verify_handshake`; tests inject a
                purpose-built callable to exercise specific handshake outcomes.
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
        self._browser_session_factory = browser_session_factory
        self._handshake_verifier = handshake_verifier or verify_handshake
        self._navigation_timeout_ms = navigation_timeout_ms
        self._certificate_health_check: CertificateHealthCheck = certificate_health_check or certificate_health
        # All asyncio primitives below are bound to the first event
        # loop that awaits the authenticator. The class assumes a
        # single-loop lifetime — constructing an instance in one loop
        # (e.g. a pytest-asyncio fixture) and reusing it in another
        # will trip "attached to a different loop" errors. Callers
        # that need cross-loop reuse must construct a fresh instance.
        self._lock = asyncio.Lock()
        self._browser_session: BrowserSessionLike | None = None
        self._context: BrowserContextLike | None = None
        self._active_session: AeatSession | None = None
        # _closing is a one-way latch that, once set under the lock,
        # prevents new verify_login() calls from registering in-flight
        # pages. Together with _inflight_drained it forms a strict
        # barrier: close() first latches _closing, then waits for
        # the drain event, then tears down the context. Any
        # verify_login() call that arrives after the latch is set
        # raises rather than starting a navigation.
        self._closing = False
        self._inflight_pages = 0
        self._inflight_drained: asyncio.Event = asyncio.Event()
        self._inflight_drained.set()

    async def __aenter__(self) -> AeatAuthenticator:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

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
            warn_days=self._settings.aeat_cert_warn_days,
            critical_days=self._settings.aeat_cert_critical_days,
            now=now,
        )

    def verify_handshake(self, *, url: str | None = None) -> HandshakeResult:
        """Run the mTLS smoke probe against ``url``.

        Args:
            url: Optional override. When omitted, the authenticator
                uses :attr:`Settings.aeat_certificate_verify_url`.

        Returns:
            A :class:`HandshakeResult` with the probe outcome.
        """
        target = url or self._settings.aeat_certificate_verify_url
        cert = self.load_certificate()
        return self._handshake_verifier(cert, target)

    def extract_nif_from_subject(self, cert: LoadedCertificate) -> str:
        """Parse the taxpayer NIF / NIE from ``cert``'s subject."""
        return extract_nif_from_subject(cert)

    # ── Async lifecycle ─────────────────────────────────────────────────────

    async def authenticate(
        self,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> AeatSession:
        """Produce an authenticated :class:`AeatSession`.

        The method first attempts to resume a previously captured
        Playwright ``storage_state`` backed by
        :class:`PersistedSessionMetadata`. If that persisted state is
        missing, malformed, stale, certificate-mismatched, or fails a live
        verification probe, it is deleted and the method falls back to a
        fresh certificate handshake plus browser login flow. Fresh contexts
        are created through :class:`CertificateContextProvisioner` so the
        AEAT origin receives the configured client certificate.

        Args:
            browser_session: Optional existing browser session to reuse.
            target_url: Optional override URL for the authentication target.

        Returns:
            An authenticated :class:`AeatSession` ready for downstream use.

        Raises:
            AeatLoginAssertionError: When the browser session factory returns a context
                missing the thumbprint marker, or when the login probe fails.
            Exception: Re-raised when storage-state capture fails after a successful
                context creation.
        """
        async with self._lock:
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "AeatAuthenticator already has an active session; "
                    "call close() or reauthenticate() before "
                    "authenticating again",
                    translated_message="adapters.auth.authenticator.errors.already_active",
                )
            target = target_url or self._settings.aeat_certificate_verify_url
            resume_path = self._resolve_storage_state_path(browser_session)
            if _session_store.exists(resume_path):
                try:
                    return await self._resume_from_storage_state_locked(
                        resume_path,
                        browser_session=browser_session,
                        target_url=target,
                    )
                except _PersistedSessionInvalidError as exc:
                    reason = persisted_session_reason_from_error(exc)
                    log.info(
                        "AeatAuthenticator: persisted session invalid session=%s reason=%s; falling back to fresh auth",
                        _PERSISTED_SESSION_LABEL,
                        reason,
                    )

            cert = self.load_certificate()
            # verify_handshake performs real network I/O via httpx; it
            # is synchronous. Running it on the default event-loop
            # thread would block every other coroutine for the
            # duration of the TLS round-trip. asyncio.to_thread lets
            # concurrent tasks make progress while the handshake runs.
            handshake = await asyncio.to_thread(self._handshake_verifier, cert, target)
            nif = extract_nif_from_subject(cert)

            session_like = browser_session or await self._resolve_browser_session()
            context = await session_like.create_context(
                provisioner=CertificateContextProvisioner(
                    cert,
                    origin=self._settings.aeat_certificate_verify_url,
                ),
            )

            try:
                self._assert_context_marker(context, cert)
            except AeatLoginAssertionError:
                try:
                    await context.close()
                except Exception as _exc:  # Playwright context.close() undocumented; log and continue
                    log.debug(
                        "AeatAuthenticator: context.close after marker failure suppressed: %s",
                        _exc,
                        exc_info=True,
                    )
                await self._close_browser_session(session_like)
                raise

            storage_state_path = self._resolve_storage_state_path(session_like)
            provisional_at = now()
            provisional_session = AeatSession(
                provider_kind=self.kind,
                authenticated_at=provisional_at,
                idle_deadline=provisional_at + AEAT_SESSION_IDLE_TTL,
                storage_state_path=storage_state_path,
                identity_nif=nif,
                provider_detail=CertificateSessionDetail(
                    certificate_thumbprint=cert.sha256_thumbprint,
                    certificate_subject=cert.subject,
                    handshake=handshake,
                ),
            )
            assertion = await self._run_login_probe(context, provisional_session, target)
            if not assertion.is_valid:
                try:
                    await context.close()
                except Exception as _exc:
                    log.debug(
                        "AeatAuthenticator: context.close after failed probe suppressed: %s",
                        _exc,
                        exc_info=True,
                    )
                await self._close_browser_session(session_like)
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
                await self._close_browser_session(session_like)
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
        handshake fails, or ``verify_login`` still returns
        ``certificate_recognised=False`` — MUST raise
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

    async def verify_login(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion:
        """Navigate the authenticated context to ``target_url``.

        The assertion record captures three independent signals:

        * ``handshake_success`` — the TLS handshake attached to the
          session completed successfully.
        * ``certificate_recognised`` — the post-auth navigation
          returned a non-challenge HTTP response.
        * ``parsed_nif`` — the NIF / NIE extracted from the
          certificate subject (always populated when the session
          carries a cert; ``None`` only in exceptional structural
          failures).

        Args:
            session: The :class:`AeatSession` returned from
                :meth:`authenticate`.
            target_url: Optional override. Defaults to
                :attr:`Settings.aeat_certificate_verify_url`.

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
        # The _closing latch is checked inside the lock to close the
        # TOCTOU window between close()'s drain-wait and its teardown.
        async with self._lock:
            if self._closing:
                raise AeatLoginAssertionError(
                    "authenticator is closing; no new verify_login allowed",
                    translated_message="adapters.auth.authenticator.errors.closing",
                )
            context = self._context
            if context is None:
                raise AeatLoginAssertionError(
                    "no active browser context; call authenticate() first",
                    translated_message="adapters.auth.authenticator.errors.no_active_context",
                )
            self._inflight_pages += 1
            self._inflight_drained.clear()

        target = target_url or self._settings.aeat_certificate_verify_url
        try:
            return await self._run_login_probe(context, session, target)
        finally:
            async with self._lock:
                self._inflight_pages -= 1
                if self._inflight_pages <= 0:
                    self._inflight_pages = 0
                    self._inflight_drained.set()

    async def verify(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion:
        """Provider-protocol alias for :meth:`verify_login`.

        Returns:
            A :class:`AeatLoginAssertion` describing the verification outcome.
        """
        return await self.verify_login(session, target_url=target_url)

    async def capture_storage_state(self, session: AeatSession) -> Path:
        """Persist the active Playwright state and :class:`PersistedSessionMetadata`."""
        async with self._lock:
            if self._active_session != session:
                raise AeatLoginAssertionError(
                    "capture_storage_state() requires the currently active authenticated session",
                    translated_message="adapters.auth.authenticator.errors.capture_requires_active_session",
                )
            return await self._capture_storage_state_locked(session)

    async def resume_from_storage_state(
        self,
        path: Path,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> AeatSession:
        """Resume a certificate :class:`AeatSession` from encrypted storage.

        The persisted browser state and :class:`PersistedSessionMetadata` are
        validated before a :class:`CertificateContextProvisioner` opens a
        context with the restored storage state. A successful live probe
        refreshes ``authenticated_at`` and ``idle_deadline`` before the
        session is returned.
        """
        async with self._lock:
            if self._context is not None:
                raise AuthValidationError(
                    "AeatAuthenticator already has an active session; call close() before resuming another one",
                    translated_message="adapters.auth.authenticator.errors.already_active_before_resume",
                )
            return await self._resume_from_storage_state_locked(
                path,
                browser_session=browser_session,
                target_url=target_url or self._settings.aeat_certificate_verify_url,
            )

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

        if self._settings.aeat_certificate_path is None:
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=False,
                available=False,
                health_severity="info",
                health_summary=tr("application.auth.certificate.health.path_unset"),
            )
        if not self._settings.aeat_certificate_path.is_file():
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=False,
                available=False,
                health_severity="warning",
                health_summary=tr(
                    "application.auth.certificate.health.file_missing",
                    path=str(self._settings.aeat_certificate_path),
                ),
            )
        if self._settings.aeat_certificate_password_secret is None:
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=True,
                available=False,
                health_summary=f"{_CERT_PASSWORD_SECRET_ENV} not set",
            )
        # CertificateBundle now carries the passphrase as a SecretStr
        # directly. The authenticator passes the settings-resolved
        # secret straight through; the OpenSSL-binding env channel is
        # gone, so the secret never enters os.environ.
        _deferred_error: AuthValidationError | None = None
        try:
            backend = self._settings.aeat_certificate_backend
            health = self._certificate_health_check(
                self._settings.aeat_certificate_path,
                password=self._settings.aeat_certificate_password_secret,
                warn_days=self._settings.aeat_cert_warn_days,
                critical_days=self._settings.aeat_cert_critical_days,
                backend=backend,
                friendly_name=self._settings.aeat_certificate_friendly_name,
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
                        source_path=self._settings.aeat_certificate_path,
                        friendly_name=self._settings.aeat_certificate_friendly_name,
                        backend=backend,
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

        Waits for any in-flight :meth:`verify_login` call to finish
        its navigation before tearing down the browser context, so a
        page cannot be closed out from under a running probe. A
        one-way ``_closing`` latch is set under the lock before the
        drain wait so that a new ``verify_login`` cannot slip in
        between the wait returning and the teardown acquiring the
        lock — the latch forces any arriving probe to raise.

        After ``close()`` returns, the authenticator is re-usable
        (the latch is reset, the browser session is nulled, the
        context is nulled). ``reauthenticate()`` depends on this
        re-use path.
        """
        # Step 1: latch _closing under the lock so subsequent
        # verify_login() calls raise before they register.
        async with self._lock:
            self._closing = True
        # Step 2: wait for any already-registered verify_login() to
        # finish. No new registrations can clear the event because
        # the latch blocks them at their own lock acquisition.
        await self._inflight_drained.wait()
        # Step 3: tear down under the lock. Reset the latch at the
        # end so the instance is usable again (reauthenticate relies
        # on this).
        async with self._lock:
            await self._drop_context()
            await self._close_browser_session(self._browser_session)
            self._browser_session = None
            self._active_session = None
            self._closing = False

    # ── Internals ───────────────────────────────────────────────────────────

    async def _run_login_probe(
        self,
        context: BrowserContextLike,
        session: AeatSession,
        target: str,
    ) -> AeatLoginAssertion:
        """Run the post-auth probe and build an :class:`AeatLoginAssertion`."""
        attempted_at = now()
        start = time.perf_counter()

        status_code = 0
        certificate_recognised = False
        error_message: str | None = None
        page: BrowserPageLike | None = None
        try:
            page = await context.new_page()
            response = await page.goto(target, timeout=self._navigation_timeout_ms)
            if response is not None:
                status_code = int(response.status)
                certificate_recognised = 200 <= status_code < 400
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
        handshake = session.handshake
        handshake_success = bool(handshake.success) if handshake is not None else False
        is_valid = handshake_success and certificate_recognised and bool(session.identity_nif)
        return AeatLoginAssertion(
            target_url=target,
            is_valid=is_valid,
            provider_kind=session.provider_kind,
            identity_nif=session.identity_nif,
            status_code=status_code,
            elapsed_ms=elapsed_ms,
            attempted_at=attempted_at,
            error_message=error_message,
            assertion_detail=CertificateLoginAssertionDetail(
                handshake_success=handshake_success,
                certificate_recognised=certificate_recognised,
                parsed_subject=session.certificate_subject,
            ),
        )

    async def _capture_storage_state_locked(self, session: AeatSession) -> Path:
        """Write encrypted storage state with :class:`PersistedSessionMetadata`."""
        context = self._context
        if context is None:
            raise AeatLoginAssertionError(
                "no active browser context; cannot capture storage_state",
                translated_message="adapters.auth.authenticator.errors.no_context_capture_storage",
            )

        storage_state_path = session.storage_state_path or self._resolve_storage_state_path(self._browser_session)
        storage_state: Mapping[str, object] = await context.storage_state()
        storage_state_sha256 = _session_store.storage_state_sha256(storage_state)
        certificate_thumbprint = session.certificate_thumbprint
        certificate_subject = session.certificate_subject
        handshake = session.handshake
        if certificate_thumbprint is None or certificate_subject is None or handshake is None:
            raise AeatLoginAssertionError(
                "capture_storage_state() requires a certificate-backed session with handshake metadata",
                translated_message="adapters.auth.authenticator.errors.capture_requires_certificate",
            )
        metadata = PersistedSessionMetadata(
            certificate_thumbprint=certificate_thumbprint,
            certificate_subject=certificate_subject,
            certificate_nif=session.identity_nif,
            authenticated_at=session.authenticated_at,
            idle_deadline=session.idle_deadline,
            storage_state_sha256=storage_state_sha256,
            handshake=handshake,
        )
        _session_store.save(
            storage_state_path,
            storage_state=storage_state,
            metadata=metadata.model_dump(mode="json"),
        )
        return storage_state_path

    async def _resume_from_storage_state_locked(
        self,
        path: Path,
        *,
        browser_session: BrowserSessionLike | None,
        target_url: str,
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
            storage_state_sha256=persisted.storage_state_sha256,
            storage_state_path=storage_state_path,
        )

        session_like = browser_session or await self._resolve_browser_session()
        owns_session = browser_session is None
        context: BrowserContextLike | None = None
        session: AeatSession | None = None
        resume_failed = False
        try:
            context = await session_like.create_context(
                provisioner=CertificateContextProvisioner(
                    cert,
                    origin=self._settings.aeat_certificate_verify_url,
                ),
                storage_state=persisted.storage_state,
            )
            self._assert_context_marker(context, cert)
            session = AeatSession(
                provider_kind=self.kind,
                authenticated_at=metadata.authenticated_at,
                idle_deadline=metadata.idle_deadline,
                storage_state_path=storage_state_path,
                identity_nif=metadata.certificate_nif,
                provider_detail=CertificateSessionDetail(
                    certificate_thumbprint=metadata.certificate_thumbprint,
                    certificate_subject=metadata.certificate_subject,
                    handshake=metadata.handshake,
                ),
            )
            assertion = await self._run_login_probe(context, session, target_url)
            if not assertion.is_valid:
                raise _PersistedSessionInvalidError(
                    "persisted AEAT browser session failed live verification",
                    translated_message="adapters.auth.authenticator.errors.persisted_session_verification_failed",
                )
            session = session.model_copy(
                update={
                    "authenticated_at": assertion.attempted_at,
                    "idle_deadline": assertion.attempted_at + AEAT_SESSION_IDLE_TTL,
                },
            )
        except _PersistedSessionInvalidError:
            await self._teardown_resume_attempt(
                context,
                session_like,
                owns_session=owns_session,
                context_close_log="AeatAuthenticator: context.close after invalid persisted session suppressed: %s",
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
                owns_session=owns_session,
                context_close_log="AeatAuthenticator: context.close after resume error suppressed: %s",
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
            if owns_session:
                await self._close_browser_session(session_like)
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
        deadline, certificate thumbprint, certificate subject — and each
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

    async def _teardown_resume_attempt(
        self,
        context: BrowserContextLike | None,
        session_like: BrowserSessionLike,
        *,
        owns_session: bool,
        context_close_log: str,
    ) -> None:
        """Close a failed resume attempt's context and owned browser session.

        Mirrors the suppress-and-log teardown shared by both failure
        branches: any ``context.close()`` error is swallowed and logged at
        DEBUG with ``context_close_log``, and the browser session is closed
        only when this authenticator owns it (``owns_session``).
        """
        if context is not None:
            try:
                await context.close()
            except Exception as _exc:
                log.debug(context_close_log, _exc, exc_info=True)
        if owns_session:
            await self._close_browser_session(session_like)

    def _assert_context_marker(
        self,
        context: BrowserContextLike,
        cert: LoadedCertificate,
    ) -> None:
        """Ensure the browser context was created with the expected certificate."""
        marker = getattr(context, CERTIFICATE_CONTEXT_MARKER, None)
        if marker != cert.sha256_thumbprint:
            raise AeatLoginAssertionError(
                "browser context was not tagged with the expected "
                f"{CERTIFICATE_CONTEXT_MARKER} marker; cannot continue",
                translated_message="adapters.auth.authenticator.errors.context_marker_missing",
            )

    def _resolve_storage_state_path(
        self,
        browser_session: BrowserSessionLike | None,
    ) -> Path:
        """Return the storage-state path for ``browser_session`` or settings."""
        if browser_session is not None:
            profile = getattr(browser_session, "profile", None)
            storage_state_path = getattr(profile, "storage_state_path", None)
            if isinstance(storage_state_path, Path):
                return storage_state_path
        from .....core import require_active_bucket_id
        from .....core.auth_session_keys import aeat_auth_session_storage_state_path

        return aeat_auth_session_storage_state_path(require_active_bucket_id(), "storage")

    def _load_persisted_browser_session(self, storage_state_path: Path) -> _session_store.PersistedBrowserSession:
        """Load encrypted browser session state or invalidate the logical path."""
        persisted: _session_store.PersistedBrowserSession | None = None
        load_failed = False
        try:
            persisted = _session_store.load(storage_state_path)
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
        return _session_store.storage_state_sha256(payload_dict)

    def _raise_invalid_persisted_state(self, storage_state_path: Path, reason: str) -> NoReturn:
        """Delete persisted state and raise :class:`_PersistedSessionInvalidError`."""
        reason_code = persisted_session_reason_code(reason)
        self._invalidate_persisted_state(storage_state_path, reason_code)
        raise _PersistedSessionInvalidError(
            "persisted AEAT browser session is invalid",
            context={"session": _PERSISTED_SESSION_LABEL, "reason": reason_code},
            translated_message="errors.auth.auth_auth_authenticator_persisted_session_invalid",
        ) from None

    def _invalidate_persisted_state(self, storage_state_path: Path, reason_code: str) -> None:
        """Best-effort delete of the persisted state pair."""
        _session_store.delete(storage_state_path)
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
        path = self._settings.aeat_certificate_path
        if path is None:
            raise CertificateLoadError(
                translated_message="application.auth.certificate.load.path_unset",
            )
        password = self._settings.aeat_certificate_password_secret
        if password is None:
            raise CertificateLoadError(
                translated_message="application.auth.certificate.load.password_unset",
            )
        return CertificateBundle(
            path=path,
            password=password,
            friendly_name=self._settings.aeat_certificate_friendly_name,
            backend=self._settings.aeat_certificate_backend,
        )

    async def _resolve_browser_session(self) -> BrowserSessionLike:
        """Return the injected factory's session, or construct a real one.

        The real construction path is intentionally deferred to call
        time so modules that only use the synchronous surface never
        pay the Playwright import cost.
        """
        if self._browser_session_factory is not None:
            return await self._browser_session_factory(self._settings)
        raise AeatLoginAssertionError(
            "AeatAuthenticator was constructed without a browser "
            "session factory; the default Playwright factory is not "
            "yet wired. Pass a factory explicitly or use only the "
            "synchronous helpers (health, verify_handshake).",
        )

    async def _drop_context(self) -> None:
        """Close any held browser context; swallow errors on teardown."""
        context = self._context
        self._context = None
        if context is None:
            return
        try:
            await context.close()
        except PlaywrightError:
            log.warning("AeatAuthenticator: context close failed", exc_info=True)

    async def _close_browser_session(self, session: BrowserSessionLike | None) -> None:
        """Best-effort teardown of a :class:`BrowserSessionLike`.

        The Protocol does not mandate a ``close()`` coroutine; real
        :class:`aeat.adapters.outbound.aeat.browser.BrowserSession` wraps a Playwright
        ``Browser`` which owns a Chromium OS process. Tests supply
        lightweight implementations that may not. We probe for the method and call it when
        present; failure to close is logged but never raised.
        """
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
            log.warning("AeatAuthenticator: browser session close failed", exc_info=True)


__all__ = [
    "AEAT_SESSION_IDLE_TTL",
    "AeatAuthenticator",
    "AeatLoginAssertion",
    "AeatSession",
    "BrowserContextLike",
    "BrowserResponseLike",
    "BrowserSessionFactory",
    "BrowserSessionLike",
]
