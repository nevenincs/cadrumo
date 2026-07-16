"""Shared support for split adapter tests."""

from __future__ import annotations

import asyncio
import functools
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NoReturn as NoReturn
from typing import cast

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from ......application.auth import (
    AuthProvider as AuthProvider,
)
from ......application.auth_credentials import unnamed_certificate_credentials
from ......core import AuthProviderDescription as AuthProviderDescription
from ......core import AuthProviderKind as AuthProviderKind
from ......core.config import (
    AEAT_CERTIFICATE_PROTECTED_ORIGIN,
    AEAT_CERTIFICATE_PROTECTED_PATH,
    AEAT_CERTIFICATE_PROTECTED_URL,
    Settings,
)
from ......tests.secure_sql import isolated_runtime_profile
from .....persistence.storage import AEAT_BROWSER_SESSION_NAMESPACE
from .....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from .. import (
    AEAT_SESSION_IDLE_TTL,
    AeatAuthenticator,
    AeatLoginAssertion,
    AeatLoginAssertionError,
    AeatSession,
    AeatSessionExpiredError,
    AuthConfigurationError,
    BrowserContextLike,
    BrowserContextProvisioner,
    BrowserSessionLike,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
    LoadedCertificate,
    _session_store,
    extract_nif_from_subject,
    load_certificate,
)
from .. import (
    AuthValidationError as AuthValidationError,
)
from .. import (
    CertificateError as CertificateError,
)
from .. import (
    CertificateNifParseError as CertificateNifParseError,
)
from .. import (
    ClaveMovilLoginAssertionDetail as ClaveMovilLoginAssertionDetail,
)
from .. import (
    ClaveMovilSessionDetail as ClaveMovilSessionDetail,
)
from .. import _authenticator as authenticator_module
from .. import (
    select_provider as select_provider,
)
from .._fixtures import SECRET_PASSPHRASE
from ..certificate import CertificateBundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_BUCKET_ID = "auth-session"

_SENSITIVE_STORAGE_BASENAME = "12345678Z-private-storage.json"

_SENSITIVE_NAVIGATION_PAYLOAD = "12345678Z private browser payload"

_SENSITIVE_HEALTH_PAYLOAD = "C:/Users/operator/private-cert-12345678Z.p12"

_SEDE_ORIGIN = AEAT_CERTIFICATE_PROTECTED_ORIGIN


@pytest.fixture(autouse=True)
def _isolated_secure_session_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


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


class _RecordingBrowserContext:
    """In-process browser context implementing the production auth protocol."""

    def __init__(
        self,
        recognised: bool = True,
        *,
        final_url: str | None = None,
        status: int | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> None:
        self._recognised = recognised
        self._final_url = (
            final_url
            if final_url is not None
            else (AEAT_CERTIFICATE_PROTECTED_URL if recognised else f"{AEAT_CERTIFICATE_PROTECTED_ORIGIN}/")
        )
        self._status = status if status is not None else (200 if recognised else 401)
        if storage_state is None:
            self._storage_state: Mapping[str, object] = {"cookies": [], "origins": []}
        else:
            self._storage_state = storage_state
        self._pages: list[_RecordingPage] = []
        self.closed = False

    async def new_page(self) -> _RecordingPage:
        page = _RecordingPage(final_url=self._final_url, status=self._status)
        self._pages.append(page)
        return page

    async def close(self) -> None:
        self.closed = True

    async def storage_state(self) -> Mapping[str, object]:
        return self._storage_state


class _RecordingPage:
    def __init__(self, *, final_url: str, status: int) -> None:
        self._final_url = final_url
        self._status = status
        self.url = ""

    async def goto(self, url: str, *, timeout: float | None = None) -> _RecordingResponse:
        del timeout
        del url
        self.url = self._final_url
        return _RecordingResponse(self._status)

    async def close(self) -> None:
        return None


class _RecordingResponse:
    def __init__(self, status: int) -> None:
        self.status = status
        self.ok = 200 <= status <= 299


class _RaisingPage:
    url = AEAT_CERTIFICATE_PROTECTED_URL

    async def goto(self, url: str, *, timeout: float | None = None) -> _RecordingResponse:
        raise RuntimeError(f"navigation failed for {_SENSITIVE_NAVIGATION_PAYLOAD}")

    async def close(self) -> None:
        return None


class _RaisingBrowserContext:
    async def new_page(self) -> _RaisingPage:
        return _RaisingPage()

    async def close(self) -> None:
        return None

    async def storage_state(self) -> dict[str, object]:
        return {"cookies": [], "origins": []}


class _RecordingBrowserSession:
    # ``BrowserSessionProfileLike`` conformance: ``None`` exercises the
    # settings-derived storage-state fallback in
    # ``AeatAuthenticator._resolve_storage_state_path`` rather than
    # raising ``AttributeError`` on plain attribute access.
    profile: None = None

    def __init__(
        self,
        cert_ok: bool = True,
        *,
        final_url: str | None = None,
        status: int | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> None:
        self._cert_ok = cert_ok
        self._final_url = final_url
        self._status = status
        if storage_state is None:
            self._storage_state: Mapping[str, object] = {"cookies": [], "origins": []}
        else:
            self._storage_state = storage_state
        self.created: list[_RecordingBrowserContext] = []
        self.storage_state_paths: list[Path | None] = []
        self.closed = False

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _RecordingBrowserContext:
        assert provisioner is not None
        assert isinstance(provisioner, BrowserContextProvisioner)
        context_kwargs = provisioner.build_context_kwargs()
        client_certificates = context_kwargs.get("client_certificates")
        assert client_certificates is not None
        assert len(client_certificates) == 1
        client_certificate = client_certificates[0]
        assert client_certificate["origin"] == AEAT_CERTIFICATE_PROTECTED_ORIGIN
        assert Path(client_certificate["pfxPath"]).name == "bundle.p12"
        assert client_certificate["passphrase"] == SECRET_PASSPHRASE
        self.storage_state_paths.append(storage_state_path)
        if storage_state is not None:
            self._storage_state = storage_state
        ctx = _RecordingBrowserContext(
            recognised=self._cert_ok,
            final_url=self._final_url,
            status=self._status,
            storage_state=self._storage_state,
        )
        self.created.append(ctx)
        return ctx

    async def close(self) -> None:
        self.closed = True


def _factory_returning(session: BrowserSessionLike):
    """Return a browser-session factory bound to one protocol implementation."""

    async def factory(settings: Settings) -> BrowserSessionLike:
        del settings
        return session

    return factory


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

    seed_auth = AeatAuthenticator(settings, credentials=unnamed_certificate_credentials(settings))
    cert = seed_auth.load_certificate()
    context = _RecordingBrowserContext(
        storage_state={
            "cookies": [{"name": "AEATSESSID", "value": "resume-ok"}],
            "origins": [{"origin": _SEDE_ORIGIN, "localStorage": []}],
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
    auth = AeatAuthenticator(settings, credentials=unnamed_certificate_credentials(settings))
    cert = auth.load_certificate()
    context = _RecordingBrowserContext(
        storage_state={
            "cookies": [{"name": "AEATSESSID", "value": "ok"}],
            "origins": [{"origin": _SEDE_ORIGIN, "localStorage": []}],
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
async def test_resume_from_storage_state_reuses_persisted_session_with_live_protected_probe(
    tmp_path: Path,
    _settings_factory,
) -> None:
    settings, storage_state_path, cert = await _seed_persisted_session(tmp_path, _settings_factory)

    browser_session = _RecordingBrowserSession(cert_ok=True)
    auth = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        browser_session_factory=_factory_returning(browser_session),
    )

    resumed = await auth.resume_from_storage_state(storage_state_path)

    assert resumed.certificate_thumbprint == cert.sha256_thumbprint
    assert resumed.storage_state_path == storage_state_path
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
    storage_state: Mapping[str, object] | None = None,
    metadata: Mapping[str, object] | None = None,
) -> None:
    persisted = _load_test_session(path)
    _session_store.save(
        path,
        storage_state=storage_state if storage_state is not None else persisted.storage_state,
        metadata=metadata if metadata is not None else persisted.metadata,
    )


def _store_raw_session_payload(path: Path, payload: bytes) -> None:
    secure_object_repository_for_active_bucket().save(
        namespace=AEAT_BROWSER_SESSION_NAMESPACE.namespace,
        object_key=_session_store.logical_object_key(path),
        classification=AEAT_BROWSER_SESSION_NAMESPACE.sensitivity,
        schema_version=AEAT_BROWSER_SESSION_NAMESPACE.schema_version,
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

    browser_session = _RecordingBrowserSession(cert_ok=True)
    auth = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        browser_session_factory=_factory_returning(browser_session),
    )

    with pytest.raises(AeatLoginAssertionError, match=r"storage|session|cert|login|probe"):
        await auth.resume_from_storage_state(storage_state_path)

    assert not _session_store.exists(storage_state_path), case_id
    assert not storage_state_path.exists(), case_id
    assert not storage_state_path.with_suffix(".meta.json").exists(), case_id


@pytest.mark.asyncio
async def test_resume_from_storage_state_invalidates_failed_live_probe(
    tmp_path: Path,
    _settings_factory,
) -> None:
    settings, storage_state_path, _cert = await _seed_persisted_session(tmp_path, _settings_factory)

    browser_session = _RecordingBrowserSession(cert_ok=False)
    auth = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        browser_session_factory=_factory_returning(browser_session),
    )

    with pytest.raises(AeatLoginAssertionError, match=r"storage|session|cert|login|probe"):
        await auth.resume_from_storage_state(storage_state_path)

    assert not _session_store.exists(storage_state_path)
    assert not storage_state_path.exists()
    assert not storage_state_path.with_suffix(".meta.json").exists()


@pytest.mark.asyncio
async def test_run_login_probe_redacts_navigation_exception_text(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    _settings_factory,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    auth = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    )
    cert = auth.load_certificate()
    now = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=now,
        idle_deadline=now + AEAT_SESSION_IDLE_TTL,
        thumbprint=cert.sha256_thumbprint,
        subject=cert.subject,
        identity_nif=extract_nif_from_subject(cert),
    )

    caplog.set_level(logging.DEBUG, logger=authenticator_module.__name__)
    assertion = await auth._run_login_probe(
        cast(BrowserContextLike, _RaisingBrowserContext()),
        session,
    )

    assert assertion.is_valid is False
    assert assertion.error_message == "RuntimeError"
    assert _SENSITIVE_NAVIGATION_PAYLOAD not in assertion.model_dump_json()

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert _SENSITIVE_NAVIGATION_PAYLOAD not in log_text
    assert "target=<aeat-login-probe>" in log_text
    assert "failure=RuntimeError" in log_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("final_url", "status", "expected_valid"),
    [
        (AEAT_CERTIFICATE_PROTECTED_URL, 200, True),
        (AEAT_CERTIFICATE_PROTECTED_URL, 500, False),
        (f"{AEAT_CERTIFICATE_PROTECTED_ORIGIN}/", 200, False),
        (
            f"{Settings.external_constants().aeat.domains.www1}{AEAT_CERTIFICATE_PROTECTED_PATH}",
            200,
            False,
        ),
    ],
    ids=["canonical-success", "unsuccessful-response", "wrong-path", "wrong-host"],
)
async def test_protected_probe_requires_success_and_exact_final_resource(
    tmp_path: Path,
    _settings_factory,
    final_url: str,
    status: int,
    expected_valid: bool,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    auth = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    )
    cert = auth.load_certificate()
    attempted_at = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=attempted_at,
        idle_deadline=attempted_at + AEAT_SESSION_IDLE_TTL,
        thumbprint=cert.sha256_thumbprint,
        subject=cert.subject,
        identity_nif=extract_nif_from_subject(cert),
    )
    context = _RecordingBrowserContext(final_url=final_url, status=status)

    assertion = await auth._run_login_probe(cast(BrowserContextLike, context), session)

    assert assertion.is_valid is expected_valid
    assert assertion.target_url == AEAT_CERTIFICATE_PROTECTED_URL
    assert assertion.final_url == final_url
    assert assertion.response_successful is (200 <= status <= 299)


@pytest.mark.asyncio
async def test_authenticate_falls_back_after_stale_persisted_session(
    tmp_path: Path,
    _settings_factory,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    from ......core.auth_session_keys import aeat_auth_session_storage_state_path

    storage_state_path = aeat_auth_session_storage_state_path(_BUCKET_ID, "storage")
    stale_storage_state: dict[str, object] = {"cookies": [], "origins": []}
    _session_store.save(
        storage_state_path,
        storage_state=stale_storage_state,
        metadata={
            "schema_version": 2,
            "certificate_thumbprint": "stale-thumbprint",
            "certificate_subject": "CN=STALE",
            "certificate_nif": "12345678Z",
            "authenticated_at": datetime.now(UTC).isoformat(),
            "idle_deadline": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "storage_state_sha256": _session_store.storage_state_sha256(stale_storage_state),
            "protected_resource_url": AEAT_CERTIFICATE_PROTECTED_URL,
        },
    )

    browser_session = _RecordingBrowserSession(cert_ok=True)
    auth = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        browser_session_factory=_factory_returning(browser_session),
    )

    session = await auth.authenticate()

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
    timeout. Does NOT prove correct delegation (no happy-path
    browser factory is injected here); that is covered by
    ``test_reauthenticate_happy_path_with_fake_browser_factory`` in
    ``test_authenticator_part2.py``.
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


@pytest.mark.asyncio
async def test_close_latch_blocks_concurrent_verify(tmp_path: Path, _settings_factory) -> None:
    """Regression test for the close()/verify TOCTOU race.

    The fix uses a one-way ``_closing`` latch checked inside
    ``verify`` under the lock. Once ``close()`` sets the
    latch, any subsequent ``verify`` — even one that arrives
    between the drain-wait returning and the teardown acquiring
    the lock — must raise rather than start a navigation on a
    stale context.

    The test simulates the race by directly toggling the latch
    (no true concurrency needed to exercise the guard) and
    confirms ``verify`` refuses.
    """
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    authenticator = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    )

    # Install a recording context so the lock-protected snapshot would
    # otherwise succeed — we want the latch to be the cause of the
    # refusal.
    cert = authenticator.load_certificate()
    from typing import cast

    from .. import BrowserContextLike

    context = _RecordingBrowserContext(recognised=True)
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
        await authenticator.verify(session)

    # Reset + confirm post-close the latch is clear again (so that
    # reauthenticate can re-use the authenticator).
    authenticator._closing = False
    await authenticator.close()
    assert authenticator._closing is False


@pytest.mark.asyncio
async def test_concurrent_close_and_verify_race(tmp_path: Path, _settings_factory) -> None:
    """True interleaved race: start verify + close concurrently.

    Uses an ``asyncio.Event`` inside the recording page's ``goto`` to
    deterministically suspend mid-navigation, letting ``close()``
    progress to its drain-wait. close()'s wait should block until
    goto is allowed to complete; after that, the teardown runs
    under the lock and leaves the authenticator in a clean state.
    """
    from typing import cast

    from .. import BrowserContextLike

    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    authenticator = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    )

    proceed = asyncio.Event()

    class _SuspendingPage:
        url = AEAT_CERTIFICATE_PROTECTED_URL

        async def goto(self, url: str, *, timeout: float | None = None) -> object:
            # Block until the test releases us; proves close() waits.
            await proceed.wait()
            return type("R", (), {"status": 200, "ok": True})()

        async def close(self) -> None:
            return None

    class _SuspendingContext:
        async def new_page(self) -> _SuspendingPage:
            return _SuspendingPage()

        async def close(self) -> None:
            return None

        async def storage_state(self) -> dict[str, object]:
            return {"cookies": [], "origins": []}

    cert = authenticator.load_certificate()
    ctx = _SuspendingContext()
    authenticator._context = cast(BrowserContextLike, ctx)

    now = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=now,
        idle_deadline=now + AEAT_SESSION_IDLE_TTL,
        thumbprint=cert.sha256_thumbprint,
        subject=cert.subject,
    )

    # Start verify; it will suspend inside goto until proceed.set().
    verify_task = asyncio.create_task(authenticator.verify(session))
    # Yield so verify enters the lock, bumps _inflight_pages, clears
    # _inflight_drained, and begins the suspended goto.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    # Start close; it should latch _closing, then block on the drain.
    close_task = asyncio.create_task(authenticator.close())
    # Give close a tick to reach drain-wait.
    await asyncio.sleep(0.05)
    # close must still be pending — verify is holding a page.
    assert not close_task.done(), "close() returned before verify finished"
    # Release the navigation; both tasks should now complete.
    proceed.set()
    assertion = await asyncio.wait_for(verify_task, timeout=5.0)
    await asyncio.wait_for(close_task, timeout=5.0)
    # verify saw a live context and a successful goto.
    assert assertion.response_successful is True
    # close() cleanly reset state.
    assert authenticator._closing is False
    assert authenticator._context is None


@pytest.mark.asyncio
async def test_close_is_idempotent(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    auth = AeatAuthenticator(settings, credentials=unnamed_certificate_credentials(settings))
    await auth.close()
    await auth.close()  # must not raise
