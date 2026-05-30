"""Unit tests for :mod:`aeat.adapters.outbound.aeat.auth._authenticator`.

The authenticator is exercised with a real ``LoadedCertificate`` generated at
runtime via :mod:`cryptography` and a browser-session class that honours the
``_aeat_certificate_thumbprint`` marker contract.
"""

from __future__ import annotations

import asyncio
import functools
import json
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

from .....application.auth import AuthProvider, AuthProviderDescription, AuthProviderKind
from .....core.classification import SensitivityClass
from .....tests.secure_sql import isolated_runtime_profile
from ....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from . import (
    AEAT_SESSION_IDLE_TTL,
    CERTIFICATE_CONTEXT_MARKER,
    AeatAuthenticator,
    AeatLoginAssertion,
    AeatLoginAssertionError,
    AeatSession,
    AeatSessionExpiredError,
    BrowserContextLike,
    BrowserSessionLike,
    CertificateBackend,
    CertificateLoginAssertionDetail,
    CertificateNifParseError,
    CertificateSessionDetail,
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
    HandshakeResult,
    LoadedCertificate,
    _session_store,
    extract_nif_from_subject,
    load_certificate,
    select_provider,
)
from . import _authenticator as authenticator_module
from .certificate import CertificateBundle

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]

if TYPE_CHECKING:
    from .....core.config import Settings

SECRET_PASSPHRASE = "correct-horse-battery-staple"
_BUCKET_ID = "auth-session"


@pytest.fixture(autouse=True)
def _isolated_secure_session_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


def _serialise_pkcs12(
    *,
    subject_attrs: list[x509.NameAttribute] | None,
    not_valid_after: datetime | None,
) -> bytes:
    """Generate a real self-signed PKCS#12 bundle and return its bytes."""
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
    subject_attrs: list[x509.NameAttribute] | None = None,
    not_valid_after: datetime | None = None,
) -> Path:
    """Generate a real self-signed PKCS#12 bundle on disk.

    Default-argument calls are served from the cached bytes built by
    :func:`_default_pkcs12_bytes`; custom subjects or expiries always
    regenerate.
    """
    out = tmp_path / "bundle.p12"
    if subject_attrs is None and not_valid_after is None:
        out.write_bytes(_default_pkcs12_bytes())
        return out
    out.write_bytes(_serialise_pkcs12(subject_attrs=subject_attrs, not_valid_after=not_valid_after))
    return out


def _load_cert(
    tmp_path: Path,
    *,
    subject_attrs: list[x509.NameAttribute] | None = None,
    not_valid_after: datetime | None = None,
) -> LoadedCertificate:
    """Build a bundle + load it under a deterministic env var name."""
    from pydantic import SecretStr

    bundle_path = _build_bundle(
        tmp_path,
        subject_attrs=subject_attrs,
        not_valid_after=not_valid_after,
    )
    bundle = CertificateBundle(
        path=bundle_path,
        password=SecretStr(SECRET_PASSPHRASE),
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
    with pytest.raises(CertificateNifParseError, match=r"NIF|subject|certificate"):
        extract_nif_from_subject(cert)


def test_extract_nif_rejects_unparseable(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NO-NIF-HERE"),
        ],
    )
    with pytest.raises(CertificateNifParseError, match=r"NIF|subject|certificate"):
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


# ── AeatAuthenticator — concrete browser session factory ────────────────────


class _RecordingBrowserContext:
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
        self._pages: list[_RecordingPage] = []
        self.closed = False

    async def new_page(self) -> _RecordingPage:
        page = _RecordingPage(recognised=self._recognised)
        self._pages.append(page)
        return page

    async def close(self) -> None:
        self.closed = True

    async def storage_state(self) -> dict[str, object]:
        return self._storage_state


class _RecordingPage:
    def __init__(self, recognised: bool) -> None:
        self._recognised = recognised

    async def goto(self, url: str, *, timeout: float | None = None) -> _RecordingResponse:
        return _RecordingResponse(200 if self._recognised else 401)

    async def close(self) -> None:
        return None


class _RecordingResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class _RecordingBrowserSession:
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
        self.created: list[_RecordingBrowserContext] = []
        self.storage_state_paths: list[Path | None] = []

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: dict[str, object] | None = None,
    ) -> _RecordingBrowserContext:
        assert provisioner is not None
        cert = self._resolve_cert(provisioner)
        self.storage_state_paths.append(storage_state_path)
        if storage_state is not None:
            self._storage_state = storage_state
        ctx = _RecordingBrowserContext(
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


def _successful_handshake() -> HandshakeResult:
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
        self.result = result or _successful_handshake()

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
            handshake=_successful_handshake(),
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


@pytest.fixture
def _settings_factory():
    """Yield a callable that pins Settings via the ContextVar override.

    Replaces the historical ``monkeypatch.setenv`` shim per the project
    no-monkeypatch mandate (CLAUDE.md). The ContextVar is set directly
    rather than via ``override_settings``-as-contextmanager because
    asyncio tasks copy the context; a token-based ``reset`` from the
    fixture teardown raises ``ValueError`` if the test body that called
    ``set`` ran in a child context. Capturing the prior value and
    restoring it with a plain ``set`` is async-context-safe.
    """
    from .....core.config import Settings, _settings_override, load_settings

    saved_prior = _settings_override.get()
    applied = False

    def factory(
        path: Path,
        *,
        verify_url: str = "https://127.0.0.1:1/",
        **extra_overrides: object,
    ) -> Settings:
        nonlocal applied
        overrides: dict[str, object] = {
            "aeat_certificate_path": path,
            "aeat_certificate_password_secret": SECRET_PASSPHRASE,
            "aeat_certificate_backend": CertificateBackend.HTTPX_FALLBACK,
            "aeat_certificate_verify_url": verify_url,
            "aeat_token_dir": path.parent / ".tokens",
        }
        overrides.update(extra_overrides)
        current = load_settings()
        merged = current.model_dump()
        merged.update(overrides)
        new_settings = Settings.model_validate(merged)
        explicit_fields = current.model_fields_set | set(overrides.keys())
        object.__setattr__(new_settings, "__pydantic_fields_set__", explicit_fields)
        _settings_override.set(new_settings)
        applied = True
        return new_settings

    try:
        yield factory
    finally:
        if applied:
            _settings_override.set(saved_prior)


async def _seed_persisted_session(
    tmp_path: Path,
    settings_factory,
    *,
    storage_state_path: Path | None = None,
) -> tuple[Settings, Path, LoadedCertificate]:
    """Create a valid persisted storage-state pair for resume-path tests."""
    bundle_path = _build_bundle(tmp_path)
    settings = settings_factory(bundle_path)
    persisted_path = storage_state_path or (tmp_path / "persisted-storage.json")

    seed_auth = AeatAuthenticator(settings)
    cert = seed_auth.load_certificate()
    context = _RecordingBrowserContext(
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
    _settings_factory,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    storage_state_path = tmp_path / "captured-storage.json"
    auth = AeatAuthenticator(settings)
    cert = auth.load_certificate()
    context = _RecordingBrowserContext(
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
    assert not storage_state_path.exists()
    assert not storage_state_path.with_suffix(".meta.json").exists()
    persisted = _session_store.load(storage_state_path)
    assert persisted is not None
    cookies = persisted.storage_state["cookies"]
    assert isinstance(cookies, list)
    assert isinstance(cookies[0], Mapping)
    # Playwright storage_state cookies are documented string-keyed dicts;
    # the persisted payload exposes them only as ``object``.
    first_cookie = cast("Mapping[str, object]", cookies[0])
    assert first_cookie["name"] == "AEATSESSID"
    metadata = persisted.metadata
    assert metadata["certificate_thumbprint"] == cert.sha256_thumbprint
    assert metadata["storage_state_sha256"] == persisted.storage_state_sha256


@pytest.mark.asyncio
async def test_resume_from_storage_state_reuses_persisted_session_without_handshake(
    tmp_path: Path,
    _settings_factory,
) -> None:
    settings, storage_state_path, cert = await _seed_persisted_session(tmp_path, _settings_factory)

    verifier = _HandshakeVerifier()
    browser_session = _RecordingBrowserSession(cert_ok=True)
    auth = AeatAuthenticator(settings, handshake_verifier=verifier)

    resumed = await auth.resume_from_storage_state(
        storage_state_path,
        browser_session=cast(BrowserSessionLike, browser_session),
    )

    assert resumed.certificate_thumbprint == cert.sha256_thumbprint
    assert resumed.storage_state_path == storage_state_path
    assert verifier.calls == 0
    assert browser_session.storage_state_paths == [None]


def _invalidate_by_missing_storage(path: Path, _cert: LoadedCertificate) -> None:
    _session_store.delete(path)


def _invalidate_by_invalid_storage_json(path: Path, _cert: LoadedCertificate) -> None:
    _store_raw_session_payload(path, b"{not-json")


def _invalidate_by_storage_root_list(path: Path, _cert: LoadedCertificate) -> None:
    persisted = _load_test_session(path)
    payload = {
        "schema_version": 1,
        "storage_state": [],
        "metadata": persisted.metadata,
        "written_at": datetime.now(UTC).isoformat(),
    }
    _store_raw_session_payload(path, json.dumps(payload).encode("utf-8"))


def _invalidate_by_missing_cookies(path: Path, _cert: LoadedCertificate) -> None:
    _store_test_session(path, storage_state={"origins": []})


def _invalidate_by_missing_origins(path: Path, _cert: LoadedCertificate) -> None:
    _store_test_session(path, storage_state={"cookies": []})


def _invalidate_by_missing_metadata(path: Path, _cert: LoadedCertificate) -> None:
    _store_test_session(path, metadata={})


def _invalidate_by_malformed_metadata(path: Path, _cert: LoadedCertificate) -> None:
    persisted = _load_test_session(path)
    payload = {
        "schema_version": 1,
        "storage_state": persisted.storage_state,
        "metadata": [],
        "written_at": datetime.now(UTC).isoformat(),
    }
    _store_raw_session_payload(path, json.dumps(payload).encode("utf-8"))


def _invalidate_by_schema_mismatch(path: Path, _cert: LoadedCertificate) -> None:
    metadata = dict(_load_test_session(path).metadata)
    metadata["schema_version"] = 999
    _store_test_session(path, metadata=metadata)


def _invalidate_by_hash_mismatch(path: Path, _cert: LoadedCertificate) -> None:
    metadata = dict(_load_test_session(path).metadata)
    metadata["storage_state_sha256"] = "0" * 64
    _store_test_session(path, metadata=metadata)


def _invalidate_by_expired_idle_deadline(path: Path, _cert: LoadedCertificate) -> None:
    metadata = dict(_load_test_session(path).metadata)
    metadata["idle_deadline"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    _store_test_session(path, metadata=metadata)


def _invalidate_by_thumbprint_mismatch(path: Path, _cert: LoadedCertificate) -> None:
    metadata = dict(_load_test_session(path).metadata)
    metadata["certificate_thumbprint"] = "f" * 64
    _store_test_session(path, metadata=metadata)


def _invalidate_by_subject_mismatch(path: Path, _cert: LoadedCertificate) -> None:
    metadata = dict(_load_test_session(path).metadata)
    metadata["certificate_subject"] = "CN=DIFFERENT"
    _store_test_session(path, metadata=metadata)


def _load_test_session(path: Path) -> _session_store.PersistedBrowserSession:
    persisted = _session_store.load(path)
    assert persisted is not None
    return persisted


def _store_test_session(
    path: Path,
    *,
    storage_state: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    persisted = _load_test_session(path)
    _session_store.save(
        path,
        storage_state=storage_state if storage_state is not None else persisted.storage_state,
        metadata=metadata if metadata is not None else persisted.metadata,
    )


def _store_raw_session_payload(path: Path, payload: bytes) -> None:
    secure_object_repository_for_active_bucket().save(
        namespace=_session_store._SESSION_NAMESPACE,
        object_key=path.as_posix(),
        classification=SensitivityClass.SESSION,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=payload,
    )


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
    _settings_factory,
    mutator,
    case_id: str,
) -> None:
    settings, storage_state_path, cert = await _seed_persisted_session(tmp_path, _settings_factory)
    mutator(storage_state_path, cert)

    auth = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())
    browser_session = _RecordingBrowserSession(cert_ok=True)

    with pytest.raises(AeatLoginAssertionError, match=r"storage|session|cert|login|probe"):
        await auth.resume_from_storage_state(
            storage_state_path,
            browser_session=cast(BrowserSessionLike, browser_session),
        )

    assert not _session_store.exists(storage_state_path), case_id
    assert not storage_state_path.exists(), case_id
    assert not storage_state_path.with_suffix(".meta.json").exists(), case_id


@pytest.mark.asyncio
async def test_resume_from_storage_state_invalidates_failed_live_probe(
    tmp_path: Path,
    _settings_factory,
) -> None:
    settings, storage_state_path, _cert = await _seed_persisted_session(tmp_path, _settings_factory)

    auth = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())
    browser_session = _RecordingBrowserSession(cert_ok=False)

    with pytest.raises(AeatLoginAssertionError, match=r"storage|session|cert|login|probe"):
        await auth.resume_from_storage_state(
            storage_state_path,
            browser_session=cast(BrowserSessionLike, browser_session),
        )

    assert not _session_store.exists(storage_state_path)
    assert not storage_state_path.exists()
    assert not storage_state_path.with_suffix(".meta.json").exists()


@pytest.mark.asyncio
async def test_authenticate_falls_back_after_stale_persisted_session(
    tmp_path: Path,
    _settings_factory,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    storage_state_path = settings.aeat_token_dir / f"{_BUCKET_ID}-storage.json"
    stale_storage_state: dict[str, object] = {"cookies": [], "origins": []}
    _session_store.save(
        storage_state_path,
        storage_state=stale_storage_state,
        metadata={
            "schema_version": 1,
            "certificate_thumbprint": "stale-thumbprint",
            "certificate_subject": "CN=STALE",
            "certificate_nif": "12345678Z",
            "authenticated_at": datetime.now(UTC).isoformat(),
            "idle_deadline": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "storage_state_sha256": _session_store.storage_state_sha256(stale_storage_state),
            "handshake": _successful_handshake().model_dump(mode="json"),
        },
    )

    verifier = _HandshakeVerifier()
    browser_session = _RecordingBrowserSession(cert_ok=True)
    auth = AeatAuthenticator(settings, handshake_verifier=verifier)

    session = await auth.authenticate(browser_session=cast(BrowserSessionLike, browser_session))

    assert verifier.calls == 1
    assert session.storage_state_path == storage_state_path
    assert browser_session.storage_state_paths == [None]
    assert not storage_state_path.exists()
    assert not storage_state_path.with_suffix(".meta.json").exists()
    persisted = _session_store.load(storage_state_path)
    assert persisted is not None
    assert persisted.storage_state["cookies"] == []
    metadata = persisted.metadata
    assert metadata["certificate_thumbprint"] == auth.load_certificate().sha256_thumbprint


@pytest.mark.asyncio
async def test_authenticator_synchronous_surface(tmp_path: Path, _settings_factory) -> None:
    """Synchronous helpers work under the async context manager.

    ``authenticate()`` is not exercised here because
    ``verify_handshake`` reaches the network and cannot succeed
    against the local closed-port verify URL; the full path is covered by the
    live test suite. This unit test asserts the helpers that do
    not require network access are usable through the same
    authenticator instance.
    """
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    async with AeatAuthenticator(settings) as auth:
        cert = auth.load_certificate()
        nif = auth.extract_nif_from_subject(cert)
        assert nif == "12345678Z"


def test_describe_warns_when_password_missing(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path, aeat_certificate_password_secret=None)
    description = AeatAuthenticator(settings).describe()

    assert description.configured is True
    assert description.available is False
    assert description.health_summary == "AEAT_CERTIFICATE_PASSWORD_SECRET not set"


def test_describe_preserves_expired_certificate_severity(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(
        tmp_path,
        not_valid_after=datetime.now(UTC) - timedelta(hours=12),
    )
    settings = _settings_factory(bundle_path)
    description = AeatAuthenticator(settings).describe()

    assert description.available is True
    assert description.health_severity == "EXPIRED"
    assert description.days_until_expiry is not None
    assert description.days_until_expiry <= 0


def test_describe_forwards_bundle_backend_and_friendly_name(
    tmp_path: Path,
    _settings_factory,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    from pydantic import SecretStr

    settings = _settings_factory(bundle_path, aeat_certificate_friendly_name="operator cert")

    captured: dict[str, object] = {}
    real_certificate_health = authenticator_module.certificate_health

    def _capture_certificate_health(
        path: Path,
        *,
        password: SecretStr,
        warn_days: int,
        critical_days: int,
        backend: CertificateBackend = CertificateBackend.PLAYWRIGHT_CONTEXT,
        friendly_name: str | None = None,
        now: datetime | None = None,
    ):
        captured["path"] = path
        captured["password"] = password
        captured["warn_days"] = warn_days
        captured["critical_days"] = critical_days
        captured["backend"] = backend
        captured["friendly_name"] = friendly_name
        return real_certificate_health(
            path,
            password=password,
            warn_days=warn_days,
            critical_days=critical_days,
            backend=backend,
            friendly_name=friendly_name,
            now=now,
        )

    description = AeatAuthenticator(
        settings,
        certificate_health_check=_capture_certificate_health,
    ).describe()

    assert description.available is True
    assert captured["path"] == bundle_path
    captured_password = captured["password"]
    assert isinstance(captured_password, SecretStr)
    assert captured_password.get_secret_value() == SECRET_PASSPHRASE
    assert captured["backend"] == CertificateBackend.HTTPX_FALLBACK
    assert captured["friendly_name"] == "operator cert"


def test_describe_does_not_touch_os_environ(
    tmp_path: Path,
    _settings_factory,
) -> None:
    """``AeatAuthenticator.describe()`` carries the passphrase as a
    SecretStr directly to ``certificate_health`` via the
    :class:`CertificateBundle.password` field. It never writes the
    secret into ``os.environ``, so a pre-call snapshot of the
    relevant env vars must equal the post-call snapshot exactly.

    The Settings passphrase is injected via ContextVar-backed
    ``override_settings`` rather than env, so the os.environ delta
    is the only thing under test.
    """

    import os as _os

    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    before = dict(_os.environ)

    description = AeatAuthenticator(settings).describe()
    assert description.available is True

    after = dict(_os.environ)
    assert before == after, "describe() must not mutate os.environ"


@pytest.mark.asyncio
async def test_verify_login_raises_on_stale_session(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    async with AeatAuthenticator(settings) as auth:
        now = datetime.now(UTC)
        stale = _certificate_session(
            authenticated_at=now - timedelta(hours=1),
            idle_deadline=now - timedelta(minutes=30),
            thumbprint="abc",
            subject="CN=x",
        )
        with pytest.raises(AeatSessionExpiredError, match=r"aeat|session|expired"):
            await auth.verify_login(stale)


@pytest.mark.asyncio
async def test_verify_login_raises_without_context(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    async with AeatAuthenticator(settings) as auth:
        now = datetime.now(UTC)
        session = _certificate_session(
            authenticated_at=now,
            idle_deadline=now + AEAT_SESSION_IDLE_TTL,
            thumbprint="abc",
            subject="CN=x",
        )
        with pytest.raises(AeatLoginAssertionError, match=r"browser context|authenticate"):
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
async def test_reauthenticate_does_not_deadlock(tmp_path: Path, _settings_factory) -> None:
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
    settings = _settings_factory(bundle_path)
    verifier = _HandshakeVerifier()
    async with AeatAuthenticator(settings, handshake_verifier=verifier) as auth:
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
        # raises AeatLoginAssertionError; we only care that the call
        # returns in bounded time (no deadlock).
        with pytest.raises(AeatLoginAssertionError, match=r"login|browser|session|factory|reauthenticate"):
            await asyncio.wait_for(auth.reauthenticate(session), timeout=5.0)
    assert verifier.calls == 1


@pytest.mark.asyncio
async def test_close_latch_blocks_concurrent_verify_login(tmp_path: Path, _settings_factory) -> None:
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
    settings = _settings_factory(bundle_path)
    authenticator = AeatAuthenticator(settings)

    # Install a recording context so the lock-protected snapshot would
    # otherwise succeed — we want the latch to be the cause of the
    # refusal.
    cert = authenticator.load_certificate()
    from typing import cast

    from . import BrowserContextLike

    context = _RecordingBrowserContext(cert, recognised=True)
    authenticator._context = cast(BrowserContextLike, context)
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
async def test_concurrent_close_and_verify_login_race(tmp_path: Path, _settings_factory) -> None:
    """True interleaved race: start verify_login + close concurrently.

    Uses an ``asyncio.Event`` inside the recording page's ``goto`` to
    deterministically suspend mid-navigation, letting ``close()``
    progress to its drain-wait. close()'s wait should block until
    goto is allowed to complete; after that, the teardown runs
    under the lock and leaves the authenticator in a clean state.
    """
    from typing import cast

    from . import BrowserContextLike

    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
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
async def test_close_is_idempotent(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    auth = AeatAuthenticator(settings)
    await auth.close()
    await auth.close()  # must not raise


def test_auth_provider_protocol_conformance() -> None:
    class _NullAuthProvider:
        kind = AuthProviderKind.CLAVE_MOVIL

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
                provider_detail=ClaveMovilSessionDetail(dni_nie="X1234567L"),
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
                assertion_detail=ClaveMovilLoginAssertionDetail(session_cookie_present=True),
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


def test_select_provider_returns_certificate_provider(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)

    provider = select_provider(AuthProviderKind.CERTIFICATE, settings=settings)

    assert isinstance(provider, AeatAuthenticator)
    assert isinstance(provider, AuthProvider)
