"""Unified live-AEAT authenticator facade.

This module is the single entry point every future remote-read
module (filing history #168, missing-filing detection #169, AEAT
messages #170, VAT balance tracking #171) should depend on. It
composes the certificate loader, the Playwright browser session,
and the login-assertion flow into a narrow async surface.

The module also defines :class:`AeatSession` and
:class:`AeatLoginAssertion` — the two pydantic records that describe
"what it means to have live AEAT access right now" and "what
happened the last time we verified that access". Both records are
strict, frozen, carry no secret material, and are safe to log or
serialise into the submission audit trail.

Design notes — see
``.vault/adr/2026-04-17-aeat-access-gate-adr.md``:

* The module holds an 18-minute session idle TTL as a code-level
  constant. The value is deliberately **not** an env var — the
  operator surface is kept narrow, and AEAT's observed idle window
  is ~20 minutes (the extra 2 minutes is safety margin).
* ``authenticate()`` accepts an optional injectable browser session
  factory. Unit tests pass a fake factory that produces a stand-in
  context honouring the ``_aeat_certificate_thumbprint`` marker
  contract. This lets the whole authenticator exercise run under
  ``@pytest.mark.unit`` without importing Playwright.
* ``reauthenticate()`` is single-shot. Callers cap retries at ONE
  per downstream call-site; a second consecutive failure raises
  :class:`AeatSessionExpiredError` upwards rather than loop.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from aeat.auth.certificate import (
    AeatLoginAssertionError,
    AeatSessionExpiredError,
    CertificateBundle,
    CertificateHealth,
    HandshakeResult,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
    load_certificate,
    verify_handshake,
)
from aeat.logging import get_logger

if TYPE_CHECKING:
    from aeat.config import Settings

log = get_logger(__name__)


AEAT_SESSION_IDLE_TTL: Final[timedelta] = timedelta(minutes=18)
"""Maximum idle lifetime for an authenticated AEAT Playwright session.

AEAT's observed server-side idle window is ~20 minutes; 18 minutes
leaves a 2-minute safety margin before the next downstream call
would see a 401/403. Tuning this value is a code change, not an
env-var change — the operator surface stays narrow.
"""


_MARKER_ATTR = "_aeat_certificate_thumbprint"


# ── Boundary records ────────────────────────────────────────────────────────


class AeatLoginAssertion(BaseModel):
    """Structured outcome of a single live AEAT verification attempt.

    The record captures the three independent signals the
    authenticator collects during ``verify_login()`` — the TLS
    handshake, the post-auth portal reachability, and the
    cert-derived identity — plus a composite ``is_valid`` predicate
    downstream code should read.

    Attributes:
        target_url: Navigation target used for the verification.
        is_valid: Composite predicate:
            ``handshake_success AND certificate_recognised AND
            parsed_nif is not None``.
        handshake_success: TLS handshake leg.
        certificate_recognised: Playwright navigation returned a
            non-challenge response (HTTP 2xx / 3xx) with the cert
            supplied.
        parsed_nif: NIF / NIE extracted from the certificate subject
            (authoritative — never scraped from AEAT HTML).
        parsed_subject: RFC-4514 subject DN of the cert.
        status_code: HTTP status of the navigation probe.
        elapsed_ms: Wall-clock elapsed time for the full
            verification (handshake + navigation).
        attempted_at: Timezone-aware UTC timestamp of the attempt.
        error_message: Human-readable failure reason when the
            assertion is not valid.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    target_url: str
    is_valid: bool
    handshake_success: bool
    certificate_recognised: bool
    parsed_nif: str | None
    parsed_subject: str | None
    status_code: int
    elapsed_ms: int
    attempted_at: datetime
    error_message: str | None = None


class AeatSession(BaseModel):
    """Record describing an authenticated live AEAT session.

    The session carries **no secret material** — every field is
    safe to log, serialise into audit trails, and surface via CLI
    diagnostics. Secrets (passphrase, raw PKCS#12 bytes, private-key
    handle) live on :class:`LoadedCertificate` via
    :class:`pydantic.PrivateAttr` and never bleed into this record.

    Attributes:
        certificate_thumbprint: SHA-256 hex of the cert's DER
            encoding. Ties the session to a specific PKCS#12
            bundle; the browser context's
            ``_aeat_certificate_thumbprint`` marker attribute is
            set to the same value.
        certificate_subject: RFC-4514 subject DN of the cert.
        certificate_nif: DNI / NIE extracted from the subject via
            :func:`extract_nif_from_subject`.
        authenticated_at: Timezone-aware UTC timestamp of the
            successful ``authenticate()`` call that produced this
            record.
        idle_deadline: Timezone-aware UTC timestamp beyond which the
            session MUST be reauthenticated. Derived as
            ``authenticated_at + AEAT_SESSION_IDLE_TTL``.
        storage_state_path: Playwright ``storage_state`` JSON
            location (cookies + localStorage), or ``None`` if the
            caller chose not to persist.
        handshake: Embedded :class:`HandshakeResult` from the TLS
            leg of the authentication. Kept so callers can inspect
            ``elapsed_ms`` etc. without re-running the probe.
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    certificate_thumbprint: str = Field(min_length=1)
    certificate_subject: str = Field(min_length=1)
    certificate_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_path: Path | None
    handshake: HandshakeResult

    def is_stale(self, now: datetime | None = None) -> bool:
        """Return True when the session's idle deadline has elapsed."""
        reference = now if now is not None else datetime.now(UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        return reference > self.idle_deadline


# ── Browser session Protocol ────────────────────────────────────────────────


@runtime_checkable
class BrowserPageLike(Protocol):
    """Minimum structural shape of a Playwright ``Page``.

    Declared so :meth:`AeatAuthenticator.verify_login` can walk the
    navigation/close path without importing ``playwright`` at
    module load. Tests supply stand-in objects that conform
    structurally.
    """

    async def goto(self, url: str) -> BrowserResponseLike | None: ...
    async def close(self) -> None: ...


@runtime_checkable
class BrowserResponseLike(Protocol):
    """Minimum shape of a Playwright ``Response`` we read."""

    @property
    def status(self) -> int: ...


@runtime_checkable
class BrowserContextLike(Protocol):
    """Minimum structural shape of a Playwright ``BrowserContext``.

    Declared so the authenticator can be type-checked without
    importing ``playwright`` at module load. The thumbprint marker
    attribute is the only field we read explicitly.
    """

    async def new_page(self) -> BrowserPageLike: ...
    async def close(self) -> None: ...


@runtime_checkable
class BrowserSessionLike(Protocol):
    """Structural shape of :class:`aeat.browser.BrowserSession`.

    We depend on a single coroutine — ``create_context(cert=...)``
    — and a ``close()``. The authenticator does not reach into the
    session's evasion or profile machinery.
    """

    async def create_context(
        self,
        *,
        cert: LoadedCertificate | None = None,
    ) -> BrowserContextLike: ...


# ── Authenticator ───────────────────────────────────────────────────────────


class AeatAuthenticator:
    """Single entry point for live AEAT access.

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

    The class is async and meant to be used as an async context
    manager::

        async with AeatAuthenticator(settings) as auth:
            session = await auth.authenticate()
            assertion = await auth.verify_login(session)

    Callers that only need the synchronous parts (health, handshake,
    NIF extraction) can instantiate without entering the async
    context.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        browser_session_factory: BrowserSessionFactory | None = None,
    ) -> None:
        """Construct an authenticator bound to ``settings``.

        Args:
            settings: The :class:`aeat.config.Settings` instance the
                authenticator reads its certificate path,
                passphrase env var, backend, and verify URL from.
            browser_session_factory: Optional async callable
                returning a :class:`BrowserSessionLike`. When
                omitted, the authenticator constructs a real
                :class:`aeat.browser.BrowserSession` lazily at
                :meth:`authenticate` time. Tests pass a fake here
                to avoid the Playwright import path.
        """
        self._settings = settings
        self._browser_session_factory = browser_session_factory
        self._lock = asyncio.Lock()
        self._browser_session: BrowserSessionLike | None = None
        self._context: BrowserContextLike | None = None
        self._active_session: AeatSession | None = None

    async def __aenter__(self) -> AeatAuthenticator:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    # ── Synchronous helpers ─────────────────────────────────────────────────

    def load_certificate(self) -> LoadedCertificate:
        """Load the configured PKCS#12 bundle and return a frozen record."""
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
        """
        target = url or self._settings.aeat_certificate_verify_url
        cert = self.load_certificate()
        return verify_handshake(cert, target)

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

        Steps:

        1. Load the certificate (raising on expiry / missing
           passphrase / malformed bundle).
        2. Run the TLS handshake probe so we have a signed
           :class:`HandshakeResult` to embed in the returned
           session.
        3. Construct a Playwright context via the injected (or
           lazily-constructed) browser session factory, passing the
           cert through to ``browser.new_context(client_certificates=...)``
           via the session's ``cert`` kwarg. The resulting context
           is tagged with the ``_aeat_certificate_thumbprint``
           marker so :func:`preload_into_browser_context` validation
           passes.
        4. Compose and return the frozen session record.

        Raises:
            CertificateError: Any of the cert load / health / handshake
                errors propagate unchanged.
            AeatLoginAssertionError: When the browser session factory
                returns a context missing the thumbprint marker.
        """
        async with self._lock:
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "AeatAuthenticator already has an active session; "
                    "call close() or reauthenticate() before "
                    "authenticating again"
                )
            cert = self.load_certificate()
            handshake = verify_handshake(
                cert,
                target_url or self._settings.aeat_certificate_verify_url,
            )
            nif = extract_nif_from_subject(cert)

            session_like = browser_session or await self._resolve_browser_session()
            context = await session_like.create_context(cert=cert)
            self._browser_session = session_like
            self._context = context

            marker = getattr(context, _MARKER_ATTR, None)
            if marker != cert.sha256_thumbprint:
                await self._drop_context()
                raise AeatLoginAssertionError(
                    f"browser context was not tagged with the expected {_MARKER_ATTR} marker; cannot continue"
                )

            authenticated_at = datetime.now(UTC)
            storage_state_path: Path | None = None
            profile = getattr(session_like, "profile", None)
            if profile is not None:
                storage_state_path = getattr(
                    profile,
                    "storage_state_path",
                    None,
                )

            session = AeatSession(
                certificate_thumbprint=cert.sha256_thumbprint,
                certificate_subject=cert.subject,
                certificate_nif=nif,
                authenticated_at=authenticated_at,
                idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
                storage_state_path=storage_state_path,
                handshake=handshake,
            )
            self._active_session = session
            log.info(
                "AeatAuthenticator: authenticated nif=%s thumbprint=%s",
                session.certificate_nif,
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

        Args:
            session: The session to replace. Passed for traceability
                (logging, audit) and to document that the caller
                acknowledges it is discarded.

        Returns:
            A fresh :class:`AeatSession` with a new
            ``authenticated_at`` + ``idle_deadline``.
        """
        log.info(
            "AeatAuthenticator: reauthenticate old_nif=%s old_authenticated_at=%s",
            session.certificate_nif,
            session.authenticated_at.isoformat(),
        )
        async with self._lock:
            await self._drop_context()
            self._active_session = None
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
            raise AeatSessionExpiredError(
                f"session for nif={session.certificate_nif} is stale "
                f"(idle_deadline={session.idle_deadline.isoformat()})"
            )
        context = self._context
        if context is None:
            raise AeatLoginAssertionError("no active browser context; call authenticate() first")

        target = target_url or self._settings.aeat_certificate_verify_url
        attempted_at = datetime.now(UTC)
        start_seconds = datetime.now(UTC).timestamp()

        status_code = 0
        certificate_recognised = False
        error_message: str | None = None
        try:
            page = await context.new_page()
            response = await page.goto(target)
            status_code = int(getattr(response, "status", 0) or 0)
            certificate_recognised = 200 <= status_code < 400
            await page.close()
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"

        elapsed_ms = int((datetime.now(UTC).timestamp() - start_seconds) * 1000)
        handshake_success = session.handshake.success
        is_valid = handshake_success and certificate_recognised and bool(session.certificate_nif)
        return AeatLoginAssertion(
            target_url=target,
            is_valid=is_valid,
            handshake_success=handshake_success,
            certificate_recognised=certificate_recognised,
            parsed_nif=session.certificate_nif or None,
            parsed_subject=session.certificate_subject or None,
            status_code=status_code,
            elapsed_ms=elapsed_ms,
            attempted_at=attempted_at,
            error_message=error_message,
        )

    async def close(self) -> None:
        """Release the browser context + session. Idempotent."""
        async with self._lock:
            await self._drop_context()
            self._active_session = None

    # ── Internals ───────────────────────────────────────────────────────────

    def _require_bundle(self) -> CertificateBundle:
        """Assemble a :class:`CertificateBundle` from ``settings``.

        Raises :class:`ValueError` if the mandatory env-driven
        fields are not configured. This is a structural precondition
        — callers should have verified env var presence before
        calling the authenticator.
        """
        path = self._settings.aeat_certificate_path
        if path is None:
            raise ValueError("AEAT_CERTIFICATE_PATH is not set; cannot build CertificateBundle")
        return CertificateBundle(
            path=path,
            password_env_var="AEAT_CERTIFICATE_PASSWORD_SECRET",  # noqa: S106 — env var NAME, not a secret
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
            "synchronous helpers (health, verify_handshake)."
        )

    async def _drop_context(self) -> None:
        """Close any held browser context; swallow errors on teardown."""
        context = self._context
        self._context = None
        if context is None:
            return
        try:
            await context.close()
        except Exception as exc:
            log.warning("AeatAuthenticator: context close failed: %s", exc)


class BrowserSessionFactory(Protocol):
    """Async callable returning a :class:`BrowserSessionLike`.

    The factory receives the active :class:`Settings` and is
    responsible for constructing / configuring the Playwright
    session. Unit tests supply a fake factory; the production
    factory lives with the caller (typically the CLI layer) so
    ``aeat.auth`` does not import ``aeat.browser`` at module load.
    """

    async def __call__(self, settings: Settings) -> BrowserSessionLike: ...


__all__ = [
    "AEAT_SESSION_IDLE_TTL",
    "AeatAuthenticator",
    "AeatLoginAssertion",
    "AeatSession",
    "BrowserContextLike",
    "BrowserSessionFactory",
    "BrowserSessionLike",
]
