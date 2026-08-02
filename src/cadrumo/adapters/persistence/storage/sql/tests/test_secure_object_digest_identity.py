"""Secure-object digest columns carry the canonical content-digest shape.

Every digest-shaped field on the SQL secure-object records is written by
``core.hashing.sha256_hex`` (directly, or through ``derive_revision_id``), so
each one is a :data:`~core.identity.ContentDigest`. Before these records were
typed through that alias they carried a length-only ``min_length=64,
max_length=64`` constraint, which admits ``"z" * 64`` and ``"A" * 64`` -- values
no digest function can produce. A malformed digest therefore reached a
persisted record and surfaced only when a later verification pass recomputed
the hash and disagreed.

These tests pin the refusal at the record boundary against the canonical alias
rather than against a hand-copied constraint: the parity assertion compares the
records' verdict with :data:`ContentDigest`'s own verdict on the same values, so
a future widening of either side fails here rather than drifting apart
silently. The valid round-trip runs over real SQLite, a real
``EphemeralMasterKeyProvider``, and real AEAD -- the positive control that
proves the refusals are a constraint on malformed input and not a broken
fixture.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from pydantic import TypeAdapter, ValidationError

from ......core.identity import ContentDigest
from ......tests.master_key import EphemeralMasterKeyProvider
from .._secure_object_records import SecureObjectRawRow, SecureObjectRecord
from ._secure_objects_support import (
    UTC,
    Base,
    Path,
    SecureObjectRepository,
    SensitivityClass,
    Settings,
    create_engine_from_settings,
    datetime,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo.digest.identity"
_KEY = "digest-identity-subject"
_PAYLOAD = b"digest-identity-payload"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)

_VALID_DIGEST = "a" * 64
#: 64 characters, so a length-only constraint admits both; neither is hex.
_NON_HEX = "z" * 64
_UPPERCASE = "A" * 64
_MALFORMED = (_NON_HEX, _UPPERCASE)

_RAW_ROW_DIGEST_FIELDS = (
    "revision_id",
    "previous_revision_id",
    "previous_payload_hash",
    "payload_hash",
    "ciphertext_hash",
)

_digest_adapter: TypeAdapter[str] = TypeAdapter(ContentDigest)


def _accepts_digest(value: str) -> bool:
    """Return whether the canonical alias admits ``value``."""
    try:
        _digest_adapter.validate_python(value)
    except ValidationError:
        return False
    return True


def _record(**overrides: object) -> SecureObjectRecord:
    payload: dict[str, object] = {
        "namespace": _NAMESPACE,
        "object_key": b"object-key",
        "classification": SensitivityClass.FINANCIAL,
        "schema_version": 1,
        "written_at": _NOW,
        "payload": _PAYLOAD,
        "revision_id": _VALID_DIGEST,
    }
    payload.update(overrides)
    return SecureObjectRecord.model_validate(payload)


def _raw_row(**overrides: object) -> SecureObjectRawRow:
    payload: dict[str, object] = {
        "row_id": 1,
        "namespace": _NAMESPACE,
        "object_key": b"object-key",
        "classification": SensitivityClass.FINANCIAL.value,
        "schema_version": 1,
        "written_at": _NOW,
        "payload": _PAYLOAD,
    }
    payload.update(overrides)
    return SecureObjectRawRow.model_validate(payload)


@contextmanager
def _repo_at(db_path: Path) -> Iterator[SecureObjectRepository]:
    engine = create_engine_from_settings(Settings(cadrumo_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        yield SecureObjectRepository(engine=engine)
    finally:
        engine.dispose()


@pytest.mark.parametrize("malformed", _MALFORMED)
def test_canonical_alias_refuses_the_malformed_digests_under_test(malformed: str) -> None:
    """Positive control on the instrument: the alias refuses both values.

    Without this, a records-level refusal could be caused by anything at all --
    a broken fixture, an unrelated required field -- and the parity assertions
    below would read as agreement when the two sides were simply both broken.
    """
    assert not _accepts_digest(malformed)
    assert _accepts_digest(_VALID_DIGEST)


@pytest.mark.parametrize("malformed", _MALFORMED)
def test_secure_object_record_revision_id_matches_canonical_verdict(malformed: str) -> None:
    """``SecureObjectRecord.revision_id`` refuses exactly what the alias refuses."""
    with pytest.raises(ValidationError):
        _record(revision_id=malformed)

    assert _record(revision_id=_VALID_DIGEST).revision_id == _VALID_DIGEST


@pytest.mark.parametrize("field", _RAW_ROW_DIGEST_FIELDS)
@pytest.mark.parametrize("malformed", _MALFORMED)
def test_raw_row_digest_fields_match_canonical_verdict(field: str, malformed: str) -> None:
    """Every optional digest column on the raw row refuses malformed values.

    Parametrised per field because these are independent constraints: typing
    one of them through the canonical alias and leaving the rest length-only
    would leave the boundary open, and a single-field test would not notice.
    """
    with pytest.raises(ValidationError):
        _raw_row(**{field: malformed})

    assert getattr(_raw_row(**{field: _VALID_DIGEST}), field) == _VALID_DIGEST
    assert getattr(_raw_row(), field) is None


@pytest.mark.parametrize("malformed", _MALFORMED)
def test_raw_row_ancestor_ids_are_element_wise_validated(malformed: str) -> None:
    """The lineage tuple validates each element, not merely its container.

    ``revision_ancestor_ids`` was a bare ``tuple[str, ...]`` with no per-element
    shape at all -- looser even than the length-only sibling columns.
    """
    with pytest.raises(ValidationError):
        _raw_row(revision_ancestor_ids=(_VALID_DIGEST, malformed))

    assert _raw_row(revision_ancestor_ids=(_VALID_DIGEST,)).revision_ancestor_ids == (_VALID_DIGEST,)


def test_valid_encrypted_round_trip_still_yields_a_canonical_revision_id(tmp_path: Path) -> None:
    """Real save/load produces a revision id the tightened record accepts.

    The refusals above are only meaningful if the production writer's own
    output still passes: this drives a genuine encrypted round-trip over SQLite
    with real AEAD and asserts the returned ``revision_id`` is the canonical
    shape, so the constraint cannot have been tightened past what the substrate
    actually writes.
    """
    db_path = tmp_path / "digest-identity.sqlite3"
    with EphemeralMasterKeyProvider():
        with _repo_at(db_path) as repo:
            repo.save(
                namespace=_NAMESPACE,
                object_key=_KEY,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=_PAYLOAD,
            )
        with _repo_at(db_path) as repo:
            loaded = repo.load(
                _NAMESPACE,
                _KEY,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            )

    assert loaded is not None
    assert loaded.payload == _PAYLOAD
    assert _accepts_digest(loaded.revision_id)
