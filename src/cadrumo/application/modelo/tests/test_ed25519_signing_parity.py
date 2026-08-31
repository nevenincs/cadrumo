"""Both artefact-signing surfaces share one Ed25519 primitive.

Corpus-bundle signing (maintainer key on disk) and review-package signing
(profile key in encrypted secure storage) have genuinely different custody and
error vocabularies, but identical cryptography. These tests pin that the
cryptography has one home and that the primitive's contract is what both
surfaces actually get.

Lives in the application layer because it imports both a ``core`` module and an
``application`` module; a ``core`` test may not reach outward.
"""

from __future__ import annotations

import inspect
from importlib import import_module

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ....core import corpus_manifest as _corpus_manifest_pkg
from ....core.corpus_manifest import _bundle_signing as corpus_signing
from ....core.ed25519_signing import (
    digest_signature_is_valid,
    ed25519_private_key_from_hex,
    ed25519_public_key_from_hex,
    generate_ed25519_keypair_hex,
    sign_digest_hex,
)

review_signing = import_module("cadrumo.application.modelo._review_package_signing")

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

    It matters because the two surfaces persist ``manifest_sha256`` as hex. If
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


def test_the_two_surfaces_reconstruct_identical_keys_from_one_keypair() -> None:
    """A corpus keypair and a review keypair over the same hex are the same key.

    DISCRIMINATING for the shared-primitive claim at the behavioural level: a
    signature produced through one surface's key model verifies through the
    other's. If either surface reconstructed keys its own way, this cross-check
    is where the divergence would surface.
    """
    minted = generate_ed25519_keypair_hex()
    corpus_keypair = corpus_signing.CorpusSigningKeypair(
        private_key_hex=minted.private_key_hex,
        public_key_hex=minted.public_key_hex,
        created_at=_utc_now(),
    )
    review_keypair = review_signing.ReviewPackageSigningKeypair(
        bucket_id="parity-bucket",
        private_key_hex=minted.private_key_hex,
        public_key_hex=minted.public_key_hex,
        created_at=_utc_now(),
    )

    corpus_signature = corpus_keypair.private_key().sign(bytes.fromhex(_DIGEST))
    review_keypair.public_key().verify(corpus_signature, bytes.fromhex(_DIGEST))

    review_signature = review_keypair.private_key().sign(bytes.fromhex(_DIGEST))
    corpus_keypair.public_key().verify(review_signature, bytes.fromhex(_DIGEST))

    assert corpus_signature == review_signature, "Ed25519 is deterministic; the two surfaces must agree byte for byte"


def test_neither_signing_module_implements_the_primitive_itself() -> None:
    """Both modules delegate every Ed25519 operation to the core primitive.

    DISCRIMINATING, and the only assertion here that survives a re-inlining
    mutation: a byte-identical copy of key generation, signing, or verification
    pasted back into either module reproduces every behavioural result above,
    because it is the same algorithm. This is what notices the copy.
    """
    for module in (corpus_signing, review_signing):
        source = inspect.getsource(module)
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
                f"{module.__name__} re-implements {reimplemented} instead of using core.ed25519_signing"
            )
        assert "ed25519_signing import" in body, f"{module.__name__} does not import the core primitive"


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
    assert _corpus_manifest_pkg is not None


def _utc_now():
    from ....core.time.clock import now

    return now()
