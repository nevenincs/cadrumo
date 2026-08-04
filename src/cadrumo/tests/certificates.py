"""Real PKCS#12 bundles for tests that must exercise a certificate decode.

Certificate behaviour is not mockable here without testing the mock: the
health probe, the subject-identifier read, and the login path all open a
real bundle through :mod:`cryptography`, so a stand-in would prove
nothing about any of them. This builds genuine self-signed bundles at
runtime instead, cheaply enough to do per test.

Lives in the shared test-support package rather than beside one suite
because certificate setup is reached from three layers at once — the
auth application verbs, the certificate adapter, and the config
entrypoint's manager page — and a helper owned by any one of them makes
the other two reach into a sibling's internals.

A subject carrying ``"NAME - NNNNNNNNL"`` is what
:func:`~adapters.outbound.aeat.auth.certificate.extract_nif_from_subject`
reads as a *persona física* identifier, so a test needing a certificate
that names a taxpayer passes ``subject_cn=f"TEST HOLDER - {nif}"``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

CERTIFICATE_BUNDLE_PASSPHRASE = "correct-horse-battery-staple"  # noqa: S105 - synthetic test fixture, not a secret
"""Default passphrase the generated bundles are encrypted under."""


def build_pkcs12_bundle(
    tmp_path: Path,
    *,
    not_valid_before: datetime,
    not_valid_after: datetime,
    name: str,
    subject_cn: str,
    password: str = CERTIFICATE_BUNDLE_PASSPHRASE,
) -> Path:
    """Generate a real self-signed PKCS#12 bundle with the given validity window.

    Args:
        tmp_path: Directory to write the bundle into.
        not_valid_before: Start of the certificate's validity window.
        not_valid_after: End of the certificate's validity window.
        name: Friendly name, also the bundle's filename stem.
        subject_cn: Subject common name. Use ``"NAME - NNNNNNNNL"`` when
            the test needs the certificate to name a taxpayer.
        password: Passphrase to encrypt the bundle under.

    Returns:
        Path to the written ``.p12`` file.
    """
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


__all__ = ["CERTIFICATE_BUNDLE_PASSPHRASE", "build_pkcs12_bundle"]
