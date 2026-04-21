"""Unified live-AEAT authenticator facade.

This module is the single entry point every future remote-read
module should depend on. It coordinates authentication providers and
Playwright browser sessions into a narrow async surface.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, NoReturn, cast

from pydantic import BaseModel, ConfigDict, Field

from ..logging import get_logger
from ._browser import BrowserContextLike, BrowserSessionFactory, BrowserSessionLike
from ._models import (
    AeatLoginAssertion,
    AeatSession,
    CertificateSessionDetail,
)
from ._protocols import AuthProvider, AuthProviderDescription
from ._providers._certificate.certificate import (
    AeatLoginAssertionError,
    AeatSessionExpiredError,
    CertificateExpiredError,
    CertificateHealth,
    CertificateHealthSeverity,
    HandshakeResult,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    load_certificate,
    verify_handshake,
)
from ._providers._certificate.provider import CertificateAuthProvider

if TYPE_CHECKING:
    from ..config import Settings

log = get_logger(__name__)

AEAT_LOGIN_NAVIGATION_TIMEOUT_MS: Final[int] = 30_000
AEAT_STORAGE_STATE_SCHEMA_VERSION: Final[int] = 1


class AeatSecurityError(AeatLoginAssertionError):
    """Raised when file permission hardening fails in strict mode."""


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
        provider: AuthProvider | None = None,
        browser_session_factory: BrowserSessionFactory | None = None,
        handshake_verifier: Callable[[LoadedCertificate, str], HandshakeResult] | None = None,
        navigation_timeout_ms: int | None = None,
    ) -> None:
        self._settings = settings
        self._navigation_timeout_ms = navigation_timeout_ms or settings.aeat_auth_timeout_ms
        self._provider = provider or CertificateAuthProvider(
            handshake_verifier=handshake_verifier or verify_handshake,
            navigation_timeout_ms=self._navigation_timeout_ms,
        )
        self._browser_session_factory = browser_session_factory
        self._handshake_verifier = handshake_verifier or verify_handshake
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

    @property
    def provider(self) -> AuthProvider:
        """The active authentication provider."""
        return self._provider

    def describe(self) -> AuthProviderDescription:
        """Return the active provider's safe configuration summary."""
        return self._provider.describe(self._settings)

    # --- Legacy Certificate-specific methods (delegated if provider is CertificateAuthProvider) ---

    def load_certificate(self) -> LoadedCertificate:
        if isinstance(self._provider, CertificateAuthProvider):
            bundle = self._provider._require_bundle(self._settings)
            return load_certificate(bundle)
        # Fallback for legacy tests
        from ._providers._certificate.certificate import CertificateBundle

        path = self._settings.aeat_certificate_path
        if path is None:
            raise ValueError("AEAT_CERTIFICATE_PATH is not set")
        bundle = CertificateBundle(
            path=path,
            password_env_var="AEAT_CERTIFICATE_PASSWORD_SECRET",  # noqa: S106
            friendly_name=self._settings.aeat_certificate_friendly_name,
            backend=self._settings.aeat_certificate_backend,
        )
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

    # --- Generic Provider-agnostic methods ---

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
                    "call close() or reauthenticate() before authenticating again"
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

            # 2. Proactive Health Gate (#270)
            # Before fresh auth, check if the provider's identity (cert) is healthy.
            # (Currently only implemented for CertificateAuthProvider)
            if isinstance(self._provider, CertificateAuthProvider):
                health = self.health()
                if health.severity == CertificateHealthSeverity.EXPIRED:
                    raise CertificateExpiredError(
                        f"AEAT certificate has expired (not_after={health.not_after.isoformat()}). "
                        "Please renew your FNMT certificate."
                    )
                if health.severity == CertificateHealthSeverity.CRITICAL:
                    # In a real CLI, we might allow --force-expiring-cert,
                    # but here we log a loud warning and let the probe decide.
                    log.warning(
                        "AEAT certificate is in CRITICAL expiry window (%d days remaining). "
                        "Renew it soon at https://www.sede.fnmt.gob.es/",
                        health.days_until_expiry,
                    )

            session_like = browser_session or await self._resolve_browser_session()
            try:
                session, context = await self._provider.authenticate(session_like, self._settings)
            except Exception as exc:
                await self._close_browser_session(session_like)
                if isinstance(exc, AeatLoginAssertionError):
                    raise
                raise AeatLoginAssertionError(f"AEAT authentication failed: {exc}") from exc

            self._browser_session = session_like
            self._context = context
            try:
                storage_state_path = await self._capture_storage_state_locked(session)
                self._active_session = session.model_copy(update={"storage_state_path": storage_state_path})
            except Exception:
                await self._drop_context()
                await self._close_browser_session(session_like)
                self._browser_session = None
                self._active_session = None
                raise
            log.info(
                "AeatAuthenticator: authenticated nif=%s kind=%s",
                self._active_session.identity_nif,
                self._active_session.provider_kind,
            )
            return self._active_session

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

        try:
            return await self._provider.verify(context, session, self._settings)
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

    async def _capture_storage_state_locked(self, session: AeatSession) -> Path:
        context = self._context
        if context is None:
            raise AeatLoginAssertionError("no active browser context; cannot capture storage_state")

        storage_state_path = session.storage_state_path or self._resolve_storage_state_path(self._browser_session)

        storage_data = await context.storage_state()
        self._write_json_atomic(storage_state_path, storage_data)
        storage_state_sha256 = self._validate_storage_state_file(storage_state_path)

        # Build metadata sidecar.
        # We need to extract the detail fields into the flat metadata for now (legacy compatibility).
        # In a real future, metadata would be a dump of AeatSession.

        metadata_dict = {
            "schema_version": AEAT_STORAGE_STATE_SCHEMA_VERSION,
            "certificate_nif": session.identity_nif,
            "authenticated_at": session.authenticated_at.isoformat(),
            "idle_deadline": session.idle_deadline.isoformat(),
            "storage_state_sha256": storage_state_sha256,
        }
        if isinstance(session.provider_detail, CertificateSessionDetail):
            metadata_dict.update(
                {
                    "certificate_thumbprint": session.provider_detail.certificate_thumbprint,
                    "certificate_subject": session.provider_detail.certificate_subject,
                    "handshake": session.provider_detail.handshake.model_dump(mode="json"),
                }
            )

        self._write_json_atomic(
            self._metadata_path_for(storage_state_path),
            metadata_dict,
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
        storage_state_sha256 = self._validate_storage_state_file(storage_state_path)

        metadata_path = self._metadata_path_for(storage_state_path)
        if not metadata_path.exists():
            self._raise_invalid_persisted_state(storage_state_path, "persisted metadata sidecar missing")

        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._raise_invalid_persisted_state(
                storage_state_path, f"persisted metadata sidecar is not valid JSON: {exc}"
            )

        if metadata.get("schema_version") != AEAT_STORAGE_STATE_SCHEMA_VERSION:
            self._raise_invalid_persisted_state(
                storage_state_path,
                f"unsupported metadata schema version: {metadata.get('schema_version')}",
            )
        if metadata.get("storage_state_sha256") != storage_state_sha256:
            self._raise_invalid_persisted_state(
                storage_state_path, "persisted storage_state hash does not match metadata sidecar"
            )

        idle_deadline = datetime.fromisoformat(metadata["idle_deadline"])
        if idle_deadline <= datetime.now(UTC):
            self._raise_invalid_persisted_state(storage_state_path, "persisted AEAT session is past its idle deadline")

        session_like = browser_session or await self._resolve_browser_session()
        owns_session = browser_session is None

        try:
            session, context = await self._provider.resume(session_like, storage_state_path, metadata, self._settings)
        except Exception as exc:
            if owns_session:
                await self._close_browser_session(session_like)
            self._invalidate_persisted_state(
                storage_state_path, f"persisted AEAT browser session could not be resumed: {exc}"
            )
            raise _PersistedSessionInvalidError(str(exc)) from exc

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
            "AeatAuthenticator: resumed persisted session nif=%s kind=%s",
            session.identity_nif,
            session.provider_kind,
        )
        return session

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

    def _raise_invalid_persisted_state(self, storage_state_path: Path, reason: str) -> NoReturn:
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
            self._restrict_file_permissions(tmp_path, strict=self._settings.aeat_strict_security)
            os.replace(tmp_path, path)
            self._restrict_file_permissions(path, strict=self._settings.aeat_strict_security)
        finally:
            if tmp_path is not None:
                with contextlib.suppress(FileNotFoundError):
                    tmp_path.unlink()

    @staticmethod
    def _restrict_file_permissions(path: Path, *, strict: bool = False) -> None:
        import getpass

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

            error_msg = f"AeatAuthenticator: failed to harden Windows ACLs on {path}"
            if result is not None and result.stderr:
                error_msg += f": {result.stderr.strip()}"

            if strict:
                raise AeatSecurityError(error_msg)
            log.warning(error_msg)
            return
        if os.name != "posix":
            return
        try:
            os.chmod(path, 0o600)
        except OSError as exc:
            error_msg = f"AeatAuthenticator: failed to chmod 0600 on {path}: {exc}"
            if strict:
                raise AeatSecurityError(error_msg) from exc
            log.warning(error_msg)

    async def _resolve_browser_session(self) -> BrowserSessionLike:
        if self._browser_session_factory is not None:
            return await self._browser_session_factory(self._settings)
        raise AeatLoginAssertionError(
            "AeatAuthenticator was constructed without a browser "
            "session factory; the default Playwright factory is not "
            "yet wired."
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
