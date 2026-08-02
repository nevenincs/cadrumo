"""The class of a secret is stated three times and all three must agree.

One stored secret carries its sensitivity class on the index row that locates
it, on the envelope sealed together with it, and on the record itself. Only
the first two were ever compared -- and only indirectly, by the blob store's
own manifest gate -- so relabelling the index and the manifest *together*
satisfied every check in the chain while the encrypted bytes still held a
SECRET record. ``get`` returned it.

That combined relabel is the case under test, and it is the only one that
matters: changing the index alone was already refused by the manifest gate,
so a test that did so would pass without the triad check existing. The record
inside the ciphertext is the one statement an editor cannot reach without the
key, which is why it is the authority the other two must match.

Separately, ``_SecretIndexEntry.classification`` accepted the whole
``SensitivityClass`` enum while ``SecretRecord`` accepted only SECRET or
SESSION -- so the index could name a class no record in this store can ever
have, and the blob layout was routed from that value. Both now enforce the
same closed set.

Real encrypted stores over real blob stores and a real master key; the
encrypted bytes are never touched.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ......core.classification import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ......tests.master_key import EphemeralMasterKeyProvider
from ...blob_store import EncryptedBlobStore
from ...crypto import KEY_SIZE
from ...errors import StorageValidationError
from .._secret_store import (
    SECRET_STORE_CLASSES,
    SecretRecord,
    SecretStore,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_KEY = "aeat:test:classification-triad"
_VALUE = b"classification-triad-secret"
_CREATED_AT = datetime(2026, 5, 28, 11, 55, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2099, 5, 28, 11, 55, 0, tzinfo=UTC)

_FOREIGN_CLASSES = tuple(
    pytest.param(member, id=member.value) for member in SensitivityClass if member not in SECRET_STORE_CLASSES
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SecretStore]:
    provider = EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE))
    blob_store = EncryptedBlobStore(root_dir=tmp_path / "blobs", master_key_provider=provider)
    yield SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )


def _record(classification: SensitivityClass = SensitivityClass.SECRET) -> SecretRecord:
    return SecretRecord(
        key=_KEY,
        value=_VALUE,
        classification=classification,
        metadata={"issued_by": "test-suite"},
        created_at=_CREATED_AT,
        expires_at=_EXPIRES_AT,
    )


def _index_path(store: SecretStore) -> Path:
    return store.store_dir / "index.json"


def _manifest_path(store: SecretStore, blob_digest: str) -> Path:
    return store._blob_store.root_dir / "blobs" / blob_digest[:2] / f"{blob_digest}.manifest.json"


def _relabel_index_and_manifest(store: SecretStore, classification: SensitivityClass) -> None:
    """Retag the index row and its blob manifest, leaving ciphertext untouched.

    Both layers move together on purpose: the blob store's manifest gate
    already refuses an index-only edit, so only the coordinated relabel
    reaches the check under test.
    """
    index_path = _index_path(store)
    document = json.loads(index_path.read_text(encoding=UTF_8_ENCODING))
    entries = document["entries"]
    assert isinstance(entries, dict)
    (key,) = entries
    blob_digest = entries[key]["blob_sha256_plaintext_hex"]
    entries[key]["classification"] = classification.value
    index_path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)

    manifest_path = _manifest_path(store, blob_digest)
    manifest = json.loads(manifest_path.read_text(encoding=UTF_8_ENCODING))
    manifest["classification"] = classification.value
    manifest["payload"]["classification"] = classification.value
    manifest_path.write_text(json.dumps(manifest), encoding=UTF_8_ENCODING)


@pytest.mark.parametrize(
    "classification",
    [pytest.param(member, id=member.value) for member in sorted(SECRET_STORE_CLASSES)],
)
def test_an_untampered_record_round_trips(store: SecretStore, classification: SensitivityClass) -> None:
    """Positive control on both permitted classes."""
    store.put(_record(classification))

    loaded = store.get(_KEY)

    assert loaded.value == _VALUE
    assert loaded.classification is classification


def test_a_coordinated_relabel_to_the_other_permitted_class_is_refused(store: SecretStore) -> None:
    """SECRET relabelled as SESSION is refused even though both are permitted.

    The discriminating case. A guard written as "the index must name a class
    this store allows" would pass here -- SESSION is allowed -- while the
    ciphertext still holds a SECRET record. Only comparing the three
    statements with each other catches it, and the substitution between two
    permitted classes is the one an attacker would actually reach for, since
    it survives every closed-set check.
    """
    store.put(_record(SensitivityClass.SECRET))
    _relabel_index_and_manifest(store, SensitivityClass.SESSION)

    with pytest.raises(StorageValidationError):
        store.get(_KEY)


@pytest.mark.parametrize("classification", _FOREIGN_CLASSES)
def test_a_relabel_to_a_class_this_store_never_persists_is_refused(
    store: SecretStore,
    classification: SensitivityClass,
) -> None:
    """A class outside the store's closed set is refused at the index boundary."""
    store.put(_record(SensitivityClass.SECRET))
    _relabel_index_and_manifest(store, classification)

    with pytest.raises((StorageValidationError, ValidationError)):
        store.get(_KEY)


@pytest.mark.parametrize("classification", _FOREIGN_CLASSES)
def test_the_index_row_holds_the_same_closed_set_as_the_record(classification: SensitivityClass) -> None:
    """The index cannot name a class no record in this store can carry.

    Asserted on the model directly, not only through a tampered file: the
    index row is constructed on the write path too, and a closed set enforced
    only at read would let a future writer persist the mismatch.
    """
    from .._secret_store import _SecretIndexEntry

    with pytest.raises((StorageValidationError, ValidationError)):
        _SecretIndexEntry(
            digest_hex="a" * 64,
            blob_sha256_plaintext_hex="b" * 64,
            classification=classification,
        )


def test_restoring_the_true_class_restores_the_store(store: SecretStore) -> None:
    """The refusal tracks the disagreement, not the fact of a rewrite."""
    store.put(_record(SensitivityClass.SECRET))

    _relabel_index_and_manifest(store, SensitivityClass.SESSION)
    with pytest.raises(StorageValidationError):
        store.get(_KEY)

    _relabel_index_and_manifest(store, SensitivityClass.SECRET)
    assert store.get(_KEY).value == _VALUE
