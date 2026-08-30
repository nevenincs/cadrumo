"""Secure-object lineage and restore contracts for the current profile record."""

from __future__ import annotations

import sqlite3
from base64 import b64encode
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody.records import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
)
from ....adapters.persistence.storage.custody.sentinel import create_profile_custody_sentinel
from ....adapters.persistence.storage.custody.sentinel_contract import ProfileCustodySentinelRecord
from ....domain.buckets.event import BucketEventType
from ....domain.user_profile.values import ProfileSetupState, UserProfileRecord
from ....tests.profile_capsule import mint_test_profile_recovery_envelope
from ..capsule_record import ProfileRecordIntegrityError, ProfileRecordSession, ProfileRecordStore
from ..lifecycle import ProfileCapsuleLifecycle

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("cc0aeac5-30af-460d-b2cc-dcbbf30c578a")
_DEK = bytes(range(32))
_RECORD_NAMESPACE = "cadrumo.application.user_profile.value"


def _envelope(
    *,
    profile_id: UUID = _PROFILE_ID,
    password_generation: int = 7,
    dek_epoch: bytes = b"e" * 16,
) -> ProfileCustodyEnvelope:
    return ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=password_generation,
        dek_epoch=b64encode(dek_epoch).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=b64encode(b"c" * 32).decode("ascii"),
            tag_b64=b64encode(b"t" * 16).decode("ascii"),
        ),
    )


def _create_capsule(
    root: Path,
) -> tuple[ProfileCapsuleLifecycle, ProfileCustodyEnvelope, ProfileCustodySentinelRecord, ProfileRecordSession]:
    envelope = _envelope()
    sentinel = create_profile_custody_sentinel(envelope=envelope, dek=_DEK)
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=_DEK)
    lifecycle = ProfileCapsuleLifecycle(root=root)
    lifecycle.create(
        label="Lineage operator",
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=sentinel,
        data_files={"state/payload.bin": b"x"},
        recovery_envelope=mint_test_profile_recovery_envelope(_PROFILE_ID, dek=_DEK, dek_epoch=envelope.dek_epoch),
        initial_record=UserProfileRecord(
            profile_id=str(_PROFILE_ID),
            setup_state=ProfileSetupState.INCOMPLETE,
        ),
        record_session=session,
    )
    return lifecycle, envelope, sentinel, session


def _database(root: Path) -> Path:
    return root / "buckets" / str(_PROFILE_ID) / "db" / "cadrumo.db"


def test_initial_record_is_one_encrypted_database_row_with_authenticated_creation_history(tmp_path: Path) -> None:
    _lifecycle, _envelope_value, _sentinel, session = _create_capsule(tmp_path)

    loaded = ProfileRecordStore(session=session, root=tmp_path).load()
    events = ProfileRecordStore(session=session, root=tmp_path).history()

    assert loaded.record.record_revision == 1
    assert loaded.record.previous_record_digest is None
    assert (tmp_path / "buckets" / str(_PROFILE_ID) / "data" / "profile-record.v1.json").exists() is False
    assert _database(tmp_path).is_file()
    assert [event.event_type for event in events] == [BucketEventType.PROFILE_BUCKET_CREATED]
    assert events[0].event_id == loaded.event_id


def test_record_refuses_a_row_whose_envelope_bound_provenance_was_tampered(tmp_path: Path) -> None:
    _lifecycle, _envelope_value, _sentinel, session = _create_capsule(tmp_path)
    with sqlite3.connect(_database(tmp_path)) as connection:
        connection.execute(
            "UPDATE secure_objects SET write_provenance = ? WHERE namespace = ?",
            ("cadrumo.profile-record.v2:forged", _RECORD_NAMESPACE),
        )

    with pytest.raises(ProfileRecordIntegrityError, match="provenance"):
        ProfileRecordStore(session=session, root=tmp_path).load()


def test_record_refuses_a_different_current_custody_envelope(tmp_path: Path) -> None:
    _lifecycle, _envelope_value, _sentinel, _session = _create_capsule(tmp_path)
    changed_session = ProfileRecordSession.from_envelope(envelope=_envelope(password_generation=8), dek=_DEK)

    with pytest.raises(ProfileRecordIntegrityError, match="provenance"):
        ProfileRecordStore(session=changed_session, root=tmp_path).load()


def test_record_refuses_a_changed_custody_dek_epoch(tmp_path: Path) -> None:
    _lifecycle, _envelope_value, _sentinel, _session = _create_capsule(tmp_path)
    changed_session = ProfileRecordSession.from_envelope(envelope=_envelope(dek_epoch=b"z" * 16), dek=_DEK)

    with pytest.raises(ProfileRecordIntegrityError, match="provenance"):
        ProfileRecordStore(session=changed_session, root=tmp_path).load()


def test_restore_refuses_missing_arbitrary_and_malformed_current_database(tmp_path: Path) -> None:
    _lifecycle, envelope, sentinel, session = _create_capsule(tmp_path / "source")
    database_bytes = _database(tmp_path / "source").read_bytes()

    with pytest.raises(ValueError, match="requires its canonical profile database"):
        ProfileCapsuleLifecycle(root=tmp_path / "missing").restore(
            label="Restore target",
            password_envelope=envelope,
            sentinel=sentinel,
            data_files={},
            record_session=session,
            database_bytes=b"",
            authority="password",
        )
    with pytest.raises(ValueError, match="refuses arbitrary capsule data files"):
        ProfileCapsuleLifecycle(root=tmp_path / "arbitrary").restore(
            label="Restore target",
            password_envelope=envelope,
            sentinel=sentinel,
            data_files={"untrusted.bin": b"arbitrary"},
            record_session=session,
            database_bytes=database_bytes,
            authority="password",
        )
    with pytest.raises(ProfileRecordIntegrityError, match="authenticated current-record validation"):
        ProfileCapsuleLifecycle(root=tmp_path / "malformed").restore(
            label="Restore target",
            password_envelope=envelope,
            sentinel=sentinel,
            data_files={},
            record_session=session,
            database_bytes=b"not a sqlite database",
            authority="password",
        )


def test_restore_refuses_duplicate_or_mismatched_current_record_lineage(tmp_path: Path) -> None:
    _lifecycle, envelope, sentinel, session = _create_capsule(tmp_path / "source")
    duplicate_database = tmp_path / "duplicate.db"
    duplicate_database.write_bytes(_database(tmp_path / "source").read_bytes())
    with sqlite3.connect(duplicate_database) as connection:
        connection.execute(
            """
            INSERT INTO secure_objects (
                namespace, object_key, classification, schema_version, written_at,
                revision_id, previous_revision_id, revision_ancestor_ids,
                previous_payload_hash, payload_hash, ciphertext_hash,
                revision_written_at, write_provenance, source_event_id,
                conflict_policy, payload
            )
            SELECT
                namespace, randomblob(32), classification, schema_version, written_at,
                revision_id, previous_revision_id, revision_ancestor_ids,
                previous_payload_hash, payload_hash, ciphertext_hash,
                revision_written_at, write_provenance, source_event_id,
                conflict_policy, payload
            FROM secure_objects
            WHERE namespace = ?
            """,
            (_RECORD_NAMESPACE,),
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM secure_objects WHERE namespace = ?",
            (_RECORD_NAMESPACE,),
        ).fetchone() == (2,)
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    with pytest.raises(
        ProfileRecordIntegrityError, match="authenticated current-record validation"
    ) as duplicate_refusal:
        ProfileCapsuleLifecycle(root=tmp_path / "duplicate").restore(
            label="Restore target",
            password_envelope=envelope,
            sentinel=sentinel,
            data_files={},
            record_session=session,
            database_bytes=duplicate_database.read_bytes(),
            authority="password",
        )
    assert isinstance(duplicate_refusal.value.__cause__, ProfileRecordIntegrityError)
    # Two rows: the count really is what failed, so the count is what is named.
    assert "exactly one current record row; it holds 2" in str(duplicate_refusal.value.__cause__)

    # A session minted from a different envelope is now refused BEFORE the
    # capsule is staged, on the envelope digest the session copied at mint.
    # The record store still refuses the same shape on its row provenance --
    # proved directly against the store in this module -- but the earlier
    # refusal is the better one: nothing is written and the message names the
    # material that disagreed rather than the symptom two layers down.
    mismatched_session = ProfileRecordSession.from_envelope(envelope=_envelope(password_generation=8), dek=_DEK)
    with pytest.raises(ValueError, match="was not minted from this password envelope"):
        ProfileCapsuleLifecycle(root=tmp_path / "mismatch").restore(
            label="Restore target",
            password_envelope=envelope,
            sentinel=sentinel,
            data_files={},
            record_session=mismatched_session,
            database_bytes=_database(tmp_path / "source").read_bytes(),
            authority="password",
        )


def test_restore_refuses_a_database_bound_to_a_different_profile_uuid(tmp_path: Path) -> None:
    _lifecycle, _envelope_value, _sentinel, _session = _create_capsule(tmp_path / "source")
    other_profile_id = UUID("d9173bfc-8420-4715-a570-29c8f2b59a4e")
    other_envelope = _envelope(profile_id=other_profile_id)
    other_session = ProfileRecordSession.from_envelope(envelope=other_envelope, dek=_DEK)

    with pytest.raises(ProfileRecordIntegrityError, match="authenticated current-record validation") as refusal:
        ProfileCapsuleLifecycle(root=tmp_path / "uuid-mismatch").restore(
            label="Restore target",
            password_envelope=other_envelope,
            sentinel=create_profile_custody_sentinel(envelope=other_envelope, dek=_DEK),
            data_files={},
            record_session=other_session,
            database_bytes=_database(tmp_path / "source").read_bytes(),
            authority="password",
        )

    assert isinstance(refusal.value.__cause__, ProfileRecordIntegrityError)
    # One row, wrong key. The count clause passes here, so a message naming the
    # count would describe the half that did not fail and send a reader looking
    # for a missing or duplicated row that is not what went wrong.
    cause = str(refusal.value.__cause__)
    assert "addressed to a different object key" in cause
    assert "exactly one current record row" not in cause
