"""A blob manifest's embedded digest must be the one its filename names.

The store is content-addressed: a manifest lives at
``blobs/<hex[:2]>/<hex>.manifest.json``, and the payload paths are derived
from the digest the manifest *carries* rather than the one in its filename.
Nothing compared the two.

Rewriting blob A's embedded digest to blob B's therefore re-pointed the read
without any surface objecting: ``get`` on A's original reference located A's
manifest by its untouched filename, followed the embedded digest, and returned
**B's bytes**. Iteration yielded B's identity for both manifest files. Every
digest involved was real and every payload reproduced its own hash, so no
existing check -- the plaintext digest comparison, the ciphertext digest
comparison, the declared size, the classification coherence -- could see it.
That is what makes this the sharpest of the manifest findings: a caller who
asks for one document is handed a different one under its own name.

Both read surfaces now supply the digest they legitimately know -- the
caller's requested digest for a direct read, the filename for a scan -- to one
shared binding check.

Real stores on real files, with a real master key and real AEAD; only the
embedded digest is ever rewritten.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

import pytest

from ......core.classification import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ......core.hashing import sha256_hex
from ......tests.master_key import EphemeralMasterKeyProvider
from ...crypto.aead import KEY_SIZE
from ...errors import BlobIntegrityError
from .._blob_store import BlobReference, EncryptedBlobStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PAYLOAD_A = b"blob-A-payload-bytes-for-filename-binding"
_PAYLOAD_B = b"blob-B-payload-bytes-for-filename-binding-and-longer"
_LAYOUTS = (
    pytest.param(SensitivityClass.CORPUS, id="plaintext-corpus"),
    pytest.param(SensitivityClass.FINANCIAL, id="ciphertext-financial"),
)


def _manifest_path(store: EncryptedBlobStore, digest: str) -> Path:
    # "blobs" is the independent oracle for the ``blob_manifest`` grammar
    # (``<root>/blobs/<sha[:2]>/<sha>.manifest.json``), anchored at
    # ``store.root_dir`` (the ``blob_store_root`` this store was constructed
    # with) -- not the storage_root-anchored "blobs" category. Keep the
    # literal; it locates the real on-disk file this module tampers with.
    return store.root_dir / "blobs" / digest[:2] / f"{digest}.manifest.json"


def _repoint_embedded_digest(store: EncryptedBlobStore, *, at: str, to: str, size: int) -> None:
    """Rewrite one manifest's embedded plaintext digest, leaving its filename alone."""
    path = _manifest_path(store, at)
    document = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    document["payload"]["sha256_plaintext_hex"] = to
    document["payload"]["size_plaintext"] = size
    path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)


def _seed_two_blobs(
    store: EncryptedBlobStore,
    classification: SensitivityClass,
) -> tuple[BlobReference, BlobReference]:
    return (
        store.put(_PAYLOAD_A, classification=classification),
        store.put(_PAYLOAD_B, classification=classification),
    )


@pytest.mark.parametrize("classification", _LAYOUTS)
def test_two_untampered_blobs_read_back_distinctly(
    store: EncryptedBlobStore,
    classification: SensitivityClass,
) -> None:
    """Positive control: each reference returns its own bytes."""
    reference_a, reference_b = _seed_two_blobs(store, classification)

    assert store.get(reference_a) == _PAYLOAD_A
    assert store.get(reference_b) == _PAYLOAD_B
    assert reference_a.sha256_plaintext_hex == sha256_hex(_PAYLOAD_A)


@pytest.mark.parametrize("classification", _LAYOUTS)
def test_a_substituted_embedded_digest_refuses_the_read(
    store: EncryptedBlobStore,
    classification: SensitivityClass,
) -> None:
    """``get(A)`` refuses rather than returning B's bytes under A's name.

    The discriminating case. Every pre-existing integrity check passes here --
    B's payload reproduces B's digest and B's declared size -- so only the
    filename binding can object. Driven on both layouts because the plaintext
    and ciphertext read paths derive their payload filenames separately.
    """
    reference_a, reference_b = _seed_two_blobs(store, classification)
    _repoint_embedded_digest(
        store,
        at=reference_a.sha256_plaintext_hex,
        to=reference_b.sha256_plaintext_hex,
        size=len(_PAYLOAD_B),
    )

    with pytest.raises(BlobIntegrityError):
        store.get(reference_a)


@pytest.mark.parametrize("classification", _LAYOUTS)
def test_a_substituted_embedded_digest_refuses_iteration(
    store: EncryptedBlobStore,
    classification: SensitivityClass,
) -> None:
    """Iteration fails closed instead of reporting one identity twice.

    Asserted separately from the read: iteration has no requested digest and
    must derive the expectation from the filename, so a fix applied only to
    ``get`` would leave the enumeration -- the surface an audit consumes --
    still listing two files as one blob.
    """
    reference_a, reference_b = _seed_two_blobs(store, classification)
    _repoint_embedded_digest(
        store,
        at=reference_a.sha256_plaintext_hex,
        to=reference_b.sha256_plaintext_hex,
        size=len(_PAYLOAD_B),
    )

    with pytest.raises(BlobIntegrityError):
        list(store.iter_manifests())


@pytest.mark.parametrize("classification", _LAYOUTS)
def test_rotation_refuses_the_substituted_manifest_without_rewriting(
    store: EncryptedBlobStore,
    classification: SensitivityClass,
) -> None:
    """Key rotation, which walks the same scan, refuses before rewriting.

    Rotation re-writes every manifest it visits, so a substitution it did not
    detect would be re-signed under the new key and made permanent.
    """
    reference_a, reference_b = _seed_two_blobs(store, classification)
    _repoint_embedded_digest(
        store,
        at=reference_a.sha256_plaintext_hex,
        to=reference_b.sha256_plaintext_hex,
        size=len(_PAYLOAD_B),
    )
    path = _manifest_path(store, reference_a.sha256_plaintext_hex)
    before = path.read_bytes()

    with pytest.raises(BlobIntegrityError):
        store.rotate_master_key(
            old_master_key_provider=EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE)),
            new_master_key_provider=EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE)),
        )

    assert path.read_bytes() == before


def test_restoring_the_true_digest_restores_both_surfaces(store: EncryptedBlobStore) -> None:
    """The refusal tracks the substitution, not the fact of a rewrite."""
    reference_a, reference_b = _seed_two_blobs(store, SensitivityClass.FINANCIAL)

    _repoint_embedded_digest(
        store,
        at=reference_a.sha256_plaintext_hex,
        to=reference_b.sha256_plaintext_hex,
        size=len(_PAYLOAD_B),
    )
    with pytest.raises(BlobIntegrityError):
        store.get(reference_a)

    _repoint_embedded_digest(
        store,
        at=reference_a.sha256_plaintext_hex,
        to=reference_a.sha256_plaintext_hex,
        size=len(_PAYLOAD_A),
    )
    assert store.get(reference_a) == _PAYLOAD_A
    assert {manifest.sha256_plaintext_hex for manifest in store.iter_manifests()} == {
        reference_a.sha256_plaintext_hex,
        reference_b.sha256_plaintext_hex,
    }
