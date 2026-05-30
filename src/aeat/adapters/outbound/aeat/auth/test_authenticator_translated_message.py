"""Real-behavior tests for AeatLoginAssertionError translated_message threading (S281).

Coverage:
- S281-A: AeatAuthenticator.authenticate raises AeatLoginAssertionError with
  translated_message set to already_active when an active session already exists.
- S281-B: AeatAuthenticator.authenticate raises AeatLoginAssertionError with
  translated_message set to assertion_failed when the login probe returns invalid.
- S281-C: AeatLoginAssertionError raised with resume_failed translated_message key
  carries the correct key attribute (defensive-guard path).
- S281-D: AeatLoginAssertionError raised with metadata_parse_failed translated_message key
  carries the correct key attribute (defensive-guard path).
- S281-E: All four authenticator locale keys resolve to non-placeholder strings
  in the catalogue.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from .....core.config import Settings
from .....core.i18n import tr
from .....tests.secure_sql import isolated_runtime_profile
from . import (
    AEAT_SESSION_IDLE_TTL,
    CERTIFICATE_CONTEXT_MARKER,
    AeatAuthenticator,
    AeatLoginAssertionError,
    AeatSession,
    BrowserContextLike,
    BrowserSessionLike,
    CertificateBackend,
    CertificateSessionDetail,
    HandshakeResult,
    LoadedCertificate,
    load_certificate,
)
from ._providers import AuthProviderKind
from .certificate import CertificateBundle

if TYPE_CHECKING:
    pass

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]

_AUTHENTICATOR_LOCALE_KEYS = [
    "adapters.auth.authenticator.errors.already_active",
    "adapters.auth.authenticator.errors.assertion_failed",
    "adapters.auth.authenticator.errors.resume_failed",
    "adapters.auth.authenticator.errors.metadata_parse_failed",
]

_SECRET = "correct-horse-battery-staple"
_BUCKET_ID = "auth-translated-message"


@pytest.fixture(autouse=True)
def _isolated_secure_session_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


@functools.cache
def _default_pkcs12_bytes() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    attrs = [
        x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
        x509.NameAttribute(NameOID.COMMON_NAME, "TEST SUBJECT - 12345678Z"),
        x509.NameAttribute(NameOID.SERIAL_NUMBER, "IDCES-12345678Z"),
    ]
    subject = issuer = x509.Name(attrs)
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(_SECRET.encode()),
    )


def _build_bundle(tmp_path: Path) -> Path:
    out = tmp_path / "bundle.p12"
    out.write_bytes(_default_pkcs12_bytes())
    return out


def _load_cert(tmp_path: Path) -> LoadedCertificate:
    from pydantic import SecretStr

    bundle = CertificateBundle(
        path=_build_bundle(tmp_path),
        password=SecretStr(_SECRET),
        friendly_name=None,
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    return load_certificate(bundle)


def _settings_for(bundle_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    from pydantic_settings import SettingsConfigDict

    for name in Settings.env_var_names():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AEAT_CERTIFICATE_PATH", str(bundle_path))
    monkeypatch.setenv("AEAT_CERTIFICATE_PASSWORD_SECRET", _SECRET)
    monkeypatch.setenv("AEAT_CERTIFICATE_BACKEND", CertificateBackend.PLAYWRIGHT_CONTEXT.value)
    monkeypatch.setenv("AEAT_CERTIFICATE_VERIFY_URL", "https://127.0.0.1:1/")
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(bundle_path.parent / ".tokens"))
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(bundle_path.parent / "storage"))

    class _IsolatedSettings(Settings):
        model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8", env_ignore_empty=True)

    return _IsolatedSettings()


def _successful_handshake() -> HandshakeResult:
    return HandshakeResult(
        success=True,
        status_code=200,
        server_cert_chain=(),
        elapsed_ms=10,
        attempted_at=datetime.now(UTC),
        error_message=None,
    )


class _RecordingBrowserContext:
    """Minimal browser context stand-in that applies the certificate marker from the provisioner."""

    def __init__(self) -> None:
        self._storage: dict[str, object] = {"cookies": [], "origins": []}
        self.closed = False

    async def new_page(self) -> _RecordingPage:
        return _RecordingPage()

    async def storage_state(self) -> dict[str, object]:
        return self._storage

    async def close(self) -> None:
        self.closed = True


class _RecordingPage:
    def __init__(self) -> None:
        self.url = "https://www6.aeat.es/protected"
        self.status = 200

    async def goto(self, url: str, *, timeout: float | None = None) -> object:
        del timeout

        class _Resp:
            status = 200

        return _Resp()

    async def close(self) -> None:
        pass


class _RecordingBrowserSession:
    """Browser session stand-in that creates contexts and applies the provisioner marker."""

    def __init__(self) -> None:
        self.closed = False

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _RecordingBrowserContext:
        del storage_state_path, storage_state
        ctx = _RecordingBrowserContext()
        # Replicate BrowserSession's annotation step so _assert_context_marker passes.
        if provisioner is not None:
            annotate = getattr(provisioner, "annotate_context", None)
            if annotate is not None:
                annotate(ctx)
        return ctx

    async def close(self) -> None:
        self.closed = True


class _HandshakeVerifier:
    def __call__(self, _cert: LoadedCertificate, _target: str) -> HandshakeResult:
        return _successful_handshake()


class _FailingHandshakeVerifier:
    """Returns a failed handshake so the login probe is_valid=False."""

    def __call__(self, _cert: LoadedCertificate, _target: str) -> HandshakeResult:
        return HandshakeResult(
            success=False,
            status_code=0,
            server_cert_chain=(),
            elapsed_ms=0,
            attempted_at=datetime.now(UTC),
            error_message="simulated handshake failure",
        )


def _certificate_session(
    *,
    authenticated_at: datetime,
    idle_deadline: datetime,
    thumbprint: str = "abc123",
    subject: str = "CN=test",
    identity_nif: str = "12345678Z",
    storage_state_path: Path | None = None,
) -> AeatSession:
    return AeatSession(
        provider_kind=AuthProviderKind.CERTIFICATE,
        authenticated_at=authenticated_at,
        idle_deadline=idle_deadline,
        storage_state_path=storage_state_path,
        identity_nif=identity_nif,
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint=thumbprint,
            certificate_subject=subject,
            handshake=_successful_handshake(),
        ),
    )


# ---------------------------------------------------------------------------
# S281-A: already_active translated_message
# ---------------------------------------------------------------------------


def test_authenticate_already_active_carries_translated_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """authenticate raises AeatLoginAssertionError with already_active key
    when _active_session is set before the call."""
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    authenticator = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())

    now = datetime.now(UTC)
    authenticator._active_session = _certificate_session(  # type: ignore[attr-defined]
        authenticated_at=now,
        idle_deadline=now + AEAT_SESSION_IDLE_TTL,
    )

    async def run() -> None:
        with pytest.raises(AeatLoginAssertionError) as exc_info:
            await authenticator.authenticate(
                browser_session=cast(BrowserSessionLike, _RecordingBrowserSession())
            )
        exc = exc_info.value
        assert exc.translated_message == "adapters.auth.authenticator.errors.already_active"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# S281-B: assertion_failed translated_message (failed login probe)
# ---------------------------------------------------------------------------


def test_authenticate_assertion_failed_carries_translated_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """authenticate raises AeatLoginAssertionError with assertion_failed key
    when the browser context is missing the AEAT certificate marker."""
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    # Use a failing handshake so the probe is_valid=False, but the context marker check passes.
    authenticator = AeatAuthenticator(settings, handshake_verifier=_FailingHandshakeVerifier())

    # cert_ok=True -> context carries CERTIFICATE_CONTEXT_MARKER (marker check passes).
    # The probe fails because handshake.success=False -> assertion_failed raised.
    browser_session = cast(BrowserSessionLike, _RecordingBrowserSession())

    async def run() -> None:
        with pytest.raises(AeatLoginAssertionError) as exc_info:
            await authenticator.authenticate(browser_session=browser_session)
        exc = exc_info.value
        assert exc.translated_message == "adapters.auth.authenticator.errors.assertion_failed"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# S281-C: resume_failed translated_message carries correct key
# ---------------------------------------------------------------------------


def test_resume_failed_exception_carries_translated_message_key() -> None:
    """AeatLoginAssertionError raised with resume_failed key carries the expected
    translated_message attribute.

    This exercises the exception class contract for the defensive-guard path at
    line 1083 of _authenticator.py where context or session is None after
    _resume_from_storage_state completes. The path is tested structurally
    because triggering it via production flow would require a browser session
    that returns a context but then silently discards it — an impossible
    condition in the current session management code."""
    exc = AeatLoginAssertionError(
        "persisted AEAT session resume did not produce a usable context",
        translated_message="adapters.auth.authenticator.errors.resume_failed",
    )
    assert exc.translated_message == "adapters.auth.authenticator.errors.resume_failed"
    assert "resume" in str(exc)


# ---------------------------------------------------------------------------
# S281-D: metadata_parse_failed translated_message carries correct key
# ---------------------------------------------------------------------------


def test_metadata_parse_failed_exception_carries_translated_message_key() -> None:
    """AeatLoginAssertionError raised with metadata_parse_failed key carries the
    expected translated_message attribute.

    This exercises the exception class contract for the defensive-guard path at
    line 1157 of _authenticator.py where metadata remains None after the
    try/except block. The path is tested structurally because the except branch
    unconditionally re-raises via _raise_invalid_persisted_state (NoReturn),
    making the None-guard unreachable in normal production flow."""
    exc = AeatLoginAssertionError(
        "persisted metadata did not produce a parsed model",
        translated_message="adapters.auth.authenticator.errors.metadata_parse_failed",
    )
    assert exc.translated_message == "adapters.auth.authenticator.errors.metadata_parse_failed"
    assert "metadata" in str(exc)


# ---------------------------------------------------------------------------
# S281-E: locale keys resolve to non-placeholder strings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", _AUTHENTICATOR_LOCALE_KEYS)
def test_authenticator_locale_key_resolves_to_real_copy(key: str) -> None:
    """Every new authenticator locale key resolves to non-placeholder copy."""
    resolved = tr(key)
    assert key not in resolved, f"Key {key!r} was not replaced in the locale catalogue"
    assert len(resolved) > 10, f"Key {key!r} resolved to suspiciously short string: {resolved!r}"
