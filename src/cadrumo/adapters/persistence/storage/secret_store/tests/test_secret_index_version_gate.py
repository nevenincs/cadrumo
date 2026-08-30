"""The secret-store index format version is gated on every read.

``_SecretIndex.schema_version`` documented itself as a forward-compatibility
marker, and ``_read_index`` model-validated it and then compared it with
nothing. An index claiming any version was accepted, and since every read and
every mutation of the store routes through that one loader, the whole store
operated against a format it had not established it could read.

The mutation half is the sharper one. A put, delete, or rotate rewrites the
*entire* index, so a misread future format would not merely have been read
wrongly -- it would have been written back in whatever shape this build
understood, destroying the newer file. That is why the gate belongs in the
loader, ahead of both, rather than on the read verbs alone.

The format is also enrolled in the persistence compatibility policy as a
DURABLE format, so a future bump is governed by the same upgrade-chain rules
as every other persisted format rather than by one module-local constant.

The marker is required rather than defaulted, which is what lets the gate see
an index file that simply omits it. Under a default such a file hydrated at
the current version and satisfied the comparison, so the one document the gate
most needed to catch was the one it could not. The single legitimate source of
an unstamped index -- an absent file, which create-on-first-access materialises
fresh -- stamps the version explicitly instead, and is asserted here to still
work.

Real encrypted stores over real blob stores and a real master key; only the
index's own version field is ever rewritten or removed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.compatibility_lifecycle import PERSISTED_FORMATS, PersistedFormatClass
from ......core.classification import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ...errors import EnvelopeVersionError, StorageValidationError
from ..store import SECRET_INDEX_SCHEMA_VERSION, SecretRecord, SecretStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_KEY = "aeat:test:index-version-gate"
_VALUE = b"index-version-gate-secret"
_CREATED_AT = datetime(2026, 5, 28, 11, 55, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2099, 5, 28, 11, 55, 0, tzinfo=UTC)


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


def _rewrite_index_version(path: Path, version: int) -> None:
    """Rewrite only ``schema_version``, leaving every entry untouched."""
    document = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    document["schema_version"] = version
    path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)


def _strip_index_version(path: Path) -> None:
    """Delete ``schema_version`` from the stored index, leaving entries untouched."""
    document = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    del document["schema_version"]
    assert "schema_version" not in document, "the fixture must actually remove the marker"
    path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)


def test_a_written_index_declares_the_supported_version(store: SecretStore) -> None:
    """Positive control: the writer stamps the one supported version.

    Also the index's strict round trip through the real blob store and master
    key. ``entries`` is the record's only defaultable field and it is carried
    populated here rather than empty, so a save-drops-entries regression could
    not pass as a legitimately empty store.
    """
    store.put(_record())

    document = json.loads(_index_path(store).read_text(encoding=UTF_8_ENCODING))

    assert document["schema_version"] == SECRET_INDEX_SCHEMA_VERSION
    assert document["entries"], "the round trip must carry a populated entry map"
    assert store.get(_KEY).value == _VALUE
    assert store.get(_KEY).metadata == {"issued_by": "test-suite"}
    assert store.get(_KEY).expires_at == _EXPIRES_AT


def test_an_index_omitting_the_version_refuses_reads(store: SecretStore) -> None:
    """Anti-tautology proof: strip the marker from a real index and read it back.

    This is the payload the equality gate could not see while the field
    defaulted: the document hydrated at the current version, satisfied the
    comparison, and the store proceeded against a file that never declared
    what format it was.
    """
    store.put(_record())
    _strip_index_version(_index_path(store))

    with pytest.raises(StorageValidationError):
        store.get(_KEY)


def test_an_index_omitting_the_version_refuses_mutations_without_rewriting(store: SecretStore) -> None:
    """The omission must also refuse ahead of the whole-index rewrite.

    Same reasoning as the future-version case below it, and it needs asserting
    separately because the two refusals fire at different points: the version
    mismatch at the explicit gate, the omission at the parse that builds the
    record the gate reads. A mutation that refused only after rewriting would
    have destroyed the file it could not interpret.
    """
    store.put(_record())
    path = _index_path(store)
    _strip_index_version(path)
    before = path.read_bytes()

    with pytest.raises(StorageValidationError):
        store.put(_record(), overwrite=True)
    with pytest.raises(StorageValidationError):
        store.delete(_KEY)

    assert path.read_bytes() == before


def test_an_absent_index_still_materialises_a_fresh_store(tmp_path: Path, store: SecretStore) -> None:
    """Create-on-first-access survives the marker becoming required.

    An absent index file is a store that has never been written, not a
    document making a version claim, so it must still materialise. The
    assertions cover both halves: reads answer empty before anything is
    written, and the first write produces a stamped index at the current
    version.
    """
    del tmp_path
    assert not _index_path(store).exists()
    assert list(store.list_digests()) == []

    store.put(_record())

    document = json.loads(_index_path(store).read_text(encoding=UTF_8_ENCODING))
    assert document["schema_version"] == SECRET_INDEX_SCHEMA_VERSION
    assert store.get(_KEY).value == _VALUE


@pytest.mark.parametrize("version", [SECRET_INDEX_SCHEMA_VERSION + 1, 2, 999])
def test_a_future_index_version_refuses_reads(store: SecretStore, version: int) -> None:
    """A read against an index format this build cannot interpret fails closed."""
    store.put(_record())
    _rewrite_index_version(_index_path(store), version)

    with pytest.raises(EnvelopeVersionError):
        store.get(_KEY)


def test_a_future_index_version_refuses_mutations_without_rewriting(store: SecretStore) -> None:
    """The sharper half: a mutation refuses rather than overwriting the newer file.

    Discriminating. A gate placed on the read verbs alone would satisfy the
    test above while leaving ``put`` free to rewrite the whole index in this
    build's shape -- turning a recoverable version mismatch into the
    destruction of the newer file. Asserting the bytes are unchanged is what
    separates "refused" from "refused after writing".
    """
    store.put(_record())
    path = _index_path(store)
    _rewrite_index_version(path, SECRET_INDEX_SCHEMA_VERSION + 1)
    before = path.read_bytes()

    with pytest.raises(EnvelopeVersionError):
        store.put(_record(), overwrite=True)
    with pytest.raises(EnvelopeVersionError):
        store.delete(_KEY)

    assert path.read_bytes() == before


def test_restoring_the_supported_version_restores_the_store(store: SecretStore) -> None:
    """The refusal tracks the version, not the fact of a rewrite."""
    store.put(_record())
    path = _index_path(store)

    _rewrite_index_version(path, SECRET_INDEX_SCHEMA_VERSION + 1)
    with pytest.raises(EnvelopeVersionError):
        store.get(_KEY)

    _rewrite_index_version(path, SECRET_INDEX_SCHEMA_VERSION)
    assert store.get(_KEY).value == _VALUE


def test_the_index_format_is_enrolled_as_durable() -> None:
    """The format appears in the closed persisted-format inventory.

    The version constant alone governs only this build. Enrollment is what
    binds a future bump to the project's upgrade-chain rules, and DURABLE is
    the honest class: no path exists to rebuild the digest-to-blob map, so
    losing the index strands every secret it addressed.
    """
    assert PERSISTED_FORMATS["secret_index"] is PersistedFormatClass.DURABLE
