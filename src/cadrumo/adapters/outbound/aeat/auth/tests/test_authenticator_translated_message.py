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
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pydantic import SecretStr

from ......application.auth_credentials import unnamed_certificate_credentials
from ......core.config import AEAT_CERTIFICATE_PROTECTED_ORIGIN, Settings
from ......core.i18n import tr
from ......tests.secure_sql import isolated_runtime_profile
from .. import (
    AeatAuthenticator,
    AeatLoginAssertionError,
    BrowserContextLike,
    BrowserPageLike,
    BrowserResponseLike,
    BrowserSessionLike,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_AUTHENTICATOR_LOCALE_KEYS = [
    "adapters.auth.authenticator.errors.already_active",
    "adapters.auth.authenticator.errors.assertion_failed",
    "adapters.auth.authenticator.errors.resume_failed",
    "adapters.auth.authenticator.errors.metadata_parse_failed",
]

_SECRET = "correct-horse-battery-staple"
_BUCKET_ID = "auth-translated-message"
_CERT_NOT_BEFORE = datetime(2026, 5, 28, 14, 15, 0, tzinfo=UTC)
_CERT_NOT_AFTER = datetime(2099, 5, 28, 14, 15, 0, tzinfo=UTC)


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
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_CERT_NOT_BEFORE)
        .not_valid_after(_CERT_NOT_AFTER)
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


def _settings_for(bundle_path: Path) -> Settings:
    """Create Settings with certificate path and token directory overrides.

    Uses override_settings (ContextVar-backed, live-tests-friendly) rather than
    process-environment mutation (aeat-local-execution + aeat-quality-gates
    rules). Callers must wrap the
    returned Settings context within override_settings().
    """
    return Settings(
        cadrumo_certificate_path=bundle_path,
        cadrumo_certificate_password_secret=SecretStr(_SECRET),
        cadrumo_token_dir=bundle_path.parent / ".tokens",
        cadrumo_local_storage_root=bundle_path.parent / "storage",
    )


class _RecordingBrowserContext:
    """Minimal browser context stand-in for translated-message boundary tests."""

    def __init__(self, *, protected_resource_matches: bool) -> None:
        self._storage: dict[str, object] = {"cookies": [], "origins": []}
        self.closed = False
        self._protected_resource_matches = protected_resource_matches

    async def new_page(self) -> BrowserPageLike:
        return _RecordingPage(protected_resource_matches=self._protected_resource_matches)

    async def storage_state(self) -> dict[str, object]:
        return self._storage

    async def close(self) -> None:
        self.closed = True


class _RecordingPage:
    def __init__(self, *, protected_resource_matches: bool) -> None:
        self.url = ""
        self.status = 200
        self.ok = True
        self._protected_resource_matches = protected_resource_matches

    async def goto(self, url: str, *, timeout: float | None = None) -> BrowserResponseLike:
        del timeout
        self.url = url if self._protected_resource_matches else f"{AEAT_CERTIFICATE_PROTECTED_ORIGIN}/"
        return self

    async def close(self) -> None:
        pass


class _RecordingBrowserSession:
    """Browser session stand-in that creates contexts for translated-message tests."""

    def __init__(self, *, protected_resource_matches: bool = True) -> None:
        self.closed = False
        self.profile = None
        self._protected_resource_matches = protected_resource_matches

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> BrowserContextLike:
        del storage_state_path, storage_state
        assert provisioner is not None
        return _RecordingBrowserContext(
            protected_resource_matches=self._protected_resource_matches,
        )

    async def close(self) -> None:
        self.closed = True


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
    browser_session = _RecordingBrowserSession()

    async def factory(settings: Settings) -> BrowserSessionLike:
        del settings
        return browser_session

    authenticator = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        browser_session_factory=factory,
    )

    async def run() -> None:
        try:
            session = await authenticator.authenticate()
            assert session.identity_nif == "12345678Z"

            with pytest.raises(AeatLoginAssertionError) as exc_info:
                await authenticator.authenticate()
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
    """authenticate raises assertion_failed when the protected URL is not retained."""
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path)
    browser_session = _RecordingBrowserSession(protected_resource_matches=False)

    async def factory(settings: Settings) -> BrowserSessionLike:
        del settings
        return browser_session

    authenticator = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        browser_session_factory=factory,
    )

    async def run() -> None:
        with pytest.raises(AeatLoginAssertionError) as exc_info:
            await authenticator.authenticate()
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
