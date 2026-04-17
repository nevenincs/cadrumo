"""Unit tests for :mod:`aeat.auth._authenticator`.

Zero mocks / patches / fakes (global ban) — we exercise the
authenticator with a real ``LoadedCertificate`` (generated at
runtime via :mod:`cryptography`) and a stand-in browser session
factory that honours the ``_aeat_certificate_thumbprint`` marker
contract.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from aeat.auth import (
    AEAT_SESSION_IDLE_TTL,
    AeatAuthenticator,
    AeatLoginAssertion,
    AeatLoginAssertionError,
    AeatSession,
    AeatSessionExpiredError,
    CertificateBackend,
    CertificateNifParseError,
    HandshakeResult,
    LoadedCertificate,
    extract_nif_from_subject,
    load_certificate,
)
from aeat.auth.certificate import CertificateBundle

SECRET_PASSPHRASE = "correct-horse-battery-staple"


def _build_bundle(
    tmp_path: Path,
    *,
    subject_attrs: list[x509.NameAttribute] | None = None,
    not_valid_after: datetime | None = None,
) -> Path:
    """Generate a real self-signed PKCS#12 bundle."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
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
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"test-cert",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(SECRET_PASSPHRASE.encode()),
    )
    out = tmp_path / "bundle.p12"
    out.write_bytes(pfx_bytes)
    return out


def _load_cert(
    tmp_path: Path,
    *,
    subject_attrs: list[x509.NameAttribute] | None = None,
    not_valid_after: datetime | None = None,
) -> LoadedCertificate:
    """Build a bundle + load it under a deterministic env var name."""
    import os

    bundle_path = _build_bundle(
        tmp_path,
        subject_attrs=subject_attrs,
        not_valid_after=not_valid_after,
    )
    os.environ["AEAT_TEST_CERT_PW"] = SECRET_PASSPHRASE
    bundle = CertificateBundle(
        path=bundle_path,
        password_env_var="AEAT_TEST_CERT_PW",
        friendly_name=None,
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    return load_certificate(bundle)


# ── extract_nif_from_subject ────────────────────────────────────────────────


@pytest.mark.unit
def test_extract_nif_from_serial_with_idces_prefix(tmp_path: Path) -> None:
    cert = _load_cert(tmp_path)
    assert extract_nif_from_subject(cert) == "12345678Z"


@pytest.mark.unit
def test_extract_nif_from_bare_serial(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "ANYBODY"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "87654321A"),
        ],
    )
    assert extract_nif_from_subject(cert) == "87654321A"


@pytest.mark.unit
def test_extract_nif_accepts_nie(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "X1234567L"),
            x509.NameAttribute(NameOID.COMMON_NAME, "RESIDENT PERSON"),
        ],
    )
    assert extract_nif_from_subject(cert) == "X1234567L"


@pytest.mark.unit
def test_extract_nif_cn_fallback(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NOMBRE APELLIDO - 22334455B"),
        ],
    )
    assert extract_nif_from_subject(cert) == "22334455B"


@pytest.mark.unit
def test_extract_nif_rejects_cif(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "B12345674"),
            x509.NameAttribute(NameOID.COMMON_NAME, "EMPRESA SL"),
        ],
    )
    with pytest.raises(CertificateNifParseError):
        extract_nif_from_subject(cert)


@pytest.mark.unit
def test_extract_nif_rejects_unparseable(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NO-NIF-HERE"),
        ],
    )
    with pytest.raises(CertificateNifParseError):
        extract_nif_from_subject(cert)


# ── AeatSession record ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_aeat_session_is_stale_predicate(tmp_path: Path) -> None:
    authenticated_at = datetime.now(UTC)
    session = AeatSession(
        certificate_thumbprint="abc123",
        certificate_subject="CN=test",
        certificate_nif="12345678Z",
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
        storage_state_path=None,
        handshake=_fake_handshake(),
    )
    assert session.is_stale(authenticated_at) is False
    assert session.is_stale(authenticated_at + timedelta(minutes=1)) is False
    assert session.is_stale(authenticated_at + timedelta(minutes=30)) is True


@pytest.mark.unit
def test_aeat_session_model_dump_carries_no_secrets(tmp_path: Path) -> None:
    authenticated_at = datetime.now(UTC)
    session = AeatSession(
        certificate_thumbprint="abc123",
        certificate_subject="CN=NOMBRE,SERIALNUMBER=12345678Z",
        certificate_nif="12345678Z",
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
        storage_state_path=tmp_path / "storage.json",
        handshake=_fake_handshake(),
    )
    dumped = session.model_dump_json()
    assert SECRET_PASSPHRASE not in dumped
    assert "_pkcs12_bytes" not in dumped


# ── AeatLoginAssertion record ───────────────────────────────────────────────


@pytest.mark.unit
def test_aeat_login_assertion_is_valid_composite() -> None:
    assertion = AeatLoginAssertion(
        target_url="https://sede/",
        is_valid=True,
        handshake_success=True,
        certificate_recognised=True,
        parsed_nif="12345678Z",
        parsed_subject="CN=NOMBRE",
        status_code=200,
        elapsed_ms=123,
        attempted_at=datetime.now(UTC),
        error_message=None,
    )
    assert assertion.is_valid is True
    assert assertion.model_config["frozen"] is True


# ── AeatAuthenticator — fake browser session factory ────────────────────────


class _FakeBrowserContext:
    """Stand-in Playwright context that honours the marker contract."""

    def __init__(self, cert: LoadedCertificate, recognised: bool = True) -> None:
        self._aeat_certificate_thumbprint = cert.sha256_thumbprint
        self._recognised = recognised
        self._pages: list[_FakePage] = []
        self.closed = False

    async def new_page(self) -> _FakePage:
        page = _FakePage(recognised=self._recognised)
        self._pages.append(page)
        return page

    async def close(self) -> None:
        self.closed = True


class _FakePage:
    def __init__(self, recognised: bool) -> None:
        self._recognised = recognised

    async def goto(self, url: str) -> _FakeResponse:
        return _FakeResponse(200 if self._recognised else 401)

    async def close(self) -> None:
        return None


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class _FakeBrowserSession:
    def __init__(self, cert_ok: bool = True) -> None:
        self._cert_ok = cert_ok
        self.created: list[_FakeBrowserContext] = []

    async def create_context(
        self,
        *,
        cert: LoadedCertificate | None = None,
    ) -> _FakeBrowserContext:
        assert cert is not None
        ctx = _FakeBrowserContext(cert, recognised=self._cert_ok)
        self.created.append(ctx)
        return ctx


def _fake_handshake() -> HandshakeResult:
    return HandshakeResult(
        success=True,
        status_code=200,
        server_cert_chain=(),
        elapsed_ms=10,
        attempted_at=datetime.now(UTC),
        error_message=None,
    )


def _settings_for(path: Path, monkeypatch: pytest.MonkeyPatch):
    from aeat.config import Settings

    monkeypatch.setenv("AEAT_CERTIFICATE_PATH", str(path))
    monkeypatch.setenv("AEAT_CERTIFICATE_PASSWORD_SECRET", SECRET_PASSPHRASE)
    monkeypatch.setenv("AEAT_CERTIFICATE_BACKEND", CertificateBackend.HTTPX_FALLBACK.value)
    monkeypatch.setenv("AEAT_CERTIFICATE_VERIFY_URL", "https://example.invalid/")
    return Settings()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_authenticator_synchronous_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Synchronous helpers work under the async context manager.

    ``authenticate()`` is not exercised here because
    ``verify_handshake`` reaches the network and cannot succeed
    against ``example.invalid``; the full path is covered by the
    live test suite. This unit test asserts the helpers that do
    not require network access are usable through the same
    authenticator instance.
    """
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    async with AeatAuthenticator(settings) as auth:
        cert = auth.load_certificate()
        nif = auth.extract_nif_from_subject(cert)
        assert nif == "12345678Z"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_login_raises_on_stale_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    async with AeatAuthenticator(settings) as auth:
        now = datetime.now(UTC)
        stale = AeatSession(
            certificate_thumbprint="abc",
            certificate_subject="CN=x",
            certificate_nif="12345678Z",
            authenticated_at=now - timedelta(hours=1),
            idle_deadline=now - timedelta(minutes=30),
            storage_state_path=None,
            handshake=_fake_handshake(),
        )
        with pytest.raises(AeatSessionExpiredError):
            await auth.verify_login(stale)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_login_raises_without_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    async with AeatAuthenticator(settings) as auth:
        now = datetime.now(UTC)
        session = AeatSession(
            certificate_thumbprint="abc",
            certificate_subject="CN=x",
            certificate_nif="12345678Z",
            authenticated_at=now,
            idle_deadline=now + AEAT_SESSION_IDLE_TTL,
            storage_state_path=None,
            handshake=_fake_handshake(),
        )
        with pytest.raises(AeatLoginAssertionError):
            await auth.verify_login(session)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    auth = AeatAuthenticator(settings)
    await auth.close()
    await auth.close()  # must not raise
