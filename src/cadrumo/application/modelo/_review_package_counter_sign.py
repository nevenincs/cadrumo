"""Counter-signed accountant receipt round trip for signed review packages.

This module implements the counter-sign slice deferred by
:mod:`~application.modelo._review_package_signing`: that module adds an
AUTHENTICITY layer over a review package's checksum manifest by having the
operator sign the manifest digest with their own Ed25519 keypair
(:func:`~application.modelo.sign_review_package`). It makes no claim
about what the RECEIVING accountant did with the package once it arrived.

A :class:`CounterSignedReceipt` closes that loop: the accountant signs a
second, independent Ed25519 signature over the operator's ORIGINAL signature
bytes plus a short free-text note (e.g. a verdict such as "reviewed, no
changes" or "see attached corrections"). Verifying the receipt
(:func:`verify_counter_signed_receipt`) re-checks BOTH layers -- the
operator's original signature against the operator's public key (delegating
to :func:`~application.modelo.verify_review_package_signature`, so the
checksum-manifest integrity re-check happens first, exactly as it does for a
bare :class:`~application.modelo.SignedReviewPackage`), and the
accountant's counter-signature against the accountant's public key -- so a
receipt only verifies clean when neither party's signature nor the note text
has been tampered with.

Signing the ORIGINAL SIGNATURE BYTES (not the manifest digest a second time,
and not a re-derived hash) means the counter-signature transitively commits
the accountant to the specific operator signature they received: swapping in
a different (even validly-signed) operator signature for the same package
invalidates the counter-signature, because the bytes it covers changed.

Key custody (``sensitive-financial-data-secure-storage-only`` /
``no-legacy-compatibility``): the counter-signer's (accountant's) keypair is
minted and persisted through the exact same
:func:`~application.modelo.ensure_review_package_signing_keypair`
primitive the operator uses, scoped to whatever ``bucket_id`` the caller
supplies for the counter-signer's identity -- there is no separate key-custody
mechanism to introduce. The private key never leaves that primitive as raw
bytes except transiently in process memory to sign.

See Also:
    :mod:`~application.modelo._review_package_signing`
        The operator-side signing primitive this module counter-signs on top of.
    :mod:`~application.modelo.review_package`
        Builds and integrity-verifies the review package that is signed.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, Field

from ...core import HEX_PATTERN_64 as _HEX_PATTERN_64
from ...core import HEX_PATTERN_128 as _HEX_PATTERN_128
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import UTF_8_ENCODING
from ...core.time import UtcInstant
from ...core.time import now as _utc_now
from ._review_package_signing import (
    ReviewPackageSigningKeypair,
    SignedReviewPackage,
    verify_review_package_signature,
)

#: Wire-format version of the counter-signature envelope. Bumped when the
#: envelope schema changes shape.
_COUNTER_SIGNATURE_ENVELOPE_VERSION = 1


class ReviewPackageCounterSigningError(CadrumoError):
    """Base error for review-package counter-signing/verification failures."""


class CounterSignedReceipt(BaseModel):
    """A review package's operator signature, counter-signed by an accountant.

    Wraps the operator's :class:`~application.modelo.SignedReviewPackage`
    verbatim (the ``original_signature`` field) alongside the accountant's own
    Ed25519 signature over ``original_signature.signature_hex`` plus ``note``.
    Binding the counter-signature to the ORIGINAL SIGNATURE BYTES (rather than
    the manifest digest) means the counter-signature can only ever attest to
    that one specific operator signature: a different signature over the same
    manifest (e.g. re-signed by a rotated operator key) has different
    ``signature_hex`` bytes and would need a fresh counter-signature.
    """

    model_config = _STRICT_FROZEN

    envelope_version: int = Field(default=_COUNTER_SIGNATURE_ENVELOPE_VERSION, ge=1)
    original_signature: SignedReviewPackage
    note: str = Field(default="", max_length=2000)
    counter_signature_hex: str = Field(pattern=_HEX_PATTERN_128)
    counter_public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    counter_signed_at: UtcInstant

    @property
    def counter_signed_message(self) -> bytes:
        """Return the exact byte string the counter-signature covers.

        Reconstructing this independently of :func:`counter_sign_review_package`
        lets :func:`verify_counter_signed_receipt` recompute the signed message
        from the receipt's own fields rather than trusting a cached value, so a
        receipt whose ``note`` was edited after counter-signing fails
        verification instead of silently re-approving different text.
        """
        return _counter_signed_message(
            signature_hex=self.original_signature.signature_hex,
            note=self.note,
        )


def _counter_signed_message(*, signature_hex: str, note: str) -> bytes:
    """Return the canonical byte string a counter-signature is minted over.

    Binds the operator's original signature hex and the accountant's note
    with an explicit separator so the two fields cannot be concatenated
    ambiguously (e.g. ``sig="ab"`` + ``note="cd"`` colliding with
    ``sig="abc"`` + ``note="d"``).
    """
    return signature_hex.encode("ascii") + b"\x00" + note.encode(UTF_8_ENCODING)


def counter_sign_review_package(
    signed_package: SignedReviewPackage,
    *,
    counter_signer_keypair: ReviewPackageSigningKeypair,
    note: str = "",
    counter_signed_at: datetime | None = None,
) -> CounterSignedReceipt:
    """Counter-sign an operator-signed review package on behalf of the accountant.

    Does NOT re-verify the operator's ``signed_package`` signature or the
    underlying archive's checksum manifest -- that is
    :func:`~application.modelo.verify_review_package_signature`'s job,
    and it is re-run unconditionally inside
    :func:`verify_counter_signed_receipt`. Counter-signing a signature that
    later turns out to be invalid is not itself an error: the receipt's
    verification is what asserts both layers are clean, and a caller that
    wants to guarantee the original signature is valid BEFORE counter-signing
    should verify it first.

    Args:
        signed_package: The operator's :class:`SignedReviewPackage` envelope
            (see :func:`~application.modelo.sign_review_package`).
        counter_signer_keypair: The accountant's
            :class:`~application.modelo.ReviewPackageSigningKeypair`
            (minted the same way as the operator's, via
            :func:`~application.modelo.ensure_review_package_signing_keypair`
            scoped to the accountant's own identity).
        note: Optional free-text counter-signer note or verdict (e.g.
            ``"reviewed, no changes"``). Bound into the signed message, so
            editing the note after counter-signing invalidates the receipt.
        counter_signed_at: Optional override for the envelope's
            ``counter_signed_at`` timestamp (tests only); defaults to the
            current UTC time.
    """
    message = _counter_signed_message(signature_hex=signed_package.signature_hex, note=note)
    counter_signature = counter_signer_keypair.private_key().sign(message)

    return CounterSignedReceipt(
        original_signature=signed_package,
        note=note,
        counter_signature_hex=counter_signature.hex(),
        counter_public_key_hex=counter_signer_keypair.public_key_hex,
        counter_signed_at=counter_signed_at or _utc_now(),
    )


def verify_counter_signed_receipt(
    package_path: Path,
    receipt: CounterSignedReceipt,
    *,
    operator_public_key_hex: str,
    counter_signer_public_key_hex: str,
) -> bool:
    """Verify BOTH signature layers of a counter-signed review-package receipt.

    First re-verifies the operator's original signature via
    :func:`~application.modelo.verify_review_package_signature` --
    which itself re-runs the checksum-manifest integrity check against the
    package's CURRENT bytes before touching any Ed25519 signature, so a
    tampered archive fails here regardless of either signature. Only once
    that layer passes does this function verify the accountant's
    counter-signature against the message it recomputes from the receipt's
    own ``original_signature.signature_hex`` and ``note`` fields (never a
    cached message), so an edited note invalidates the receipt.

    Args:
        package_path: Path to the review-package ZIP the receipt attests to.
        receipt: The :class:`CounterSignedReceipt` produced by
            :func:`counter_sign_review_package`.
        operator_public_key_hex: The operator's raw public key, as 64
            lowercase hex characters. Passed explicitly (never read off the
            receipt) so a verifier must supply the key it actually trusts.
        counter_signer_public_key_hex: The accountant's raw public key, as 64
            lowercase hex characters. Passed explicitly for the same reason;
            the receipt's own ``counter_public_key_hex`` is never trusted as
            the verification key.

    Returns:
        ``True`` iff the package is currently checksum-clean, the operator's
        original signature verifies against ``operator_public_key_hex``, AND
        the accountant's counter-signature verifies against
        ``counter_signer_public_key_hex``. Returns ``False`` (never raises)
        on any mismatch, tamper, or invalid-signature outcome.
    """
    if not verify_review_package_signature(
        package_path,
        receipt.original_signature,
        public_key_hex=operator_public_key_hex,
    ):
        return False

    counter_public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(counter_signer_public_key_hex))
    message = _counter_signed_message(signature_hex=receipt.original_signature.signature_hex, note=receipt.note)
    try:
        counter_public_key.verify(bytes.fromhex(receipt.counter_signature_hex), message)
    except InvalidSignature:
        return False
    return True


__all__ = [
    "CounterSignedReceipt",
    "ReviewPackageCounterSigningError",
    "counter_sign_review_package",
    "verify_counter_signed_receipt",
]
