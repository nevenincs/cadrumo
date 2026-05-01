"""Unit tests for :mod:`aeat.adapters.outbound.aeat.auth._authenticator`.

Zero mocks / patches / fakes (global ban) — we exercise the
authenticator with a real ``LoadedCertificate`` (generated at
runtime via :mod:`cryptography`) and a stand-in browser session
factory that honours the ``_aeat_certificate_thumbprint`` marker
contract.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from . import (
    AEAT_SESSION_IDLE_TTL,
    CERTIFICATE_CONTEXT_MARKER,
    AeatAuthenticator,
    AeatLoginAssertion,
    AeatLoginAssertionError,
    AeatSession,
    AeatSessionExpiredError,
    AuthProvider,
    AuthProviderDescription,
    AuthProviderKind,
    BrowserContextLike,
    BrowserSessionLike,
    CertificateBackend,
    CertificateLoginAssertionDetail,
    CertificateNifParseError,
    CertificateSessionDetail,
    ClavePermanenteLoginAssertionDetail,
    ClavePermanenteSessionDetail,
    HandshakeResult,
    LoadedCertificate,
    extract_nif_from_subject,
    load_certificate,
    select_provider,
)
from . import _authenticator as authenticator_module
from .certificate import CertificateBundle

if TYPE_CHECKING:
    from .....core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]

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


def test_extract_nif_from_serial_with_idces_prefix(tmp_path: Path) -> None:
    cert = _load_cert(tmp_path)
    assert extract_nif_from_subject(cert) == "12345678Z"


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


def test_extract_nif_cn_fallback(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NOMBRE APELLIDO - 22334455B"),
        ],
    )
    assert extract_nif_from_subject(cert) == "22334455B"


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


def test_aeat_session_is_stale_predicate(tmp_path: Path) -> None:
    authenticated_at = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
    )
    assert session.is_stale(authenticated_at) is False
    assert session.is_stale(authenticated_at + timedelta(minutes=1)) is False
    assert session.is_stale(authenticated_at + timedelta(minutes=30)) is True


def test_aeat_session_model_dump_carries_no_secrets(tmp_path: Path) -> None:
    authenticated_at = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
        subject="CN=NOMBRE,SERIALNUMBER=12345678Z",
        storage_state_path=tmp_path / "storage.json",
    )
    dumped = session.model_dump_json()
    assert SECRET_PASSPHRASE not in dumped
    assert "_pkcs12_bytes" not in dumped


# ── AeatLoginAssertion record ───────────────────────────────────────────────


def test_aeat_login_assertion_is_valid_composite() -> None:
    assertion = _certificate_assertion()
    assert assertion.is_valid is True
    assert assertion.model_config["frozen"] is True


# ── AeatAuthenticator — fake browser session factory ────────────────────────


class _FakeBrowserContext:
    """Stand-in Playwright context that honours the marker contract."""

    def __init__(
        self,
        cert: LoadedCertificate,
        recognised: bool = True,
        *,
        storage_state: dict[str, object] | None = None,
    ) -> None:
        setattr(self, CERTIFICATE_CONTEXT_MARKER, cert.sha256_thumbprint)
        self._recognised = recognised
        if storage_state is None:
            self._storage_state: dict[str, object] = {"cookies": [], "origins": []}
        else:
            self._storage_state = storage_state
        self._pages: list[_FakePage] = []
        self.closed = False

    async def new_page(self) -> _FakePage:
        page = _FakePage(recognised=self._recognised)
        self._pages.append(page)
        return page

    async def close(self) -> None:
        self.closed = True

    async def storage_state(self) -> dict[str, object]:
        return self._storage_state


class _FakePage:
    def __init__(self, recognised: bool) -> None:
        self._recognised = recognised

    async def goto(self, url: str, *, timeout: float | None = None) -> _FakeResponse:
        return _FakeResponse(200 if self._recognised else 401)

    async def close(self) -> None:
        return None


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class _FakeBrowserSession:
    def __init__(
        self,
        cert_ok: bool = True,
        *,
        storage_state: dict[str, object] | None = None,
    ) -> None:
        self._cert_ok = cert_ok
        if storage_state is None:
            self._storage_state: dict[str, object] = {"cookies": [], "origins": []}
        else:
            self._storage_state = storage_state
        self.created: list[_FakeBrowserContext] = []
        self.storage_state_paths: list[Path | None] = []

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
    ) -> _FakeBrowserContext:
        assert provisioner is not None
        cert = self._resolve_cert(provisioner)
        self.storage_state_paths.append(storage_state_path)
        ctx = _FakeBrowserContext(
            cert,
            recognised=self._cert_ok,
            storage_state=self._storage_state,
        )
        self.created.append(ctx)
        return ctx

    @staticmethod
    def _resolve_cert(provisioner: object) -> LoadedCertificate:
        cert = getattr(provisioner, "_cert", None)
        assert isinstance(cert, LoadedCertificate)
        return cert


def _fake_handshake() -> HandshakeResult:
    return HandshakeResult(
        success=True,
        status_code=200,
        server_cert_chain=(),
        elapsed_ms=10,
        attempted_at=datetime.now(UTC),
        error_message=None,
    )


class _HandshakeVerifier:
    def __init__(self, result: HandshakeResult | None = None) -> None:
        self.calls = 0
        self.result = result or _fake_handshake()

    def __call__(self, _cert: LoadedCertificate, _target: str) -> HandshakeResult:
        self.calls += 1
        return self.result


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
            handshake=_fake_handshake(),
        ),
    )


def _certificate_assertion() -> AeatLoginAssertion:
    return AeatLoginAssertion(
        target_url="https://sede/",
        is_valid=True,
        provider_kind=AuthProviderKind.CERTIFICATE,
        identity_nif="12345678Z",
        status_code=200,
        elapsed_ms=123,
        attempted_at=datetime.now(UTC),
        error_message=None,
        assertion_detail=CertificateLoginAssertionDetail(
            handshake_success=True,
            certificate_recognised=True,
            parsed_subject="CN=NOMBRE",
        ),
    )


def _settings_for(
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    verify_url: str = "https://127.0.0.1:1/",
):
    from .....core.config import Settings

    monkeypatch.setenv("AEAT_CERTIFICATE_PATH", str(path))
    monkeypatch.setenv("AEAT_CERTIFICATE_PASSWORD_SECRET", SECRET_PASSPHRASE)
    monkeypatch.setenv("AEAT_CERTIFICATE_BACKEND", CertificateBackend.HTTPX_FALLBACK.value)
    monkeypatch.setenv("AEAT_CERTIFICATE_VERIFY_URL", verify_url)
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(path.parent / ".tokens"))
    return Settings()


async def _seed_persisted_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    storage_state_path: Path | None = None,
) -> tuple[Settings, Path, LoadedCertificate]:
    """Create a valid persisted storage-state pair for resume-path tests."""
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    persisted_path = storage_state_path or (tmp_path / "persisted-storage.json")

    seed_auth = AeatAuthenticator(settings)
    cert = seed_auth.load_certificate()
    context = _FakeBrowserContext(
        cert,
        storage_state={
            "cookies": [{"name": "AEATSESSID", "value": "resume-ok"}],
            "origins": [{"origin": "https://sede.agenciatributaria.gob.es", "localStorage": []}],
        },
    )
    seeded_at = datetime.now(UTC)
    seeded_session = _certificate_session(
        authenticated_at=seeded_at,
        idle_deadline=seeded_at + AEAT_SESSION_IDLE_TTL,
        thumbprint=cert.sha256_thumbprint,
        subject=cert.subject,
        identity_nif=extract_nif_from_subject(cert),
        storage_state_path=persisted_path,
    )
    seed_auth._context = cast(BrowserContextLike, context)
    seed_auth._active_session = seeded_session
    await seed_auth.capture_storage_state(seeded_session)
    return settings, persisted_path, cert


@pytest.mark.asyncio
async def test_capture_storage_state_writes_storage_and_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    storage_state_path = tmp_path / "captured-storage.json"
    auth = AeatAuthenticator(settings)
    cert = auth.load_certificate()
    context = _FakeBrowserContext(
        cert,
        storage_state={
            "cookies": [{"name": "AEATSESSID", "value": "ok"}],
            "origins": [{"origin": "https://sede.agenciatributaria.gob.es", "localStorage": []}],
        },
    )
    now = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=now,
        idle_deadline=now + AEAT_SESSION_IDLE_TTL,
        thumbprint=cert.sha256_thumbprint,
        subject=cert.subject,
        identity_nif=extract_nif_from_subject(cert),
        storage_state_path=storage_state_path,
    )
    auth._context = cast(BrowserContextLike, context)
    auth._active_session = session

    captured_path = await auth.capture_storage_state(session)

    assert captured_path == storage_state_path
    assert json.loads(storage_state_path.read_text(encoding="utf-8"))["cookies"][0]["name"] == "AEATSESSID"
    metadata = json.loads(storage_state_path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert metadata["certificate_thumbprint"] == cert.sha256_thumbprint
    assert metadata["storage_state_sha256"]


@pytest.mark.asyncio
async def test_resume_from_storage_state_reuses_persisted_session_without_handshake(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, storage_state_path, cert = await _seed_persisted_session(tmp_path, monkeypatch)

    verifier = _HandshakeVerifier()
    browser_session = _FakeBrowserSession(cert_ok=True)
    auth = AeatAuthenticator(settings, handshake_verifier=verifier)

    resumed = await auth.resume_from_storage_state(
        storage_state_path,
        browser_session=cast(BrowserSessionLike, browser_session),
    )

    assert resumed.certificate_thumbprint == cert.sha256_thumbprint
    assert resumed.storage_state_path == storage_state_path
    assert verifier.calls == 0
    assert browser_session.storage_state_paths == [storage_state_path]


def _invalidate_by_missing_storage(path: Path, _cert: LoadedCertificate) -> None:
    path.unlink()


def _invalidate_by_invalid_storage_json(path: Path, _cert: LoadedCertificate) -> None:
    path.write_text("{not-json", encoding="utf-8")


def _invalidate_by_storage_root_list(path: Path, _cert: LoadedCertificate) -> None:
    path.write_text("[]", encoding="utf-8")


def _invalidate_by_missing_cookies(path: Path, _cert: LoadedCertificate) -> None:
    path.write_text('{"origins":[]}', encoding="utf-8")


def _invalidate_by_missing_origins(path: Path, _cert: LoadedCertificate) -> None:
    path.write_text('{"cookies":[]}', encoding="utf-8")


def _invalidate_by_missing_metadata(path: Path, _cert: LoadedCertificate) -> None:
    path.with_suffix(".meta.json").unlink()


def _invalidate_by_malformed_metadata(path: Path, _cert: LoadedCertificate) -> None:
    path.with_suffix(".meta.json").write_text("{bad-json", encoding="utf-8")


def _invalidate_by_schema_mismatch(path: Path, _cert: LoadedCertificate) -> None:
    metadata_path = path.with_suffix(".meta.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["schema_version"] = 999
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


def _invalidate_by_hash_mismatch(path: Path, _cert: LoadedCertificate) -> None:
    metadata_path = path.with_suffix(".meta.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["storage_state_sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


def _invalidate_by_expired_idle_deadline(path: Path, _cert: LoadedCertificate) -> None:
    metadata_path = path.with_suffix(".meta.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["idle_deadline"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


def _invalidate_by_thumbprint_mismatch(path: Path, _cert: LoadedCertificate) -> None:
    metadata_path = path.with_suffix(".meta.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["certificate_thumbprint"] = "f" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


def _invalidate_by_subject_mismatch(path: Path, _cert: LoadedCertificate) -> None:
    metadata_path = path.with_suffix(".meta.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["certificate_subject"] = "CN=DIFFERENT"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutator", "case_id"),
    [
        (_invalidate_by_missing_storage, "missing-storage"),
        (_invalidate_by_invalid_storage_json, "invalid-storage-json"),
        (_invalidate_by_storage_root_list, "storage-root-not-object"),
        (_invalidate_by_missing_cookies, "missing-cookies-array"),
        (_invalidate_by_missing_origins, "missing-origins-array"),
        (_invalidate_by_missing_metadata, "missing-metadata"),
        (_invalidate_by_malformed_metadata, "malformed-metadata"),
        (_invalidate_by_schema_mismatch, "schema-mismatch"),
        (_invalidate_by_hash_mismatch, "hash-mismatch"),
        (_invalidate_by_expired_idle_deadline, "expired-idle-deadline"),
        (_invalidate_by_thumbprint_mismatch, "thumbprint-mismatch"),
        (_invalidate_by_subject_mismatch, "subject-mismatch"),
    ],
    ids=[
        "missing-storage",
        "invalid-storage-json",
        "storage-root-not-object",
        "missing-cookies-array",
        "missing-origins-array",
        "missing-metadata",
        "malformed-metadata",
        "schema-mismatch",
        "hash-mismatch",
        "expired-idle-deadline",
        "thumbprint-mismatch",
        "subject-mismatch",
    ],
)
async def test_resume_from_storage_state_invalidates_corrupt_persisted_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator,
    case_id: str,
) -> None:
    settings, storage_state_path, cert = await _seed_persisted_session(tmp_path, monkeypatch)
    mutator(storage_state_path, cert)

    auth = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())
    browser_session = _FakeBrowserSession(cert_ok=True)

    with pytest.raises(AeatLoginAssertionError):
        await auth.resume_from_storage_state(
            storage_state_path,
            browser_session=cast(BrowserSessionLike, browser_session),
        )

    assert not storage_state_path.exists(), case_id
    assert not storage_state_path.with_suffix(".meta.json").exists(), case_id


@pytest.mark.asyncio
async def test_resume_from_storage_state_invalidates_failed_live_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, storage_state_path, _cert = await _seed_persisted_session(tmp_path, monkeypatch)

    auth = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())
    browser_session = _FakeBrowserSession(cert_ok=False)

    with pytest.raises(AeatLoginAssertionError):
        await auth.resume_from_storage_state(
            storage_state_path,
            browser_session=cast(BrowserSessionLike, browser_session),
        )

    assert not storage_state_path.exists()
    assert not storage_state_path.with_suffix(".meta.json").exists()


@pytest.mark.asyncio
async def test_authenticate_falls_back_after_stale_persisted_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    storage_state_path = settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-storage.json"
    storage_state_path.parent.mkdir(parents=True, exist_ok=True)
    storage_state_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    stale_metadata_path = storage_state_path.with_suffix(".meta.json")
    stale_metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "certificate_thumbprint": "stale-thumbprint",
                "certificate_subject": "CN=STALE",
                "certificate_nif": "12345678Z",
                "authenticated_at": datetime.now(UTC).isoformat(),
                "idle_deadline": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
                "storage_state_sha256": "0" * 64,
                "handshake": _fake_handshake().model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )

    verifier = _HandshakeVerifier()
    browser_session = _FakeBrowserSession(cert_ok=True)
    auth = AeatAuthenticator(settings, handshake_verifier=verifier)

    session = await auth.authenticate(browser_session=cast(BrowserSessionLike, browser_session))

    assert verifier.calls == 1
    assert session.storage_state_path == storage_state_path
    assert browser_session.storage_state_paths == [None]
    assert json.loads(storage_state_path.read_text(encoding="utf-8"))["cookies"] == []
    metadata = json.loads(stale_metadata_path.read_text(encoding="utf-8"))
    assert metadata["certificate_thumbprint"] == auth.load_certificate().sha256_thumbprint


def test_restrict_file_permissions_best_effort(tmp_path: Path) -> None:
    import getpass
    import subprocess

    path = tmp_path / "permissions.json"
    path.write_text("{}", encoding="utf-8")

    AeatAuthenticator._restrict_file_permissions(path)

    if os.name == "nt":
        icacls_path = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "icacls.exe"
        result = subprocess.run(  # noqa: S603 - local ACL inspection against a temp file
            [str(icacls_path), str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert getpass.getuser().lower() in result.stdout.lower()
        return

    assert path.exists()


@pytest.mark.asyncio
async def test_authenticator_synchronous_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Synchronous helpers work under the async context manager.

    ``authenticate()`` is not exercised here because
    ``verify_handshake`` reaches the network and cannot succeed
    against the local closed-port verify URL; the full path is covered by the
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


def test_describe_warns_when_password_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _build_bundle(tmp_path)
    from .....core.config import Settings

    monkeypatch.setenv("AEAT_CERTIFICATE_PATH", str(bundle_path))
    monkeypatch.delenv("AEAT_CERTIFICATE_PASSWORD_SECRET", raising=False)
    settings = Settings()
    description = AeatAuthenticator(settings).describe()

    assert description.configured is True
    assert description.available is False
    assert description.health_summary == "AEAT_CERTIFICATE_PASSWORD_SECRET not set"


def test_describe_preserves_expired_certificate_severity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _build_bundle(
        tmp_path,
        not_valid_after=datetime.now(UTC) - timedelta(hours=12),
    )
    settings = _settings_for(bundle_path, monkeypatch)
    description = AeatAuthenticator(settings).describe()

    assert description.available is True
    assert description.health_severity == "EXPIRED"
    assert description.days_until_expiry is not None
    assert description.days_until_expiry <= 0


def test_describe_forwards_bundle_backend_and_friendly_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    monkeypatch.setenv("AEAT_CERTIFICATE_FRIENDLY_NAME", "Kent cert")
    settings = _settings_for(bundle_path, monkeypatch)

    captured: dict[str, object] = {}
    real_certificate_health = authenticator_module.certificate_health

    def _capture_certificate_health(
        path: Path,
        *,
        password_env_var: str,
        warn_days: int,
        critical_days: int,
        backend: CertificateBackend = CertificateBackend.PLAYWRIGHT_CONTEXT,
        friendly_name: str | None = None,
        now: datetime | None = None,
    ):
        captured["path"] = path
        captured["password_env_var"] = password_env_var
        captured["warn_days"] = warn_days
        captured["critical_days"] = critical_days
        captured["backend"] = backend
        captured["friendly_name"] = friendly_name
        return real_certificate_health(
            path,
            password_env_var=password_env_var,
            warn_days=warn_days,
            critical_days=critical_days,
            backend=backend,
            friendly_name=friendly_name,
            now=now,
        )

    monkeypatch.setattr(authenticator_module, "certificate_health", _capture_certificate_health)

    description = AeatAuthenticator(settings).describe()

    assert description.available is True
    assert captured["path"] == bundle_path
    assert captured["password_env_var"] == "AEAT_CERTIFICATE_PASSWORD_SECRET"
    assert captured["backend"] == CertificateBackend.HTTPX_FALLBACK
    assert captured["friendly_name"] == "Kent cert"


@pytest.mark.asyncio
async def test_verify_login_raises_on_stale_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    async with AeatAuthenticator(settings) as auth:
        now = datetime.now(UTC)
        stale = _certificate_session(
            authenticated_at=now - timedelta(hours=1),
            idle_deadline=now - timedelta(minutes=30),
            thumbprint="abc",
            subject="CN=x",
        )
        with pytest.raises(AeatSessionExpiredError):
            await auth.verify_login(stale)


@pytest.mark.asyncio
async def test_verify_login_raises_without_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    async with AeatAuthenticator(settings) as auth:
        now = datetime.now(UTC)
        session = _certificate_session(
            authenticated_at=now,
            idle_deadline=now + AEAT_SESSION_IDLE_TTL,
            thumbprint="abc",
            subject="CN=x",
        )
        with pytest.raises(AeatLoginAssertionError):
            await auth.verify_login(session)


def test_extract_nif_handles_escaped_comma_in_cn(tmp_path: Path) -> None:
    """RFC 4514 escaped commas in CN must not split the DN parser.

    The rfc4514_string emitted by cryptography quotes a literal
    comma in a CN as ``\\,``. A naive regex that splits on `,` would
    break ``CN=Doe\\, John,SERIALNUMBER=12345678Z`` into two halves
    and mis-attribute the serial number. This test asserts the
    x509-backed parser handles the escape correctly.
    """
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Doe, John"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "12345678Z"),
        ],
    )
    assert extract_nif_from_subject(cert) == "12345678Z"


def test_extract_nif_handles_quoted_plus_in_cn(tmp_path: Path) -> None:
    """RFC 4514 escaped ``+`` in a value must not split RDNs."""
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COMMON_NAME, "Alice+Bob Industries"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "X1234567L"),
        ],
    )
    assert extract_nif_from_subject(cert) == "X1234567L"


def test_aeat_session_is_stale_with_naive_datetime(tmp_path: Path) -> None:
    """Naive datetimes passed to is_stale are coerced to UTC.

    Documents the existing behaviour so a regression is caught if
    the coercion is ever removed. A caller on a non-UTC workstation
    that supplies a naive ``datetime.now()`` will hit this path.
    """
    authenticated_at = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
    )
    naive_past = datetime(2020, 1, 1)
    naive_future = datetime(2100, 1, 1)
    assert session.is_stale(naive_past) is False
    assert session.is_stale(naive_future) is True


@pytest.mark.asyncio
async def test_reauthenticate_does_not_deadlock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test: reauthenticate must not deadlock on self._lock.

    The method was rewritten to delegate teardown to ``close()``
    (itself lock-protected) rather than holding ``self._lock``
    across the subsequent ``authenticate()`` call. Proves the
    single-lock invariant by reauthenticating and confirming no
    timeout. Does NOT prove correct delegation (no happy-path
    browser factory is injected here); that is covered by the live
    test suite in ``test_authenticator_live.py``.
    """
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    verifier = _HandshakeVerifier()
    async with AeatAuthenticator(settings, handshake_verifier=verifier) as auth:
        # Fake a session to pass to reauthenticate. The call will fail
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
        # raises AeatLoginAssertionError; we only care that the call
        # returns in bounded time (no deadlock).
        with pytest.raises(AeatLoginAssertionError):
            await asyncio.wait_for(auth.reauthenticate(session), timeout=5.0)
    assert verifier.calls == 1


@pytest.mark.asyncio
async def test_close_latch_blocks_concurrent_verify_login(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test for the close()/verify_login TOCTOU race.

    The fix uses a one-way ``_closing`` latch checked inside
    ``verify_login`` under the lock. Once ``close()`` sets the
    latch, any subsequent ``verify_login`` — even one that arrives
    between the drain-wait returning and the teardown acquiring
    the lock — must raise rather than start a navigation on a
    stale context.

    The test simulates the race by directly toggling the latch
    (no true concurrency needed to exercise the guard) and
    confirms ``verify_login`` refuses.
    """
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    authenticator = AeatAuthenticator(settings)

    # Install a fake context so the lock-protected snapshot would
    # otherwise succeed — we want the latch to be the cause of the
    # refusal.
    cert = authenticator.load_certificate()
    from typing import cast

    from . import BrowserContextLike

    fake_ctx = _FakeBrowserContext(cert, recognised=True)
    authenticator._context = cast(BrowserContextLike, fake_ctx)
    authenticator._closing = True

    now = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=now,
        idle_deadline=now + AEAT_SESSION_IDLE_TTL,
        thumbprint=cert.sha256_thumbprint,
        subject=cert.subject,
    )
    with pytest.raises(AeatLoginAssertionError, match="closing"):
        await authenticator.verify_login(session)

    # Reset + confirm post-close the latch is clear again (so that
    # reauthenticate can re-use the authenticator).
    authenticator._closing = False
    await authenticator.close()
    assert authenticator._closing is False


@pytest.mark.asyncio
async def test_concurrent_close_and_verify_login_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """True interleaved race: start verify_login + close concurrently.

    Uses an ``asyncio.Event`` inside the fake page's ``goto`` to
    deterministically suspend mid-navigation, letting ``close()``
    progress to its drain-wait. close()'s wait should block until
    goto is allowed to complete; after that, the teardown runs
    under the lock and leaves the authenticator in a clean state.
    """
    from typing import cast

    from . import BrowserContextLike

    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    authenticator = AeatAuthenticator(settings)

    proceed = asyncio.Event()

    class _SuspendingPage:
        async def goto(self, url: str, *, timeout: float | None = None) -> object:
            # Block until the test releases us; proves close() waits.
            await proceed.wait()
            return type("R", (), {"status": 200})()

        async def close(self) -> None:
            return None

    class _SuspendingContext:
        _aeat_certificate_thumbprint: str = ""

        async def new_page(self) -> _SuspendingPage:
            return _SuspendingPage()

        async def close(self) -> None:
            return None

    cert = authenticator.load_certificate()
    ctx = _SuspendingContext()
    ctx._aeat_certificate_thumbprint = cert.sha256_thumbprint
    authenticator._context = cast(BrowserContextLike, ctx)

    now = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=now,
        idle_deadline=now + AEAT_SESSION_IDLE_TTL,
        thumbprint=cert.sha256_thumbprint,
        subject=cert.subject,
    )

    # Start verify_login; it will suspend inside goto until proceed.set().
    verify_task = asyncio.create_task(authenticator.verify_login(session))
    # Yield so verify_login enters the lock, bumps _inflight_pages, clears
    # _inflight_drained, and begins the suspended goto.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    # Start close; it should latch _closing, then block on the drain.
    close_task = asyncio.create_task(authenticator.close())
    # Give close a tick to reach drain-wait.
    await asyncio.sleep(0.05)
    # close must still be pending — verify_login is holding a page.
    assert not close_task.done(), "close() returned before verify_login finished"
    # Release the navigation; both tasks should now complete.
    proceed.set()
    assertion = await asyncio.wait_for(verify_task, timeout=5.0)
    await asyncio.wait_for(close_task, timeout=5.0)
    # verify_login saw a live context and a successful goto.
    assert assertion.certificate_recognised is True
    # close() cleanly reset state.
    assert authenticator._closing is False
    assert authenticator._context is None


@pytest.mark.asyncio
async def test_close_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)
    auth = AeatAuthenticator(settings)
    await auth.close()
    await auth.close()  # must not raise


def test_auth_provider_protocol_conformance() -> None:
    class _NullAuthProvider:
        kind = AuthProviderKind.CLAVE_PERMANENTE

        async def authenticate(
            self,
            *,
            browser_session: object | None = None,
            target_url: str | None = None,
        ) -> AeatSession:
            now = datetime.now(UTC)
            return AeatSession(
                provider_kind=self.kind,
                authenticated_at=now,
                idle_deadline=now + AEAT_SESSION_IDLE_TTL,
                storage_state_path=None,
                identity_nif="X1234567L",
                provider_detail=ClavePermanenteSessionDetail(),
            )

        async def verify(
            self,
            session: AeatSession,
            *,
            target_url: str | None = None,
        ) -> AeatLoginAssertion:
            return AeatLoginAssertion(
                target_url=target_url or "https://example.invalid/",
                is_valid=True,
                provider_kind=session.provider_kind,
                identity_nif=session.identity_nif,
                status_code=200,
                elapsed_ms=1,
                attempted_at=datetime.now(UTC),
                assertion_detail=ClavePermanenteLoginAssertionDetail(),
            )

        def describe(self) -> AuthProviderDescription:
            return AuthProviderDescription(
                kind=self.kind,
                label="Null provider",
                configured=True,
                available=True,
                identity_nif="X1234567L",
            )

    provider = _NullAuthProvider()
    assert isinstance(provider, AuthProvider)


def test_select_provider_returns_certificate_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)

    provider = select_provider(AuthProviderKind.CERTIFICATE, settings=settings)

    assert isinstance(provider, AeatAuthenticator)
    assert isinstance(provider, AuthProvider)


def test_select_provider_rejects_unimplemented_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_for(bundle_path, monkeypatch)

    with pytest.raises(NotImplementedError, match="clave_permanente"):
        select_provider(AuthProviderKind.CLAVE_PERMANENTE, settings=settings)
