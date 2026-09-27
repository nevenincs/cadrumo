"""The derived per-profile key a calculation report's references are digested with.

The subject is the derivation and the digest spelling, so the keypair comes from
the inward in-memory capability rather than encrypted storage: what must hold is
that the report's key is NOT the signing key, that one profile always derives the
same key, and that two profiles never share one.
"""

from __future__ import annotations

import pytest
from pydantic import SecretBytes

from ....core.hashing import sha256_hex
from ....core.keyed_digest import DERIVED_KEY_BYTES, KEYED_DIGEST_ALGORITHM, derive_labelled_key
from ..calculation_report_provenance_key import (
    CALCULATION_REPORT_PROVENANCE_KEY_INFO,
    OPAQUE_PROVENANCE_FAMILY,
    CalculationReportProvenanceKey,
    derive_calculation_report_provenance_key,
)
from ..review_package_signing import ensure_review_package_signing_keypair
from ._review_package_signing_support import InMemoryReviewPackageSigningKeypairCapability

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_OTHER_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_PERCEPTOR_NIF = "12345678Z"


def _key() -> CalculationReportProvenanceKey:
    """A key with fixed material, so every digest below is reproducible."""
    return CalculationReportProvenanceKey(bucket_id=_BUCKET_ID, key=SecretBytes(bytes(range(DERIVED_KEY_BYTES))))


def test_the_provenance_key_is_derived_from_the_signing_key_and_is_not_it() -> None:
    """The report's key is a labelled derivative, so it cannot sign or be signed with."""
    capability = InMemoryReviewPackageSigningKeypairCapability()
    keypair = ensure_review_package_signing_keypair(bucket_id=_BUCKET_ID, signing_keypair=capability)

    derived = derive_calculation_report_provenance_key(bucket_id=_BUCKET_ID, signing_keypair=capability)
    secret = derived.key.get_secret_value()

    assert derived.bucket_id == _BUCKET_ID
    assert len(secret) == DERIVED_KEY_BYTES
    assert secret != bytes.fromhex(keypair.private_key_hex)
    assert secret != bytes.fromhex(keypair.public_key_hex)
    assert secret.hex() not in (keypair.private_key_hex, keypair.public_key_hex)
    assert secret == derive_labelled_key(
        key_material=bytes.fromhex(keypair.private_key_hex),
        info=CALCULATION_REPORT_PROVENANCE_KEY_INFO,
    )
    # A different label over the same secret is a different key, which is what
    # keeps one purpose's digests out of another's.
    assert secret != derive_labelled_key(
        key_material=bytes.fromhex(keypair.private_key_hex),
        info=b"cadrumo/some-other-purpose/v1",
    )


def test_one_profile_derives_one_stable_key_and_two_profiles_never_share_it() -> None:
    """Stability is what lets a later rebuild reproduce a published report's digests."""
    capability = InMemoryReviewPackageSigningKeypairCapability()

    first = derive_calculation_report_provenance_key(bucket_id=_BUCKET_ID, signing_keypair=capability)
    again = derive_calculation_report_provenance_key(bucket_id=_BUCKET_ID, signing_keypair=capability)
    other = derive_calculation_report_provenance_key(bucket_id=_OTHER_BUCKET_ID, signing_keypair=capability)

    assert first.key.get_secret_value() == again.key.get_secret_value()
    assert first.reference_digest("invoice:abc") == again.reference_digest("invoice:abc")
    assert other.key.get_secret_value() != first.key.get_secret_value()
    assert other.reference_digest("invoice:abc") != first.reference_digest("invoice:abc")


def test_the_key_is_redacted_in_every_representation_it_could_be_logged_through() -> None:
    """A key that printed itself would defeat the redaction it exists to provide."""
    derived = _key()

    assert derived.key.get_secret_value().hex() not in repr(derived)
    assert derived.key.get_secret_value().hex() not in str(derived)
    assert derived.key.get_secret_value().hex() not in derived.model_dump_json()


def test_a_known_family_stays_legible_while_its_subject_is_digested() -> None:
    """A reader learns what kind of source a row rests on and nothing about whose."""
    digest = _key().reference_digest(f"perceptor:{_PERCEPTOR_NIF}")

    assert digest.startswith(f"perceptor:{KEYED_DIGEST_ALGORITHM}:")
    assert _PERCEPTOR_NIF not in digest
    assert len(digest.rsplit(":", 1)[1]) == 64


def test_the_digest_covers_the_family_too_so_two_families_never_collide() -> None:
    """Digesting only the subject would make one identifier's digest reusable."""
    provenance_key = _key()

    assert (
        provenance_key.reference_digest("perceptor:X").rsplit(":", 1)[1]
        != (provenance_key.reference_digest("invoice:X").rsplit(":", 1)[1])
    )


@pytest.mark.parametrize(
    "reference",
    [
        _PERCEPTOR_NIF,
        "12345678Z:trailing",
        "Perceptor:12345678Z",
        "PERCEPTOR:12345678Z",
        "perceptor:",
        "0123456789:12345678Z",
    ],
)
def test_a_reference_whose_leading_segment_is_not_a_family_is_digested_whole(reference: str) -> None:
    """Detector teeth: anything but a lowercase family name fails closed.

    Every case here either has no family at all or has one that could itself be
    an identifier. A canonical Spanish tax identifier is uppercased, so no
    identifier can pass the family test -- and that is exactly what these cases
    prove, one shape at a time.
    """
    digest = _key().reference_digest(reference)

    assert digest.split(":", 1)[0] == OPAQUE_PROVENANCE_FAMILY
    assert digest.startswith(f"{OPAQUE_PROVENANCE_FAMILY}:{KEYED_DIGEST_ALGORITHM}:")
    assert _PERCEPTOR_NIF not in digest


def test_a_canonical_content_digest_passes_through_and_anything_else_is_keyed() -> None:
    """The spelling says which construction a verifier must recompute."""
    provenance_key = _key()
    canonical = sha256_hex(b"one source object's facts")

    assert provenance_key.content_digest(canonical) == f"sha256:{canonical}"
    keyed = provenance_key.content_digest("row-7")
    assert keyed.startswith(f"{KEYED_DIGEST_ALGORITHM}:")
    assert "row-7" not in keyed
    # Uppercase hex is not the canonical spelling, so it is keyed rather than
    # passed through as though it were comparable to a stored digest.
    assert provenance_key.content_digest(canonical.upper()).startswith(f"{KEYED_DIGEST_ALGORITHM}:")
