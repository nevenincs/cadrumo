"""Shared support for split adapter tests."""

from __future__ import annotations

import asyncio
import functools
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NoReturn as NoReturn

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from ......application.auth.providers import AuthProvider as AuthProvider
from ......application.auth.session_types import (
    AeatLoginAssertion,
    AeatSession,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
)
from ......application.auth_credentials import unnamed_certificate_credentials
from ......core.auth_provider import AuthProviderDescription as AuthProviderDescription
from ......core.auth_provider import AuthProviderKind as AuthProviderKind
from ......core.config import (
    AEAT_CERTIFICATE_PROTECTED_ORIGIN,
    AEAT_CERTIFICATE_PROTECTED_URL,
    Settings,
)
from ......core.errors.hierarchy import AeatLoginAssertionError
from .....persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..authenticator import AEAT_SESSION_IDLE_TTL, AeatAuthenticator
from ..certificate import CertificateBundle, LoadedCertificate, extract_nif_from_subject, load_certificate
from ..certificate import CertificateError as CertificateError
from ..certificate import CertificateNifParseError as CertificateNifParseError
from ..errors import AeatSessionExpiredError, AuthConfigurationError
from ..errors import AuthValidationError as AuthValidationError
from ..provider_selection import select_provider as select_provider
from ._auth_fixtures import SECRET_PASSPHRASE

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_BUCKET_ID = "1f6b0000-0000-4000-8000-00000000a0a0"

_SENSITIVE_STORAGE_BASENAME = "12345678Z-private-storage.json"

_SENSITIVE_NAVIGATION_PAYLOAD = "12345678Z private browser payload"

_SENSITIVE_HEALTH_PAYLOAD = "C:/Users/operator/private-cert-12345678Z.p12"

_SEDE_ORIGIN = AEAT_CERTIFICATE_PROTECTED_ORIGIN


_isolated_secure_session_backend = bucket_scoped_runtime_profile_fixture(
    _BUCKET_ID, autouse=True, name="_isolated_secure_session_backend"
)


def _serialise_pkcs12(
    *,
    subject_attrs: list[x509.NameAttribute[str | bytes]] | None,
    not_valid_after: datetime | None,
    subject_name: x509.Name | None = None,
) -> bytes:
    """Generate a real self-signed PKCS#12 bundle and return its bytes.

    ``subject_name`` takes precedence over ``subject_attrs`` and lets a
    caller supply a pre-built :class:`x509.Name` carrying a multi-valued
    RDN (``CN=X+SERIALNUMBER=Y``) that a flat attribute list cannot express.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    if subject_name is not None:
        subject = issuer = subject_name
    else:
        attrs = subject_attrs or [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NOMBRE APELLIDO1 APELLIDO2 - 12345678Z"),
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
        .not_valid_after(not_valid_after or (now + timedelta(days=365)))
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        name=b"test-cert",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(SECRET_PASSPHRASE.encode()),
    )


@functools.cache
def _default_pkcs12_bytes() -> bytes:
    """Cache the default-subject PKCS#12 bytes for the lifetime of the process.

    RSA-2048 keygen + PKCS#12 serialise costs ~0.5-1 s per call. The
    13+ ``test_resume_from_storage_state*`` tests and several other
    cert-bearing tests in this module all want the default subject
    (NIF 12345678Z) and the default validity window; computing the
    bytes once and writing them to each test's ``tmp_path`` brings
    the per-test fixed cost down to a single ``write_bytes`` call.
    """
    return _serialise_pkcs12(subject_attrs=None, not_valid_after=None)


def _build_bundle(
    tmp_path: Path,
    *,
    subject_attrs: list[x509.NameAttribute[str | bytes]] | None = None,
    not_valid_after: datetime | None = None,
    subject_name: x509.Name | None = None,
) -> Path:
    """Generate a real self-signed PKCS#12 bundle on disk.

    Default-argument calls are served from the cached bytes built by
    :func:`_default_pkcs12_bytes`; custom subjects or expiries always
    regenerate.
    """
    out = tmp_path / "bundle.p12"
    if subject_attrs is None and not_valid_after is None and subject_name is None:
        out.write_bytes(_default_pkcs12_bytes())
        return out
    out.write_bytes(
        _serialise_pkcs12(
            subject_attrs=subject_attrs,
            not_valid_after=not_valid_after,
            subject_name=subject_name,
        )
    )
    return out


def _load_cert(
    tmp_path: Path,
    *,
    subject_attrs: list[x509.NameAttribute[str | bytes]] | None = None,
    not_valid_after: datetime | None = None,
    subject_name: x509.Name | None = None,
) -> LoadedCertificate:
    """Build a bundle + load it under a deterministic env var name."""
    from pydantic import SecretStr

    bundle_path = _build_bundle(
        tmp_path,
        subject_attrs=subject_attrs,
        not_valid_after=not_valid_after,
        subject_name=subject_name,
    )
    bundle = CertificateBundle(
        path=bundle_path,
        password=SecretStr(SECRET_PASSPHRASE),
        friendly_name=None,
    )
    return load_certificate(bundle)


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
        authenticated_at=authenticated_at,
        idle_deadline=idle_deadline,
        storage_state_path=storage_state_path,
        identity_nif=identity_nif,
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint=thumbprint,
            certificate_subject=subject,
        ),
    )


def _certificate_assertion() -> AeatLoginAssertion:
    return AeatLoginAssertion(
        target_url=AEAT_CERTIFICATE_PROTECTED_URL,
        is_valid=True,
        identity_nif="12345678Z",
        status_code=200,
        elapsed_ms=123,
        attempted_at=datetime.now(UTC),
        error_message=None,
        assertion_detail=CertificateLoginAssertionDetail(
            final_url=AEAT_CERTIFICATE_PROTECTED_URL,
            response_successful=True,
            parsed_subject="CN=NOMBRE",
        ),
    )


@pytest.fixture
def _settings_factory():
    """Yield a cert-shaped Settings factory built on the centralized scope helper.

    Delegates the async-context-safe ContextVar mutation to
    :func:`aeat-tests.settings_scope.settings_factory`, then wraps the
    generic factory with this module's certificate-bundle defaults
    (path, passphrase, and token-dir derived from the bundle path).
    Tests pass the bundle ``Path`` as the single
    positional argument; extra Settings overrides go through ``**``.
    """
    from ......tests.settings_scope import settings_factory as _scoped_factory

    with _scoped_factory() as scoped:

        def factory(
            path: Path,
            **extra_overrides: object,
        ) -> Settings:
            overrides: dict[str, object] = {
                "cadrumo_certificate_path": path,
                "cadrumo_certificate_password_secret": SECRET_PASSPHRASE,
                "cadrumo_token_dir": path.parent / ".tokens",
            }
            overrides.update(extra_overrides)
            return scoped(**overrides)

        yield factory


@pytest.mark.asyncio
async def test_authenticator_synchronous_surface(tmp_path: Path, _settings_factory) -> None:
    """Synchronous helpers work under the async context manager.

    This unit test asserts the certificate helpers that do not require
    protected browser access are usable through the same authenticator
    instance.
    """
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    async with AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    ) as auth:
        cert = auth.load_certificate()
        nif = extract_nif_from_subject(cert)
        assert nif == "12345678Z"


@pytest.mark.asyncio
async def test_verify_raises_on_stale_session(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    async with AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    ) as auth:
        now = datetime.now(UTC)
        stale = _certificate_session(
            authenticated_at=now - timedelta(hours=1),
            idle_deadline=now - timedelta(minutes=30),
            thumbprint="abc",
            subject="CN=x",
        )
        with pytest.raises(AeatSessionExpiredError, match=r"aeat|session|expired"):
            await auth.verify(stale)


@pytest.mark.asyncio
async def test_verify_raises_without_context(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    async with AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    ) as auth:
        now = datetime.now(UTC)
        session = _certificate_session(
            authenticated_at=now,
            idle_deadline=now + AEAT_SESSION_IDLE_TTL,
            thumbprint="abc",
            subject="CN=x",
        )
        with pytest.raises(AeatLoginAssertionError, match=r"browser context|authenticate"):
            await auth.verify(session)


@pytest.mark.asyncio
async def test_reauthenticate_does_not_deadlock(tmp_path: Path, _settings_factory) -> None:
    """Regression test: reauthenticate must not deadlock on self._lock.

    The method was rewritten to delegate teardown to ``close()``
    (itself lock-protected) rather than holding ``self._lock``
    across the subsequent ``authenticate()`` call. Proves the
    single-lock invariant by reauthenticating and confirming no
    timeout. It intentionally does not claim successful external
    authentication; that remains the credential-gated live oracle.
    """
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    async with AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    ) as auth:
        # Build a session to pass to reauthenticate. The call will fail
        # at the network-free browser-session resolution step, so we
        # assert that reauthenticate completes without deadlocking
        # regardless of the authenticate outcome.
        now = datetime.now(UTC)
        session = _certificate_session(
            authenticated_at=now,
            idle_deadline=now + AEAT_SESSION_IDLE_TTL,
            thumbprint="abc",
            subject="CN=x",
        )
        # authenticate() without an injected browser_session_factory
        # raises AuthConfigurationError (missing-factory taxonomy, per
        # AeatAuthenticator._resolve_browser_session); we only care that
        # the call returns in bounded time (no deadlock).
        with pytest.raises(AuthConfigurationError, match=r"browser.*session factory"):
            await asyncio.wait_for(auth.reauthenticate(session), timeout=5.0)
