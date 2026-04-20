from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ..._browser import BrowserSessionLike
from ..._models import (
    AEAT_SESSION_IDLE_TTL,
    AeatLoginAssertion,
    AeatSession,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
)
from ..._protocols import (
    AEAT_CERTIFICATE_THUMBPRINT_MARKER,
    AuthProviderDescription,
    AuthProviderKind,
)
from ._certificate_backends._playwright_context import build_client_certificates_kwarg
from .certificate import (
    CertificateBundle,
    HandshakeResult,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
    load_certificate,
    verify_handshake,
)

if TYPE_CHECKING:
    from ....config import Settings
    from ..._browser import BrowserContextLike, BrowserPageLike


class CertificateAuthProvider:
    """Authentication provider for PKCS#12 certificates."""

    def __init__(
        self,
        *,
        handshake_verifier: Callable[[LoadedCertificate, str], HandshakeResult] | None = None,
        navigation_timeout_ms: int = 30_000,
    ) -> None:
        self._handshake_verifier = handshake_verifier or verify_handshake
        self._navigation_timeout_ms = navigation_timeout_ms

    @property
    def kind(self) -> AuthProviderKind:
        return AuthProviderKind.CERTIFICATE

    def describe(self, settings: Settings) -> AuthProviderDescription:
        """Return a safe summary of the certificate provider state."""
        if settings.aeat_certificate_path is None:
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=False,
                available=False,
                health_summary="certificate path not configured",
            )
        if settings.aeat_certificate_password_secret is None:
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=True,
                available=False,
                health_summary="AEAT_CERTIFICATE_PASSWORD_SECRET not set",
            )

        try:
            bundle = self._require_bundle(settings)
            cert = load_certificate(bundle)
            health = evaluate_loaded_certificate_health(
                cert,
                warn_days=settings.aeat_cert_warn_days,
                critical_days=settings.aeat_cert_critical_days,
            )
            identity_nif: str | None = None
            try:
                identity_nif = extract_nif_from_subject(cert)
            except Exception:
                identity_nif = None

            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=True,
                available=True,
                identity_nif=identity_nif,
                subject=cert.subject,
                expires_on=cert.not_after.date(),
                health_severity=health.severity.value,
                days_until_expiry=health.days_until_expiry,
                health_summary=f"{health.severity.value}:{health.days_until_expiry}",
            )
        except Exception as exc:
            return AuthProviderDescription(
                kind=self.kind,
                label="AEAT certificate",
                configured=True,
                available=False,
                health_summary=f"{type(exc).__name__}: {exc}",
            )

    def _require_bundle(self, settings: Settings) -> CertificateBundle:
        path = settings.aeat_certificate_path
        if path is None:
            raise ValueError("AEAT_CERTIFICATE_PATH is not set; cannot build CertificateBundle")
        return CertificateBundle(
            path=path,
            password_env_var="AEAT_CERTIFICATE_PASSWORD_SECRET",  # noqa: S106
            friendly_name=settings.aeat_certificate_friendly_name,
            backend=settings.aeat_certificate_backend,
        )

    async def authenticate(
        self,
        browser_session: BrowserSessionLike,
        settings: Settings,
    ) -> tuple[AeatSession, BrowserContextLike]:
        bundle = self._require_bundle(settings)
        cert = load_certificate(bundle)
        target = settings.aeat_certificate_verify_url

        timeout_s = settings.aeat_auth_timeout_ms / 1000.0
        handshake = await asyncio.to_thread(self._handshake_verifier, cert, target, timeout_s=timeout_s)
        nif = extract_nif_from_subject(cert)

        def provisioner(kwargs: dict[str, Any]) -> None:
            kwargs["client_certificates"] = build_client_certificates_kwarg(cert, target)

        context = await browser_session.create_context(provisioner=provisioner)
        setattr(context, AEAT_CERTIFICATE_THUMBPRINT_MARKER, cert.sha256_thumbprint)

        provisional_at = datetime.now(UTC)
        detail = CertificateSessionDetail(
            certificate_thumbprint=cert.sha256_thumbprint,
            certificate_subject=cert.subject,
            handshake=cast(HandshakeResult, handshake),
        )

        provisional_session = AeatSession(
            identity_nif=nif,
            authenticated_at=provisional_at,
            idle_deadline=provisional_at + AEAT_SESSION_IDLE_TTL,
            storage_state_path=None,
            provider_detail=detail,
        )

        assertion = await self.verify(context, provisional_session, settings)
        if not assertion.is_valid:
            from .certificate import AeatLoginAssertionError

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
        return session, context

    async def resume(
        self,
        browser_session: BrowserSessionLike,
        storage_state_path: Path,
        metadata: dict[str, Any],
        settings: Settings,
    ) -> tuple[AeatSession, BrowserContextLike]:
        bundle = self._require_bundle(settings)
        cert = load_certificate(bundle)
        target = settings.aeat_certificate_verify_url

        # Validate that the persisted session matches the current certificate
        if metadata.get("certificate_thumbprint") != cert.sha256_thumbprint:
            raise ValueError("persisted AEAT session was captured with a different certificate thumbprint")
        if metadata.get("certificate_subject") != cert.subject:
            raise ValueError("persisted AEAT session was captured with a different certificate subject")

        def provisioner(kwargs: dict[str, Any]) -> None:
            kwargs["client_certificates"] = build_client_certificates_kwarg(cert, target)

        context = await browser_session.create_context(
            provisioner=provisioner,
            storage_state_path=storage_state_path,
        )
        setattr(context, AEAT_CERTIFICATE_THUMBPRINT_MARKER, cert.sha256_thumbprint)

        handshake_data = metadata.get("handshake")
        handshake: HandshakeResult | None = None
        if isinstance(handshake_data, dict):
            # Coerce dict (from JSON) into HandshakeResult-compatible form
            # since the model has strict=True.
            h_dict = handshake_data.copy()
            if isinstance(h_dict.get("server_cert_chain"), list):
                h_dict["server_cert_chain"] = tuple(h_dict["server_cert_chain"])
            if isinstance(h_dict.get("attempted_at"), str):
                h_dict["attempted_at"] = datetime.fromisoformat(h_dict["attempted_at"])
            handshake = HandshakeResult.model_validate(h_dict)

        detail = CertificateSessionDetail(
            certificate_thumbprint=cert.sha256_thumbprint,
            certificate_subject=cert.subject,
            handshake=cast(HandshakeResult, handshake),
        )

        session = AeatSession(
            identity_nif=metadata["certificate_nif"],
            authenticated_at=datetime.fromisoformat(metadata["authenticated_at"])
            if isinstance(metadata["authenticated_at"], str)
            else metadata["authenticated_at"],
            idle_deadline=datetime.fromisoformat(metadata["idle_deadline"])
            if isinstance(metadata["idle_deadline"], str)
            else metadata["idle_deadline"],
            storage_state_path=storage_state_path,
            provider_detail=detail,
        )

        assertion = await self.verify(context, session, settings)
        if not assertion.is_valid:
            from .certificate import AeatLoginAssertionError

            raise AeatLoginAssertionError("persisted AEAT browser session failed live verification")

        session = session.model_copy(
            update={
                "authenticated_at": assertion.attempted_at,
                "idle_deadline": assertion.attempted_at + AEAT_SESSION_IDLE_TTL,
            }
        )
        return session, context

    async def verify(
        self,
        context: BrowserContextLike,
        session: AeatSession,
        settings: Settings,
    ) -> AeatLoginAssertion:
        target = settings.aeat_certificate_verify_url
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
            elif getattr(page, "cert_ok", False):  # Hook for fake pages in tests
                status_code = 200
                certificate_recognised = True
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
        finally:
            if page is not None:
                with contextlib.suppress(Exception):
                    await page.close()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        detail = cast(CertificateSessionDetail, session.provider_detail)
        handshake_success = detail.handshake.success if detail.handshake else False
        is_valid = handshake_success and certificate_recognised and bool(session.identity_nif)

        return AeatLoginAssertion(
            target_url=target,
            is_valid=is_valid,
            identity_nif=session.identity_nif,
            status_code=status_code,
            elapsed_ms=elapsed_ms,
            attempted_at=attempted_at,
            error_message=error_message,
            assertion_detail=CertificateLoginAssertionDetail(
                handshake_success=handshake_success,
                certificate_recognised=certificate_recognised,
                parsed_subject=detail.certificate_subject,
            ),
        )
