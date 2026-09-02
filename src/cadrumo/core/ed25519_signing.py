"""Ed25519 signing primitive used by the review-package signing surface.

The review-package signer signs a checksum-manifest digest with Ed25519 and
keeps its profile key in encrypted secure storage. Its custody, envelope
metadata, and error vocabulary stay in
:mod:`~application.modelo._review_package_signing`; the cryptography lives
here.

What this module owns is deliberately narrow: key generation, the raw-bytes
hex projection the signer persists, and the sign / verify pair over a
hex-encoded digest. It knows nothing about manifests, bundles, packages,
files, or storage, so it cannot acquire a custody policy by accident.

The digest is passed as HEX and decoded here, because that is the shape both
callers hold -- ``manifest_sha256`` is a hex string on the wire and in every
persisted record. Signing the decoded 32 raw bytes (not the 64 ASCII
characters) is the property that must not drift between the two surfaces: a
verifier that decoded differently from the signer would reject every genuine
signature, and the failure would look like key mismatch rather than an
encoding bug.

See Also:
    :mod:`~application.modelo._review_package_signing`
        Review-package signing built on this primitive.
"""

from __future__ import annotations

from typing import NamedTuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


class Ed25519KeypairHex(NamedTuple):
    """A freshly generated Ed25519 keypair in the raw-bytes hex form callers persist.

    Both halves are 32 raw bytes rendered as 64 hex characters. The private
    half is secret: a caller is responsible for its custody (a
    permission-hardened file, or encrypted secure storage), and this type
    carries no persistence policy of its own.
    """

    private_key_hex: str
    public_key_hex: str


def generate_ed25519_keypair_hex() -> Ed25519KeypairHex:
    """Mint a fresh Ed25519 keypair and project both halves to raw-bytes hex."""
    private_key = Ed25519PrivateKey.generate()
    return Ed25519KeypairHex(
        private_key_hex=private_key.private_bytes(
            encoding=Encoding.Raw,
            format=PrivateFormat.Raw,
            encryption_algorithm=NoEncryption(),
        ).hex(),
        public_key_hex=private_key.public_key()
        .public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )
        .hex(),
    )


def ed25519_private_key_from_hex(private_key_hex: str) -> Ed25519PrivateKey:
    """Reconstruct a live private key from its stored raw-bytes hex."""
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))


def ed25519_public_key_from_hex(public_key_hex: str) -> Ed25519PublicKey:
    """Reconstruct a live public key from its stored raw-bytes hex."""
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))


def sign_digest_hex(*, private_key_hex: str, digest_hex: str) -> str:
    """Sign a hex-encoded digest, returning the signature as hex.

    The digest is decoded to raw bytes before signing; see the module
    docstring for why that decode must be shared with the verifier.
    """
    signature = ed25519_private_key_from_hex(private_key_hex).sign(bytes.fromhex(digest_hex))
    return signature.hex()


def digest_signature_is_valid(*, public_key_hex: str, digest_hex: str, signature_hex: str) -> bool:
    """Return whether ``signature_hex`` is a valid signature over ``digest_hex``.

    Returns ``False`` rather than raising on an invalid signature: both
    callers treat "signed by someone else" and "tampered" as ordinary
    negative verification outcomes to report, not as exceptional control
    flow. A malformed hex input still raises, because that is a caller bug
    rather than a verification verdict.
    """
    try:
        ed25519_public_key_from_hex(public_key_hex).verify(
            bytes.fromhex(signature_hex),
            bytes.fromhex(digest_hex),
        )
    except InvalidSignature:
        return False
    return True


__all__ = [
    "Ed25519KeypairHex",
    "digest_signature_is_valid",
    "ed25519_private_key_from_hex",
    "ed25519_public_key_from_hex",
    "generate_ed25519_keypair_hex",
    "sign_digest_hex",
]
