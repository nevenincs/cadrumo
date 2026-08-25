"""Ed25519 signing and signature verification for review packages.

This module implements the signing slice deferred by
:mod:`~application.modelo._review_package`: that module's
:func:`~application.modelo.verify_review_package` is an INTEGRITY check
only (did every archived member arrive byte-for-byte as built); it makes no
claim about WHO built the package. This module adds the AUTHENTICITY layer on
top of that integrity check by signing the package's self-attesting
:attr:`~core.corpus_manifest.CorpusManifest.manifest_sha256` digest with a
per-profile Ed25519 keypair.

Signing the manifest digest (not the archive bytes or a re-derived hash) means
the signature transitively covers every archived member: the digest is a
SHA-256 over the canonical JSON of the manifest's per-file entries, and a
tampered member is already caught by
:func:`~core.corpus_manifest.verify_corpus_bundle` before signature
verification is even attempted (see :func:`verify_review_package_signature`).

Key custody (``sensitive-financial-data-secure-storage-only`` /
``no-legacy-compatibility``): the private key is generated once per profile
bucket and persisted ONLY as ciphertext through
:class:`~adapters.persistence.storage.SecureObjectRepository` at
``MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity`` classification
(:data:`~adapters.persistence.storage.MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE`).
It is never logged, never written to a plaintext file, and never leaves this
module as raw bytes except transiently in process memory to sign. The public
key is, by construction, safe to export and hand to a receiving accountant for
signature verification -- it carries no secrecy requirement.

Counter-signed accountant feedback-package round trips remain OUT OF SCOPE for
this module; it exposes only the primitive: mint/load a per-profile keypair,
sign a package's manifest digest, verify a signature against a public key.

See Also:
    :mod:`~application.modelo._review_package`
        Builds and integrity-verifies the review package this module signs.
    :class:`~adapters.persistence.storage.SecureObjectRepository`
        Encrypted substrate the private key is persisted through.
    :class:`~adapters.persistence.storage.SensitivityClass`
        Storage classification policy used for the persisted signing keypair.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, Field

from ...adapters.persistence.storage import MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE as _NAMESPACE
from ...core import HEX_PATTERN_64 as _HEX_PATTERN_64
from ...core import HEX_PATTERN_128 as _HEX_PATTERN_128
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.corpus_manifest import CorpusBundleError, CorpusManifestTamperError, verify_corpus_bundle
from ...core.ed25519_signing import (
    digest_signature_is_valid,
    ed25519_private_key_from_hex,
    ed25519_public_key_from_hex,
    generate_ed25519_keypair_hex,
    sign_digest_hex,
)
from ...core.errors import CadrumoError
from ...core.identity import BucketId, CalculationRevisionId, canonical_bucket_id
from ...core.time import UtcInstant
from ...core.time import now as _utc_now
from ._review_package import assert_review_package_verifies
from ._review_package_keypair import ensure_singleton_keypair

if TYPE_CHECKING:
    from ...adapters.persistence.storage import SecureObjectRepository

#: Wire-format version of the signature envelope. Bumped when the envelope
#: schema changes shape (e.g. a future multi-signer / counter-sign extension).
_SIGNATURE_ENVELOPE_VERSION = 1


class ReviewPackageSigningError(CadrumoError):
    """Base error for review-package signing/verification failures."""


class ReviewPackageSigningKeyNotFoundError(ReviewPackageSigningError):
    """Raised when no signing keypair has been minted for a profile bucket yet.

    Callers should mint one via :func:`ensure_review_package_signing_keypair`
    before signing a package for the first time in a given profile.
    """


class ReviewPackageSigningKeypair(BaseModel):
    """A profile's Ed25519 signing keypair, private key included.

    This model is the PLAINTEXT in-memory shape used only transiently around
    generation, persistence, and signing; :meth:`private_key` /
    :meth:`public_key` reconstruct live ``cryptography`` key objects from the
    stored raw hex bytes. Nothing about this model changes the secure-storage
    contract: the caller (:func:`ensure_review_package_signing_keypair`) is
    responsible for persisting it only through
    :class:`~adapters.persistence.storage.SecureObjectRepository`.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    private_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    created_at: UtcInstant

    def private_key(self) -> Ed25519PrivateKey:
        """Reconstruct the live :class:`Ed25519PrivateKey` from stored raw bytes."""
        return ed25519_private_key_from_hex(self.private_key_hex)

    def public_key(self) -> Ed25519PublicKey:
        """Reconstruct the live :class:`Ed25519PublicKey` from stored raw bytes."""
        return ed25519_public_key_from_hex(self.public_key_hex)


class ReviewPackageSigningPublicKey(BaseModel):
    """The exportable, non-secret half of a profile's signing keypair.

    Safe to hand to a receiving accountant so they can verify a package's
    signature independently. Carries no secrecy requirement -- unlike
    :class:`ReviewPackageSigningKeypair`, this model is fine to write to a
    plaintext file, print, or transmit.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    created_at: UtcInstant


class SignedReviewPackage(BaseModel):
    """Signature envelope binding a review package's manifest digest to a signer.

    ``manifest_sha256`` is the review package's own self-attesting
    :attr:`~core.corpus_manifest.CorpusManifest.manifest_sha256` (recovered
    via :func:`~application.modelo.verify_review_package`), NOT a
    re-derived hash of the archive bytes: signing the manifest digest
    transitively covers every archived member because the manifest digest
    already covers every per-file checksum record.
    """

    model_config = _STRICT_FROZEN

    envelope_version: int = Field(default=_SIGNATURE_ENVELOPE_VERSION, ge=1)
    bucket_id: BucketId
    calculation_revision_id: CalculationRevisionId
    manifest_sha256: str = Field(pattern=_HEX_PATTERN_64)
    signature_hex: str = Field(pattern=_HEX_PATTERN_128)
    public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    signed_at: UtcInstant


def _signing_key_object_key(bucket_id: str) -> str:
    """Return the natural :class:`~adapters.persistence.storage.SecureObjectRepository` key for ``bucket_id``'s keypair.

    Matches the namespace's declared
    ``object_key_grammar="review-package-signing-key:{bucket_id}"``.
    """
    return f"review-package-signing-key:{canonical_bucket_id(bucket_id)}"


def _keypair_from_repository_payload(payload: bytes, *, bucket_id: str) -> ReviewPackageSigningKeypair:
    """Load a keypair only when its encrypted payload agrees with its storage key.

    The natural object key binds the record to ``bucket_id``.  The encrypted
    payload repeats that identity so a foreign keypair re-keyed under this
    bucket cannot silently become this profile's signing key.  Exact rather
    than normalized equality also refuses legacy whitespace spellings: those
    would otherwise address the canonical key while preserving a second,
    ambiguous payload identity.
    """
    keypair = ReviewPackageSigningKeypair.model_validate_json(payload)
    if keypair.bucket_id != bucket_id:
        raise ReviewPackageSigningError(
            translated_message="application.modelo.errors.review_package_generic",
        )
    return keypair


def ensure_review_package_signing_keypair(
    *,
    bucket_id: str,
    repository: SecureObjectRepository,
    generated_at: datetime | None = None,
) -> ReviewPackageSigningKeypair:
    """Return the profile's Ed25519 signing keypair, minting one on first use.

    Composes :func:`~application.modelo._review_package_keypair.ensure_singleton_keypair`
    for the mint-or-load-winner mechanic shared with
    :func:`~application.modelo.ensure_recipient_encryption_keypair` (that
    function's X25519 counterpart): loads the existing keypair from
    :data:`~adapters.persistence.storage.MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE`
    when present; otherwise generates a fresh keypair via
    :func:`~core.ed25519_signing.generate_ed25519_keypair_hex`, persists it
    (private key included) as ciphertext, and returns it. Idempotent: a second
    call against the same
    bucket returns the SAME keypair rather than rotating it, so a package
    signed today verifies against a keypair fetched next week.

    Args:
        bucket_id: The active profile bucket id this keypair is scoped to.
        repository: The bucket's
            :class:`~adapters.persistence.storage.SecureObjectRepository`,
            e.g. obtained via
            :func:`~adapters.persistence.storage.secure_object_repository_for_active_bucket`.
        generated_at: Optional override for the keypair's ``created_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    normalised_bucket_id = canonical_bucket_id(bucket_id)
    object_key = _signing_key_object_key(normalised_bucket_id)

    def _generate() -> ReviewPackageSigningKeypair:
        minted = generate_ed25519_keypair_hex()
        return ReviewPackageSigningKeypair(
            bucket_id=normalised_bucket_id,
            private_key_hex=minted.private_key_hex,
            public_key_hex=minted.public_key_hex,
            created_at=generated_at or _utc_now(),
        )

    def _mismatch_error() -> ReviewPackageSigningError:
        return ReviewPackageSigningError(
            "stored review-package signing keypair does not belong to the bucket it was read from",
        )

    return ensure_singleton_keypair(
        repository=repository,
        namespace=_NAMESPACE,
        object_key=object_key,
        model_type=ReviewPackageSigningKeypair,
        generate=_generate,
        bucket_id_of=lambda keypair: keypair.bucket_id,
        created_at_of=lambda keypair: keypair.created_at,
        expected_bucket_id=normalised_bucket_id,
        mismatch_error=_mismatch_error,
        write_provenance="application.modelo.review_package_signing.ensure_keypair",
    )


def load_review_package_signing_keypair(
    *,
    bucket_id: str,
    repository: SecureObjectRepository,
) -> ReviewPackageSigningKeypair:
    """Load the profile's existing Ed25519 signing keypair.

    Args:
        bucket_id: The profile bucket whose signing keypair is loaded.
        repository: The bucket's
            :class:`~adapters.persistence.storage.SecureObjectRepository`.

    Raises:
        ReviewPackageSigningKeyNotFoundError: If no keypair has been minted
            yet for ``bucket_id``. Call
            :func:`ensure_review_package_signing_keypair` first.
    """
    normalised_bucket_id = canonical_bucket_id(bucket_id)
    object_key = _signing_key_object_key(normalised_bucket_id)
    record = repository.load(
        _NAMESPACE.namespace,
        object_key,
        expected_class=_NAMESPACE.sensitivity,
        max_supported_version=_NAMESPACE.schema_version,
    )
    if record is None:
        raise ReviewPackageSigningKeyNotFoundError(
            translated_message="application.modelo.errors.review_package_generic",
            context={"bucket_id": normalised_bucket_id},
        )
    return _keypair_from_repository_payload(record.payload, bucket_id=normalised_bucket_id)


def review_package_signing_public_key(
    keypair: ReviewPackageSigningKeypair,
) -> ReviewPackageSigningPublicKey:
    """Project the exportable public half out of a full keypair.

    The projection never touches ``private_key_hex``; the returned model is
    safe to hand to a receiving accountant.
    """
    return ReviewPackageSigningPublicKey(
        bucket_id=keypair.bucket_id,
        public_key_hex=keypair.public_key_hex,
        created_at=keypair.created_at,
    )


def sign_review_package(
    package_path: Path,
    *,
    keypair: ReviewPackageSigningKeypair,
    signed_at: datetime | None = None,
) -> SignedReviewPackage:
    """Verify ``package_path``'s checksum manifest, then sign its digest.

    Delegates the integrity check entirely to
    :func:`~application.modelo.assert_review_package_verifies` (no
    hashing logic is re-derived here): a package that is not checksum-clean
    raises before any signature is produced, so a signature can never be
    minted over a package this module itself cannot vouch is intact.

    Args:
        package_path: Path to the review-package ZIP to sign.
        keypair: The signer's :class:`ReviewPackageSigningKeypair` (see
            :func:`ensure_review_package_signing_keypair`).
        signed_at: Optional override for the envelope's ``signed_at``
            timestamp (tests only); defaults to the current UTC time.

    Raises:
        FileNotFoundError: If ``package_path`` does not exist.
        ReviewPackageIntegrityError: If the package fails checksum-manifest
            verification (propagated from
            :func:`~application.modelo.assert_review_package_verifies`).
    """
    manifest = assert_review_package_verifies(package_path)
    manifest_sha256 = _package_manifest_sha256(package_path)
    signature_hex = sign_digest_hex(
        private_key_hex=keypair.private_key_hex,
        digest_hex=manifest_sha256,
    )

    return SignedReviewPackage(
        bucket_id=manifest.bucket_id,
        calculation_revision_id=manifest.calculation_revision_id,
        manifest_sha256=manifest_sha256,
        signature_hex=signature_hex,
        public_key_hex=keypair.public_key_hex,
        signed_at=signed_at or _utc_now(),
    )


def verify_review_package_signature(
    package_path: Path,
    signed_package: SignedReviewPackage,
    *,
    public_key_hex: str,
) -> bool:
    """Verify ``signed_package``'s signature against ``public_key_hex``.

    Re-runs the checksum-manifest integrity check (a fresh
    :func:`~core.corpus_manifest.verify_corpus_bundle` call, not a trust
    of ``signed_package.manifest_sha256``) first. This matters because
    ``manifest_sha256`` is a digest over the embedded manifest's OWN recorded
    per-file hashes -- it does NOT change if an archived member's bytes are
    swapped without touching the manifest metadata; only the ``mismatched``
    check (re-hashing every archived file against its manifest record) catches
    that tamper. So a package whose CURRENT bytes are not checksum-clean, or
    whose current manifest digest no longer matches the signed digest, fails
    here even before the Ed25519 check runs.

    Args:
        package_path: Path to the review-package ZIP to verify.
        signed_package: The :class:`SignedReviewPackage` envelope produced by
            :func:`sign_review_package`.
        public_key_hex: The signer's raw public key, as 64 lowercase hex
            characters (see :attr:`~ReviewPackageSigningPublicKey.public_key_hex`).
            Passed explicitly (never read off ``signed_package``) so a
            verifier must supply the key it actually trusts, rather than
            trusting whatever key the envelope claims.

    Returns:
        ``True`` iff the package is currently checksum-clean, its manifest
        digest matches the signed digest, AND the Ed25519 signature verifies
        against ``public_key_hex``. Returns ``False`` (never raises) on any
        mismatch or invalid-signature outcome -- signature verification is an
        authenticity *check*, not an assertion; callers that want a raising
        assertion should call :func:`sign_review_package`'s sibling
        :func:`~application.modelo.assert_review_package_verifies` first
        and test this function's boolean themselves.
    """
    try:
        result = verify_corpus_bundle(package_path)
    except (CorpusBundleError, CorpusManifestTamperError):
        return False

    if not result.is_clean:
        return False
    if result.manifest.manifest_sha256 != signed_package.manifest_sha256:
        return False

    return digest_signature_is_valid(
        public_key_hex=public_key_hex,
        digest_hex=signed_package.manifest_sha256,
        signature_hex=signed_package.signature_hex,
    )


def _package_manifest_sha256(package_path: Path) -> str:
    """Return the package's current self-attesting corpus manifest digest.

    Re-runs :func:`~core.corpus_manifest.verify_corpus_bundle` directly
    (the same checksum layer :func:`~application.modelo.verify_review_package`
    delegates to) so the digest reflects the archive's CURRENT bytes, never a
    cached value, and is available even when the caller only needs the digest
    rather than the full review-specific verification result.
    """
    return verify_corpus_bundle(package_path).manifest.manifest_sha256


__all__ = [
    "ReviewPackageSigningError",
    "ReviewPackageSigningKeyNotFoundError",
    "ReviewPackageSigningKeypair",
    "ReviewPackageSigningPublicKey",
    "SignedReviewPackage",
    "ensure_review_package_signing_keypair",
    "load_review_package_signing_keypair",
    "review_package_signing_public_key",
    "sign_review_package",
    "verify_review_package_signature",
]
