"""Authenticated current-profile records in the capsule-local secure-object DB.

The profile record is one encrypted ``USER_PROFILE_VALUE_NAMESPACE`` row in
the capsule's normal SQLite substrate.  It is never a sidecar JSON document.
Every create or replacement co-writes the row and the canonical bucket-event
history through one ``SecureObjectRepository.apply_batch`` transaction.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import crypto
from ...core import ABSENT_SECURE_OBJECT_REVISION_ID, SecureObjectWrite
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.paths import effective_storage_root
from ...domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    build_bucket_event,
)
from ...domain.user_profile import UserProfileError, UserProfileRecord
from ._custody_ports import (
    ProfileCustodySecureObjectNamespace,
    ProfileCustodySecureObjectRawRowPort,
    ProfileCustodySecureObjectRecordPort,
    ProfileCustodySecureObjectRepositoryPort,
    default_profile_bucket_event_history_repository,
    profile_custody_secure_object_namespace,
    profile_custody_secure_object_repository,
)

if TYPE_CHECKING:
    from ._custody_ports import ProfileCustodyEnvelopePort


PROFILE_RECORD_SCHEMA_VERSION = 2
"""Current record binding grammar, independent of the profile fact schema."""

_RECORD_NAMESPACE = "cadrumo.application.user_profile.value"
_RECORD_OBJECT_KEY_PREFIX = "user-profile:"
_RECORD_WRITE_PROVENANCE_PREFIX = "cadrumo.profile-record.v2"
_RECORD_ACTOR = "profile-capsule-lifecycle"
_REQUIRED_EVENT_FIELDS = frozenset(
    {
        "content_digest",
        "dek_epoch",
        "envelope_digest",
        "password_generation",
        "previous_record_digest",
        "record_revision",
    }
)
_RECORD_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid")


class ProfileRecordConflictError(UserProfileError, ValueError):
    """The authenticated record changed before its CAS command committed.

    Joins the :class:`~domain.user_profile.UserProfileError` family so the
    refusal binds to the error registry and one clause still catches the whole
    user-profile surface. :exc:`ValueError` is retained deliberately: it is
    load-bearing ancestry here, not decoration -- see
    :class:`ProfileRecordIntegrityError`.
    """


class ProfileRecordIntegrityError(UserProfileError, ValueError):
    """A current-record row or its event witness is malformed or mis-bound.

    Joins the :class:`~domain.user_profile.UserProfileError` family so the
    refusal binds to the error registry. :exc:`ValueError` is retained
    because the lifecycle restore path converts a failed authenticated
    validation into its own refusal through a ``ValueError`` arm; dropping the
    builtin ancestry would let the inner refusal escape that conversion and
    reach the operator naming a stage it never reached.
    """


class ProfileRecordCommandEvent(BaseModel):
    """Non-secret command witness co-written into canonical bucket history."""

    model_config = _RECORD_CONFIG

    event_type: BucketEventType
    occurred_at: str = Field(min_length=20, max_length=64)
    payload: Mapping[str, str] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LoadedProfileRecord:
    """One verified current record together with its secure-object CAS token."""

    record: UserProfileRecord
    row_revision_id: str
    previous_row_revision_id: str | None
    event_id: str


@dataclass(slots=True)
class ProfileRecordSession:
    """Short-lived authority bound to one unlocked custody envelope and DEK."""

    profile_id: UUID
    envelope_digest: str
    password_generation: int
    dek_epoch: str
    _dek: bytearray

    @classmethod
    def from_envelope(
        cls,
        *,
        envelope: ProfileCustodyEnvelopePort,
        dek: bytes,
    ) -> ProfileRecordSession:
        if len(dek) != 32:
            raise ProfileRecordIntegrityError("profile record session requires a 32-byte DEK")
        return cls(
            profile_id=envelope.profile_id,
            envelope_digest=envelope.self_digest,
            password_generation=envelope.password_generation,
            dek_epoch=envelope.dek_epoch,
            _dek=bytearray(dek),
        )

    def close(self) -> None:
        """Zeroise the DEK in place, retiring this authority without discarding it."""
        self._dek[:] = b"\0" * len(self._dek)

    @property
    def closed(self) -> bool:
        """Whether the DEK has been zeroised, so this authority can no longer decrypt.

        Retirement is destructive but not observable from the outside: ``close``
        zeroises the key in place and leaves the object, its UUID and its
        envelope binding intact, so a holder cannot tell a retired authority
        from a live one by looking at it. Anything deciding whether to REUSE a
        session has to ask, and before this predicate existed the only way to
        find out was to ask for the key and catch the refusal -- an integrity
        error raised at the point of use, far from the reuse decision that
        caused it.

        Read as the absence of key material rather than as a separate flag, so
        there is one definition of retired rather than a boolean a future
        ``close`` variant could forget to set.
        """
        return not self._dek or not any(self._dek)

    def encryption_key(self) -> bytes:
        """Return the DEK only to the local secure-object session bridge."""
        if self.closed:
            raise ProfileRecordIntegrityError("profile record session is closed")
        return bytes(self._dek)

    def assert_initial_record(self, record: UserProfileRecord) -> None:
        if UUID(str(record.profile_id)) != self.profile_id:
            raise ProfileRecordIntegrityError("initial profile record UUID differs from its custody session")
        if record.record_revision != 1 or record.previous_record_digest is not None:
            raise ProfileRecordIntegrityError(
                "initial profile record must be exactly revision one without a predecessor"
            )

    def assert_replacement(self, current: UserProfileRecord, replacement: UserProfileRecord) -> None:
        if UUID(str(replacement.profile_id)) != self.profile_id:
            raise ProfileRecordIntegrityError("replacement profile record UUID differs from its custody session")
        if (
            replacement.record_revision != current.record_revision + 1
            or replacement.previous_record_digest != current.content_digest
        ):
            raise ProfileRecordIntegrityError("replacement record does not carry the authenticated predecessor")

    def write_provenance(self, record: UserProfileRecord) -> str:
        """Return the strict row header cross-bound to the encrypted payload."""
        binding = {
            "content_digest": record.content_digest,
            "dek_epoch": self.dek_epoch,
            "envelope_digest": self.envelope_digest,
            "password_generation": self.password_generation,
            "previous_record_digest": record.previous_record_digest,
            "profile_id": str(self.profile_id),
            "record_revision": record.record_revision,
        }
        canonical = canonical_json_bytes(binding)
        return f"{_RECORD_WRITE_PROVENANCE_PREFIX}:{sha256_hex(canonical)}"

    def assert_row_binding(self, raw: ProfileCustodySecureObjectRawRowPort, record: UserProfileRecord) -> None:
        """Authenticate the row header against the unlocked envelope and record."""
        _assert_record_profile_binding(self.profile_id, record)
        _assert_record_provenance(self, raw, record)
        if record.record_revision == 1:
            _assert_initial_row_lineage(raw, record)
        else:
            _assert_replacement_row_lineage(raw, record)
        _assert_row_revision_metadata(raw)


def _assert_record_profile_binding(
    profile_id: UUID,
    record: UserProfileRecord,
) -> None:
    """Require the decrypted record UUID to match its live session."""
    if UUID(str(record.profile_id)) != profile_id:
        raise ProfileRecordIntegrityError("profile record UUID differs from the unlocked custody session")


def _assert_record_provenance(
    session: ProfileRecordSession,
    raw: ProfileCustodySecureObjectRawRowPort,
    record: UserProfileRecord,
) -> None:
    """Require the row header to carry the session-bound lineage witness."""
    if raw.write_provenance != session.write_provenance(record):
        raise ProfileRecordIntegrityError("profile record row provenance differs from authenticated lineage")


def _assert_initial_row_lineage(
    raw: ProfileCustodySecureObjectRawRowPort,
    record: UserProfileRecord,
) -> None:
    """Refuse a revision-one row that names an earlier record."""
    if raw.previous_revision_id is not None or record.previous_record_digest is not None:
        raise ProfileRecordIntegrityError("initial profile record row carries a predecessor")


def _assert_replacement_row_lineage(
    raw: ProfileCustodySecureObjectRawRowPort,
    record: UserProfileRecord,
) -> None:
    """Require later rows to carry both predecessor witnesses."""
    if raw.previous_revision_id is None or record.previous_record_digest is None:
        raise ProfileRecordIntegrityError("later profile record row lacks its predecessor")


def _assert_row_revision_metadata(raw: ProfileCustodySecureObjectRawRowPort) -> None:
    """Require the secure-object repository's revision metadata to be present."""
    if raw.revision_id is None or raw.payload_hash is None or raw.ciphertext_hash is None:
        raise ProfileRecordIntegrityError("profile record row lacks secure-object lineage metadata")


def profile_record_object_key(profile_id: UUID) -> str:
    """Return the registered natural key for the one current profile record."""
    return f"{_RECORD_OBJECT_KEY_PREFIX}{profile_id}"


@contextmanager
def _secure_objects_for_record(
    session: ProfileRecordSession,
    *,
    root: Path,
    database_file: Path | None = None,
) -> Generator[ProfileCustodySecureObjectRepositoryPort]:
    """Open the canonical profile-local secure-object repository for this session."""
    with profile_custody_secure_object_repository(
        profile_id=session.profile_id,
        dek=session.encryption_key(),
        root=root,
        database_file=database_file,
    ) as objects:
        yield objects


class ProfileRecordStore:
    """Strict current-record storage over the capsule's canonical secure DB."""

    def __init__(self, *, session: ProfileRecordSession, root: Path | None = None) -> None:
        self._session = session
        self._root = effective_storage_root(root)

    def load(self) -> LoadedProfileRecord:
        """Return the one authenticated current row and its secure CAS lineage."""
        with _secure_objects_for_record(self._session, root=self._root) as objects:
            return self._load_from_objects(objects)

    def history(self) -> tuple[BucketEvent, ...]:
        """Return the append-only authenticated history for this profile record."""
        with _secure_objects_for_record(self._session, root=self._root) as objects:
            return (
                default_profile_bucket_event_history_repository(objects=objects)
                .load()
                .for_object(
                    object_type=BucketEventObjectType.PROFILE,
                    object_id=str(self._session.profile_id),
                )
            )

    def create_initial(self, record: UserProfileRecord, *, stage_path: Path) -> None:
        """Write revision one and its creation event before the stage commit marker."""
        self._session.assert_initial_record(record)
        database_file = stage_path / "db" / "cadrumo.db"
        (stage_path / "blobs").mkdir(mode=0o700, exist_ok=False)
        with _secure_objects_for_record(self._session, root=self._root, database_file=database_file) as objects:
            self._write_with_event(
                objects,
                record=record,
                expected_row_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
                expected_event_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
                event=ProfileRecordCommandEvent(
                    event_type=BucketEventType.PROFILE_BUCKET_CREATED,
                    occurred_at=record.updated_at.isoformat(),
                ),
            )
            self._load_from_objects(objects)

    def validate_staged_database(self, *, stage_path: Path) -> LoadedProfileRecord:
        """Refuse a restore stage unless its exact current record is authenticated."""
        database_file = stage_path / "db" / "cadrumo.db"
        if not database_file.is_file() or database_file.is_symlink():
            raise ProfileRecordIntegrityError("restore stage does not contain a regular profile database")
        with _secure_objects_for_record(self._session, root=self._root, database_file=database_file) as objects:
            return self._load_from_objects(objects)

    def replace(
        self,
        *,
        replacement: UserProfileRecord,
        event: ProfileRecordCommandEvent,
        expected_revision: int,
        expected_content_digest: str,
    ) -> UserProfileRecord:
        """CAS-replace the sole current row and append its event in one transaction."""
        with _secure_objects_for_record(self._session, root=self._root) as objects:
            current = self._load_from_objects(objects)
            if (
                current.record.record_revision != expected_revision
                or current.record.content_digest != expected_content_digest
            ):
                raise ProfileRecordConflictError("profile record revision compare-and-swap failed")
            self._session.assert_replacement(current.record, replacement)
            event_revision = _event_history_revision(objects)
            self._write_with_event(
                objects,
                record=replacement,
                expected_row_revision_id=current.row_revision_id,
                expected_event_revision_id=event_revision,
                event=event,
            )
            persisted = self._load_from_objects(objects)
            if persisted.record != replacement:
                raise ProfileRecordIntegrityError("profile record replacement did not persist its authenticated value")
            return persisted.record

    def rehead_under_rotated_envelope(
        self,
        *,
        rotated: ProfileRecordSession,
        event: ProfileRecordCommandEvent,
    ) -> UserProfileRecord:
        """Re-publish the current row's witness under a re-wrapped envelope.

        A passphrase rotation re-mints the password envelope over the SAME
        data key. The row's ``write_provenance`` folds the envelope digest and
        the password generation, so after the swap the stored witness names a
        wrapper that no longer exists and every read refuses. Nothing about
        the RECORD changed, but its custody witness must.

        Read and write use different sessions on purpose, and that asymmetry
        is the whole method: the stored row can only be authenticated by the
        session that wrote it, while the replacement can only be authenticated
        afterwards by the rotated one. Both address the same profile and hold
        the same key -- rotation does not re-key -- so the secure-object
        repository is indifferent to which one opens it.

        The revision advances rather than being rewritten in place. A row
        rewritten under its own revision would leave a revision-one record
        carrying a predecessor row, which the initial-lineage assertion
        refuses outright; and the rotation is a real lifecycle fact that ought
        to appear in the profile's history rather than mutate its past
        silently. Content is preserved exactly, so the advance records the
        custody change and nothing else.
        """
        if rotated.profile_id != self._session.profile_id:
            raise ProfileRecordIntegrityError("rotated record session does not serve this profile")
        if rotated.dek_epoch != self._session.dek_epoch:
            raise ProfileRecordIntegrityError("rotated record session names a different DEK epoch")
        if rotated.envelope_digest == self._session.envelope_digest:
            raise ProfileRecordIntegrityError("rotated record session carries the same envelope as the current one")
        with _secure_objects_for_record(self._session, root=self._root) as objects:
            current = self._load_from_objects(objects)
            replacement = UserProfileRecord(
                schema_id=current.record.schema_id,
                schema_version=current.record.schema_version,
                profile_id=current.record.profile_id,
                facts=current.record.facts,
                setup_state=current.record.setup_state,
                record_revision=current.record.record_revision + 1,
                previous_record_digest=current.record.content_digest,
                content_digest="",
                created_at=current.record.created_at,
                updated_at=datetime.fromisoformat(event.occurred_at).astimezone(UTC),
            )
            rotated.assert_replacement(current.record, replacement)
            self._write_with_event(
                objects,
                record=replacement,
                expected_row_revision_id=current.row_revision_id,
                expected_event_revision_id=_event_history_revision(objects),
                event=event,
                writing_session=rotated,
            )
            persisted = ProfileRecordStore(session=rotated, root=self._root)._load_from_objects(objects)
            if persisted.record != replacement:
                raise ProfileRecordIntegrityError("re-headed profile record did not persist its authenticated value")
            return persisted.record

    def _load_from_objects(self, objects: ProfileCustodySecureObjectRepositoryPort) -> LoadedProfileRecord:
        namespace = profile_custody_secure_object_namespace()
        raw, loaded = _load_profile_record_row(objects, self._session.profile_id, namespace)
        record = _decode_profile_record(loaded)
        self._session.assert_row_binding(raw, record)
        event_id, event = _load_profile_record_event(objects, raw)
        _assert_event_binding(self._session, record, event_id, event)
        assert raw.revision_id is not None
        return LoadedProfileRecord(
            record=record,
            row_revision_id=raw.revision_id,
            previous_row_revision_id=raw.previous_revision_id,
            event_id=event_id,
        )

    def _write_with_event(
        self,
        objects: ProfileCustodySecureObjectRepositoryPort,
        *,
        record: UserProfileRecord,
        expected_row_revision_id: str,
        expected_event_revision_id: str,
        event: ProfileRecordCommandEvent,
        writing_session: ProfileRecordSession | None = None,
    ) -> None:
        # Defaults to the store's own session; a rotation supplies the
        # re-wrapped one so the witness it stamps is the one every later read
        # will recompute. Keeping this the single writer is the point --
        # a rotation that assembled its own SecureObjectWrite would be a
        # second write path into the one row this class exists to own.
        writer = writing_session or self._session
        event_value = _build_record_event(writer, record, event)
        events = default_profile_bucket_event_history_repository(objects=objects)
        history, observed_event_revision = events.load_revisioned()
        if observed_event_revision != expected_event_revision_id:
            raise ProfileRecordConflictError("bucket event history changed before the profile record command committed")
        next_history = append_bucket_event(history, event_value)
        record_write = SecureObjectWrite(
            namespace=profile_custody_secure_object_namespace().namespace,
            object_key=profile_record_object_key(writer.profile_id),
            classification=profile_custody_secure_object_namespace().sensitivity,
            schema_version=profile_custody_secure_object_namespace().schema_version,
            written_at=record.updated_at,
            payload=record.model_dump_json().encode(UTF_8_ENCODING),
            write_provenance=writer.write_provenance(record),
            source_event_id=event_value.event_id,
            expected_revision_id=expected_row_revision_id,
        )
        event_write = events.to_secure_object_write(next_history, expected_revision_id=expected_event_revision_id)
        objects.apply_batch((record_write, event_write))


def _load_profile_record_row(
    objects: ProfileCustodySecureObjectRepositoryPort,
    profile_id: UUID,
    namespace: ProfileCustodySecureObjectNamespace,
) -> tuple[ProfileCustodySecureObjectRawRowPort, ProfileCustodySecureObjectRecordPort]:
    """Load the one exact current-record row and its decrypted payload.

    The admission test is two independent conditions -- how many rows the
    namespace holds, and whether the single row is addressed to this profile --
    and they are reported separately because they send a reader to different
    places. A row count of one with a divergent key is a row that is PRESENT,
    so a message naming the count sends whoever reads it looking for a missing
    or duplicated row that does not exist.
    """
    object_key = profile_record_object_key(profile_id)
    expected_key = crypto.secure_object_key_digest(object_key)
    rows = tuple(row for row in objects.iter_all_records_raw() if row.namespace == _RECORD_NAMESPACE)
    if len(rows) != 1:
        raise ProfileRecordIntegrityError(
            f"profile capsule must contain exactly one current record row; it holds {len(rows)}"
        )
    raw = rows[0]
    if raw.object_key != expected_key:
        # The stored key is HMAC(subkey(data key), "user-profile:<uuid>"), so a
        # divergence names one of exactly two causes and the refusal states both
        # rather than asserting whichever one the reader happens to expect.
        raise ProfileRecordIntegrityError(
            "profile capsule holds one current record row addressed to a different object key than "
            "this profile derives: the row was written for another profile UUID or under other key material"
        )
    loaded = objects.load(
        namespace.namespace,
        object_key,
        expected_class=namespace.sensitivity,
        max_supported_version=namespace.schema_version,
    )
    if loaded is None or loaded.revision_id != raw.revision_id:
        raise ProfileRecordIntegrityError("profile record row disappeared during authenticated read")
    return raw, loaded


def _decode_profile_record(loaded: ProfileCustodySecureObjectRecordPort) -> UserProfileRecord:
    """Decode the strict current profile record payload."""
    try:
        return UserProfileRecord.model_validate_json(loaded.payload)
    except ValueError as exc:
        raise ProfileRecordIntegrityError("profile record row is not the current strict record shape") from exc


def _load_profile_record_event(
    objects: ProfileCustodySecureObjectRepositoryPort,
    raw: ProfileCustodySecureObjectRawRowPort,
) -> tuple[str, BucketEvent]:
    """Load the durable event witness named by a current-record row."""
    event_id = raw.source_event_id
    if event_id is None:
        raise ProfileRecordIntegrityError("profile record row lacks its bucket event witness")
    history = default_profile_bucket_event_history_repository(objects=objects).load()
    event = history.get(event_id)
    if event is None:
        raise ProfileRecordIntegrityError("profile record row names no durable bucket event")
    return event_id, event


def stage_initial_profile_record_database(
    *,
    stage_path: Path,
    root: Path,
    session: ProfileRecordSession,
    record: UserProfileRecord,
) -> None:
    """Materialise the canonical encrypted DB before the custody commit marker exists."""
    ProfileRecordStore(session=session, root=root).create_initial(record, stage_path=stage_path)


def validate_staged_profile_record_database(
    *,
    stage_path: Path,
    root: Path,
    session: ProfileRecordSession,
) -> LoadedProfileRecord:
    """Authenticate the exact staged record before restore publication can continue."""
    return ProfileRecordStore(session=session, root=root).validate_staged_database(stage_path=stage_path)


def _event_history_revision(objects: ProfileCustodySecureObjectRepositoryPort) -> str:
    _history, revision = default_profile_bucket_event_history_repository(objects=objects).load_revisioned()
    return revision


def _build_record_event(
    session: ProfileRecordSession,
    record: UserProfileRecord,
    command: ProfileRecordCommandEvent,
):
    try:
        occurred_at = datetime.fromisoformat(command.occurred_at).astimezone(UTC)
    except ValueError as exc:
        raise ProfileRecordIntegrityError("profile record command event instant is not a parsable timestamp") from exc
    if occurred_at != record.updated_at:
        raise ProfileRecordIntegrityError("profile record event instant differs from its replacement record")
    if _REQUIRED_EVENT_FIELDS.intersection(command.payload):
        raise ProfileRecordIntegrityError("profile record event attempts to override its lineage witness")
    payload = {
        "content_digest": record.content_digest,
        "dek_epoch": session.dek_epoch,
        "envelope_digest": session.envelope_digest,
        "password_generation": str(session.password_generation),
        "previous_record_digest": record.previous_record_digest or "-",
        "record_revision": str(record.record_revision),
        **dict(command.payload),
    }
    return build_bucket_event(
        bucket_id=str(session.profile_id),
        event_type=command.event_type,
        occurred_at=occurred_at,
        actor=_RECORD_ACTOR,
        object_type=BucketEventObjectType.PROFILE,
        object_id=str(session.profile_id),
        payload=payload,
        payload_version=1,
    )


def _assert_event_binding(
    session: ProfileRecordSession,
    record: UserProfileRecord,
    event_id: str,
    event: object,
) -> None:
    from ...domain.buckets import BucketEvent

    if not isinstance(event, BucketEvent):
        raise ProfileRecordIntegrityError("profile record event history returned an invalid event")
    expected = {
        "content_digest": record.content_digest,
        "dek_epoch": session.dek_epoch,
        "envelope_digest": session.envelope_digest,
        "password_generation": str(session.password_generation),
        "previous_record_digest": record.previous_record_digest or "-",
        "record_revision": str(record.record_revision),
    }
    if (
        event.event_id != event_id
        or event.bucket_id != str(session.profile_id)
        or event.object_type is not BucketEventObjectType.PROFILE
        or event.object_id != str(session.profile_id)
        or any(event.payload.get(key) != value for key, value in expected.items())
    ):
        raise ProfileRecordIntegrityError("profile record event does not authenticate the current lineage")


__all__ = [
    "PROFILE_RECORD_SCHEMA_VERSION",
    "LoadedProfileRecord",
    "ProfileRecordCommandEvent",
    "ProfileRecordConflictError",
    "ProfileRecordIntegrityError",
    "ProfileRecordSession",
    "ProfileRecordStore",
    "profile_record_object_key",
    "stage_initial_profile_record_database",
    "validate_staged_profile_record_database",
]
