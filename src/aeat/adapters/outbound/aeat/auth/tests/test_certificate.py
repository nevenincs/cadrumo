"""Unit tests for :mod:`aeat.adapters.outbound.aeat.auth.certificate`.

Every test generates a real self-signed PKCS#12 bundle at runtime via
:mod:`cryptography`. Tests assert both functional correctness and
SecretStr / PrivateAttr non-leakage.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pydantic import SecretStr

from ......core.config import CertificateBackend, Settings
from ......tests.env_scope import isolated_aeat_env
from .. import (
    CERTIFICATE_CONTEXT_MARKER,
    CertificateBundle,
    CertificateExpiredError,
    CertificateHandshakeError,
    CertificateLoadError,
    CertificatePasswordError,
    HandshakeResult,
    LoadedCertificate,
    load_certificate,
    preload_into_browser_context,
    verify_handshake,
)
from .._fixtures import SECRET_PASSPHRASE
from ..certificate import _select_backend

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_SEDE_ORIGIN = Settings.external_constants().aeat.domains.sede


def _build_pkcs12_bundle(
    tmp_path: Path,
    *,
    password: str = SECRET_PASSPHRASE,
    not_valid_before: datetime | None = None,
    not_valid_after: datetime | None = None,
    friendly_name: bytes = b"test-cert",
) -> Path:
    """Generate a real self-signed PKCS#12 bundle on disk."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "aeat-test-subject"),
        ],
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before or (now - timedelta(days=1)))
        .not_valid_after(not_valid_after or (now + timedelta(days=365)))
        .sign(key, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=friendly_name,
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
    )
    out = tmp_path / "bundle.p12"
    out.write_bytes(pfx_bytes)
    return out


# ── CertificateBundle schema ────────────────────────────────────────────────


def test_bundle_rejects_extra_fields(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"Extra inputs are not permitted|not_a_field"):
        CertificateBundle.model_validate(
            {
                "path": tmp_path / "x.p12",
                "password": SecretStr(SECRET_PASSPHRASE),
                "backend": CertificateBackend.PLAYWRIGHT_CONTEXT,
                "not_a_field": 1,
            },
        )


def test_bundle_is_frozen(tmp_path: Path) -> None:
    bundle = CertificateBundle(
        path=tmp_path / "x.p12",
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    with pytest.raises(ValueError, match=r"frozen|Instance is frozen"):
        bundle.path = tmp_path / "y.p12"


def test_bundle_password_does_not_leak_in_repr_or_dump(tmp_path: Path) -> None:
    """The passphrase is a SecretStr — repr() and model_dump_json()
    never surface the cleartext."""
    bundle = CertificateBundle(
        path=tmp_path / "x.p12",
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    assert SECRET_PASSPHRASE not in repr(bundle)
    assert SECRET_PASSPHRASE not in bundle.model_dump_json()
    assert bundle.password.get_secret_value() == SECRET_PASSPHRASE


# ── load_certificate happy path ─────────────────────────────────────────────


def test_load_certificate_happy_path(tmp_path: Path) -> None:
    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        friendly_name=None,
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    loaded = load_certificate(bundle)
    assert isinstance(loaded, LoadedCertificate)
    assert "aeat-test-subject" in loaded.subject
    assert loaded.friendly_name == "test-cert"
    assert loaded.is_expired() is False
    assert len(loaded.sha256_thumbprint) == 64  # hex SHA-256


# ── Error paths ─────────────────────────────────────────────────────────────


def test_load_certificate_empty_password(tmp_path: Path) -> None:
    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(""),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    with pytest.raises(CertificatePasswordError, match=r"empty|passphrase"):
        load_certificate(bundle)


def test_load_certificate_wrong_password(tmp_path: Path) -> None:
    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr("definitely-wrong"),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    with pytest.raises(CertificatePasswordError, match=r"password|incorrect|wrong|decrypt"):
        load_certificate(bundle)


def test_load_certificate_expired(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    p12 = _build_pkcs12_bundle(
        tmp_path,
        not_valid_before=now - timedelta(days=365),
        not_valid_after=now - timedelta(days=1),
    )
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    with pytest.raises(CertificateExpiredError, match=r"certificate|expired"):
        load_certificate(bundle)


def test_load_certificate_garbage_bytes(tmp_path: Path) -> None:
    bad = tmp_path / "bad.p12"
    bad.write_bytes(b"this is not a pkcs12 file")
    bundle = CertificateBundle(
        path=bad,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    with pytest.raises((CertificateLoadError, CertificatePasswordError), match=r"certificate|pkcs12|password|load"):
        load_certificate(bundle)


# ── SecretStr / PrivateAttr non-leakage ─────────────────────────────────────


def test_loaded_certificate_does_not_leak_secrets(tmp_path: Path) -> None:
    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    loaded = load_certificate(bundle)

    dump = loaded.model_dump()
    dump_json = loaded.model_dump_json()
    repr_str = repr(loaded)
    str_str = str(loaded)

    # Password must not appear in any serialisation form.
    for haystack in (str(dump), dump_json, repr_str, str_str):
        assert SECRET_PASSPHRASE not in haystack, f"passphrase leaked in: {haystack[:80]}..."

    # PrivateAttr keys must not appear in model_dump output.
    assert "_pkcs12_bytes" not in dump
    assert "_password" not in dump
    assert "_private_key_handle" not in dump

    # But the private material is still accessible on the instance.
    assert loaded._pkcs12_bytes
    assert loaded._password.get_secret_value() == SECRET_PASSPHRASE
    assert loaded._private_key_handle is not None


# ── Backend dispatch ────────────────────────────────────────────────────────


@pytest.mark.parametrize("backend", list(CertificateBackend))
def test_select_backend_returns_matching_class(backend: CertificateBackend) -> None:
    from .._certificate_backends._httpx_fallback import HttpxFallbackBackend
    from .._certificate_backends._playwright_context import (
        PlaywrightContextBackend,
    )

    expected = {
        CertificateBackend.PLAYWRIGHT_CONTEXT: PlaywrightContextBackend,
        CertificateBackend.HTTPX_FALLBACK: HttpxFallbackBackend,
    }[backend]
    assert isinstance(_select_backend(backend), expected)


# ── verify_handshake input validation ──────────────────────────────────────


def test_verify_handshake_rejects_empty_url(tmp_path: Path) -> None:
    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.HTTPX_FALLBACK,
    )
    loaded = load_certificate(bundle)
    with pytest.raises(CertificateHandshakeError, match=r"certificate|handshake"):
        verify_handshake(loaded, "")


def test_verify_handshake_returns_failure_on_tls_error(tmp_path: Path) -> None:
    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.HTTPX_FALLBACK,
    )
    loaded = load_certificate(bundle)
    # Closed local port: connection refused, fails the handshake in milliseconds.
    # TEST-NET addresses can route into a long connect timeout on some networks.
    result = verify_handshake(loaded, "https://127.0.0.1:1/")
    assert isinstance(result, HandshakeResult)
    assert result.success is False
    assert result.status_code == 0
    assert result.error_message is not None


# ── Playwright backend contract ─────────────────────────────────────────────


def test_playwright_preload_rejects_unmarked_context(tmp_path: Path) -> None:
    from ..certificate import CertificateError

    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    loaded = load_certificate(bundle)

    with pytest.raises(CertificateError, match=r"certificate"):
        preload_into_browser_context(loaded, SimpleNamespace())


def test_playwright_preload_accepts_marked_context(tmp_path: Path) -> None:
    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    loaded = load_certificate(bundle)

    ctx = SimpleNamespace(**{CERTIFICATE_CONTEXT_MARKER: loaded.sha256_thumbprint})
    assert getattr(ctx, CERTIFICATE_CONTEXT_MARKER) == loaded.sha256_thumbprint
    result = preload_into_browser_context(loaded, ctx)
    assert result is None


def test_playwright_client_certificates_kwarg_materialises_secret(tmp_path: Path) -> None:
    from .._certificate_backends._playwright_context import (
        build_client_certificates_kwarg,
    )

    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    loaded = load_certificate(bundle)
    kwarg = build_client_certificates_kwarg(loaded, _SEDE_ORIGIN)
    assert kwarg == [
        {
            "origin": _SEDE_ORIGIN,
            "pfxPath": str(p12),
            "passphrase": SECRET_PASSPHRASE,
        },
    ]


# ── Browserless backends ────────────────────────────────────────────────────


def test_httpx_fallback_preload_rejects_browser_path(tmp_path: Path) -> None:
    from .._certificate_backends._httpx_fallback import HttpxFallbackBackend
    from .._errors import AuthConfigurationError

    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.HTTPX_FALLBACK,
    )
    loaded = load_certificate(bundle)
    with pytest.raises(AuthConfigurationError, match="HTTPX_FALLBACK has no browser path"):
        HttpxFallbackBackend().preload(loaded, object())


# ── Settings integration ────────────────────────────────────────────────────


def test_settings_loads_cert_env_vars(tmp_path: Path) -> None:
    from pydantic_settings import SettingsConfigDict

    from ......core.config import Settings

    class IsolatedSettings(Settings):
        model_config = SettingsConfigDict(env_file=None)

    placeholder_p12 = tmp_path / "op.p12"
    placeholder_p12.write_bytes(b"placeholder")
    with isolated_aeat_env(
        AEAT_CERTIFICATE_PATH=str(placeholder_p12),
        AEAT_CERTIFICATE_PASSWORD_SECRET=SECRET_PASSPHRASE,
        AEAT_CERTIFICATE_FRIENDLY_NAME="op-cert",
        AEAT_CERTIFICATE_BACKEND="httpx_fallback",
        AEAT_CERTIFICATE_VERIFY_URL="https://example.test/",
    ):
        settings = IsolatedSettings()
    assert settings.aeat_certificate_path == placeholder_p12
    assert settings.aeat_certificate_password_secret is not None
    assert settings.aeat_certificate_password_secret.get_secret_value() == SECRET_PASSPHRASE
    assert settings.aeat_certificate_friendly_name == "op-cert"
    assert settings.aeat_certificate_backend.name == CertificateBackend.HTTPX_FALLBACK.name
    assert settings.aeat_certificate_verify_url == "https://example.test/"

    # SecretStr must not leak via repr()
    assert SECRET_PASSPHRASE not in repr(settings)


# ── UTC helper migration: coerce_utc_aware semantics ───────────────────────


def test_load_certificate_not_before_is_utc_aware(tmp_path: Path) -> None:
    """not_before on a loaded certificate is always UTC-aware.

    ``coerce_utc_aware`` is the coerce helper: naive datetimes get UTC
    attached, aware datetimes are converted to UTC.  The PKCS#12 boundary
    must always produce UTC-aware timestamps regardless of what
    ``x509_cert.not_valid_before_utc`` returns.
    """
    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    loaded = load_certificate(bundle)
    assert loaded.not_before.tzinfo is not None
    assert loaded.not_before.utcoffset() is not None


def test_load_certificate_not_after_is_utc_aware(tmp_path: Path) -> None:
    """not_after on a loaded certificate is always UTC-aware.

    Mirrors ``test_load_certificate_not_before_is_utc_aware`` for the
    expiry timestamp, confirming both PKCS#12 datetime call-sites pass
    through ``coerce_utc_aware``.
    """
    p12 = _build_pkcs12_bundle(tmp_path)
    bundle = CertificateBundle(
        path=p12,
        password=SecretStr(SECRET_PASSPHRASE),
        backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
    )
    loaded = load_certificate(bundle)
    assert loaded.not_after.tzinfo is not None
    assert loaded.not_after.utcoffset() is not None


def test_settings_rejects_removed_certificate_backends() -> None:
    import pydantic
    from pydantic_settings import SettingsConfigDict

    from ......core.config import Settings

    class IsolatedSettings(Settings):
        model_config = SettingsConfigDict(env_file=None)

    with isolated_aeat_env(AEAT_CERTIFICATE_BACKEND="MTLS_PROXY"):
        with pytest.raises(pydantic.ValidationError, match=r"aeat_certificate_backend|MTLS_PROXY|Input should be"):
            IsolatedSettings()
