from __future__ import annotations

from datetime import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

_SECRET = "correct-horse-battery-staple"  # noqa: S105 - synthetic test fixture, not a secret


def _build_pkcs12(
    tmp_path: Path,
    *,
    not_valid_before: datetime,
    not_valid_after: datetime,
    name: str,
    subject_cn: str,
    password: str = _SECRET,
) -> Path:
    """Generate a real self-signed PKCS#12 bundle with the given validity window."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, subject_cn),
        ],
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
        .sign(key, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=name.encode("utf-8"),
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
    )
    out = tmp_path / f"{name}.p12"
    out.write_bytes(pfx_bytes)
    return out
