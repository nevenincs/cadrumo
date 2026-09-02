"""The review-package signing surface uses one Ed25519 primitive.

The profile key stays in encrypted secure storage and the signing surface owns
its custody and error vocabulary. These tests pin that the cryptography has
one home and that the primitive's contract is what the signer actually gets.

Lives in the application layer because it imports both a ``core`` module and an
``application`` module; a ``core`` test may not reach outward.
"""

from __future__ import annotations

import inspect
from importlib import import_module

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ....core.ed25519_signing import (
    digest_signature_is_valid,
    ed25519_private_key_from_hex,
    ed25519_public_key_from_hex,
    generate_ed25519_keypair_hex,
    sign_digest_hex,
)

review_signing = import_module("cadrumo.application.modelo.review_package_signing")

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIGEST = "a" * 64
_OTHER_DIGEST = "b" * 64


def test_the_signature_covers_the_decoded_digest_not_its_hex_text() -> None:
    """The primitive signs the 32 RAW digest bytes, verified independently.

    DISCRIMINATING, and the reason this test does not use the primitive's own
    verifier: a sign/verify roundtrip cannot see an encoding change, because
    signing the ASCII hex and verifying the ASCII hex still agree with each
    other. Only an INDEPENDENT verifier -- raw ``cryptography`` over
    ``bytes.fromhex(digest)`` -- pins which message was actually signed.

    It matters because the signer persists ``manifest_sha256`` as hex. If the
    signer and verifier ever decoded it differently, every genuine signature
    would be rejected and the failure would look like a key mismatch rather
    than an encoding bug.
    """
    keypair = generate_ed25519_keypair_hex()
    signature_hex = sign_digest_hex(private_key_hex=keypair.private_key_hex, digest_hex=_DIGEST)

    public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(keypair.public_key_hex))
    # Raises InvalidSignature unless the signed message was the decoded digest.
    public_key.verify(bytes.fromhex(signature_hex), bytes.fromhex(_DIGEST))

    # And the ASCII-hex form is NOT what was signed.
    with pytest.raises(InvalidSignature):
        public_key.verify(bytes.fromhex(signature_hex), _DIGEST.encode("ascii"))


def test_a_tampered_digest_fails_verification() -> None:
    """A signature does not verify over a different digest.

    DISCRIMINATING: this is the whole point of signing the manifest digest, and
    it fails if verification is ever short-circuited to a constant ``True``.
    """
    keypair = generate_ed25519_keypair_hex()
    signature_hex = sign_digest_hex(private_key_hex=keypair.private_key_hex, digest_hex=_DIGEST)

    assert not digest_signature_is_valid(
        public_key_hex=keypair.public_key_hex,
        digest_hex=_OTHER_DIGEST,
        signature_hex=signature_hex,
    )


def test_another_keypair_does_not_verify() -> None:
    """A signature does not verify under an unrelated public key.

    DISCRIMINATING for the authenticity claim: without it, "signed" would mean
    only "well-formed", and any party could pass as the signer.
    """
    signer = generate_ed25519_keypair_hex()
    stranger = generate_ed25519_keypair_hex()
    signature_hex = sign_digest_hex(private_key_hex=signer.private_key_hex, digest_hex=_DIGEST)

    assert not digest_signature_is_valid(
        public_key_hex=stranger.public_key_hex,
        digest_hex=_DIGEST,
        signature_hex=signature_hex,
    )
    # Positive control: the genuine key DOES verify the same signature, so the
    # refusal above is attributable to the key and not to a broken signature.
    assert digest_signature_is_valid(
        public_key_hex=signer.public_key_hex,
        digest_hex=_DIGEST,
        signature_hex=signature_hex,
    )


def test_review_signing_module_does_not_implement_the_primitive_itself() -> None:
    """The review signer delegates every Ed25519 operation to the core primitive.

    DISCRIMINATING, and the only assertion here that survives a re-inlining
    mutation: a byte-identical copy of key generation, signing, or verification
    pasted back into the signer reproduces every behavioural result above,
    because it is the same algorithm. This is what notices the copy.
    """
    source = inspect.getsource(review_signing)
    body = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    for reimplemented in (
        "Ed25519PrivateKey.generate()",
        "from_private_bytes(",
        "from_public_bytes(",
        "private_bytes(",
        "public_bytes(",
        "InvalidSignature",
    ):
        assert reimplemented not in body, (
            f"{review_signing.__name__} re-implements {reimplemented} instead of using core.ed25519_signing"
        )
    assert "ed25519_signing import" in body, f"{review_signing.__name__} does not import the core primitive"


def test_the_primitive_is_the_only_home_of_the_raw_operations() -> None:
    """The core primitive genuinely contains what the wrappers delegate.

    SUPPORTING: pairs with the assertion above so "absent from the wrappers"
    cannot be satisfied by the operations being absent everywhere.
    """
    from ....core import ed25519_signing

    source = inspect.getsource(ed25519_signing)
    for owned in ("Ed25519PrivateKey.generate()", "from_private_bytes(", "from_public_bytes(", "InvalidSignature"):
        assert owned in source


def test_round_trip_verification_succeeds() -> None:
    """A freshly signed digest verifies under its own key.

    SUPPORTING: the happy path. It cannot detect an encoding change on its own
    -- see the independent-verifier test above for that.
    """
    keypair = generate_ed25519_keypair_hex()
    signature_hex = sign_digest_hex(private_key_hex=keypair.private_key_hex, digest_hex=_DIGEST)

    assert digest_signature_is_valid(
        public_key_hex=keypair.public_key_hex,
        digest_hex=_DIGEST,
        signature_hex=signature_hex,
    )
    assert ed25519_private_key_from_hex(keypair.private_key_hex)
    assert ed25519_public_key_from_hex(keypair.public_key_hex)
