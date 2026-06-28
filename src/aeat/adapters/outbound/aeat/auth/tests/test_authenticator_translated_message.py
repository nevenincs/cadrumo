"""Real-behavior tests for AeatLoginAssertionError translated_message threading.

Coverage:
- already_active: AeatAuthenticator.authenticate raises AeatLoginAssertionError
  with translated_message set to already_active when an active session exists.
- assertion_failed: AeatAuthenticator.authenticate raises AeatLoginAssertionError
  with translated_message set to assertion_failed when the login probe returns
  invalid.
- resume_failed: AeatLoginAssertionError raised with the resume_failed
  translated_message key carries the correct key attribute (defensive-guard
  path).
- metadata_parse_failed: AeatLoginAssertionError raised with the
  metadata_parse_failed translated_message key carries the correct key
  attribute (defensive-guard path).
- locale resolution: All four authenticator locale keys resolve to
  non-placeholder strings in the catalogue.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pydantic import SecretStr

from ......core.config import CertificateBackend, Settings
from ......core.i18n import tr
from ......tests.secure_sql import isolated_runtime_profile
from .. import (
    AeatAuthenticator,
    AeatLoginAssertionError,
    HandshakeResult,
    LoadedCertificate,
    load_certificate,
)
from ..certificate import CertificateBundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

if TYPE_CHECKING:
    pass

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
    bundle = CertificateBundle(
        path=_build_bundle(tmp_path),
        password=SecretStr(_SECRET),
        friendly_name=None,
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    return load_certificate(bundle)


def _settings_for(bundle_path: Path) -> Settings:
    """Create Settings with certificate path and token directory overrides.

    Uses override_settings (ContextVar-backed, live-tests-friendly) rather than
    process-environment mutation (aeat-local-execution + aeat-quality-gates
    rules). Callers must wrap the
    returned Settings context within override_settings().
    """
    return Settings(
        aeat_certificate_path=bundle_path,
        aeat_certificate_password_secret=SecretStr(_SECRET),
        aeat_certificate_backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
        aeat_certificate_verify_url="https://127.0.0.1:1/",
        aeat_token_dir=bundle_path.parent / ".tokens",
        aeat_local_storage_root=bundle_path.parent / "storage",
    )


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


class _RecordingResponse:
    status = 200


class _RecordingPage:
    def __init__(self) -> None:
        self.url = "https://www6.aeat.es/protected"
        self.status = 200

    async def goto(self, url: str, *, timeout: float | None = None) -> _RecordingResponse:
        del timeout
        self.url = url
        return _RecordingResponse()

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


# ---------------------------------------------------------------------------
# already_active translated_message
# ---------------------------------------------------------------------------


def test_authenticate_already_active_carries_translated_message(
    tmp_path: Path,
) -> None:
    """authenticate raises AeatLoginAssertionError with already_active key
    when authenticate is called while a real session is still active."""
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path)
    authenticator = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())
    browser_session = _RecordingBrowserSession()

    async def run() -> None:
        try:
            session = await authenticator.authenticate(browser_session=browser_session)
            assert session.identity_nif == "12345678Z"

            with pytest.raises(AeatLoginAssertionError) as exc_info:
                await authenticator.authenticate(browser_session=browser_session)
            exc = exc_info.value
            assert exc.translated_message == "adapters.auth.authenticator.errors.already_active"
        finally:
            await authenticator.close()

    asyncio.run(run())


# ---------------------------------------------------------------------------
# assertion_failed translated_message (failed login probe)
# ---------------------------------------------------------------------------


def test_authenticate_assertion_failed_carries_translated_message(
    tmp_path: Path,
) -> None:
    """authenticate raises AeatLoginAssertionError with assertion_failed key
    when the browser context is missing the AEAT certificate marker."""
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path)
    # Use a failing handshake so the probe is_valid=False, but the context marker check passes.
    authenticator = AeatAuthenticator(settings, handshake_verifier=_FailingHandshakeVerifier())

    # cert_ok=True -> context carries CERTIFICATE_CONTEXT_MARKER (marker check passes).
    # The probe fails because handshake.success=False -> assertion_failed raised.
    browser_session = _RecordingBrowserSession()

    async def run() -> None:
        with pytest.raises(AeatLoginAssertionError) as exc_info:
            await authenticator.authenticate(browser_session=browser_session)
        exc = exc_info.value
        assert exc.translated_message == "adapters.auth.authenticator.errors.assertion_failed"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# resume_failed translated_message carries correct key
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
# metadata_parse_failed translated_message carries correct key
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
# locale keys resolve to non-placeholder strings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", _AUTHENTICATOR_LOCALE_KEYS)
def test_authenticator_locale_key_resolves_to_real_copy(key: str) -> None:
    """Every new authenticator locale key resolves to non-placeholder copy."""
    resolved = tr(key)
    assert key not in resolved, f"Key {key!r} was not replaced in the locale catalogue"
    assert len(resolved) > 10, f"Key {key!r} resolved to suspiciously short string: {resolved!r}"
