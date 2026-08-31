"""Ed25519 authenticity signing for offline corpus bundles.

:func:`~core.corpus_manifest.build_corpus_bundle` and
:func:`~core.corpus_manifest.verify_corpus_bundle` give a distributable
corpus ``.zip`` an INTEGRITY guarantee: every archived file matches its
embedded SHA-256 manifest record, and the manifest itself is self-attesting.
That is deliberately silent on AUTHENTICITY -- a bundle rebuilt by anyone from
an unmodified corpus tree verifies exactly as clean as one built by the
project's maintainers, so an installer with only the checksum layer cannot
tell "this bundle's checksums are internally consistent" from "this bundle was
actually published by the project".

This module adds that authenticity layer on top, following the SAME pattern
:mod:`~application.modelo._review_package_signing` established for
review-package signing: sign the bundle's self-attesting
:attr:`~core.corpus_manifest.CorpusManifest.manifest_sha256` digest with
an Ed25519 keypair (RFC 8032), so the signature transitively covers every
archived member (a tampered member is already caught by
:func:`~core.corpus_manifest.verify_corpus_bundle` before the signature
check is even attempted; see
:func:`~core.corpus_manifest.verify_corpus_bundle_signature`).

Key custody differs from the review-package case by necessity. A review
package is signed by one profile's operator and verified by a peer who
receives the public key out of band; a corpus bundle is signed ONCE by the
project's maintainers (an offline, pre-distribution act, with no profile
bucket in scope) and verified by every installer, including installers who
have never provisioned a profile at all. This module therefore has no
:class:`~adapters.persistence.storage.SecureObjectRepository` dependency
(this is a ``core`` module; ``core`` may not import ``adapters`` or
``application`` -- see the ``core-not-outer`` import-linter contract) and
persists a maintainer's private key as a hex-encoded file on disk instead,
through :func:`~core.atomic_write.atomic_write_hardened_text`. The corresponding
public key carries no secrecy requirement: it is meant to be embedded in the
``aeat`` distribution (or passed explicitly) so every installer can verify a
downloaded bundle against a key they already trust, without contacting anyone.

See Also:
    :mod:`~core.corpus_manifest`
        Builds and integrity-verifies the bundle this module signs.
    :mod:`~application.modelo._review_package_signing`
        The sibling implementation of the same signing primitive, scoped to
        one profile bucket's review-package authenticity instead of a
        maintainer-published corpus bundle.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, Field, ValidationError, field_validator

from ..atomic_write import atomic_write_hardened_text
from ..ed25519_signing import (
    digest_signature_is_valid,
    ed25519_private_key_from_hex,
    ed25519_public_key_from_hex,
    generate_ed25519_keypair_hex,
    sign_digest_hex,
)
from ..errors.hierarchy import CadrumoError
from ..external_constants import UTF_8_ENCODING
from ..hex import HEX_PATTERN_64 as _HEX_PATTERN_64
from ..hex import HEX_PATTERN_128 as _HEX_PATTERN_128
from ..models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..time.clock import now as _utc_now
from ..time.utc import validate_utc_aware as _validate_utc_aware

#: Wire-format version of the signature envelope. Bumped when the envelope
#: schema changes shape.
_SIGNATURE_ENVELOPE_VERSION = 1


class CorpusBundleSigningError(CadrumoError):
    """Base error for corpus-bundle signing/verification failures."""


class CorpusBundleSigningKeyNotFoundError(CorpusBundleSigningError):
    """Raised when no signing keypair file exists at the requested path.

    Callers should mint one via
    :func:`~core.corpus_manifest.generate_corpus_signing_keypair` before signing
    a bundle for the first time.
    """


class CorpusSigningKeypair(BaseModel):
    """A maintainer's Ed25519 corpus-signing keypair, private key included.

    This model is the PLAINTEXT in-memory shape used only transiently around
    generation, persistence, and signing;
    :meth:`~core.corpus_manifest.CorpusSigningKeypair.private_key` /
    :meth:`~core.corpus_manifest.CorpusSigningKeypair.public_key` reconstruct
    live ``cryptography`` key objects from the stored raw hex bytes. The caller
    (:func:`~core.corpus_manifest.generate_corpus_signing_keypair` /
    :func:`~core.corpus_manifest.load_corpus_signing_keypair`) is responsible for
    keeping the on-disk file permission-hardened; this model carries no
    persistence logic of its own.
    """

    model_config = _STRICT_FROZEN

    private_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        return _validate_utc_aware(value)

    def private_key(self) -> Ed25519PrivateKey:
        """Reconstruct the live :class:`Ed25519PrivateKey` from stored raw bytes."""
        return ed25519_private_key_from_hex(self.private_key_hex)

    def public_key(self) -> Ed25519PublicKey:
        """Reconstruct the live :class:`Ed25519PublicKey` from stored raw bytes."""
        return ed25519_public_key_from_hex(self.public_key_hex)


class CorpusSigningPublicKey(BaseModel):
    """The exportable, non-secret half of a maintainer's corpus-signing keypair.

    Safe to embed in the ``aeat`` distribution, print, or transmit so every
    installer can verify a downloaded bundle's signature independently.
    Carries no secrecy requirement -- unlike
    :class:`~core.corpus_manifest.CorpusSigningKeypair`, this model is fine to
    write to a plaintext file.
    """

    model_config = _STRICT_FROZEN

    public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        return _validate_utc_aware(value)


class SignedCorpusBundle(BaseModel):
    """Signature envelope binding a corpus bundle's manifest digest to a signer.

    ``manifest_sha256`` is the bundle's own self-attesting
    :attr:`~core.corpus_manifest.CorpusManifest.manifest_sha256` (recovered
    via :func:`~core.corpus_manifest.verify_corpus_bundle`), NOT a
    re-derived hash of the archive bytes: signing the manifest digest
    transitively covers every archived member because the manifest digest
    already covers every per-file checksum record.
    """

    model_config = _STRICT_FROZEN

    envelope_version: int = Field(default=_SIGNATURE_ENVELOPE_VERSION, ge=1)
    corpus_root_name: str = Field(min_length=1, max_length=64)
    manifest_sha256: str = Field(pattern=_HEX_PATTERN_64)
    signature_hex: str = Field(pattern=_HEX_PATTERN_128)
    public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    signed_at: datetime

    @field_validator("signed_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        return _validate_utc_aware(value)


def generate_corpus_signing_keypair(
    *,
    private_key_path: Path,
    generated_at: datetime | None = None,
) -> CorpusSigningKeypair:
    """Mint a fresh Ed25519 keypair and persist it (private key included) to disk.

    Writes the keypair as JSON to ``private_key_path`` through the hardened
    atomic secret-write owner: collision-hardened staging, restrictive mode,
    durability barriers, replacement, and cleanup on failure. This is a
    maintainer-side, offline, one-time act: unlike the review-package keypair
    (minted per profile bucket, on demand), a corpus signing keypair is
    generated once by the project and its public half is then embedded in the
    distribution or handed to installers explicitly.

    Args:
        private_key_path: Destination path for the keypair JSON. Parent
            directories are created as needed. An existing file at this path
            is overwritten -- callers who want key rotation safety should
            back up the existing key first.
        generated_at: Optional override for the keypair's ``created_at``
            timestamp (tests only); defaults to the current UTC time.

    Returns:
        The freshly minted
        :class:`~core.corpus_manifest.CorpusSigningKeypair`.
    """
    minted = generate_ed25519_keypair_hex()
    keypair = CorpusSigningKeypair(
        private_key_hex=minted.private_key_hex,
        public_key_hex=minted.public_key_hex,
        created_at=generated_at or _utc_now(),
    )
    resolved = private_key_path.resolve()
    atomic_write_hardened_text(
        resolved,
        keypair.model_dump_json(),
        encoding=UTF_8_ENCODING,
    )
    return keypair


def load_corpus_signing_keypair(private_key_path: Path) -> CorpusSigningKeypair:
    """Load a maintainer's existing Ed25519 corpus-signing keypair from disk.

    Args:
        private_key_path: Path to the keypair JSON written by
            :func:`~core.corpus_manifest.generate_corpus_signing_keypair`.

    Raises:
        CorpusBundleSigningKeyNotFoundError: If no file exists at
            ``private_key_path``. Call
            :func:`~core.corpus_manifest.generate_corpus_signing_keypair` first.
        CorpusBundleSigningError: If the file exists but is not a
            structurally valid keypair record.
    """
    if not private_key_path.exists():
        raise CorpusBundleSigningKeyNotFoundError(
            f"no corpus signing keypair found at {private_key_path}; call generate_corpus_signing_keypair() first",
        )
    raw = private_key_path.read_text(encoding=UTF_8_ENCODING)
    try:
        return CorpusSigningKeypair.model_validate_json(raw)
    except (ValueError, ValidationError) as exc:
        raise CorpusBundleSigningError(
            f"corpus signing keypair at {private_key_path} is structurally invalid: {exc}",
        ) from exc


def corpus_signing_public_key(keypair: CorpusSigningKeypair) -> CorpusSigningPublicKey:
    """Project the exportable public half out of a full keypair.

    The projection never touches ``private_key_hex``; the returned model is
    safe to embed in the distribution or hand to an installer.

    Returns:
        A :class:`~core.corpus_manifest.CorpusSigningPublicKey` carrying only
        the public verifier material and creation timestamp.
    """
    return CorpusSigningPublicKey(
        public_key_hex=keypair.public_key_hex,
        created_at=keypair.created_at,
    )


def sign_corpus_bundle(
    bundle_path: Path,
    *,
    keypair: CorpusSigningKeypair,
    signed_at: datetime | None = None,
) -> SignedCorpusBundle:
    """Verify ``bundle_path``'s checksum manifest, then sign its digest.

    Delegates the integrity check entirely to
    :func:`~core.corpus_manifest.assert_corpus_bundle_verifies` (no
    hashing logic is re-derived here): a bundle that is not checksum-clean
    raises before any signature is produced, so a signature can never be
    minted over a bundle this module itself cannot vouch is intact.

    Args:
        bundle_path: Path to the corpus bundle ``.zip`` to sign.
        keypair: The signer's
            :class:`~core.corpus_manifest.CorpusSigningKeypair` (see
            :func:`~core.corpus_manifest.generate_corpus_signing_keypair`).
        signed_at: Optional override for the envelope's ``signed_at``
            timestamp (tests only); defaults to the current UTC time.

    Raises:
        FileNotFoundError: If ``bundle_path`` does not exist.
        CorpusBundleError: If the bundle fails structural verification.
        CorpusManifestTamperError: If the embedded manifest's self-attesting
            digest does not match its body.
        CorpusBundleVerificationError: If the bundle fails checksum-manifest
            verification (propagated from
            :func:`~core.corpus_manifest.assert_corpus_bundle_verifies`).
    """
    from .manifest import assert_corpus_bundle_verifies

    manifest = assert_corpus_bundle_verifies(bundle_path)
    signature_hex = sign_digest_hex(
        private_key_hex=keypair.private_key_hex,
        digest_hex=manifest.manifest_sha256,
    )

    return SignedCorpusBundle(
        corpus_root_name=manifest.corpus_root_name,
        manifest_sha256=manifest.manifest_sha256,
        signature_hex=signature_hex,
        public_key_hex=keypair.public_key_hex,
        signed_at=signed_at or _utc_now(),
    )


def verify_corpus_bundle_signature(
    bundle_path: Path,
    signed_bundle: SignedCorpusBundle,
    *,
    public_key_hex: str,
) -> bool:
    """Verify ``signed_bundle``'s signature against ``public_key_hex``.

    Re-runs the checksum-manifest integrity check (a fresh
    :func:`~core.corpus_manifest.verify_corpus_bundle` call, not a trust
    of ``signed_bundle.manifest_sha256``) first. This matters because
    ``manifest_sha256`` is a digest over the embedded manifest's OWN recorded
    per-file hashes -- it does NOT change if an archived member's bytes are
    swapped without touching the manifest metadata; only the ``mismatched``
    check (re-hashing every archived file against its manifest record) catches
    that tamper. So a bundle whose CURRENT bytes are not checksum-clean, or
    whose current manifest digest no longer matches the signed digest, fails
    here even before the Ed25519 check runs.

    Args:
        bundle_path: Path to the corpus bundle ``.zip`` to verify.
        signed_bundle: The
            :class:`~core.corpus_manifest.SignedCorpusBundle` envelope produced
            by :func:`~core.corpus_manifest.sign_corpus_bundle`.
        public_key_hex: The signer's raw public key, as 64 lowercase hex
            characters (see
            :attr:`~core.corpus_manifest.CorpusSigningPublicKey.public_key_hex`).
            Passed explicitly (never read off ``signed_bundle``) so a verifier
            must supply the key it actually trusts, rather than trusting
            whatever key the envelope claims.

    Returns:
        ``True`` iff the bundle is currently checksum-clean, its manifest
        digest matches the signed digest, AND the Ed25519 signature verifies
        against ``public_key_hex``. Returns ``False`` (never raises) on any
        mismatch or invalid-signature outcome -- signature verification is an
        authenticity *check*, not an assertion; callers that want a raising
        assertion should call
        :func:`~core.corpus_manifest.assert_corpus_bundle_signature_verifies`.
    """
    from .errors import CorpusBundleError, CorpusManifestTamperError
    from .manifest import verify_corpus_bundle

    try:
        result = verify_corpus_bundle(bundle_path)
    except (CorpusBundleError, CorpusManifestTamperError):
        return False

    if not result.is_clean:
        return False
    if result.manifest.manifest_sha256 != signed_bundle.manifest_sha256:
        return False

    return digest_signature_is_valid(
        public_key_hex=public_key_hex,
        digest_hex=signed_bundle.manifest_sha256,
        signature_hex=signed_bundle.signature_hex,
    )


def assert_corpus_bundle_signature_verifies(
    bundle_path: Path,
    signed_bundle: SignedCorpusBundle,
    *,
    public_key_hex: str,
) -> None:
    """Raise unless ``signed_bundle`` verifies clean against ``public_key_hex``.

    The install-time assertion: call this before extracting or trusting a
    downloaded/copied corpus bundle whose signature you hold. Raises
    :class:`~core.corpus_manifest.CorpusBundleSigningError` naming the bundle
    path on any failure -- a checksum mismatch, a manifest-digest mismatch, or
    an invalid signature are not distinguished in the error message beyond
    naming the bundle, matching
    :func:`~core.corpus_manifest.verify_corpus_bundle_signature`'s deliberately
    coarse boolean contract (a tampered bundle and a forged signature must both
    refuse installation identically).
    """
    if not verify_corpus_bundle_signature(bundle_path, signed_bundle, public_key_hex=public_key_hex):
        raise CorpusBundleSigningError(
            f"corpus bundle {bundle_path} failed signature verification: "
            "the bundle is not checksum-clean, its manifest digest does not match "
            "the signed digest, or the Ed25519 signature is invalid for the given public key",
        )


__all__ = [
    "CorpusBundleSigningError",
    "CorpusBundleSigningKeyNotFoundError",
    "CorpusSigningKeypair",
    "CorpusSigningPublicKey",
    "SignedCorpusBundle",
    "assert_corpus_bundle_signature_verifies",
    "corpus_signing_public_key",
    "generate_corpus_signing_keypair",
    "load_corpus_signing_keypair",
    "sign_corpus_bundle",
    "verify_corpus_bundle_signature",
]
