"""Unified live-AEAT authenticator facade.

This module is the single entry point every future remote-read
module should depend on. It composes the certificate loader, the Playwright
browser session, and the login-assertion flow into a narrow async surface.
"""

from __future__ import annotations

import asyncio
import contextlib
import getpass
import hashlib
import json
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

from pydantic import BaseModel, ConfigDict, Field

from ..logging import get_logger
from ._browser import BrowserContextLike, BrowserPageLike, BrowserSessionFactory, BrowserSessionLike
from ._models import AeatLoginAssertion, AeatSession, CertificateSessionDetail
from ._providers._certificate._certificate_backends._playwright_context import build_client_certificates_kwarg
from ._providers._certificate.certificate import (
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

if TYPE_CHECKING:
    from ..config import Settings

log = get_logger(__name__)

AEAT_SESSION_IDLE_TTL: Final[timedelta] = timedelta(minutes=18)
AEAT_LOGIN_NAVIGATION_TIMEOUT_MS: Final[int] = 30_000
AEAT_STORAGE_STATE_SCHEMA_VERSION: Final[int] = 1

_MARKER_ATTR = "_aeat_certificate_thumbprint"


class _PersistedSessionMetadata(BaseModel):
    """AEAT-specific metadata stored beside a Playwright storage-state file."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: int = Field(default=AEAT_STORAGE_STATE_SCHEMA_VERSION, ge=1)
    certificate_thumbprint: str = Field(min_length=1)
    certificate_subject: str = Field(min_length=1)
    certificate_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_sha256: str = Field(min_length=64, max_length=64)
    handshake: HandshakeResult


class _PersistedSessionInvalidError(AeatLoginAssertionError):
    """Raised when a persisted AEAT browser session cannot be trusted."""


class AeatAuthenticator:
    """Single entry point for live AEAT access."""

    def __init__(
        self,
        settings: Settings,
        *,
        browser_session_factory: BrowserSessionFactory | None = None,
        handshake_verifier: Callable[[LoadedCertificate, str], HandshakeResult] | None = None,
        navigation_timeout_ms: int = AEAT_LOGIN_NAVIGATION_TIMEOUT_MS,
    ) -> None:
        self._settings = settings
        self._browser_session_factory = browser_session_factory
        self._handshake_verifier = handshake_verifier or verify_handshake
        self._navigation_timeout_ms = navigation_timeout_ms
        self._lock = asyncio.Lock()
        self._browser_session: BrowserSessionLike | None = None
        self._context: BrowserContextLike | None = None
        self._active_session: AeatSession | None = None
        self._closing = False
        self._inflight_pages = 0
        self._inflight_drained: asyncio.Event = asyncio.Event()
        self._inflight_drained.set()

    async def __aenter__(self) -> AeatAuthenticator:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    def load_certificate(self) -> LoadedCertificate:
        bundle = self._require_bundle()
        return load_certificate(bundle)

    def health(self, *, now: datetime | None = None) -> CertificateHealth:
        cert = self.load_certificate()
        return evaluate_loaded_certificate_health(
            cert,
            warn_days=self._settings.aeat_cert_warn_days,
            critical_days=self._settings.aeat_cert_critical_days,
            now=now,
        )

    def verify_handshake(self, *, url: str | None = None) -> HandshakeResult:
        target = url or self._settings.aeat_certificate_verify_url
        cert = self.load_certificate()
        return self._handshake_verifier(cert, target)

    def extract_nif_from_subject(self, cert: LoadedCertificate) -> str:
        return extract_nif_from_subject(cert)

    async def authenticate(
        self,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> AeatSession:
        async with self._lock:
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "AeatAuthenticator already has an active session; "
                    "call close() or reauthenticate() before "
                    "authenticating again"
                )
            target = target_url or self._settings.aeat_certificate_verify_url
            resume_path = self._resolve_storage_state_path(browser_session)
            if resume_path.exists() or self._metadata_path_for(resume_path).exists():
                try:
                    return await self._resume_from_storage_state_locked(
                        resume_path,
                        browser_session=browser_session,
                        target_url=target,
                    )
                except _PersistedSessionInvalidError as exc:
                    log.info(
                        "AeatAuthenticator: persisted session invalid at %s; falling back to fresh auth (%s)",
                        resume_path,
                        exc,
                    )

            cert = self.load_certificate()
            handshake = await asyncio.to_thread(self._handshake_verifier, cert, target)
            nif = extract_nif_from_subject(cert)
            session_like = browser_session or await self._resolve_browser_session()

            def provisioner(kwargs: dict[str, Any]) -> None:
                kwargs["client_certificates"] = build_client_certificates_kwarg(
                    cert, self._settings.aeat_certificate_verify_url
                )

            context = await session_like.create_context(provisioner=provisioner)
            setattr(context, _MARKER_ATTR, cert.sha256_thumbprint)

            try:
                self._assert_context_marker(context, cert)
            except Exception:
                with contextlib.suppress(Exception):
                    await context.close()
                await self._close_browser_session(session_like)
                raise

            storage_state_path = self._resolve_storage_state_path(session_like)
            provisional_at = datetime.now(UTC)

            detail = CertificateSessionDetail(
                certificate_thumbprint=cert.sha256_thumbprint,
                certificate_subject=cert.subject,
                handshake=handshake,
            )

            provisional_session = AeatSession(
                identity_nif=nif,
                authenticated_at=provisional_at,
                idle_deadline=provisional_at + AEAT_SESSION_IDLE_TTL,
                storage_state_path=storage_state_path,
                provider_detail=detail,
            )
            assertion = await self._run_login_probe(
                context,
                provisional_session,
                target,
            )
            if not assertion.is_valid:
                with contextlib.suppress(Exception):
                    await context.close()
                await self._close_browser_session(session_like)
                raise AeatLoginAssertionError(
                    "fresh AEAT authentication did not produce a valid login assertion; "
                    f"status={assertion.status_code} error={assertion.error_message!r}"
                )

            authenticated_at = assertion.attempted_at
            session = provisional_session.model_copy(
                update={
                    "authenticated_at": authenticated_at,
                    "idle_deadline": authenticated_at + AEAT_SESSION_IDLE_TTL,
                }
            )
            self._browser_session = session_like
            self._context = context
            self._active_session = session
            try:
                await self._capture_storage_state_locked(session)
            except Exception:
                await self._drop_context()
                await self._close_browser_session(session_like)
                self._browser_session = None
                self._active_session = None
                raise
            log.info(
                "AeatAuthenticator: authenticated nif=%s thumbprint=%s",
                session.identity_nif,
                session.provider_detail.certificate_thumbprint,
            )
            return session

    async def reauthenticate(self, session: AeatSession) -> AeatSession:
        log.info(
            "AeatAuthenticator: reauthenticate old_nif=%s old_authenticated_at=%s",
            session.identity_nif,
            session.authenticated_at.isoformat(),
        )
        await self.close()
        return await self.authenticate()

    async def verify_login(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion:
        if session.is_stale():
            raise AeatSessionExpiredError(
                f"session for nif={session.identity_nif} is stale (idle_deadline={session.idle_deadline.isoformat()})"
            )

        async with self._lock:
            if self._closing:
                raise AeatLoginAssertionError("authenticator is closing; no new verify_login allowed")
            context = self._context
            if context is None:
                raise AeatLoginAssertionError("no active browser context; call authenticate() first")
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

    async def capture_storage_state(self, session: AeatSession) -> Path:
        async with self._lock:
            if self._active_session != session:
                raise AeatLoginAssertionError(
                    "capture_storage_state() requires the currently active authenticated session"
                )
            return await self._capture_storage_state_locked(session)

    async def resume_from_storage_state(
        self,
        path: Path,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> AeatSession:
        async with self._lock:
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "AeatAuthenticator already has an active session; "
                    "call close() or reauthenticate() before resuming another one"
                )
            return await self._resume_from_storage_state_locked(
                path,
                browser_session=browser_session,
                target_url=target_url or self._settings.aeat_certificate_verify_url,
            )

    async def close(self) -> None:
        async with self._lock:
            self._closing = True
        await self._inflight_drained.wait()
        async with self._lock:
            await self._drop_context()
            await self._close_browser_session(self._browser_session)
            self._browser_session = None
            self._active_session = None
            self._closing = False

    async def _run_login_probe(
        self,
        context: BrowserContextLike,
        session: AeatSession,
        target: str,
    ) -> AeatLoginAssertion:
        attempted_at = datetime.now(UTC)
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
            error_message = f"{type(exc).__name__}: {exc}"
        finally:
            if page is not None:
                with contextlib.suppress(Exception):
                    await page.close()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        detail = session.provider_detail
        handshake_success = detail.handshake.success
        is_valid = handshake_success and certificate_recognised and bool(session.identity_nif)
        return AeatLoginAssertion(
            target_url=target,
            is_valid=is_valid,
            handshake_success=handshake_success,
            certificate_recognised=certificate_recognised,
            parsed_nif=session.identity_nif,
            parsed_subject=detail.certificate_subject,
            status_code=status_code,
            elapsed_ms=elapsed_ms,
            attempted_at=attempted_at,
            error_message=error_message,
        )

    async def _capture_storage_state_locked(self, session: AeatSession) -> Path:
        context = self._context
        if context is None:
            raise AeatLoginAssertionError("no active browser context; cannot capture storage_state")

        storage_state_path = session.storage_state_path or self._resolve_storage_state_path(self._browser_session)
        self._write_json_atomic(storage_state_path, await context.storage_state())
        storage_state_sha256 = self._validate_storage_state_file(storage_state_path)
        detail = session.provider_detail
        metadata = _PersistedSessionMetadata(
            certificate_thumbprint=detail.certificate_thumbprint,
            certificate_subject=detail.certificate_subject,
            certificate_nif=session.identity_nif,
            authenticated_at=session.authenticated_at,
            idle_deadline=session.idle_deadline,
            storage_state_sha256=storage_state_sha256,
            handshake=detail.handshake,
        )
        self._write_json_atomic(
            self._metadata_path_for(storage_state_path),
            metadata.model_dump(mode="json"),
        )
        return storage_state_path

    async def _resume_from_storage_state_locked(
        self,
        path: Path,
        *,
        browser_session: BrowserSessionLike | None,
        target_url: str,
    ) -> AeatSession:
        storage_state_path = path
        cert = self.load_certificate()
        storage_state_sha256 = self._validate_storage_state_file(storage_state_path)
        metadata = self._read_persisted_metadata(storage_state_path)

        if metadata.storage_state_sha256 != storage_state_sha256:
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted storage_state hash does not match metadata sidecar",
            )
        if metadata.idle_deadline <= datetime.now(UTC):
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

        session_like = browser_session or await self._resolve_browser_session()
        owns_session = browser_session is None
        context: BrowserContextLike | None = None
        session: AeatSession | None = None
        try:

            def provisioner(kwargs: dict[str, Any]) -> None:
                kwargs["client_certificates"] = build_client_certificates_kwarg(
                    cert, self._settings.aeat_certificate_verify_url
                )

            context = await session_like.create_context(
                provisioner=provisioner,
                storage_state_path=storage_state_path,
            )
            setattr(context, _MARKER_ATTR, cert.sha256_thumbprint)
            self._assert_context_marker(context, cert)

            detail = CertificateSessionDetail(
                certificate_thumbprint=metadata.certificate_thumbprint,
                certificate_subject=metadata.certificate_subject,
                handshake=metadata.handshake,
            )
            session = AeatSession(
                identity_nif=metadata.certificate_nif,
                authenticated_at=metadata.authenticated_at,
                idle_deadline=metadata.idle_deadline,
                storage_state_path=storage_state_path,
                provider_detail=detail,
            )
            assertion = await self._run_login_probe(context, session, target_url)
            if not assertion.is_valid:
                raise _PersistedSessionInvalidError("persisted AEAT browser session failed live verification")
            session = session.model_copy(
                update={
                    "authenticated_at": assertion.attempted_at,
                    "idle_deadline": assertion.attempted_at + AEAT_SESSION_IDLE_TTL,
                }
            )
        except _PersistedSessionInvalidError:
            if context is not None:
                with contextlib.suppress(Exception):
                    await context.close()
            if owns_session:
                await self._close_browser_session(session_like)
            self._invalidate_persisted_state(
                storage_state_path,
                "persisted AEAT browser session failed live verification",
            )
            raise
        except Exception as exc:
            if context is not None:
                with contextlib.suppress(Exception):
                    await context.close()
            if owns_session:
                await self._close_browser_session(session_like)
            self._raise_invalid_persisted_state(
                storage_state_path,
                f"persisted AEAT browser session could not be resumed: {exc}",
            )

        if context is None or session is None:
            raise AeatLoginAssertionError("persisted AEAT session resume did not produce a usable context")
        self._browser_session = session_like
        self._context = context
        self._active_session = session
        try:
            await self._capture_storage_state_locked(session)
        except Exception:
            await self._drop_context()
            if owns_session:
                await self._close_browser_session(session_like)
            self._browser_session = None
            self._active_session = None
            raise
        log.info(
            "AeatAuthenticator: resumed persisted session nif=%s thumbprint=%s",
            session.identity_nif,
            session.provider_detail.certificate_thumbprint,
        )
        return session

    def _assert_context_marker(
        self,
        context: BrowserContextLike,
        cert: LoadedCertificate,
    ) -> None:
        marker = getattr(context, _MARKER_ATTR, None)
        if marker != cert.sha256_thumbprint:
            raise AeatLoginAssertionError(
                f"browser context was not tagged with the expected {_MARKER_ATTR} marker; cannot continue"
            )

    def _resolve_storage_state_path(
        self,
        browser_session: BrowserSessionLike | None,
    ) -> Path:
        if browser_session is not None:
            profile = getattr(browser_session, "profile", None)
            storage_state_path = getattr(profile, "storage_state_path", None)
            if isinstance(storage_state_path, Path):
                return storage_state_path
        return self._settings.aeat_token_dir / f"{self._settings.aeat_default_profile_name}-storage.json"

    @staticmethod
    def _metadata_path_for(storage_state_path: Path) -> Path:
        return storage_state_path.with_suffix(".meta.json")

    def _read_persisted_metadata(self, storage_state_path: Path) -> _PersistedSessionMetadata:
        metadata_path = self._metadata_path_for(storage_state_path)
        if not metadata_path.exists():
            self._raise_invalid_persisted_state(
                storage_state_path,
                f"persisted metadata sidecar missing: {metadata_path}",
            )
        metadata: _PersistedSessionMetadata | None = None
        try:
            metadata = _PersistedSessionMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._raise_invalid_persisted_state(
                storage_state_path,
                f"persisted metadata sidecar is malformed: {exc}",
            )
        if metadata is None:
            raise AeatLoginAssertionError("persisted metadata sidecar did not produce a parsed model")
        if metadata.schema_version != AEAT_STORAGE_STATE_SCHEMA_VERSION:
            self._raise_invalid_persisted_state(
                storage_state_path,
                f"unsupported persisted session schema version: {metadata.schema_version}",
            )
        return metadata

    def _validate_storage_state_file(self, storage_state_path: Path) -> str:
        if not storage_state_path.exists():
            self._raise_invalid_persisted_state(
                storage_state_path,
                f"persisted storage_state missing: {storage_state_path}",
            )
        raw = storage_state_path.read_bytes()
        payload: Any = None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self._raise_invalid_persisted_state(
                storage_state_path,
                f"persisted storage_state is not valid JSON: {exc}",
            )
        if not isinstance(payload, dict):
            self._raise_invalid_persisted_state(
                storage_state_path,
                "persisted storage_state root must be a JSON object",
            )
        payload_dict = cast(dict[str, Any], payload)
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
        return hashlib.sha256(raw).hexdigest()

    def _raise_invalid_persisted_state(self, storage_state_path: Path, reason: str) -> None:
        self._invalidate_persisted_state(storage_state_path, reason)
        raise _PersistedSessionInvalidError(reason)

    def _invalidate_persisted_state(self, storage_state_path: Path, reason: str) -> None:
        metadata_path = self._metadata_path_for(storage_state_path)
        for candidate in (storage_state_path, metadata_path):
            try:
                candidate.unlink(missing_ok=True)
            except Exception as exc:
                log.warning(
                    "AeatAuthenticator: failed to remove invalid persisted session file %s: %s",
                    candidate,
                    exc,
                )
        log.info(
            "AeatAuthenticator: invalidated persisted session at %s (%s)",
            storage_state_path,
            reason,
        )

    def _write_json_atomic(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        json_text = json.dumps(payload, indent=2, sort_keys=True)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=str(path.parent),
                prefix=f".{path.name}.",
                suffix=".tmp",
                mode="w",
                encoding="utf-8",
                newline="\n",
                delete=False,
            ) as handle:
                tmp_path = Path(handle.name)
                handle.write(json_text)
                handle.write("\n")
            self._restrict_file_permissions(tmp_path)
            os.replace(tmp_path, path)
            self._restrict_file_permissions(path)
        finally:
            if tmp_path is not None:
                with contextlib.suppress(FileNotFoundError):
                    tmp_path.unlink()

    @staticmethod
    def _restrict_file_permissions(path: Path) -> None:
        if os.name == "nt":
            username = getpass.getuser()
            icacls_path = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "icacls.exe"
            candidates = [username]
            userdomain = os.environ.get("USERDOMAIN")
            if userdomain:
                candidates.insert(0, f"{userdomain}\\{username}")
            result: subprocess.CompletedProcess[str] | None = None
            for candidate in candidates:
                result = subprocess.run(  # noqa: S603
                    [
                        str(icacls_path),
                        str(path),
                        "/inheritance:r",
                        "/grant:r",
                        f"{candidate}:(F)",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    return
            log.warning(
                "AeatAuthenticator: failed to harden Windows ACLs on %s: %s",
                path,
                result.stderr.strip() if result is not None and result.stderr else "icacls returned non-zero",
            )
            return
        if os.name != "posix":
            return
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)

    def _require_bundle(self) -> CertificateBundle:
        path = self._settings.aeat_certificate_path
        if path is None:
            raise ValueError("AEAT_CERTIFICATE_PATH is not set; cannot build CertificateBundle")
        return CertificateBundle(
            path=path,
            password_env_var="AEAT_CERTIFICATE_PASSWORD_SECRET",  # noqa: S106
            friendly_name=self._settings.aeat_certificate_friendly_name,
            backend=self._settings.aeat_certificate_backend,
        )

    async def _resolve_browser_session(self) -> BrowserSessionLike:
        if self._browser_session_factory is not None:
            return await self._browser_session_factory(self._settings)
        raise AeatLoginAssertionError(
            "AeatAuthenticator was constructed without a browser "
            "session factory; the default Playwright factory is not "
            "yet wired. Pass a factory explicitly or use only the "
            "synchronous helpers (health, verify_handshake)."
        )

    async def _drop_context(self) -> None:
        context = self._context
        self._context = None
        if context is None:
            return
        try:
            await context.close()
        except Exception as exc:
            log.warning("AeatAuthenticator: context close failed: %s", exc)

    async def _close_browser_session(self, session: BrowserSessionLike | None) -> None:
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
            log.warning("AeatAuthenticator: browser session close failed: %s", exc)
