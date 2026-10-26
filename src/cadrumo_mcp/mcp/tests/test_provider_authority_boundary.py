"""Local automation custody cannot satisfy independent provider verification."""

from __future__ import annotations

import base64
import os
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretBytes, SecretStr

from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import administration_subject
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.auth.protocols import BrowserSessionFactoryPort, BrowserSessionPort
from cadrumo.application.auth.providers import AuthProvider, bind_auth_provider_selector
from cadrumo.application.auth.session_types import (
    AeatLoginAssertion,
    AeatSession,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
)
from cadrumo.application.auth.sessions import AuthenticatedAeatSessionResult, ensure_authenticated_aeat_session
from cadrumo.application.auth_credentials import ActiveCertificateCredentials
from cadrumo.core.auth_provider import AuthProviderDescription, AuthProviderKind
from cadrumo.core.config import Settings, load_settings
from cadrumo.core.errors.hierarchy import AeatLoginAssertionError
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


async def _no_browser(settings: Settings) -> BrowserSessionPort:
    del settings
    raise AssertionError("recording provider must not open a live browser")


class _RecordingProvider:
    kind = AuthProviderKind.CERTIFICATE

    def __init__(self, verified: bool) -> None:
        self.verified = verified
        self.authentication_count = 0
        self.verification_count = 0
        self.close_count = 0
        self.arguments: list[bytes] = []

    async def authenticate(self) -> AeatSession:
        self.authentication_count += 1
        return AeatSession(
            authenticated_at=now(),
            idle_deadline=now() + timedelta(minutes=5),
            storage_state_path=None,
            identity_nif="00000000T",
            provider_detail=CertificateSessionDetail(
                certificate_thumbprint="synthetic-certificate", certificate_subject="synthetic-provider"
            ),
        )

    async def verify(self, session: AeatSession) -> AeatLoginAssertion:
        self.verification_count += 1
        self.arguments.append(canonical_json_bytes(session.model_dump(mode="json")))
        assert isinstance(session.provider_detail, CertificateSessionDetail)
        return AeatLoginAssertion(
            target_url=session.provider_detail.protected_resource_url,
            is_valid=self.verified,
            identity_nif=session.identity_nif,
            status_code=200 if self.verified else 401,
            elapsed_ms=1,
            attempted_at=now(),
            assertion_detail=CertificateLoginAssertionDetail(response_successful=self.verified),
        )

    def describe(self) -> AuthProviderDescription:
        return AuthProviderDescription(kind=self.kind, label="Recording certificate", configured=True, available=True)

    async def close(self) -> None:
        self.close_count += 1


class _RecordingSelector:
    def __init__(self, provider: _RecordingProvider) -> None:
        self.provider = provider
        self.arguments: list[bytes] = []

    def __call__(
        self,
        kind: AuthProviderKind,
        *,
        settings: Settings,
        browser_session_factory: BrowserSessionFactoryPort | None = None,
        certificate_credentials: ActiveCertificateCredentials | None = None,
    ) -> AuthProvider:
        assert kind is AuthProviderKind.CERTIFICATE
        assert browser_session_factory is _no_browser
        assert certificate_credentials is not None
        self.arguments.append(canonical_json_bytes(settings.model_dump(mode="json")))
        self.arguments.append(canonical_json_bytes(certificate_credentials.model_dump(mode="json")))
        for model in (settings, certificate_credentials):
            for field in type(model).model_fields:
                value = getattr(model, field)
                if isinstance(value, SecretBytes):
                    self.arguments.append(value.get_secret_value())
                elif isinstance(value, SecretStr):
                    self.arguments.append(value.get_secret_value().encode("utf-8"))
        return self.provider


@pytest.mark.anyio
@pytest.mark.parametrize("verified", [False, True])
async def test_enrolled_local_custody_never_substitutes_for_provider_verification(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str], verified: bool
) -> None:
    provider = _RecordingProvider(verified)
    selector = _RecordingSelector(provider)
    with bundled_indexed_authority().operation() as operation, administration_subject(tmp_path) as subject:
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        receipt = subject.approve(request_id)
        assert receipt.credential_reference is not None
        record = next(row for row in subject.store.enrollment_state().requests if row.request_id == request_id)
        credential = subject.owner.delivery.possession(record)
        assert credential is not None
        local_material = (
            credential,
            *subject.native.items.values(),
            *subject.client_native.items.values(),
        )

        async def acquire() -> AuthenticatedAeatSessionResult:
            return await ensure_authenticated_aeat_session(
                load_settings(),
                kind=AuthProviderKind.CERTIFICATE,
                fresh=True,
                certificate_secret_backend_factory=build_certificate_secret_backend,
                browser_session_factory=_no_browser,
                certificate_credentials=ActiveCertificateCredentials(),
                operator_scope_ports=build_operator_scope_ports(),
                profile_decode_context=operation.profile_decode_context(),
            )

        with (
            subject.store.unlocked(credential=credential, now=now()) as unlocked,
            bind_auth_provider_selector(selector),
        ):
            if verified:
                acquired = await acquire()
                assert acquired.assertion.is_valid
                assert not acquired.reused_persisted_session
                error_output = b""
            else:
                with pytest.raises(AeatLoginAssertionError) as refused:
                    await acquire()
                error_output = str(refused.value).encode("utf-8")
            assert provider.authentication_count == provider.verification_count == provider.close_count == 1
            assert selector.arguments
            captured = capsys.readouterr()
            public_output = b"\n".join(
                (
                    *selector.arguments,
                    *provider.arguments,
                    error_output,
                    caplog.text.encode("utf-8"),
                    captured.out.encode("utf-8"),
                    captured.err.encode("utf-8"),
                    "\n".join(sys.argv).encode("utf-8"),
                    "\n".join(os.environ.values()).encode("utf-8"),
                    *(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()),
                )
            )
            for material in (*local_material, SecretBytes(bytes(unlocked))):
                secret = material.get_secret_value()
                encoded_forms = (secret, secret.hex().encode("ascii"), base64.b64encode(secret))
                if any(value in public_output for value in encoded_forms):
                    pytest.fail("local automation custody reached provider arguments or diagnostics", pytrace=False)
        if any(unlocked):
            pytest.fail("automation unlock material survived its custody span", pytrace=False)
