"""The blob content fan-out matches its declared grammar shape.

``blobs/<sha256[:2]>/<sha256>[.enc]`` is a real, deliberate two-level
hash-prefix tree -- production code already half-documents it (the existing
``blob_manifest`` grammar spells the manifest sibling out) but until now
nothing declared the payload files themselves, and nothing checked a real
produced path against any declaration. A test asserting only the grammar
string would not have caught that gap either; this drives a real
:class:`EncryptedBlobStore` write and checks the real resulting path.
"""

from __future__ import annotations

import pytest

from ......core.classification.policies import SensitivityClass
from ......tests import assert_path_matches_grammar
from .._blob_store import EncryptedBlobStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_a_corpus_blob_lands_at_the_declared_plaintext_shape(store: EncryptedBlobStore) -> None:
    """CORPUS blobs are written verbatim -- the plaintext shape."""
    reference = store.put(b"plaintext corpus payload", classification=SensitivityClass.CORPUS)
    digest = reference.sha256_plaintext_hex

    produced = store.root_dir / "blobs" / digest[:2] / digest
    assert produced.is_file(), "the real write did not land where the store's own accessor expects it"
    assert_path_matches_grammar(key="blob_content_plaintext", root=store.root_dir, produced=produced)


def test_a_financial_blob_lands_at_the_declared_ciphertext_shape(store: EncryptedBlobStore) -> None:
    """Every non-CORPUS class is written encrypted -- the ciphertext shape."""
    reference = store.put(b"financial payload that must be encrypted", classification=SensitivityClass.FINANCIAL)
    digest = reference.sha256_plaintext_hex

    produced = store.root_dir / "blobs" / digest[:2] / f"{digest}.enc"
    assert produced.is_file(), "the real write did not land where the store's own accessor expects it"
    assert_path_matches_grammar(key="blob_content_ciphertext", root=store.root_dir, produced=produced)


def test_a_non_conforming_path_is_rejected_by_the_grammar(store: EncryptedBlobStore) -> None:
    """Positive control: the matcher can still fail.

    Without this, the two tests above would pass identically against a
    matcher that had degraded to always-true. A digest-shaped name sitting
    one directory too shallow -- the fan-out collapsed to one level instead
    of two -- is exactly the drift this grammar exists to catch.
    """
    reference = store.put(b"payload for the negative control", classification=SensitivityClass.CORPUS)
    digest = reference.sha256_plaintext_hex
    flattened = store.root_dir / "blobs" / digest

    with pytest.raises(AssertionError):
        assert_path_matches_grammar(key="blob_content_plaintext", root=store.root_dir, produced=flattened)
