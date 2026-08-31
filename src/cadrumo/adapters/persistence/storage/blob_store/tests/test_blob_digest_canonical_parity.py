"""Blob handle and manifest digests are the canonical content-digest shape.

``BlobManifest`` and ``BlobReference`` restated the lowercase-hex-64 rule in a
module-local helper plus per-model field validators. The restatement agreed
with :data:`~core.identity.ContentDigest` on every malformed value --
uppercase, non-hex, wrong length, and the path-traversal shapes the store must
refuse -- which is exactly what made the one divergence invisible: the
canonical alias strips surrounding whitespace, so a valid digest arriving
padded normalized everywhere else in the codebase and was refused here.

These tests assert both models' verdict against the alias's own verdict on the
same values rather than restating the rule a third time. The path-traversal
cases are carried explicitly: this digest becomes a filesystem path segment,
so "the canonical alias also refuses these" is the property that had to hold
before the local validator could be retired, not an incidental one.

Real blob stores on real files supply the positive control, so the constraint
cannot be tightened past what the store's own writer produces.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ......core.classification.policies import SensitivityClass
from ......core.hashing import sha256_hex
from ......core.identity import ContentDigest
from .._blob_store import BlobManifest, BlobReference, EncryptedBlobStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_VALID_DIGEST = sha256_hex(b"blob-digest-parity")

_MALFORMED = (
    pytest.param("", id="empty"),
    pytest.param("a" * 63, id="too-short"),
    pytest.param("a" * 65, id="too-long"),
    pytest.param("A" * 64, id="uppercase"),
    pytest.param("z" * 64, id="non-hex"),
    pytest.param("g" * 64, id="non-hex-adjacent"),
    # Path-traversal shapes: the digest becomes a filesystem path segment.
    pytest.param("../" + ("a" * 61), id="parent-traversal"),
    pytest.param(("a" * 63) + "/", id="trailing-separator"),
    pytest.param("." + ("a" * 63), id="leading-dot"),
)
_PADDED = (
    pytest.param(f"  {_VALID_DIGEST}  ", id="spaces"),
    pytest.param(f"\t{_VALID_DIGEST}", id="leading-tab"),
    pytest.param(f"{_VALID_DIGEST}\n", id="trailing-newline"),
)

_digest_adapter: TypeAdapter[str] = TypeAdapter(ContentDigest)


def _canonical_verdict(value: str) -> str | None:
    try:
        return _digest_adapter.validate_python(value)
    except ValidationError:
        return None


def _manifest(digest: str, *, ciphertext_digest: str | None = None) -> BlobManifest:
    return BlobManifest(
        sha256_plaintext_hex=digest,
        sha256_ciphertext_hex=ciphertext_digest,
        size_plaintext=1,
        content_type="application/octet-stream",
        classification=SensitivityClass.CORPUS,
    )


@pytest.mark.parametrize("value", _MALFORMED)
def test_the_handle_and_the_canonical_alias_agree_on_refusal(value: str) -> None:
    """``BlobReference`` refuses exactly what the canonical alias refuses.

    Includes the traversal shapes: retiring the local validator is only safe
    because the alias refuses these too, and this is where that is proved.
    """
    assert _canonical_verdict(value) is None
    with pytest.raises(ValidationError):
        BlobReference(sha256_plaintext_hex=value, classification=SensitivityClass.CORPUS)


@pytest.mark.parametrize("value", _MALFORMED)
def test_the_manifest_and_the_canonical_alias_agree_on_refusal(value: str) -> None:
    """Both manifest digest fields refuse what the canonical alias refuses.

    The ciphertext digest is asserted separately because it is nullable, and
    an optional field is the one most easily left without a shape.
    """
    assert _canonical_verdict(value) is None
    with pytest.raises(ValidationError):
        _manifest(value)
    with pytest.raises(ValidationError):
        _manifest(_VALID_DIGEST, ciphertext_digest=value)


@pytest.mark.parametrize("value", _PADDED)
def test_a_padded_digest_normalizes_rather_than_failing(value: str) -> None:
    """The divergent half: padding normalizes on every digest surface.

    The discriminating case. Restoring a hand-written lowercase-hex-64
    validator would leave every refusal test above green and only this red.
    """
    assert _canonical_verdict(value) == _VALID_DIGEST

    assert BlobReference(sha256_plaintext_hex=value, classification=SensitivityClass.CORPUS).sha256_plaintext_hex == (
        _VALID_DIGEST
    )
    assert _manifest(value).sha256_plaintext_hex == _VALID_DIGEST
    assert _manifest(_VALID_DIGEST, ciphertext_digest=value).sha256_ciphertext_hex == _VALID_DIGEST


def test_a_nullable_ciphertext_digest_stays_optional() -> None:
    """Typing the optional field must not make it required."""
    assert _manifest(_VALID_DIGEST).sha256_ciphertext_hex is None


@pytest.mark.parametrize(
    "classification",
    [
        pytest.param(SensitivityClass.CORPUS, id="plaintext-corpus"),
        pytest.param(SensitivityClass.FINANCIAL, id="ciphertext-financial"),
    ],
)
def test_a_real_blob_round_trips_on_both_layouts(
    store: EncryptedBlobStore,
    classification: SensitivityClass,
) -> None:
    """Positive control: the store's own digests satisfy the typed fields.

    Guards against over-tightening. Both layouts are driven because the
    ciphertext path populates the second digest field, which the plaintext
    path leaves ``None``.
    """
    payload = b"blob-digest-parity-payload"
    reference = store.put(payload, classification=classification)

    assert reference.sha256_plaintext_hex == sha256_hex(payload)
    assert store.get(reference) == payload
    manifests = list(store.iter_manifests())
    assert [manifest.sha256_plaintext_hex for manifest in manifests] == [sha256_hex(payload)]
