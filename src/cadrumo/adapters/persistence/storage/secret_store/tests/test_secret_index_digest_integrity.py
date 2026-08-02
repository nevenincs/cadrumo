"""Secret-index entries cannot disagree with the digest they are filed under.

The index maps an HMAC lookup digest to an entry, and the entry restates that
same digest in ``digest_hex``. Every operation -- get, delete, list --
addresses the record by the *mapping key*, so the restatement was read by
nothing: it could disagree with its own key indefinitely and ``get`` returned
the original secret exactly as before. A field that can be contradicted
without consequence is not an integrity field.

The tampering under test is deliberately a *well-formed* digest that is simply
the wrong one. That distinction is the whole point of this module: typing the
field through :data:`~core.identity.ContentDigest` already refuses garbage, so
a test that rewrote ``digest_hex`` to ``"z" * 64`` would pass on the field's
shape alone and prove nothing about the key/value agreement. It was verified
empirically -- with the agreement check removed, the malformed-value form of
this test still passed.

The mapping keys need no separate shape check. Once agreement holds, the key
IS the entry's validated canonical digest; a malformed key either differs from
its entry -- caught by the agreement check -- or matches it, in which case the
entry failed field validation first. ``test_a_malformed_key_is_refused_by_the
_agreement_check`` pins that reasoning so a future reader does not add the
unreachable branch.

Real encrypted stores over real blob stores and a real master key.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.classification import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ......core.hashing import sha256_hex
from ......tests.master_key import EphemeralMasterKeyProvider
from ...blob_store import EncryptedBlobStore
from ...crypto import KEY_SIZE
from ...errors import StorageValidationError
from .._secret_store import SecretRecord, SecretStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_KEY = "aeat:test:index-digest-integrity"
_VALUE = b"index-digest-integrity-secret"
_CREATED_AT = datetime(2026, 5, 28, 11, 55, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2099, 5, 28, 11, 55, 0, tzinfo=UTC)

#: A perfectly well-formed digest that is simply not this entry's key. The
#: canonical field type accepts it, so only the agreement check can refuse it.
_WRONG_BUT_WELL_FORMED = sha256_hex(b"a different natural key entirely")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SecretStore]:
    provider = EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE))
    blob_store = EncryptedBlobStore(root_dir=tmp_path / "blobs", master_key_provider=provider)
    yield SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )


def _record() -> SecretRecord:
    return SecretRecord(
        key=_KEY,
        value=_VALUE,
        classification=SensitivityClass.SECRET,
        metadata={"issued_by": "test-suite"},
        created_at=_CREATED_AT,
        expires_at=_EXPIRES_AT,
    )


def _index_path(store: SecretStore) -> Path:
    return store.store_dir / "index.json"


def _load(path: Path) -> tuple[dict[str, object], dict[str, dict[str, object]], str]:
    """Return ``(document, entries, sole_key)`` for a single-entry index."""
    document = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    entries = document["entries"]
    assert isinstance(entries, dict)
    (key,) = entries
    return document, entries, key


def _save(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)


def test_an_untampered_store_round_trips(store: SecretStore) -> None:
    """Positive control: the writer files each entry under its own digest."""
    store.put(_record())

    _, entries, key = _load(_index_path(store))

    assert entries[key]["digest_hex"] == key
    assert store.get(_KEY).value == _VALUE
    assert key != _WRONG_BUT_WELL_FORMED


def test_a_wrong_but_well_formed_entry_digest_refuses_reads(store: SecretStore) -> None:
    """The key/value disagreement is refused on its own merits.

    The discriminating case for this finding: the replacement is a real
    SHA-256 hex digest, so the field's canonical type accepts it and only the
    agreement check can object. Previously ``get`` returned the original
    secret, because the lookup never consulted the field at all.
    """
    store.put(_record())
    path = _index_path(store)
    document, entries, key = _load(path)
    entries[key]["digest_hex"] = _WRONG_BUT_WELL_FORMED
    _save(path, document)

    with pytest.raises(StorageValidationError):
        store.get(_KEY)


def test_a_disagreeing_entry_digest_refuses_mutations_without_rewriting(store: SecretStore) -> None:
    """A mutation refuses rather than laundering the disagreement back to disk.

    A check placed on the read verbs alone would satisfy the test above while
    leaving ``put`` free to rewrite the index, silently replacing the tampered
    value and erasing the evidence that anything had been edited.
    """
    store.put(_record())
    path = _index_path(store)
    document, entries, key = _load(path)
    entries[key]["digest_hex"] = _WRONG_BUT_WELL_FORMED
    _save(path, document)
    before = path.read_bytes()

    with pytest.raises(StorageValidationError):
        store.put(_record(), overwrite=True)
    with pytest.raises(StorageValidationError):
        store.delete(_KEY)

    assert path.read_bytes() == before


def test_a_malformed_key_is_refused_by_the_agreement_check(store: SecretStore) -> None:
    """A malformed mapping key needs no separate shape check to be refused.

    Re-filing the entry under a non-hex key while leaving ``digest_hex`` at
    its true value makes the two disagree, so the agreement check catches it.
    The other arrangement -- a malformed key whose entry field matches it --
    cannot survive field validation, because ``digest_hex`` is a canonical
    digest. Together those cover the space, which is why no key-shape branch
    exists: one would be unreachable rather than defensive.
    """
    store.put(_record())
    path = _index_path(store)
    document, entries, key = _load(path)
    entries["z" * 64] = entries.pop(key)
    _save(path, document)

    with pytest.raises(StorageValidationError):
        store.get(_KEY)


def test_restoring_agreement_restores_the_store(store: SecretStore) -> None:
    """The refusal tracks the disagreement, not the fact of a rewrite.

    Rewriting the index at all changes its bytes and formatting; writing the
    original digest back through the same helper must restore normal service,
    or the refusals above would prove only that the reader is byte-fragile.
    """
    store.put(_record())
    path = _index_path(store)
    document, entries, key = _load(path)

    entries[key]["digest_hex"] = _WRONG_BUT_WELL_FORMED
    _save(path, document)
    with pytest.raises(StorageValidationError):
        store.get(_KEY)

    entries[key]["digest_hex"] = key
    _save(path, document)
    assert store.get(_KEY).value == _VALUE
