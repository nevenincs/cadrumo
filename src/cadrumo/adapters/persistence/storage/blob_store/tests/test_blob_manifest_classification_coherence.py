"""A blob manifest states its classification twice; the two must agree.

The classification appears on the envelope that wraps the manifest and again
on the payload inside, and the two steered different decisions. Retrieval
routed the on-disk layout from the *payload* value, the envelope loader gated
the *outer* value against the caller's expectation, and key rotation
reconstructed the outer value from the nested one when it rewrote the file.
Nothing compared them.

Editing the nested field alone therefore split the store's own view of one
blob three ways: iteration reported a CORPUS blob that carried a wrapped DEK,
``get`` on a still-valid reference followed the plaintext layout and could not
find the payload, and rotation counted the manifest as rotated while writing
the tampered value outward -- after which the valid reference failed for a
different reason again.

Routing all three surfaces through one coherence gate is what these tests pin.
The rotation case is the reason the gate sits inside the shared iteration
helper rather than in the read path: rotation never calls ``get``, and a check
placed only there would have left the one surface that makes the corruption
permanent unguarded.

Real stores, real master keys, real AEAD. Only the single nested field is ever
rewritten.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest

from ......core.classification.policies import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ......tests.master_key import EphemeralMasterKeyProvider
from ...crypto.aead import KEY_SIZE
from ...errors import BlobIntegrityError
from ..blob_store import BlobReference, EncryptedBlobStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PAYLOAD = b"financial-blob-payload-bytes"
_MASTER_KEY = secrets.token_bytes(KEY_SIZE)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[EncryptedBlobStore]:
    provider = EphemeralMasterKeyProvider(key=_MASTER_KEY)
    yield EncryptedBlobStore(root_dir=tmp_path / "blob-store", master_key_provider=provider)


def _manifest_path(store: EncryptedBlobStore, digest: str) -> Path:
    # "blobs" is the independent oracle for the ``blob_manifest`` grammar
    # (``<root>/blobs/<sha[:2]>/<sha>.manifest.json``), anchored at
    # ``store.root_dir`` (the ``blob_store_root`` this store was constructed
    # with) -- not the storage_root-anchored "blobs" category. Keep the
    # literal; it locates the real on-disk file this module tampers with.
    return store.root_dir / "blobs" / digest[:2] / f"{digest}.manifest.json"


def _retag_nested_classification(path: Path, classification: SensitivityClass) -> None:
    """Rewrite only ``payload.classification``, leaving the envelope's alone."""
    document = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    document["payload"]["classification"] = classification.value
    path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)


def _retag_outer_classification(path: Path, classification: SensitivityClass) -> None:
    """Rewrite only the envelope's classification, leaving the payload's alone."""
    document = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    document["classification"] = classification.value
    path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)


def _seed(store: EncryptedBlobStore) -> BlobReference:
    return store.put(_PAYLOAD, classification=SensitivityClass.FINANCIAL)


def test_a_coherent_manifest_reads_iterates_and_rotates(store: EncryptedBlobStore) -> None:
    """Positive control across all three guarded surfaces.

    Each refusal below is only evidence against this baseline; without it a
    store that refused everything would satisfy the module.
    """
    reference = _seed(store)

    assert store.get(reference) == _PAYLOAD
    assert [manifest.classification for manifest in store.iter_manifests()] == [SensitivityClass.FINANCIAL]
    rotated, skipped, errors = store.rotate_master_key(
        old_master_key_provider=EphemeralMasterKeyProvider(key=_MASTER_KEY),
        new_master_key_provider=EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE)),
    )
    assert (rotated, skipped, errors) == (1, 0, 0)


def test_a_nested_retag_refuses_direct_retrieval(store: EncryptedBlobStore) -> None:
    """``get`` refuses rather than following the layout the tampered field names.

    Previously this surfaced as ``BlobNotFoundError`` -- the read followed the
    plaintext layout for a blob written as ciphertext and simply found no
    file. That reported a *missing* blob for one that is present and intact,
    which is the wrong diagnosis as well as the wrong verdict.
    """
    reference = _seed(store)
    _retag_nested_classification(_manifest_path(store, reference.sha256_plaintext_hex), SensitivityClass.CORPUS)

    with pytest.raises(BlobIntegrityError):
        store.get(reference)


def test_a_nested_retag_refuses_iteration(store: EncryptedBlobStore) -> None:
    """Iteration fails closed instead of yielding a self-contradicting manifest.

    The yielded record previously claimed CORPUS while carrying a wrapped DEK
    -- a combination the writer cannot produce -- so any audit consuming this
    surface saw a blob that does not exist as described.
    """
    reference = _seed(store)
    _retag_nested_classification(_manifest_path(store, reference.sha256_plaintext_hex), SensitivityClass.CORPUS)

    with pytest.raises(BlobIntegrityError):
        list(store.iter_manifests())


def test_a_nested_retag_refuses_rotation_before_rewriting(store: EncryptedBlobStore) -> None:
    """Rotation refuses, and leaves the manifest exactly as it found it.

    The discriminating case for placing the gate in the shared iteration
    helper. Rotation reconstructs the outer classification from the nested
    value, so without the gate it reported ``(1, 0, 0)`` and propagated the
    tampered value outward -- making a recoverable single-field edit permanent.
    Asserting the bytes are untouched is what separates "refused" from
    "refused after writing".
    """
    reference = _seed(store)
    manifest_path = _manifest_path(store, reference.sha256_plaintext_hex)
    _retag_nested_classification(manifest_path, SensitivityClass.CORPUS)
    before = manifest_path.read_bytes()

    with pytest.raises(BlobIntegrityError):
        store.rotate_master_key(
            old_master_key_provider=EphemeralMasterKeyProvider(key=_MASTER_KEY),
            new_master_key_provider=EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE)),
        )

    assert manifest_path.read_bytes() == before


def test_an_outer_retag_is_refused_symmetrically(store: EncryptedBlobStore) -> None:
    """The gate compares the two fields; it does not privilege one of them.

    Rewriting the *outer* value is the mirror of the cases above. A check
    written as "the payload must be X" for some independently-derived X would
    pass those and fail here, so this is what pins it as an equality between
    the manifest's own two statements.
    """
    reference = _seed(store)
    _retag_outer_classification(_manifest_path(store, reference.sha256_plaintext_hex), SensitivityClass.AUDIT)

    with pytest.raises(BlobIntegrityError):
        list(store.iter_manifests())


def test_restoring_agreement_restores_every_surface(store: EncryptedBlobStore) -> None:
    """The refusal tracks the disagreement, not the fact of a rewrite.

    Rewriting the manifest at all changes its bytes and formatting. Writing
    the original classification back through the same helper must restore
    normal service, or the refusals above would be evidence of nothing more
    than a byte-fragile reader.
    """
    reference = _seed(store)
    manifest_path = _manifest_path(store, reference.sha256_plaintext_hex)

    _retag_nested_classification(manifest_path, SensitivityClass.CORPUS)
    with pytest.raises(BlobIntegrityError):
        store.get(reference)

    _retag_nested_classification(manifest_path, SensitivityClass.FINANCIAL)
    assert store.get(reference) == _PAYLOAD
    assert [manifest.classification for manifest in store.iter_manifests()] == [SensitivityClass.FINANCIAL]
