"""A blob manifest's declared plaintext size is enforced on every read.

``BlobManifest.size_plaintext`` is written from the payload at ``put`` time and
carried as forensic metadata, but neither read path compared it with the bytes
it recovered. Rewriting only that one field left a manifest that contradicted
itself while ``get`` still reported success -- so the recorded size and the
returned bytes disagreed, and any consumer that budgets, bounds, or reports on
the declared size got an answer the store had already disproved.

The mismatch is genuinely a *manifest* fault rather than payload corruption:
the digest check that precedes the size check pins the bytes exactly, so once
it passes the only thing left that can disagree is the manifest's own field.
That is why the tests below tamper with nothing but ``size_plaintext``, and
why they cover both layouts -- the plaintext and ciphertext paths recover
their bytes by different routes and each needed the comparison.

Real stores on real files throughout, with a real master key and real AEAD.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ......core.classification.policies import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ...errors import BlobIntegrityError
from ..blob_store import EncryptedBlobStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PAYLOAD = b"thirty-four-bytes-of-blob-payload."
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


def _rewrite_declared_size(path: Path, size: int) -> None:
    """Rewrite only ``payload.size_plaintext``, leaving every other field alone."""
    document = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    document["payload"]["size_plaintext"] = size
    path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)


@pytest.mark.parametrize("classification", _LAYOUTS)
def test_untampered_blob_round_trips(store: EncryptedBlobStore, classification: SensitivityClass) -> None:
    """Positive control on both layouts before any tampering.

    Every refusal below is only evidence if this passes: without it a store
    that failed every read would satisfy the whole module.
    """
    reference = store.put(_PAYLOAD, classification=classification)

    assert store.get(reference) == _PAYLOAD


@pytest.mark.parametrize("classification", _LAYOUTS)
@pytest.mark.parametrize("declared", [0, 1, len(_PAYLOAD) - 1, len(_PAYLOAD) + 7, 10_000])
def test_a_contradicted_size_refuses_the_read(
    store: EncryptedBlobStore,
    classification: SensitivityClass,
    declared: int,
) -> None:
    """Any declared size other than the true one fails the read closed.

    Parametrised over both directions and over zero, because a comparison
    written as a one-sided bound (``>=``, or a truthiness guard that treats 0
    as "unset") would pass a narrower test while leaving half the field
    unchecked.
    """
    reference = store.put(_PAYLOAD, classification=classification)
    assert declared != len(_PAYLOAD)
    _rewrite_declared_size(_manifest_path(store, reference.sha256_plaintext_hex), declared)

    with pytest.raises(BlobIntegrityError):
        store.get(reference)


@pytest.mark.parametrize("classification", _LAYOUTS)
def test_restoring_the_true_size_restores_the_read(
    store: EncryptedBlobStore,
    classification: SensitivityClass,
) -> None:
    """The refusal tracks the contradiction, not the rewrite itself.

    Discriminating: rewriting the manifest file at all changes its bytes and
    its formatting. If the refusal were caused by the rewrite rather than by
    the contradicted value, writing the *correct* size back through the same
    path would still fail -- and this test is what notices.
    """
    reference = store.put(_PAYLOAD, classification=classification)
    manifest_path = _manifest_path(store, reference.sha256_plaintext_hex)

    _rewrite_declared_size(manifest_path, len(_PAYLOAD) + 7)
    with pytest.raises(BlobIntegrityError):
        store.get(reference)

    _rewrite_declared_size(manifest_path, len(_PAYLOAD))
    assert store.get(reference) == _PAYLOAD


def test_an_empty_blob_reads_back_at_its_declared_zero_size(store: EncryptedBlobStore) -> None:
    """A legitimately zero-length blob is not mistaken for an unset size."""
    reference = store.put(b"", classification=SensitivityClass.CORPUS)

    assert store.get(reference) == b""

    _rewrite_declared_size(_manifest_path(store, reference.sha256_plaintext_hex), 1)
    with pytest.raises(BlobIntegrityError):
        store.get(reference)
