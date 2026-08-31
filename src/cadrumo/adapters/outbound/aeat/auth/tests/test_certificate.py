"""Real PKCS#12 boundary tests for certificate authentication."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pydantic import SecretStr

from ......core.config import AEAT_CERTIFICATE_PROTECTED_ORIGIN, Settings
from ...browser import Profile
from ...browser._factory import create_browser_session
from ..certificate import (
    CertificateBundle,
    CertificateExpiredError,
    CertificateLoadError,
    CertificatePasswordError,
    LoadedCertificate,
    load_certificate,
)
from ..providers import CertificateContextProvisioner
from ._auth_fixtures import SECRET_PASSPHRASE

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_VALID_NOT_BEFORE = datetime(2026, 5, 28, 14, 0, 0, tzinfo=UTC)
_VALID_NOT_AFTER = datetime(2099, 5, 28, 14, 0, 0, tzinfo=UTC)
_EXPIRED_NOT_BEFORE = datetime(2025, 5, 28, 14, 0, 0, tzinfo=UTC)
_EXPIRED_NOT_AFTER = datetime(2026, 5, 27, 14, 0, 0, tzinfo=UTC)


def _build_pkcs12_bundle(
    tmp_path: Path,
    *,
    password: str = SECRET_PASSPHRASE,
    not_valid_before: datetime | None = None,
    not_valid_after: datetime | None = None,
    friendly_name: bytes = b"test-cert",
) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "aeat-test-subject"),
        ],
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before or _VALID_NOT_BEFORE)
        .not_valid_after(not_valid_after or _VALID_NOT_AFTER)
        .sign(key, hashes.SHA256())
    )
    out = tmp_path / "bundle.p12"
    out.write_bytes(
        pkcs12.serialize_key_and_certificates(
            name=friendly_name,
            key=key,
            cert=cert,
            cas=None,
            encryption_algorithm=serialization.BestAvailableEncryption(password.encode()),
        ),
    )
    return out


def test_bundle_is_strict_frozen_and_secret_safe(tmp_path: Path) -> None:
    bundle = CertificateBundle(
        path=tmp_path / "x.p12",
        password=SecretStr(SECRET_PASSPHRASE),
    )

    with pytest.raises(ValueError, match=r"Extra inputs are not permitted|not_a_field"):
        CertificateBundle.model_validate(
            {
                "path": tmp_path / "x.p12",
                "password": SecretStr(SECRET_PASSPHRASE),
                "not_a_field": 1,
            },
        )
    with pytest.raises(ValueError, match=r"frozen|Instance is frozen"):
        bundle.path = tmp_path / "y.p12"
    assert SECRET_PASSPHRASE not in repr(bundle)
    assert SECRET_PASSPHRASE not in bundle.model_dump_json()


def test_load_certificate_uses_real_pkcs12_and_keeps_secrets_private(tmp_path: Path) -> None:
    p12 = _build_pkcs12_bundle(tmp_path)
    loaded = load_certificate(
        CertificateBundle(
            path=p12,
            password=SecretStr(SECRET_PASSPHRASE),
        ),
    )

    assert isinstance(loaded, LoadedCertificate)
    assert "aeat-test-subject" in loaded.subject
    assert loaded.friendly_name == "test-cert"
    assert loaded.is_expired() is False
    assert len(loaded.sha256_thumbprint) == 64
    assert loaded.not_before.tzinfo is not None
    assert loaded.not_after.tzinfo is not None
    for rendered in (
        str(loaded.model_dump()),
        loaded.model_dump_json(),
        repr(loaded),
        str(loaded),
    ):
        assert SECRET_PASSPHRASE not in rendered
    assert loaded._pkcs12_bytes
    assert loaded._password.get_secret_value() == SECRET_PASSPHRASE
    assert loaded._private_key_handle is not None


@pytest.mark.parametrize(
    ("password", "expected_error"),
    [
        ("", CertificatePasswordError),
        ("definitely-wrong", CertificatePasswordError),
    ],
)
def test_load_certificate_rejects_invalid_password(
    tmp_path: Path,
    password: str,
    expected_error: type[Exception],
) -> None:
    p12 = _build_pkcs12_bundle(tmp_path)
    with pytest.raises(expected_error):
        load_certificate(CertificateBundle(path=p12, password=SecretStr(password)))


def test_load_certificate_rejects_expired_and_malformed_bundles(tmp_path: Path) -> None:
    expired = _build_pkcs12_bundle(
        tmp_path,
        not_valid_before=_EXPIRED_NOT_BEFORE,
        not_valid_after=_EXPIRED_NOT_AFTER,
    )
    with pytest.raises(CertificateExpiredError):
        load_certificate(
            CertificateBundle(
                path=expired,
                password=SecretStr(SECRET_PASSPHRASE),
            ),
        )

    malformed = tmp_path / "malformed.p12"
    malformed.write_bytes(b"not a pkcs12 bundle")
    with pytest.raises((CertificateLoadError, CertificatePasswordError)):
        load_certificate(
            CertificateBundle(
                path=malformed,
                password=SecretStr(SECRET_PASSPHRASE),
            ),
        )


def test_context_provisioner_pins_exact_origin_and_materialises_secret(tmp_path: Path) -> None:
    p12 = _build_pkcs12_bundle(tmp_path)
    loaded = load_certificate(
        CertificateBundle(
            path=p12,
            password=SecretStr(SECRET_PASSPHRASE),
        ),
    )
    validated_bytes = loaded._pkcs12_bytes
    p12.write_bytes(b"mutated-after-validation")

    assert CertificateContextProvisioner(loaded).build_context_kwargs() == {
        "client_certificates": [
            {
                "origin": AEAT_CERTIFICATE_PROTECTED_ORIGIN,
                "pfx": validated_bytes,
                "passphrase": SECRET_PASSPHRASE,
            },
        ],
    }


@pytest.mark.asyncio
async def test_context_provisioner_constructs_real_playwright_context(tmp_path: Path) -> None:
    """A real PKCS#12 bundle crosses the production Playwright context boundary."""
    p12 = _build_pkcs12_bundle(tmp_path)
    loaded = load_certificate(
        CertificateBundle(
            path=p12,
            password=SecretStr(SECRET_PASSPHRASE),
        ),
    )
    session = await create_browser_session(
        Settings(),
        Profile(name="certificate-context"),
    )
    context = await session.create_context(provisioner=CertificateContextProvisioner(loaded))
    try:
        page = await context.new_page()
        await page.goto("data:text/html,<title>certificate-context</title>")
        assert await page.title() == "certificate-context"
    finally:
        await context.close()
        await session.close()
