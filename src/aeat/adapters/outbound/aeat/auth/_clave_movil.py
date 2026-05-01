"""Cl@ve Móvil auth provider for AEAT Sede Electrónica (#285 / #284).

Implements the :class:`AuthProvider` protocol for the human-in-the-loop
Cl@ve Móvil flow. Captured live against the real portal on 2026-04-21;
see ``.vault/reference/2026-04-21-clave-portal-reference.md`` for the
URL template, form selectors, and polling endpoints that this module
depends on.

Design summary:

* Cl@ve Móvil ALWAYS requires Kent to approve a push on his phone,
  even in the non-QR fallback. We do not fake or retry the approval
  step — the provider just sits on the AEAT QR page and waits for the
  page's own JavaScript to complete the polling handshake.
* The provider opens a headed Playwright window on fresh login so Kent
  can scan the QR visually. Resume-from-storage-state runs headlessly
  because no human interaction is required.
* The persisted session uses :class:`aeat.adapters.outbound.aeat.auth._authenticator.AeatAuthenticator`'s
  existing sidecar layout, but with cert-specific fields left as
  placeholders and a ``provider_kind`` marker for the session detail.
  Kind-namespaced sidecar paths keep the Cl@ve and certificate
  sessions from overwriting each other.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import quote

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, ConfigDict, Field

from .....core.errors import AeatError
from .....core.logging import get_logger
from ._authenticator import (
    AEAT_SESSION_IDLE_TTL,
    AeatLoginAssertion,
    AeatLoginAssertionError,
    AeatSession,
    BrowserContextLike,
    BrowserPageLike,
    BrowserSessionFactory,
    BrowserSessionLike,
)
from ._providers import (
    AuthProviderDescription,
    AuthProviderKind,
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
)

if TYPE_CHECKING:
    from .....core.config import Settings


log = get_logger(__name__)


AEAT_CLAVE_MOVIL_SIDECAR_SCHEMA_VERSION: Final[int] = 2
"""Bumped from cert sidecar's v1 so a stale v1 file is never mistaken for Cl@ve data."""


# NIE: X/Y/Z + 7 digits + letter. DNI: 8 digits + letter.
_DNI_RE: Final[re.Pattern[str]] = re.compile(r"^\d{8}[A-Z]$", re.IGNORECASE)
_NIE_RE: Final[re.Pattern[str]] = re.compile(r"^[XYZ]\d{7}[A-Z]$", re.IGNORECASE)


class ClaveMovilConfigurationError(AeatError):
    """Raised when required Cl@ve Móvil settings are missing or malformed."""


class ClaveMovilApprovalTimeoutError(AeatError):
    """Raised when Kent does not approve the Cl@ve push within the time window."""


class _ClaveMovilSidecar(BaseModel):
    """On-disk metadata pair beside the Cl@ve Móvil storage-state file.

    Strict mode is ON so a malformed sidecar (e.g. ``"2"`` where the
    integer ``2`` is expected, or an unknown enum value) fails at
    validation rather than being silently coerced. Datetimes are
    stored as ISO-8601 strings by ``model_dump(mode="json")`` and
    parsed back by Pydantic's built-in datetime validator — the only
    coercion permitted is that round-trip.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: int = Field(default=AEAT_CLAVE_MOVIL_SIDECAR_SCHEMA_VERSION, ge=2)
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
            "successful login (e.g. www6.agenciatributaria.gob.es/wlpl/...). "
            "Used as the probe target by `aeat auth whoami` because AEAT's "
            "SelectorAccesos.html is a static dispatch page that always "
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


def _render_progress_banner(
    *,
    verification_code: str | None,
    timeout_seconds: int,
    used_non_qr_fallback: bool,
    stream: Any = sys.stderr,
) -> None:
    """Print a Kent-readable instruction block while the provider waits for approval."""
    lines = [
        "",
        "─────────────────────────────────────────────────────────────",
        " AEAT Cl@ve Móvil login",
        "─────────────────────────────────────────────────────────────",
    ]
    if used_non_qr_fallback:
        lines.extend(
            (
                " • A push notification has been sent to your Cl@ve app.",
                " • Open the app on your phone and tap 'Approve'.",
            )
        )
    else:
        lines.extend(
            (
                " • A browser window just opened showing a QR code.",
                " • Scan the QR with the Cl@ve app on your phone.",
            )
        )
    if verification_code:
        lines.extend(
            (
                "",
                f" Confirm this code on your phone: {verification_code}",
            )
        )
    lines.extend(
        (
            "",
            f" Waiting up to {timeout_seconds // 60}m {timeout_seconds % 60:02d}s for approval…",
            "─────────────────────────────────────────────────────────────",
            "",
        )
    )
    for line in lines:
        print(line, file=stream, flush=True)


class ClaveMovilAuthProvider:
    """Cl@ve Móvil implementation of the :class:`AuthProvider` protocol.

    Constructed by :func:`aeat.adapters.outbound.aeat.auth.select_provider` when
    ``kind == AuthProviderKind.CLAVE_MOVIL``. A fresh login opens a
    headed Playwright window so Kent can scan the QR; resume runs
    headlessly because the stored cookies are sufficient.
    """

    kind: AuthProviderKind = AuthProviderKind.CLAVE_MOVIL

    def __init__(
        self,
        settings: Settings,
        *,
        browser_session_factory: BrowserSessionFactory | None = None,
        navigation_timeout_ms: int = 30_000,
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
            sidecar_path = self._sidecar_path_for(resume_path)
            if resume_path.exists() and sidecar_path.exists():
                try:
                    return await self._resume_locked(
                        resume_path,
                        sidecar_path,
                        browser_session=browser_session,
                        target_url=target_url,
                    )
                except AeatLoginAssertionError as exc:
                    log.info(
                        "ClaveMovilAuthProvider: persisted session unusable; falling back to fresh login (%s)",
                        exc,
                    )
                    self._invalidate_persisted(resume_path, sidecar_path)

            return await self._fresh_login_locked(
                dni_nie=dni_nie,
                storage_state_path=resume_path,
                sidecar_path=sidecar_path,
                browser_session=browser_session,
                target_url=target_url,
            )

    async def probe_persisted_session(
        self,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> tuple[AeatSession, AeatLoginAssertion]:
        """Probe the on-disk session without side effects.

        Unlike :meth:`authenticate`, this method NEVER falls back to a
        fresh login and NEVER deletes the persisted session files —
        even when the probe fails. Callers (``aeat auth whoami``) can
        therefore use it as a pure diagnostic without accidentally
        triggering a phone-approval push.
        """
        async with self._lock:
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "ClaveMovilAuthProvider already has an active session; call close() first"
                )
            storage_state_path = self._storage_state_path()
            sidecar_path = self._sidecar_path_for(storage_state_path)
            if not (storage_state_path.exists() and sidecar_path.exists()):
                raise AeatLoginAssertionError("no persisted Cl@ve Móvil session on disk; run `aeat auth login` first")

            try:
                sidecar = _ClaveMovilSidecar.model_validate_json(sidecar_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise AeatLoginAssertionError(f"Cl@ve Móvil sidecar invalid: {exc}") from exc
            if sidecar.idle_deadline <= datetime.now(UTC):
                raise AeatLoginAssertionError("Cl@ve Móvil session past idle deadline")

            session_like, owns_session = await self._resolve_browser_session(browser_session=browser_session)
            context: BrowserContextLike | None = None
            try:
                context = await session_like.create_context(storage_state_path=storage_state_path)
                session = AeatSession(
                    provider_kind=self.kind,
                    authenticated_at=sidecar.authenticated_at,
                    idle_deadline=sidecar.idle_deadline,
                    storage_state_path=storage_state_path,
                    identity_nif=sidecar.identity_nif,
                    provider_detail=ClaveMovilSessionDetail(
                        dni_nie=sidecar.identity_nif,
                        used_non_qr_fallback=sidecar.used_non_qr_fallback,
                        verification_code=sidecar.verification_code,
                    ),
                )
                self._browser_session = session_like
                self._context = context
                self._active_session = session
                # Prefer an explicit target, then the recorded landing URL
                # from the successful login. If neither is available (legacy
                # sidecar written before schema v2), fall back to the
                # default target — a bare selector URL would always return
                # 200 against static HTML and falsely report an invalid
                # session.
                probe_target = target_url or sidecar.landing_url or self._default_target_url()
                assertion = await self.verify(session, target_url=probe_target)
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
                    with contextlib.suppress(Exception):
                        refreshed_sidecar = sidecar.model_copy(
                            update={
                                "authenticated_at": refreshed.authenticated_at,
                                "idle_deadline": refreshed.idle_deadline,
                            }
                        )
                        self._write_json_atomic(sidecar_path, refreshed_sidecar.model_dump(mode="json"))
                    return refreshed, assertion
                return session, assertion
            except Exception:
                with contextlib.suppress(Exception):
                    if context is not None:
                        await context.close()
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

        When ``target_url`` points at a post-auth AEAT URL (the concrete
        ``www<N>.agenciatributaria.gob.es/wlpl/...`` landing URL recorded
        at login time), the probe navigates there directly and treats a
        200 response that stays off ``SelectorAccesos.html`` /
        ``mi-area-personal`` as a live session. Otherwise — rarely — the
        probe falls back to driving the selector dispatch manually
        (which still requires a full auth round-trip and so is only
        ever used on session-less contexts).
        """
        context = self._context
        if context is None:
            raise AeatLoginAssertionError(
                "ClaveMovilAuthProvider.verify() requires an active browser context; call authenticate() first"
            )
        target_path = self._settings.aeat_sede_expedientes_path
        if target_url and target_path in target_url:
            probe_url = target_url
        else:
            # No recorded post-auth URL — probe via the button's
            # DialogoRepresentacion dispatcher, which requires auth cookies
            # to forward through.
            dispatcher_target = target_url or self._selector_url(target_path)
            probe_url = dispatcher_target
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
                if (
                    200 <= status_code < 400
                    and landing_url
                    and "SelectorAccesos" not in landing_url
                    and target_path in landing_url
                ):
                    session_cookie_present = True
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
        finally:
            if page is not None:
                with contextlib.suppress(Exception):
                    await page.close()

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
        """Return a Kent-readable description of the Cl@ve Móvil provider state."""
        dni_nie = (self._settings.aeat_clave_movil_dni_nie or "").strip()
        if not dni_nie:
            return AuthProviderDescription(
                kind=self.kind,
                label="Cl@ve Móvil",
                configured=False,
                available=False,
                health_summary="AEAT_CLAVE_MOVIL_DNI_NIE not set",
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
                health_summary=str(exc),
            )
        # Cl@ve Móvil always requires a live push on the phone, so we surface
        # availability as "ready to prompt" rather than "healthy".
        return AuthProviderDescription(
            kind=self.kind,
            label="Cl@ve Móvil",
            configured=True,
            available=True,
            identity_nif=dni_nie.upper(),
            health_summary="ready — requires push approval on the Cl@ve app",
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
                "before running `aeat auth login --provider clave_movil`."
            )
        _classify_identity(raw)
        return raw.strip().upper()

    def _default_target_url(self) -> str:
        base = "https://sede.agenciatributaria.gob.es"
        return base + self._settings.aeat_sede_expedientes_path

    def _selector_url(self, target_path: str) -> str:
        template = self._settings.aeat_clave_sede_access_url_template
        return template.format(target=quote(target_path, safe=""))

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
        with contextlib.suppress(Exception):
            await context.close()

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
        except Exception as exc:
            log.warning("ClaveMovilAuthProvider: browser session close failed: %s", exc)

    # ── Sidecar + storage state ─────────────────────────────────────────────

    def _storage_state_path(self) -> Path:
        token_dir = self._settings.aeat_token_dir
        profile = self._settings.aeat_default_profile_name
        return token_dir / f"{profile}-clave-movil-storage.json"

    @staticmethod
    def _sidecar_path_for(storage_state_path: Path) -> Path:
        return storage_state_path.with_suffix(".meta.json")

    def _write_json_atomic(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
            from .....core.locks import fsync_parent_dir

            fsync_parent_dir(path)
        except Exception:
            with contextlib.suppress(FileNotFoundError):
                tmp_path.unlink()
            raise
        # Issue #469 M-2: harden ACLs on every platform via the
        # shared helper. Previously this branch only chmod'd 0o600
        # on POSIX and silently fell through on Windows, leaving
        # the storage-state JSON (containing localStorage + cookies
        # of the AEAT browser session — bearer-equivalent material)
        # readable by anything inheriting the parent dir's ACL.
        from .....core.file_permissions import restrict_file_permissions

        restrict_file_permissions(path)

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        digest.update(path.read_bytes())
        return digest.hexdigest()

    def _invalidate_persisted(self, storage_state_path: Path, sidecar_path: Path) -> None:
        for candidate in (storage_state_path, sidecar_path):
            with contextlib.suppress(FileNotFoundError):
                candidate.unlink()

    # ── Flow ────────────────────────────────────────────────────────────────

    async def _fresh_login_locked(
        self,
        *,
        dni_nie: str,
        storage_state_path: Path,
        sidecar_path: Path,
        browser_session: BrowserSessionLike | None,
        target_url: str | None,
    ) -> AeatSession:
        target = target_url or self._default_target_url()
        target_path = self._target_path_from_url(target)
        selector_url = self._selector_url(target_path)

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

            if use_non_qr:
                await self._drive_non_qr_fallback(page, dni_nie)
            else:
                await self._click_clave_movil_button(page)
                verification_code = await self._extract_verification_code(page)

            timeout_ms = int(self._settings.aeat_clave_movil_timeout_ms)
            _render_progress_banner(
                verification_code=verification_code,
                timeout_seconds=timeout_ms // 1000,
                used_non_qr_fallback=use_non_qr,
            )

            try:
                await self._wait_for_post_auth_landing(page, target_path, timeout_ms)
            except (TimeoutError, PlaywrightTimeoutError) as exc:
                await self._dump_diagnostic(page, reason="post-auth-landing-timeout")
                raise ClaveMovilApprovalTimeoutError(
                    f"Cl@ve Móvil login timed out after {timeout_ms // 1000} seconds. "
                    "Open the Cl@ve app on your phone and approve the login request, "
                    "then run `aeat auth login` again."
                ) from exc

            storage_state = await context.storage_state()
            landing_url = getattr(page, "url", None)
            await page.close()
        except Exception as exc:
            if page is not None:
                with contextlib.suppress(Exception):
                    await self._dump_diagnostic(page, reason=f"fresh-login-exception:{type(exc).__name__}")
            if context is not None:
                with contextlib.suppress(Exception):
                    await context.close()
            if owns_session:
                await self._close_browser_session(session_like)
            raise

        authenticated_at = datetime.now(UTC)
        idle_deadline = authenticated_at + AEAT_SESSION_IDLE_TTL
        try:
            self._write_json_atomic(storage_state_path, storage_state)
            storage_state_sha256 = self._sha256_file(storage_state_path)
            sidecar = _ClaveMovilSidecar(
                identity_nif=dni_nie,
                authenticated_at=authenticated_at,
                idle_deadline=idle_deadline,
                storage_state_sha256=storage_state_sha256,
                used_non_qr_fallback=self._settings.aeat_clave_prefer_non_qr,
                verification_code=verification_code,
                landing_url=landing_url,
            )
            self._write_json_atomic(sidecar_path, sidecar.model_dump(mode="json"))
        except Exception:
            # If either write fails, remove any partial pair so the next
            # authenticate() call sees a clean slate and runs a fresh login
            # rather than silently ignoring an orphaned cookie file.
            self._invalidate_persisted(storage_state_path, sidecar_path)
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
            ),
        )
        self._browser_session = session_like
        self._context = context
        self._active_session = session
        log.info(
            "ClaveMovilAuthProvider: authenticated nif=%s non_qr=%s landing=%s",
            dni_nie,
            self._settings.aeat_clave_prefer_non_qr,
            landing_url,
        )
        return session

    async def _resume_locked(
        self,
        storage_state_path: Path,
        sidecar_path: Path,
        *,
        browser_session: BrowserSessionLike | None,
        target_url: str | None,
    ) -> AeatSession:
        try:
            # Read as raw text and use `model_validate_json` so Pydantic's
            # strict-JSON mode coerces ISO-8601 strings into datetimes
            # while still rejecting type drift on every other field.
            sidecar = _ClaveMovilSidecar.model_validate_json(sidecar_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise AeatLoginAssertionError(f"Cl@ve Móvil sidecar invalid: {exc}") from exc
        if sidecar.idle_deadline <= datetime.now(UTC):
            raise AeatLoginAssertionError("Cl@ve Móvil session past idle deadline")
        observed_sha256 = self._sha256_file(storage_state_path)
        if observed_sha256 != sidecar.storage_state_sha256:
            raise AeatLoginAssertionError("Cl@ve Móvil storage-state hash mismatch")

        session_like, owns_session = await self._resolve_browser_session(browser_session=browser_session)
        context: BrowserContextLike | None = None
        try:
            context = await session_like.create_context(
                storage_state_path=storage_state_path,
            )
            session = AeatSession(
                provider_kind=self.kind,
                authenticated_at=sidecar.authenticated_at,
                idle_deadline=sidecar.idle_deadline,
                storage_state_path=storage_state_path,
                identity_nif=sidecar.identity_nif,
                provider_detail=ClaveMovilSessionDetail(
                    dni_nie=sidecar.identity_nif,
                    used_non_qr_fallback=sidecar.used_non_qr_fallback,
                    verification_code=sidecar.verification_code,
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
            log.info(
                "ClaveMovilAuthProvider: resumed nif=%s landing=%s",
                refreshed.identity_nif,
                assertion.assertion_detail.landing_url
                if isinstance(assertion.assertion_detail, ClaveMovilLoginAssertionDetail)
                else None,
            )
            return refreshed
        except Exception:
            if context is not None:
                with contextlib.suppress(Exception):
                    await context.close()
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
        marker = ".gob.es"
        idx = target_url.find(marker)
        if idx < 0:
            return target_url
        tail = target_url[idx + len(marker) :]
        return tail or "/"

    @staticmethod
    async def _click_clave_movil_button(page: BrowserPageLike) -> None:
        click = getattr(page, "click", None)
        if click is None:
            raise AeatLoginAssertionError("Playwright page does not expose click(); cannot drive Cl@ve Móvil entry")
        await click('button[name="autoriza-P"]')

    @staticmethod
    async def _extract_verification_code(page: BrowserPageLike) -> str | None:
        wait_for = getattr(page, "wait_for_selector", None)
        text_content = getattr(page, "text_content", None)
        if wait_for is None or text_content is None:
            return None
        try:
            await wait_for("#spanCodigoVerificacion", timeout=30_000)
            raw = await text_content("#spanCodigoVerificacion")
        except Exception:
            return None
        if raw is None:
            return None
        return raw.strip() or None

    async def _drive_non_qr_fallback(self, page: BrowserPageLike, dni_nie: str) -> None:
        click = getattr(page, "click", None)
        fill = getattr(page, "fill", None)
        wait_for = getattr(page, "wait_for_selector", None)
        if click is None or fill is None or wait_for is None:
            raise AeatLoginAssertionError(
                "Playwright page missing click/fill/wait_for_selector; cannot drive the Cl@ve Móvil non-QR fallback"
            )
        await click('button[name="autoriza-P"]')
        await wait_for(
            'a[href*="ObtenerClaveMovil?qAA=2"]',
            timeout=self._navigation_timeout_ms,
        )
        await click('a[href*="ObtenerClaveMovil?qAA=2"]')
        await wait_for("#NIF", timeout=self._navigation_timeout_ms)
        await fill("#NIF", dni_nie)
        kind = _classify_identity(dni_nie)
        if kind == "DNI":
            fecha = (self._settings.aeat_clave_movil_dni_fecha or "").strip()
            if not fecha:
                raise ClaveMovilConfigurationError(
                    "AEAT_CLAVE_MOVIL_DNI_FECHA is required for the non-QR DNI fallback (format YYYY-MM-DD)."
                )
            await fill("#FECHA", fecha)
        else:
            soporte = (self._settings.aeat_clave_movil_nie_soporte or "").strip()
            if not soporte:
                raise ClaveMovilConfigurationError(
                    "AEAT_CLAVE_MOVIL_NIE_SOPORTE is required for the non-QR NIE fallback."
                )
            await fill("#SOPORTE", soporte)
        await click("#botonContinuar")
        await self._raise_if_pending_request_error(page)

    async def _raise_if_pending_request_error(self, page: BrowserPageLike) -> None:
        """Detect AEAT's 'petición pendiente' refusal page and fail fast.

        After #botonContinuar is clicked, AEAT sometimes returns the
        non-QR landing page in an error state: "No ha sido posible
        generar una nueva petición de autenticación con Cl@ve Móvil.
        Por su seguridad, acceda a la APP Cl@ve … y rechace la petición
        pendiente — o espere a que caduque tras un máximo de 5 minutos."
        This happens when a prior login left an un-acknowledged push
        alive server-side. The polling loop that normally redirects on
        approval is never rendered, so the authenticator would otherwise
        sit on the page until the outer timeout fires. Fail fast with a
        clear remediation message.
        """
        content = getattr(page, "content", None)
        if content is None:
            return
        try:
            html = await content()
        except Exception:
            return
        if "No ha sido posible generar una nueva petici" in html:
            await self._dump_diagnostic(page, reason="pending-request-refusal")
            raise ClaveMovilApprovalTimeoutError(
                "AEAT refused to issue a new Cl@ve Móvil push: a prior "
                "authentication request is still pending server-side. Open the "
                "Cl@ve app on your phone and REJECT every pending request, then "
                "retry `aeat auth login` (or wait up to 5 minutes for AEAT to "
                "time them out automatically)."
            )

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

        def _handle(dialog: Any) -> None:
            accept = getattr(dialog, "accept", None)
            if accept is None:
                return
            log.info(
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

    async def _dump_diagnostic(self, page: BrowserPageLike, *, reason: str) -> None:
        """Capture page URL + HTML + screenshot on login failure for offline triage.

        Writes artefacts to ``scratch/clave-diag/<utc-timestamp>/`` so a
        human (or the next patch author) can inspect exactly what AEAT
        served at the moment the authenticator gave up.
        """
        try:
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            root = Path("scratch") / "clave-diag" / ts
            root.mkdir(parents=True, exist_ok=True)
            url = getattr(page, "url", "") or ""
            (root / "url.txt").write_text(f"reason={reason}\nurl={url}\n", encoding="utf-8")
            content = getattr(page, "content", None)
            if content is not None:
                html = await content()
                (root / "page.html").write_text(html, encoding="utf-8")
            screenshot = getattr(page, "screenshot", None)
            if screenshot is not None:
                await screenshot(path=str(root / "page.png"), full_page=True)
            log.warning(
                "ClaveMovilAuthProvider: diagnostic captured at %s (url=%s reason=%s)",
                root,
                url,
                reason,
            )
        except Exception as exc:
            log.warning("ClaveMovilAuthProvider: diagnostic dump failed: %s", exc)

    async def _wait_for_post_auth_landing(
        self,
        page: BrowserPageLike,
        target_path: str,
        timeout_ms: int,
    ) -> None:
        """Poll until the browser reaches ``target_path`` or timeout.

        After push approval AEAT may interpose
        ``/wlpl/OVCT-CXEW/DialogoRepresentacion`` — the representation
        dispatcher. That page requires a remote form submission to choose
        an acting capacity, so the provider refuses it instead of
        auto-submitting on Kent's behalf.
        """
        from urllib.parse import urlsplit

        deadline = time.perf_counter() + timeout_ms / 1000
        while time.perf_counter() < deadline:
            current = getattr(page, "url", "") or ""
            if target_path in current and "SelectorAccesos" not in current:
                return
            # Only match DialogoRepresentacion when it is the URL PATH,
            # not the `ref=` query parameter (which contains it URL-
            # encoded on the push-waiting page).
            try:
                current_path = urlsplit(current).path
            except Exception:
                current_path = ""
            if "DialogoRepresentacion" in current_path and "SelectorAccesos" not in current:
                raise AeatLoginAssertionError(
                    "AEAT requested representation selection after Cl@ve approval. "
                    "The provider will not submit representation forms automatically."
                )
            await asyncio.sleep(0.5)
        raise TimeoutError(f"page did not navigate to {target_path!r} within {timeout_ms}ms")


__all__ = [
    "AEAT_CLAVE_MOVIL_SIDECAR_SCHEMA_VERSION",
    "ClaveMovilApprovalTimeoutError",
    "ClaveMovilAuthProvider",
    "ClaveMovilConfigurationError",
]
